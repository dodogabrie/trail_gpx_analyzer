"""Test GBM model on real Strava activity data.

Loads activity from backend/data/strava_cache and tests predictions.

Run from backend directory:
    source venv/bin/activate
    python test_gbm_real_data.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor

print("=" * 70)
print("Testing GBM Model on Real Strava Activity Data")
print("=" * 70)

# Load config
from config.hybrid_config import ML_FEATURE_NAMES, GBM_CONFIG

# Find available activity files
data_dir = Path("data/strava_cache/streams/2")
activity_files = list(data_dir.glob("*.json"))

print(f"\nFound {len(activity_files)} activity files for user 2")
print(f"Files: {[f.name for f in activity_files[:5]]}{'...' if len(activity_files) > 5 else ''}")

if not activity_files:
    print("ERROR: No activity files found!")
    sys.exit(1)

# Load first activity
activity_file = activity_files[0]
print(f"\nLoading: {activity_file.name}")

with open(activity_file) as f:
    activity_data = json.load(f)

print(f"Available streams: {list(activity_data.keys())}")
print(f"Data points: {len(activity_data['time'])}")

# Convert to DataFrame
df = pd.DataFrame({
    'time': activity_data['time'],
    'altitude': activity_data['altitude'],
    'grade': activity_data.get('grade_smooth', [0] * len(activity_data['time'])),
    'velocity': activity_data.get('velocity_smooth', [0] * len(activity_data['time'])),
    'heartrate': activity_data.get('heartrate', [0] * len(activity_data['time']))
})

print("\nActivity summary:")
print(f"  Duration: {df['time'].max()} seconds ({df['time'].max()/60:.1f} min)")
print(f"  Elevation: {df['altitude'].min():.1f}m - {df['altitude'].max():.1f}m")
print(f"  Elevation gain: {(df['altitude'].diff().clip(lower=0).sum()):.1f}m")
print(f"  Avg velocity: {df['velocity'].mean():.2f} m/s")
print(f"  Avg heartrate: {df['heartrate'].mean():.0f} bpm")

print("\n" + "-" * 70)
print("Creating segments and extracting features")
print("-" * 70)

# Segment the activity (e.g., every 500m or 100 seconds)
segment_duration = 100  # seconds
segments = []

df['distance'] = df['velocity'].cumsum()
total_distance = df['distance'].max()

for i in range(0, int(df['time'].max()), segment_duration):
    segment = df[(df['time'] >= i) & (df['time'] < i + segment_duration)]

    if len(segment) < 10:  # Skip tiny segments
        continue

    # Calculate features (matching ML_FEATURE_NAMES)
    grade_values = segment['grade'].values

    features = {
        'grade_mean': grade_values.mean(),
        'grade_std': grade_values.std(),
        'abs_grade': np.abs(grade_values).mean(),
        'cum_distance_km': segment['distance'].iloc[0] / 1000,
        'distance_remaining_km': (total_distance - segment['distance'].iloc[0]) / 1000,
        'prev_pace_ratio': 1.0,  # Would need previous segment's actual pace
        'grade_change': grade_values[-1] - grade_values[0] if len(grade_values) > 1 else 0,
        'cum_elevation_gain_m': segment['altitude'].diff().clip(lower=0).sum(),
        'elevation_gain_rate': (segment['altitude'].diff().clip(lower=0).sum() /
                                (segment['distance'].iloc[-1] - segment['distance'].iloc[0] + 0.001) * 1000),
        'rolling_avg_grade_500m': grade_values[-min(50, len(grade_values)):].mean()
    }

    segments.append(features)

X_real = pd.DataFrame(segments)

print(f"Created {len(X_real)} segments from activity")
print("\nSample features from first 3 segments:")
print(X_real.head(3)[['grade_mean', 'abs_grade', 'cum_distance_km', 'elevation_gain_rate']])

print("\n" + "-" * 70)
print("Training GBM on synthetic data (as reference)")
print("-" * 70)

# Train a model on synthetic data (as we don't have ground truth residuals)
n_train = 100
np.random.seed(42)

X_train = pd.DataFrame({
    'grade_mean': np.random.uniform(-5, 10, n_train),
    'grade_std': np.random.uniform(0, 5, n_train),
    'abs_grade': np.random.uniform(0, 10, n_train),
    'cum_distance_km': np.random.uniform(0, 20, n_train),
    'distance_remaining_km': np.random.uniform(0, 20, n_train),
    'prev_pace_ratio': np.random.uniform(0.8, 1.2, n_train),
    'grade_change': np.random.uniform(-5, 5, n_train),
    'cum_elevation_gain_m': np.random.uniform(0, 500, n_train),
    'elevation_gain_rate': np.random.uniform(0, 50, n_train),
    'rolling_avg_grade_500m': np.random.uniform(-5, 10, n_train)
})

# Simulate residual multipliers (1.0 = baseline, >1 = slower, <1 = faster)
# Make it correlated with grade and fatigue
y_train = (1.0 +
           0.02 * X_train['grade_mean'] +  # Harder on steep grades
           0.01 * X_train['cum_distance_km'] +  # Fatigue effect
           np.random.normal(0, 0.1, n_train))  # Noise
y_train = np.clip(y_train, 0.7, 1.5)

model = GradientBoostingRegressor(**GBM_CONFIG)
model.fit(X_train[ML_FEATURE_NAMES], y_train)

print(f"Model trained on {len(X_train)} synthetic activities")

print("\n" + "-" * 70)
print("Making predictions on real activity segments")
print("-" * 70)

predictions = model.predict(X_real[ML_FEATURE_NAMES])

print(f"\nPredictions for {len(predictions)} segments:")
print("\nSegment | Grade | Dist(km) | Elev Rate | Predicted Multiplier")
print("-" * 70)

for i in range(min(10, len(predictions))):
    seg = X_real.iloc[i]
    print(f"   {i+1:2d}   | {seg['grade_mean']:5.1f}% | "
          f"{seg['cum_distance_km']:6.2f}  | {seg['elevation_gain_rate']:8.1f}  | "
          f"{predictions[i]:6.3f}")

print("\nPrediction statistics:")
print(f"  Mean multiplier: {predictions.mean():.3f}")
print(f"  Std: {predictions.std():.3f}")
print(f"  Range: [{predictions.min():.3f}, {predictions.max():.3f}]")

print("\nInterpretation:")
print("  1.0 = baseline pace")
print("  >1.0 = slower than baseline (e.g., 1.2 = 20% slower)")
print("  <1.0 = faster than baseline (e.g., 0.9 = 10% faster)")

print("\n" + "-" * 70)
print("Feature importance from trained model")
print("-" * 70)

importance_df = pd.DataFrame({
    'feature': ML_FEATURE_NAMES,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

for idx, row in importance_df.iterrows():
    print(f"  {row['feature']:30s}: {row['importance']:6.4f}")

print("\n" + "=" * 70)
print("Test Complete!")
print("=" * 70)
print("\nTo test with actual ground truth:")
print("  1. Need database with UserActivityResidual records")
print("  2. Compare predicted vs actual residuals from past activities")
print("  3. Use: ResidualMLService.train_user_model(user_id=2)")
