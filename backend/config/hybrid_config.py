"""Configuration for hybrid prediction system.

Centralizes all constants and hyperparameters for easy tuning.
"""

import logging
from typing import Dict


# ============================================================================
# TIER THRESHOLDS
# ============================================================================

TIER_2_MIN_ACTIVITIES = 5
"""Minimum activities required for Tier 2 (parameter learning)"""

TIER_3_MIN_ACTIVITIES = 15
"""Minimum activities required for Tier 3 (ML residual corrections)"""

MIN_SEGMENTS_FOR_TIER3 = 50
"""Minimum segments required to train GBM model"""


# ============================================================================
# SEGMENTATION
# ============================================================================

SEGMENT_LENGTH_M = 200
"""Length of segments in meters for residual collection"""


# ============================================================================
# RECENCY WEIGHTING
# ============================================================================

RECENCY_HALF_LIFE_DAYS = 365
"""Half-life for exponential decay of activity recency weights (days)"""

MIN_RECENCY_WEIGHT = 0.1
"""Minimum recency weight (floor to not completely discard old data)"""


# ============================================================================
# PARAMETER LEARNING (TIER 2)
# ============================================================================

REGULARIZATION_STRENGTH = 0.1
"""L2 regularization strength for parameter learning"""

OPTIMIZATION_MAX_ITER = 200
"""Maximum iterations for scipy optimization"""

OPTIMIZATION_TOLERANCE = 1e-6
"""Convergence tolerance for optimization"""

PARAM_BOUNDS = {
    'v_flat': (2.0, 5.0),       # m/s - flat terrain velocity
    'k_up': (0.8, 1.5),          # uphill coefficient
    'k_tech': (0.8, 1.2),        # technical terrain coefficient
    'fatigue_alpha': (0.1, 0.6)  # fatigue accumulation rate
}
"""Parameter bounds for optimization"""

DEFAULT_PARAMS = {
    'v_flat': 3.0,
    'k_up': 1.0,
    'k_tech': 1.0,
    'fatigue_alpha': 0.3,
    'a_param': 3.0,
    'k_terrain_up': 1.08,
    'k_terrain_down': 1.12,
    'k_terrain_flat': 1.05
}
"""Default physics parameters"""


# ============================================================================
# GBM CONFIGURATION (TIER 3)
# ============================================================================

GBM_CONFIG = {
    'n_estimators': 100,       # Moderate ensemble size
    'max_depth': 3,            # Shallow trees (prevent overfitting)
    'learning_rate': 0.05,     # Conservative learning rate
    'subsample': 0.8,          # Bag 80% of data
    'min_samples_split': 10,   # Require 10+ samples to split
    'min_samples_leaf': 5,     # Require 5+ samples per leaf
    'random_state': 42
}
"""GBM hyperparameters for residual model"""

GBM_VALIDATION_SPLIT = 0.2
"""Fraction of data to hold out for validation (temporal split)"""

RESIDUAL_CLIP_MIN = 0.5
"""Minimum residual multiplier (max 2x speedup)"""

RESIDUAL_CLIP_MAX = 2.0
"""Maximum residual multiplier (max 2x slowdown)"""

ML_RESIDUAL_CLIP_MIN = 0.7
"""Minimum ML-predicted residual multiplier (more conservative)"""

ML_RESIDUAL_CLIP_MAX = 1.5
"""Maximum ML-predicted residual multiplier (more conservative)"""


# ============================================================================
# FEATURE NAMES (TIER 3)
# ============================================================================

ML_FEATURE_NAMES = [
    'grade_mean',               # Average grade over segment
    'grade_std',                # Grade variability (roughness)
    'abs_grade',                # Absolute grade magnitude
    'cum_distance_km',          # Distance covered so far
    'distance_remaining_km',    # Distance left in route
    'prev_pace_ratio',          # Pace ratio from previous segment
    'grade_change',             # Change in grade from prev segment
    'cum_elevation_gain_m',     # Total climbing so far
    'elevation_gain_rate',      # Climbing rate this segment (m/km)
    'rolling_avg_grade_500m'    # Avg grade over last 500m
]
"""Feature list for ML model (10 features, no cross-user fingerprint)"""


# ============================================================================
# EFFORT ADJUSTMENTS & CONFIDENCE INTERVALS
# ============================================================================

EFFORT_SIGMA_MULTIPLIER = 1.0
"""Sigma multiplier for race/recovery effort adjustments"""

EFFORT_VARIANCE_CAP = 0.05
"""Maximum variance (σ) applied for effort presets (5% cap)"""

CI_SIGMA_MULTIPLIER = 1.0
"""Sigma multiplier for confidence interval width"""

CI_VARIANCE_CAP = 0.06
"""Maximum variance (σ) used for confidence intervals (6% cap)"""


# ============================================================================
# PHYSICS MODEL VERSIONING
# ============================================================================

CURRENT_PHYSICS_MODEL_VERSION = "1.0"
"""Current physics model version for invalidation tracking"""


# ============================================================================
# CONFIDENCE LEVELS
# ============================================================================

CONFIDENCE_THRESHOLDS = {
    'TIER_1': {
        'default': 'MEDIUM'
    },
    'TIER_2': {
        'high_threshold': 10,  # activities
        'medium_high': 'MEDIUM_HIGH',
        'high': 'HIGH'
    },
    'TIER_3': {
        'very_high_threshold': 25,  # activities
        'high': 'HIGH',
        'very_high': 'VERY_HIGH'
    }
}
"""Confidence level thresholds by tier"""


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = logging.INFO
"""Default log level for hybrid prediction services"""

LOG_FORMAT = '[%(levelname)s] %(name)s: %(message)s'
"""Log format string"""


def get_logger(name: str) -> logging.Logger:
    """Get configured logger for a module.

    Args:
        name: Module name (use __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # Only add handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(LOG_LEVEL)
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
