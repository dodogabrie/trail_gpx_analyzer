"""Train/test evaluation of GBM model on real Strava data.

Loads multiple activities, extracts features, trains model with proper
train/test split to evaluate overfitting and generalization.

Run from backend directory:
    source venv/bin/activate
    python test_gbm_train_test.py
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
print("GBM Model: Train/Test Evaluation on Real Activities")
print("=" * 70)

from config.hybrid_config import ML_FEATURE_NAMES, GBM_CONFIG

data_dir = Path("data/strava_cache/streams/2")
activity_files = list(data_dir.glob("*.json"))

print(f"\nFound {len(activity_files)} activity files")

# Load multiple activities and extract segments
all_segments = []
segment_duration = 100  # seconds per segment

print(f"\nProcessing activities...")

for idx, activity_file in enumerate(activity_files[:50]):  # Use first 50 activities
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

        if len(df) < 50:  # Skip very short activities
            continue

        total_distance = df['distance'].max()

        # Create segments
        for i in range(0, int(df['time'].max()), segment_duration):
            segment = df[(df['time'] >= i) & (df['time'] < i + segment_duration)]

            if len(segment) < 20:  # Skip tiny segments
                continue

            grade_values = segment['grade'].values
            velocity_values = segment['velocity'].values

            # Skip segments with zero velocity (stopped)
            if velocity_values.mean() < 0.5:
                continue

            # Calculate features
            features = {
                'grade_mean': grade_values.mean(),
                'grade_std': grade_values.std(),
                'abs_grade': np.abs(grade_values).mean(),
                'cum_distance_km': segment['distance'].iloc[0] / 1000,
                'distance_remaining_km': (total_distance - segment['distance'].iloc[0]) / 1000,
                'prev_pace_ratio': 1.0,
                'grade_change': grade_values[-1] - grade_values[0] if len(grade_values) > 1 else 0,
                'cum_elevation_gain_m': segment['altitude'].diff().clip(lower=0).sum(),
                'elevation_gain_rate': (segment['altitude'].diff().clip(lower=0).sum() /
                                        max((segment['distance'].iloc[-1] - segment['distance'].iloc[0]), 1) * 1000),
                'rolling_avg_grade_500m': grade_values[-min(50, len(grade_values)):].mean(),
                # Target: pace (min/km)
                'pace': 60 / (velocity_values.mean() * 3.6)  # Convert m/s to min/km
            }

            all_segments.append(features)

        if (idx + 1) % 10 == 0:
            print(f"  Processed {idx + 1} activities, {len(all_segments)} segments...")

    except Exception as e:
        print(f"  Error processing {activity_file.name}: {e}")
        continue

df_segments = pd.DataFrame(all_segments)

print(f"\nTotal segments extracted: {len(df_segments)}")
print(f"Activities processed: {idx + 1}")

print("\nTarget variable (pace) statistics:")
print(f"  Mean pace: {df_segments['pace'].mean():.2f} min/km")
print(f"  Std: {df_segments['pace'].std():.2f} min/km")
print(f"  Range: [{df_segments['pace'].min():.2f}, {df_segments['pace'].max():.2f}] min/km")

print("\n" + "-" * 70)
print("Train/Test Split (80/20)")
print("-" * 70)

# Prepare features and target
X = df_segments[ML_FEATURE_NAMES]
y = df_segments['pace']

# Remove any NaN or inf values
mask = ~(X.isna().any(axis=1) | np.isinf(X).any(axis=1) | np.isnan(y) | np.isinf(y))
X = X[mask]
y = y[mask]

print(f"Clean samples: {len(X)}")

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, shuffle=True
)

print(f"Train set: {len(X_train)} segments")
print(f"Test set:  {len(X_test)} segments")

print("\n" + "-" * 70)
print("Training GBM Model")
print("-" * 70)

print(f"Config: {GBM_CONFIG}")

model = GradientBoostingRegressor(**GBM_CONFIG)
model.fit(X_train, y_train)

print("Model trained successfully")

print("\n" + "-" * 70)
print("Evaluation: Train Set")
print("-" * 70)

y_train_pred = model.predict(X_train)

train_mae = mean_absolute_error(y_train, y_train_pred)
train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
train_r2 = r2_score(y_train, y_train_pred)

print(f"MAE:  {train_mae:.4f} min/km")
print(f"RMSE: {train_rmse:.4f} min/km")
print(f"R²:   {train_r2:.4f}")

print("\n" + "-" * 70)
print("Evaluation: Test Set")
print("-" * 70)

y_test_pred = model.predict(X_test)

test_mae = mean_absolute_error(y_test, y_test_pred)
test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
test_r2 = r2_score(y_test, y_test_pred)

print(f"MAE:  {test_mae:.4f} min/km")
print(f"RMSE: {test_rmse:.4f} min/km")
print(f"R²:   {test_r2:.4f}")

print("\n" + "-" * 70)
print("Overfitting Analysis")
print("-" * 70)

print(f"Train MAE:  {train_mae:.4f} min/km")
print(f"Test MAE:   {test_mae:.4f} min/km")
print(f"Difference: {abs(test_mae - train_mae):.4f} min/km ({abs(test_mae - train_mae)/train_mae*100:.1f}%)")

print(f"\nTrain R²:   {train_r2:.4f}")
print(f"Test R²:    {test_r2:.4f}")
print(f"Difference: {abs(train_r2 - test_r2):.4f} ({abs(train_r2 - test_r2)/train_r2*100:.1f}%)")

if test_mae < train_mae * 1.2 and test_r2 > train_r2 * 0.8:
    print("\n✓ Model generalizes well (low overfitting)")
elif test_mae < train_mae * 1.5:
    print("\n⚠ Moderate overfitting detected")
else:
    print("\n✗ Significant overfitting - model doesn't generalize well")

print("\n" + "-" * 70)
print("Feature Importance")
print("-" * 70)

importance_df = pd.DataFrame({
    'feature': ML_FEATURE_NAMES,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print(f"\n{'Feature':<30s} {'Importance':>10s}")
print("-" * 42)
for idx, row in importance_df.iterrows():
    bar = '█' * int(row['importance'] * 100)
    print(f"{row['feature']:<30s} {row['importance']:>10.4f} {bar}")

print("\n" + "-" * 70)
print("Sample Predictions")
print("-" * 70)

print(f"\n{'Actual':>8s} {'Predicted':>10s} {'Error':>8s} {'Grade':>8s}")
print("-" * 38)

sample_indices = np.random.choice(len(X_test), min(15, len(X_test)), replace=False)
for i in sample_indices:
    actual = y_test.iloc[i]
    pred = y_test_pred[i]
    error = pred - actual
    grade = X_test.iloc[i]['grade_mean']
    print(f"{actual:8.2f} {pred:10.2f} {error:8.2f} {grade:8.1f}%")

print("\n" + "=" * 70)
print("Evaluation Complete!")
print("=" * 70)

print("\nSummary:")
print(f"  Dataset: {len(df_segments)} segments from {idx+1} activities")
print(f"  Test MAE: {test_mae:.4f} min/km")
print(f"  Test R²: {test_r2:.4f}")
print(f"  Overfitting gap: {abs(test_mae - train_mae):.4f} min/km")
