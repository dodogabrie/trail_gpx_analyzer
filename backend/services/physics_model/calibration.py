import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from .core import normalized_cost_ratio

# Constants for calibration ranges
FLAT_GRADE_MIN, FLAT_GRADE_MAX = -0.02, 0.02
UPHILL_GRADE_MIN, UPHILL_GRADE_MAX = 0.03, 0.20
DOWNHILL_GRADE_MIN, DOWNHILL_GRADE_MAX = -0.20, -0.03

# Default parameters if calibration fails
DEFAULT_PARAMS = {
    'v_flat': 3.33,  # ~5:00 min/km
    'k_up': 1.0,
    'k_tech': 1.0,
    'a_param': 3.0,
    'k_terrain_up': 1.08,
    'k_terrain_down': 1.12,
    'k_terrain_flat': 1.05
}

def calibrate_user_params(activity_streams: List[pd.DataFrame]) -> Dict[str, float]:
    """
    Derive user-specific physics parameters from historical activity streams.
    
    Args:
        activity_streams: List of DataFrames containing 'grade_smooth', 'velocity_smooth', 'distance'
                          (and optionally 'moving' mask).
    
    Returns:
        Dict of parameters: v_flat, k_up, k_tech, a_param
    """
    # 1. Aggregate all valid segments from all activities
    # We treat every point (or small segment) as a data point. 
    # For robustness, we might want to group by 50m segments, but point-cloud with median is fine if smoothed.
    
    flat_data = []
    uphill_data = []
    downhill_data = []
    
    for df in activity_streams:
        # Basic cleaning
        if 'velocity_smooth' not in df.columns or 'grade_smooth' not in df.columns:
            continue
            
        # Use moving points only
        mask = df['moving'] if 'moving' in df.columns else pd.Series([True] * len(df))
        valid = mask & (df['velocity_smooth'] > 0.5) & (df['velocity_smooth'] < 10.0) # 0.5m/s to 10m/s limits
        
        df_valid = df[valid].copy()
        
        # Convert grade percent to fraction if needed (assuming input is percent like Strava)
        # Strava 'grade_smooth' is usually percentage (e.g. 5.4).
        # Our core physics expects fraction (e.g. 0.054).
        # We need to detect or assume. Standard Strava is %.
        grades = df_valid['grade_smooth'] / 100.0
        velocities = df_valid['velocity_smooth']
        
        # Flat segments
        mask_flat = (grades >= FLAT_GRADE_MIN) & (grades <= FLAT_GRADE_MAX)
        flat_data.extend(velocities[mask_flat].tolist())
        
        # Uphill segments
        mask_up = (grades >= UPHILL_GRADE_MIN) & (grades <= UPHILL_GRADE_MAX)
        # Store pairs of (grade, velocity)
        if mask_up.any():
            uphill_data.append(np.column_stack((grades[mask_up], velocities[mask_up])))
            
        # Downhill segments
        mask_down = (grades >= DOWNHILL_GRADE_MIN) & (grades <= DOWNHILL_GRADE_MAX)
        if mask_down.any():
            downhill_data.append(np.column_stack((grades[mask_down], velocities[mask_down])))

    # === STEP 1: Fit v_flat ===
    if not flat_data:
        v_flat = DEFAULT_PARAMS['v_flat']
    else:
        v_flat = float(np.median(flat_data))
    
    # === STEP 2: Fit k_up ===
    # v_obs = v_flat / (R_C(g) * k_terrain_up * k_up)
    # => k_up = v_flat / (R_C(g) * k_terrain_up * v_obs)
    k_up_samples = []
    k_terrain_up = DEFAULT_PARAMS['k_terrain_up']
    
    if uphill_data:
        uphill_points = np.vstack(uphill_data)
        g_vals = uphill_points[:, 0]
        v_vals = uphill_points[:, 1]
        
        # Calculate Cost Ratios for all points
        # (Vectorize normalized_cost_ratio logic simply for performance)
        # C0 = 3.6. C(g) formula...
        # Doing loop for safety as minetti is complex polynomial
        rc_vals = np.array([normalized_cost_ratio(g) for g in g_vals])
        
        # k_up estimates
        k_ups = v_flat / (rc_vals * k_terrain_up * v_vals)
        k_up_est = float(np.median(k_ups))
        
        # Clamp to reasonable range [0.5, 2.0]
        k_up = max(0.5, min(2.0, k_up_est))
    else:
        k_up = DEFAULT_PARAMS['k_up']

    # === STEP 3: Fit Downhill (k_tech, a) ===
    # Model: v_obs = v_flat * (1 + a * |g|) * k_tech / k_terrain_down
    # Let y = v_obs * k_terrain_down / v_flat
    # Let x = |g|
    # y = k_tech + (k_tech * a) * x
    # Linear regression: Y = Intercept + Slope * X
    # Intercept = k_tech
    # Slope = k_tech * a  =>  a = Slope / Intercept
    
    k_tech = DEFAULT_PARAMS['k_tech']
    a_param = DEFAULT_PARAMS['a_param']
    k_terrain_down = DEFAULT_PARAMS['k_terrain_down']
    
    if downhill_data:
        downhill_points = np.vstack(downhill_data)
        g_vals = downhill_points[:, 0] # These are negative
        v_vals = downhill_points[:, 1]
        
        x_vals = np.abs(g_vals)
        y_vals = v_vals * k_terrain_down / v_flat
        
        # Use robust fit (Median of slopes or simple binning)
        # Here we'll use simple binning to handle noise
        
        bins = np.linspace(abs(DOWNHILL_GRADE_MAX), abs(DOWNHILL_GRADE_MIN), 5)
        bin_x = []
        bin_y = []
        
        for i in range(len(bins)-1):
            mask = (x_vals >= bins[i]) & (x_vals < bins[i+1])
            if mask.sum() > 10:
                bin_x.append(np.median(x_vals[mask]))
                bin_y.append(np.median(y_vals[mask]))
        
        if len(bin_x) >= 2:
            # Linear Fit on bins
            coeffs = np.polyfit(bin_x, bin_y, 1)
            slope = coeffs[0]
            intercept = coeffs[1]
            
            # Extract physics params
            k_tech_est = intercept
            if k_tech_est > 0.1: # Protect against div/0 or bad fit
                a_est = slope / k_tech_est
                
                k_tech = max(0.5, min(1.5, k_tech_est))
                a_param = max(1.0, min(6.0, a_est))
                
    return {
        'v_flat': v_flat,
        'k_up': k_up,
        'k_tech': k_tech,
        'a_param': a_param,
        'k_terrain_up': k_terrain_up,
        'k_terrain_down': k_terrain_down,
        'k_terrain_flat': DEFAULT_PARAMS['k_terrain_flat']
    }
