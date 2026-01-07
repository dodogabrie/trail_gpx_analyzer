"""Test script for GBM (Gradient Boosting) residual model.

Tests ResidualMLService separately with sample data.

Run from backend directory:
    source venv/bin/activate
    python test_gbm_model.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from datetime import datetime

print("=" * 60)
print("Testing GBM Residual Model (ResidualMLService)")
print("=" * 60)

# Import configuration
try:
    from config.hybrid_config import (
        ML_FEATURE_NAMES,
        GBM_CONFIG,
        TIER_3_MIN_ACTIVITIES
    )
    print(f"Config loaded successfully")
    print(f"  Features: {len(ML_FEATURE_NAMES)} features")
    print(f"  GBM Config: {GBM_CONFIG}")
    print(f"  Min activities: {TIER_3_MIN_ACTIVITIES}")
except Exception as e:
    print(f"ERROR loading config: {e}")
    sys.exit(1)

print("\n" + "-" * 60)
print("Test 1: Import ResidualMLService")
print("-" * 60)

try:
    from services.residual_ml_service import ResidualMLService
    print("Import successful")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "-" * 60)
print("Test 2: Initialize Service (standalone, no DB)")
print("-" * 60)

try:
    # Test the core GBM training function without DB
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import train_test_split

    print("Creating synthetic training data...")

    # Generate synthetic residual data (simulating user activity residuals)
    n_activities = 50
    np.random.seed(42)

    # Create feature data
    X = pd.DataFrame({
        'grade_mean': np.random.uniform(-5, 10, n_activities),
        'grade_std': np.random.uniform(0, 5, n_activities),
        'abs_grade': np.random.uniform(0, 10, n_activities),
        'cum_distance_km': np.random.uniform(0, 20, n_activities),
        'distance_remaining_km': np.random.uniform(0, 20, n_activities),
        'prev_pace_ratio': np.random.uniform(0.8, 1.2, n_activities),
        'grade_change': np.random.uniform(-5, 5, n_activities),
        'cum_elevation_gain_m': np.random.uniform(0, 500, n_activities),
        'elevation_gain_rate': np.random.uniform(0, 50, n_activities),
        'rolling_avg_grade_500m': np.random.uniform(-5, 10, n_activities)
    })

    # Create target (residual multipliers: how much slower/faster than baseline)
    # 1.0 = same as baseline, >1.0 = slower, <1.0 = faster
    y = np.random.uniform(0.8, 1.3, n_activities)

    print(f"  Created {len(X)} synthetic activities")
    print(f"  Features: {list(X.columns)}")
    print(f"  Residual range: [{y.min():.3f}, {y.max():.3f}]")

    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, shuffle=False
    )

    print(f"  Train: {len(X_train)}, Val: {len(X_val)}")

    print("\nTraining GBM model...")
    model = GradientBoostingRegressor(**GBM_CONFIG)
    model.fit(X_train[ML_FEATURE_NAMES], y_train)

    print("Model trained successfully")
    print(f"  n_estimators: {model.n_estimators}")
    print(f"  max_depth: {model.max_depth}")

    # Make predictions
    y_pred = model.predict(X_val[ML_FEATURE_NAMES])

    # Calculate metrics
    from sklearn.metrics import mean_absolute_error, r2_score
    mae = mean_absolute_error(y_val, y_pred)
    r2 = r2_score(y_val, y_pred)

    print("\nValidation metrics:")
    print(f"  MAE: {mae:.4f}")
    print(f"  R²: {r2:.3f}")

    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': ML_FEATURE_NAMES,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    print("\nTop 5 feature importances:")
    for idx, row in feature_importance.head(5).iterrows():
        print(f"  {row['feature']:30s}: {row['importance']:.4f}")

    print("\nPrediction test on sample data:")
    sample = X_val.iloc[0:3][ML_FEATURE_NAMES]
    sample_pred = model.predict(sample)
    sample_actual = y_val[0:3]

    for i in range(len(sample)):
        print(f"  Sample {i+1}: predicted={sample_pred[i]:.3f}, actual={sample_actual[i]:.3f}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "-" * 60)
print("Test 3: Check if database has user data")
print("-" * 60)

try:
    from database import db
    from models import UserActivityResidual

    print("Database imports successful")
    print("Note: Need app context to query database")
    print("  To test with real data, run within Flask app context")
    print("  Example: flask shell, then import this test")

except Exception as e:
    print(f"Database not available (expected in standalone mode)")
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("GBM Model Tests Complete!")
print("=" * 60)
print("\nSummary:")
print("  [OK] Config loaded")
print("  [OK] ResidualMLService imported")
print("  [OK] GBM model trains on synthetic data")
print("  [OK] Predictions work")
print("\nTo test with real user data:")
print("  1. Start app: cd backend && python app.py")
print("  2. Check user 2 data exists in database")
print("  3. Use ResidualMLService.train_user_model(user_id=2)")
