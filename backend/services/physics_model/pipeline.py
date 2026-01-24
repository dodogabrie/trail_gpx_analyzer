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

# Ultra-distance fatigue parameters
MARATHON_DISTANCE_M = 42000.0  # Marathon distance threshold in meters
DEFAULT_ULTRA_BETA = 0.4       # Ultra fatigue intensity coefficient
DEFAULT_ULTRA_GAMMA = 1.5      # Non-linearity exponent for ultra fatigue

def run_physics_prediction(
    route_df: pd.DataFrame,
    user_params: Dict[str, float],
    fatigue_alpha: float = DEFAULT_FATIGUE_ALPHA,
    ultra_beta: float = DEFAULT_ULTRA_BETA,
    ultra_gamma: float = DEFAULT_ULTRA_GAMMA
) -> Dict:
    """
    Run the full physics-based prediction loop over a route profile.

    Uses a two-phase fatigue model:
    - Phase 1: Base eccentric fatigue (linear, unchanged for <42km)
    - Phase 2: Ultra-distance multiplier (exponential, activates >42km)

    Args:
        route_df: DataFrame with columns ['distance', 'elevation'].
                  Should be pre-resampled (e.g. 10m or 50m steps).
        user_params: Dict from calibration (v_flat, k_up, etc.)
        fatigue_alpha: Parameter controlling how much eccentric load slows you down.
        ultra_beta: Ultra fatigue intensity coefficient (default 0.4).
        ultra_gamma: Non-linearity exponent for ultra fatigue (default 1.5).

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
        
        # 1. Update Fatigue State (Two-Phase Model)
        # Load accumulates based on PREVIOUS descent, affects CURRENT segment
        #
        # Phase 1: Base eccentric fatigue (unchanged for <42km)
        # Phase 2: Ultra-distance multiplier (activates >42km)

        # Normalize load by min of actual distance and marathon baseline
        normalization_distance = min(total_distance, MARATHON_DISTANCE_M) if total_distance > 0 else MARATHON_DISTANCE_M
        norm_load = accumulated_load / normalization_distance
        base_fatigue = 1.0 + (fatigue_alpha * norm_load)

        # Ultra-distance multiplier: exponential growth beyond marathon
        current_distance = distances[i]
        ultra_ratio = max(0.0, (current_distance - MARATHON_DISTANCE_M) / MARATHON_DISTANCE_M)
        ultra_multiplier = 1.0 + (ultra_beta * (ultra_ratio ** ultra_gamma))

        # Combined fatigue factor
        fatigue_factor = base_fatigue * ultra_multiplier
        
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
            'pace_min_km': 16.666 / v,  # 1000/60/v
            'time_s': float(dt),
            'fatigue_factor': float(fatigue_factor),
            'base_fatigue': float(base_fatigue),
            'ultra_multiplier': float(ultra_multiplier)
        })
        
    # Calculate fatigue diagnostics
    normalization_distance = min(total_distance, MARATHON_DISTANCE_M) if total_distance > 0 else MARATHON_DISTANCE_M
    final_base_fatigue = 1.0 + (fatigue_alpha * accumulated_load / normalization_distance)

    # Calculate final ultra multiplier at end of route
    final_ultra_ratio = max(0.0, (total_distance - MARATHON_DISTANCE_M) / MARATHON_DISTANCE_M)
    final_ultra_multiplier = 1.0 + (ultra_beta * (final_ultra_ratio ** ultra_gamma))
    final_fatigue_factor = final_base_fatigue * final_ultra_multiplier

    # Find segments with highest fatigue
    segments_with_fatigue = sorted(segments_output, key=lambda s: s['fatigue_factor'], reverse=True)[:5]

    # Calculate average slowdown due to fatigue
    avg_fatigue_slowdown = sum(s['fatigue_factor'] - 1.0 for s in segments_output) / len(segments_output) if segments_output else 0

    # Calculate ultra-specific diagnostics
    max_ultra_multiplier = max(s['ultra_multiplier'] for s in segments_output) if segments_output else 1.0
    avg_ultra_multiplier = sum(s['ultra_multiplier'] for s in segments_output) / len(segments_output) if segments_output else 1.0

    return {
        'total_time_seconds': total_time,
        'segments': segments_output,
        'diagnostics': {
            'fatigue_alpha': fatigue_alpha,
            'ultra_beta': ultra_beta,
            'ultra_gamma': ultra_gamma,
            'total_distance_km': total_distance / 1000.0,
            'final_eccentric_load': accumulated_load,
            'final_base_fatigue': final_base_fatigue,
            'final_ultra_multiplier': final_ultra_multiplier,
            'final_fatigue_factor': final_fatigue_factor,
            'avg_fatigue_slowdown_pct': avg_fatigue_slowdown * 100,
            'max_fatigue_factor': max(s['fatigue_factor'] for s in segments_output) if segments_output else 1.0,
            'max_ultra_multiplier': max_ultra_multiplier,
            'avg_ultra_multiplier': avg_ultra_multiplier,
            'segments_with_max_fatigue': [
                {
                    'distance_km': s['distance_m'] / 1000,
                    'grade_pct': s['grade'] * 100,
                    'fatigue_factor': s['fatigue_factor'],
                    'base_fatigue': s['base_fatigue'],
                    'ultra_multiplier': s['ultra_multiplier'],
                    'pace_min_km': s['pace_min_km']
                }
                for s in segments_with_fatigue
            ]
        }
    }
