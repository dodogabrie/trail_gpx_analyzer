"""Main prediction pipeline for physics-based trail running model.

This module implements the full route prediction algorithm including:
- Route preprocessing (distance calculation, grade smoothing)
- Segment-by-segment velocity prediction using regime-specific models
- Fatigue accumulation and application to subsequent segments
- Comprehensive diagnostics for model introspection

The pipeline is the primary entry point for running predictions.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from .core import predict_uphill_velocity, predict_downhill_velocity, calculate_fatigue_contribution

# Default fatigue sensitivity (0 = no fatigue effect, 2 = high sensitivity)
DEFAULT_FATIGUE_ALPHA = 0.3

def run_physics_prediction(
    route_df: pd.DataFrame,
    user_params: Dict[str, float],
    fatigue_alpha: float = DEFAULT_FATIGUE_ALPHA
) -> Dict:
    """
    Run the full physics-based prediction loop over a route profile.
    
    Args:
        route_df: DataFrame with columns ['distance', 'elevation'].
                  Should be pre-resampled (e.g. 10m or 50m steps).
        user_params: Dict from calibration (v_flat, k_up, etc.)
        fatigue_alpha: Parameter controlling how much eccentric load slows you down.
    
    Returns:
        Dict with total_time_seconds, segments (list of dicts).
    """
    # Unpack params
    v_flat = user_params.get('v_flat', 3.33)
    k_up = user_params.get('k_up', 1.0)
    k_tech = user_params.get('k_tech', 1.0)
    a_param = user_params.get('a_param', 3.0)
    
    k_terrain_up = user_params.get('k_terrain_up', 1.08)
    k_terrain_down = user_params.get('k_terrain_down', 1.12)
    k_terrain_flat = user_params.get('k_terrain_flat', 1.05)
    
    # Pre-calc arrays
    distances = route_df['distance'].values
    elevations = route_df['elevation'].values
    
    # Calculate derived gradients (Central Difference or Forward)
    # Using simple forward difference for segments
    diff_dist = np.diff(distances)
    diff_elev = np.diff(elevations)
    
    # Avoid div/0
    diff_dist = np.maximum(diff_dist, 0.1) 
    
    grades = diff_elev / diff_dist
    
    # State tracking
    accumulated_load = 0.0
    total_distance = distances[-1]
    
    segments_output = []
    total_time = 0.0
    
    for i in range(len(grades)):
        segment_len = diff_dist[i]
        grade = grades[i]
        
        # 1. Update Fatigue State (Eccentric Load)
        # Load accumulates based on PREVIOUS descent, affects CURRENT segment

        # Normalize load by min of actual distance and 42km baseline
        # This ensures fatigue scales appropriately for both short and ultra-long routes
        # For routes < 42km: higher relative impact (more aggressive)
        # For routes > 42km: use actual distance (prevents over-penalization)
        normalization_distance = min(total_distance, 42000.0) if total_distance > 0 else 42000.0
        norm_load = accumulated_load / normalization_distance
        fatigue_factor = 1.0 + (fatigue_alpha * norm_load)
        
        # 2. Select Regime and Predict Velocity
        if grade >= 0:
            # Uphill / Flat
            # Select terrain factor
            k_terr = k_terrain_flat if grade < 0.02 else k_terrain_up
            
            v = predict_uphill_velocity(
                grade, 
                v_flat, 
                k_up, 
                k_terrain=k_terr, 
                fatigue_factor=fatigue_factor
            )
        else:
            # Downhill
            v = predict_downhill_velocity(
                grade, 
                v_flat, 
                k_tech, 
                a_param, 
                k_terrain_down=k_terrain_down,
                k_terrain_up=k_terrain_up,
                fatigue_factor=fatigue_factor,
                k_up=k_up
            )
            
            # Accumulate eccentric load (only on descents)
            load_gain = calculate_fatigue_contribution(grade, segment_len)
            accumulated_load += load_gain

        # 3. Calculate Time
        dt = segment_len / v
        total_time += dt
        
        segments_output.append({
            'distance_m': float(distances[i]),
            'length_m': float(segment_len),
            'grade': float(grade),
            'velocity': float(v),
            'pace_min_km': 16.666 / v, # 1000/60/v
            'time_s': float(dt),
            'fatigue_factor': float(fatigue_factor)
        })
        
    # Calculate fatigue diagnostics
    normalization_distance = min(total_distance, 42000.0) if total_distance > 0 else 42000.0
    final_fatigue_factor = 1.0 + (fatigue_alpha * accumulated_load / normalization_distance)

    # Find segments with highest fatigue
    segments_with_fatigue = sorted(segments_output, key=lambda s: s['fatigue_factor'], reverse=True)[:5]

    # Calculate average slowdown due to fatigue
    avg_fatigue_slowdown = sum(s['fatigue_factor'] - 1.0 for s in segments_output) / len(segments_output) if segments_output else 0

    return {
        'total_time_seconds': total_time,
        'segments': segments_output,
        'diagnostics': {
            'fatigue_alpha': fatigue_alpha,
            'total_distance_km': total_distance / 1000.0,
            'final_eccentric_load': accumulated_load,
            'final_fatigue_factor': final_fatigue_factor,
            'avg_fatigue_slowdown_pct': avg_fatigue_slowdown * 100,
            'max_fatigue_factor': max(s['fatigue_factor'] for s in segments_output) if segments_output else 1.0,
            'segments_with_max_fatigue': [
                {
                    'distance_km': s['distance_m'] / 1000,
                    'grade_pct': s['grade'] * 100,
                    'fatigue_factor': s['fatigue_factor'],
                    'pace_min_km': s['pace_min_km']
                }
                for s in segments_with_fatigue
            ]
        }
    }
