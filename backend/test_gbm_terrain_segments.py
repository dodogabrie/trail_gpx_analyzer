"""Train/test GBM with terrain-based segmentation.

Segments activities by uphill/downhill/flat sections instead of fixed time.

Run from backend directory:
    source venv/bin/activate
    python test_gbm_terrain_segments.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("GBM Model: Terrain-Based Segmentation")
print("=" * 70)

from config.hybrid_config import ML_FEATURE_NAMES, GBM_CONFIG

# Segmentation thresholds
GRADE_UH_THRESHOLD = 2.0   # > 2% = uphill
GRADE_DH_THRESHOLD = -2.0  # < -2% = downhill
MIN_SEGMENT_POINTS = 30    # Minimum points per segment
MIN_SEGMENT_DISTANCE = 50  # Minimum 50m per segment

def segment_by_terrain(df):
    """Segment activity by terrain (uphill/downhill/flat).

    Args:
        df: DataFrame with time, distance, altitude, grade, velocity

    Returns:
        List of segment dictionaries
    """
    segments = []

    if len(df) < MIN_SEGMENT_POINTS:
        return segments

    # Smooth grade to reduce noise
    df['grade_smooth'] = df['grade'].rolling(window=5, center=True, min_periods=1).mean()

    # Classify each point
    df['terrain'] = 'flat'
    df.loc[df['grade_smooth'] > GRADE_UH_THRESHOLD, 'terrain'] = 'uphill'
    df.loc[df['grade_smooth'] < GRADE_DH_THRESHOLD, 'terrain'] = 'downhill'

    # Find transitions (where terrain changes)
    df['terrain_change'] = (df['terrain'] != df['terrain'].shift()).astype(int)
    df['segment_id'] = df['terrain_change'].cumsum()

    # Group by segment_id
    for seg_id, segment_df in df.groupby('segment_id'):
        if len(segment_df) < MIN_SEGMENT_POINTS:
            continue

        segment_distance = segment_df['distance'].iloc[-1] - segment_df['distance'].iloc[0]
        if segment_distance < MIN_SEGMENT_DISTANCE:
            continue

        velocity_values = segment_df['velocity'].values
        if velocity_values.mean() < 0.5:  # Skip stopped
            continue

        grade_values = segment_df['grade'].values
        terrain_type = segment_df['terrain'].iloc[0]

        # Calculate features
        total_distance = df['distance'].max()

        features = {
            'grade_mean': grade_values.mean(),
            'grade_std': grade_values.std(),
            'abs_grade': np.abs(grade_values).mean(),
            'cum_distance_km': segment_df['distance'].iloc[0] / 1000,
            'distance_remaining_km': (total_distance - segment_df['distance'].iloc[0]) / 1000,
            'prev_pace_ratio': 1.0,
            'grade_change': grade_values[-1] - grade_values[0] if len(grade_values) > 1 else 0,
            'cum_elevation_gain_m': segment_df['altitude'].diff().clip(lower=0).sum(),
            'elevation_gain_rate': (segment_df['altitude'].diff().clip(lower=0).sum() /
                                    max(segment_distance, 1) * 1000),
            'rolling_avg_grade_500m': grade_values.mean(),
            'pace': 60 / (velocity_values.mean() * 3.6),  # min/km
            'terrain_type': terrain_type,
            'segment_distance_m': segment_distance,
            'duration_s': segment_df['time'].iloc[-1] - segment_df['time'].iloc[0]
        }

        segments.append(features)

    return segments

# Process activities
data_dir = Path("data/strava_cache/streams/2")
activity_files = list(data_dir.glob("*.json"))

print(f"\nFound {len(activity_files)} activity files")
print(f"\nSegmentation strategy:")
print(f"  Uphill:   grade > {GRADE_UH_THRESHOLD}%")
print(f"  Downhill: grade < {GRADE_DH_THRESHOLD}%")
print(f"  Flat:     otherwise")
print(f"  Min segment: {MIN_SEGMENT_POINTS} points, {MIN_SEGMENT_DISTANCE}m")

all_segments = []
activities_processed = 0

print(f"\nProcessing activities...")

for idx, activity_file in enumerate(activity_files[:50]):
    try:
        with open(activity_file) as f:
            activity_data = json.load(f)

        df = pd.DataFrame({
            'time': activity_data['time'],
            'altitude': activity_data['altitude'],
            'grade': activity_data.get('grade_smooth', [0] * len(activity_data['time'])),
            'velocity': activity_data.get('velocity_smooth', [0] * len(activity_data['time'])),
            'distance': activity_data.get('distance', list(range(len(activity_data['time']))))
        })

        if len(df) < 50:
            continue

        segments = segment_by_terrain(df)

        if segments:
            activities_processed += 1
            all_segments.extend(segments)

            uh = sum(1 for s in segments if s['terrain_type'] == 'uphill')
            dh = sum(1 for s in segments if s['terrain_type'] == 'downhill')
            flat = sum(1 for s in segments if s['terrain_type'] == 'flat')

            if (idx + 1) % 10 == 0:
                print(f"  {idx+1} activities: {len(all_segments)} segments "
                      f"(UH:{uh} DH:{dh} Flat:{flat})")

    except Exception as e:
        continue

df_segments = pd.DataFrame(all_segments)

print(f"\nTotal: {activities_processed} activities, {len(df_segments)} segments")

# Terrain distribution
print("\n" + "-" * 70)
print("Terrain Distribution")
print("-" * 70)

terrain_counts = df_segments['terrain_type'].value_counts()
for terrain, count in terrain_counts.items():
    pct = count / len(df_segments) * 100
    bar = '█' * int(pct / 2)
    print(f"{terrain:10s}: {count:4d} segments ({pct:5.1f}%) {bar}")

# Statistics by terrain
print("\n" + "-" * 70)
print("Pace Statistics by Terrain")
print("-" * 70)

print(f"\n{'Terrain':10s} {'Count':>6s} {'Mean Pace':>10s} {'Std':>8s} {'Grade':>8s}")
print("-" * 45)

for terrain in ['uphill', 'flat', 'downhill']:
    if terrain in terrain_counts.index:
        terrain_data = df_segments[df_segments['terrain_type'] == terrain]
        print(f"{terrain:10s} {len(terrain_data):6d} {terrain_data['pace'].mean():10.2f} "
              f"{terrain_data['pace'].std():8.2f} {terrain_data['grade_mean'].mean():8.1f}%")

print("\n" + "-" * 70)
print("Train/Test Split (80/20)")
print("-" * 70)

X = df_segments[ML_FEATURE_NAMES]
y = df_segments['pace']

# Clean data
mask = ~(X.isna().any(axis=1) | np.isinf(X).any(axis=1) | np.isnan(y) | np.isinf(y))
X = X[mask]
y = y[mask]
terrain_types = df_segments.loc[mask, 'terrain_type']

print(f"Clean samples: {len(X)}")

X_train, X_test, y_train, y_test, terrain_train, terrain_test = train_test_split(
    X, y, terrain_types, test_size=0.2, random_state=42, shuffle=True
)

print(f"Train: {len(X_train)} segments")
print(f"Test:  {len(X_test)} segments")

print("\n" + "-" * 70)
print("Training GBM Model")
print("-" * 70)

model = GradientBoostingRegressor(**GBM_CONFIG)
model.fit(X_train, y_train)

print("Model trained")

# Evaluate
y_train_pred = model.predict(X_train)
y_test_pred = model.predict(X_test)

train_mae = mean_absolute_error(y_train, y_train_pred)
train_r2 = r2_score(y_train, y_train_pred)
test_mae = mean_absolute_error(y_test, y_test_pred)
test_r2 = r2_score(y_test, y_test_pred)

print("\n" + "-" * 70)
print("Results")
print("-" * 70)

print(f"\n{'':20s} {'Train':>12s} {'Test':>12s} {'Gap':>10s}")
print("-" * 56)
print(f"{'MAE (min/km)':20s} {train_mae:12.4f} {test_mae:12.4f} "
      f"{(test_mae-train_mae)/train_mae*100:9.1f}%")
print(f"{'R²':20s} {train_r2:12.4f} {test_r2:12.4f} "
      f"{(train_r2-test_r2)/train_r2*100:9.1f}%")

# Evaluate by terrain
print("\n" + "-" * 70)
print("Test Performance by Terrain")
print("-" * 70)

print(f"\n{'Terrain':10s} {'Samples':>8s} {'MAE':>10s} {'R²':>8s}")
print("-" * 38)

for terrain in ['uphill', 'flat', 'downhill']:
    mask_terrain = terrain_test == terrain
    if mask_terrain.sum() > 0:
        y_terrain = y_test[mask_terrain]
        y_pred_terrain = y_test_pred[mask_terrain]
        mae_terrain = mean_absolute_error(y_terrain, y_pred_terrain)
        r2_terrain = r2_score(y_terrain, y_pred_terrain)
        print(f"{terrain:10s} {mask_terrain.sum():8d} {mae_terrain:10.4f} {r2_terrain:8.4f}")

# Feature importance
print("\n" + "-" * 70)
print("Feature Importance")
print("-" * 70)

importance_df = pd.DataFrame({
    'feature': ML_FEATURE_NAMES,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

for idx, row in importance_df.head(5).iterrows():
    print(f"  {row['feature']:30s}: {row['importance']:.4f}")

print("\n" + "=" * 70)
print("Complete!")
print("=" * 70)
