"""Train GBM with variable-length vs fixed-length segmentation comparison.

Run from backend directory:
    source venv/bin/activate
    python test_variable_length_gbm.py
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
from sklearn.metrics import mean_absolute_error, r2_score
import warnings
warnings.filterwarnings('ignore')

from variable_length_segmentation import segment_by_terrain_transitions
from config.hybrid_config import GBM_CONFIG

print("=" * 70)
print("GBM Comparison: Variable-Length vs Fixed-Length Segmentation")
print("=" * 70)

# Features for GBM
FEATURES = [
    'grade_mean',
    'grade_std',
    'abs_grade',
    'cum_distance_km',
    'distance_remaining_km',
    'prev_pace_ratio',
    'grade_change',
    'cum_elevation_gain_m',
    'elevation_gain_rate',
    'rolling_avg_grade_500m'
]

data_dir = Path("data/strava_cache/streams/2")
activity_files = list(data_dir.glob("*.json"))

print(f"\nProcessing {min(50, len(activity_files))} activities...")

# APPROACH 1: Variable-length terrain segments
print("\n" + "-" * 70)
print("APPROACH 1: Variable-Length Terrain Segmentation")
print("-" * 70)

variable_segments = []

for idx, activity_file in enumerate(activity_files[:50]):
    try:
        with open(activity_file) as f:
            activity_data = json.load(f)

        df = pd.DataFrame({
            'time': activity_data['time'],
            'distance': activity_data['distance'],
            'altitude': activity_data.get('altitude', [0] * len(activity_data['time'])),
            'grade': activity_data.get('grade_smooth', [0] * len(activity_data['time'])),
            'velocity': activity_data.get('velocity_smooth', [0] * len(activity_data['time']))
        })

        if len(df) < 50:
            continue

        segments = segment_by_terrain_transitions(df)
        variable_segments.extend(segments)

        if (idx + 1) % 10 == 0:
            print(f"  {idx+1} activities: {len(variable_segments)} segments")

    except Exception as e:
        continue

print(f"\nTotal variable-length segments: {len(variable_segments)}")

# APPROACH 2: Fixed 200m segments (production)
print("\n" + "-" * 70)
print("APPROACH 2: Fixed 200m Segmentation (Production)")
print("-" * 70)

fixed_segments = []
SEGMENT_LENGTH_M = 200

for idx, activity_file in enumerate(activity_files[:50]):
    try:
        with open(activity_file) as f:
            activity_data = json.load(f)

        df = pd.DataFrame({
            'time': activity_data['time'],
            'distance': activity_data['distance'],
            'altitude': activity_data.get('altitude', [0] * len(activity_data['time'])),
            'grade': activity_data.get('grade_smooth', [0] * len(activity_data['time'])),
            'velocity': activity_data.get('velocity_smooth', [0] * len(activity_data['time']))
        })

        if len(df) < 50:
            continue

        max_dist = df['distance'].max()

        for start in np.arange(0, max_dist, SEGMENT_LENGTH_M):
            end = start + SEGMENT_LENGTH_M
            mask = (df['distance'] >= start) & (df['distance'] < end)

            if mask.sum() < 5:
                continue

            seg_df = df[mask]
            velocity_mean = seg_df['velocity'].mean()

            if velocity_mean <= 0.5:
                continue

            grade_values = seg_df['grade'].values

            # Calculate features (matching variable-length)
            segment = {
                'grade_mean': float(np.mean(grade_values)),
                'grade_std': float(np.std(grade_values)),
                'abs_grade': float(np.mean(np.abs(grade_values))),
                'cum_distance_km': start / 1000,
                'distance_remaining_km': (max_dist - start) / 1000,
                'prev_pace_ratio': 1.0,
                'grade_change': grade_values[-1] - grade_values[0] if len(grade_values) > 1 else 0.0,
                'cum_elevation_gain_m': 0.0,  # Simplified
                'elevation_gain_rate': np.diff(seg_df['altitude']).clip(min=0).sum() / SEGMENT_LENGTH_M * 1000,
                'rolling_avg_grade_500m': float(np.mean(grade_values)),
                'pace_min_per_km': 60.0 / (velocity_mean * 3.6),
                'segment_length_km': (end - start) / 1000
            }

            fixed_segments.append(segment)

    except Exception as e:
        continue

print(f"Total fixed-length segments: {len(fixed_segments)}")

# Train and compare both approaches
print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)

for name, segments in [("Variable-Length", variable_segments), ("Fixed 200m", fixed_segments)]:
    print(f"\n{'-'*70}")
    print(f"{name} Segmentation")
    print(f"{'-'*70}")

    df_seg = pd.DataFrame(segments)

    # Prepare data
    X = df_seg[FEATURES]
    y = df_seg['pace_min_per_km']

    # Clean
    mask = ~(X.isna().any(axis=1) | np.isinf(X).any(axis=1) | np.isnan(y) | np.isinf(y))
    X = X[mask]
    y = y[mask]

    print(f"Clean samples: {len(X)}")

    if 'segment_length_km' in df_seg.columns:
        lengths = df_seg.loc[mask, 'segment_length_km']
        print(f"Segment length: {lengths.min():.2f}km to {lengths.max():.2f}km "
              f"(avg {lengths.mean():.2f}km)")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, shuffle=True
    )

    # Train
    model = GradientBoostingRegressor(**GBM_CONFIG)
    model.fit(X_train, y_train)

    # Evaluate
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)

    train_mae = mean_absolute_error(y_train, y_train_pred)
    train_r2 = r2_score(y_train, y_train_pred)
    test_mae = mean_absolute_error(y_test, y_test_pred)
    test_r2 = r2_score(y_test, y_test_pred)

    print(f"\nResults:")
    print(f"  Train MAE: {train_mae:.4f} min/km, R²: {train_r2:.4f}")
    print(f"  Test MAE:  {test_mae:.4f} min/km, R²: {test_r2:.4f}")
    print(f"  Gap:       {(test_mae-train_mae)/train_mae*100:.1f}% MAE, "
          f"{abs(train_r2-test_r2)/train_r2*100:.1f}% R²")

    # Feature importance
    importance = pd.DataFrame({
        'feature': FEATURES,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    print(f"\nTop features:")
    for idx, row in importance.head(3).iterrows():
        print(f"  {row['feature']:30s}: {row['importance']:.4f}")

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print("""
Variable-length segmentation should provide:
  - Fewer, more meaningful segments
  - Each segment = homogeneous terrain section
  - Better interpretability
  - Potentially better generalization

Next step: Integrate into production if results are good!
""")
