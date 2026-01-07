"""Variable-length terrain-aware segmentation.

Groups consecutive similar-grade sections into segments of varying length.
Each segment represents homogeneous terrain (sustained climb, descent, etc).

Run from backend directory:
    source venv/bin/activate
    python variable_length_segmentation.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict

# Segmentation parameters
GRADE_TRANSITION_THRESHOLD = 3.0  # Consider transition if grade changes >3%
MIN_SEGMENT_LENGTH_M = 100        # Minimum segment length
MIN_SEGMENT_POINTS = 20           # Minimum data points
GRADE_SMOOTHING_WINDOW = 10       # Points to smooth grade signal


def segment_by_terrain_transitions(df: pd.DataFrame) -> List[Dict]:
    """Segment activity by terrain transitions (variable length).

    Groups consecutive points with similar grade into variable-length segments.
    A new segment starts when grade changes significantly.

    Args:
        df: DataFrame with distance, altitude, grade, velocity, time

    Returns:
        List of segment dicts with features
    """
    if len(df) < MIN_SEGMENT_POINTS:
        return []

    # Smooth grade to reduce noise
    df['grade_smooth'] = df['grade'].rolling(
        window=GRADE_SMOOTHING_WINDOW,
        center=True,
        min_periods=1
    ).mean()

    segments = []
    segment_start_idx = 0

    for i in range(1, len(df)):
        # Check if grade changed significantly
        grade_current = df['grade_smooth'].iloc[i]
        grade_prev = df['grade_smooth'].iloc[segment_start_idx:i].mean()

        grade_change = abs(grade_current - grade_prev)
        distance_since_start = df['distance'].iloc[i] - df['distance'].iloc[segment_start_idx]
        points_in_segment = i - segment_start_idx

        # Start new segment if:
        # 1. Grade changed significantly AND we have minimum length
        # 2. OR we've reached end of activity
        should_segment = (
            (grade_change > GRADE_TRANSITION_THRESHOLD and
             distance_since_start >= MIN_SEGMENT_LENGTH_M and
             points_in_segment >= MIN_SEGMENT_POINTS) or
            i == len(df) - 1
        )

        if should_segment:
            # Extract segment
            seg_df = df.iloc[segment_start_idx:i]

            if len(seg_df) >= MIN_SEGMENT_POINTS:
                segment = extract_segment_features(seg_df, df)
                if segment:
                    segments.append(segment)

            # Start new segment
            segment_start_idx = i

    return segments


def extract_segment_features(seg_df: pd.DataFrame, full_df: pd.DataFrame) -> Dict:
    """Extract features from a segment.

    Args:
        seg_df: Segment dataframe
        full_df: Full activity dataframe (for context)

    Returns:
        Feature dict or None if invalid
    """
    if len(seg_df) < MIN_SEGMENT_POINTS:
        return None

    # Basic metrics
    start_dist = seg_df['distance'].iloc[0]
    end_dist = seg_df['distance'].iloc[-1]
    segment_length_m = end_dist - start_dist

    if segment_length_m < MIN_SEGMENT_LENGTH_M:
        return None

    # Grade analysis
    grade_values = seg_df['grade'].values
    grade_mean = float(np.mean(grade_values))
    grade_std = float(np.std(grade_values))
    abs_grade = float(np.mean(np.abs(grade_values)))

    # Classify terrain
    if grade_mean > 2.0:
        terrain_type = 'uphill'
    elif grade_mean < -2.0:
        terrain_type = 'downhill'
    else:
        terrain_type = 'flat'

    # Elevation change
    if 'altitude' in seg_df.columns:
        elev_changes = np.diff(seg_df['altitude'].values)
        total_elevation_gain = float(np.sum(elev_changes[elev_changes > 0]))
        total_elevation_loss = float(np.abs(np.sum(elev_changes[elev_changes < 0])))
        net_elevation_change = float(seg_df['altitude'].iloc[-1] - seg_df['altitude'].iloc[0])
    else:
        total_elevation_gain = 0.0
        total_elevation_loss = 0.0
        net_elevation_change = 0.0

    # Velocity/pace
    velocity_values = seg_df['velocity'].values
    velocity_mean = float(np.mean(velocity_values))

    if velocity_mean <= 0:
        return None

    pace_min_per_km = 60.0 / (velocity_mean * 3.6)

    # Duration
    duration_s = float(seg_df['time'].iloc[-1] - seg_df['time'].iloc[0])

    # Context (position in activity)
    total_distance_km = full_df['distance'].max() / 1000
    cum_distance_km = start_dist / 1000
    distance_remaining_km = total_distance_km - cum_distance_km

    # Cumulative elevation (fatigue indicator)
    cum_elevation_gain_m = 0.0
    if 'altitude' in full_df.columns:
        prior_df = full_df[full_df['distance'] < start_dist]
        if len(prior_df) > 1:
            prior_elev_changes = np.diff(prior_df['altitude'].values)
            cum_elevation_gain_m = float(np.sum(prior_elev_changes[prior_elev_changes > 0]))

    # Elevation gain rate (m per km)
    elevation_gain_rate = (total_elevation_gain / segment_length_m * 1000) if segment_length_m > 0 else 0.0

    return {
        # Segment characteristics
        'segment_length_km': segment_length_m / 1000,
        'segment_length_m': segment_length_m,
        'duration_s': duration_s,
        'terrain_type': terrain_type,

        # Grade features
        'grade_mean': grade_mean,
        'grade_std': grade_std,
        'abs_grade': abs_grade,
        'grade_change': grade_values[-1] - grade_values[0] if len(grade_values) > 1 else 0.0,
        'rolling_avg_grade_500m': grade_mean,  # For compatibility

        # Elevation features
        'total_elevation_gain_m': total_elevation_gain,
        'total_elevation_loss_m': total_elevation_loss,
        'net_elevation_change_m': net_elevation_change,
        'elevation_gain_rate': elevation_gain_rate,

        # Position/context features
        'cum_distance_km': cum_distance_km,
        'distance_remaining_km': distance_remaining_km,
        'cum_elevation_gain_m': cum_elevation_gain_m,

        # Performance (target)
        'pace_min_per_km': pace_min_per_km,
        'velocity_m_s': velocity_mean,

        # Placeholder for prev segment
        'prev_pace_ratio': 1.0,

        # Metadata
        'start_distance_m': start_dist,
        'end_distance_m': end_dist,
        'num_points': len(seg_df)
    }


def test_segmentation():
    """Test variable-length segmentation on real activities."""

    print("=" * 70)
    print("Variable-Length Terrain Segmentation Test")
    print("=" * 70)

    data_dir = Path("data/strava_cache/streams/2")
    activity_files = list(data_dir.glob("*.json"))

    print(f"\nFound {len(activity_files)} activity files")
    print(f"\nParameters:")
    print(f"  Grade transition threshold: {GRADE_TRANSITION_THRESHOLD}%")
    print(f"  Min segment length: {MIN_SEGMENT_LENGTH_M}m")
    print(f"  Min points per segment: {MIN_SEGMENT_POINTS}")

    # Test on first few activities
    test_files = activity_files[:5]

    for idx, activity_file in enumerate(test_files):
        print(f"\n{'='*70}")
        print(f"Activity {idx+1}: {activity_file.name}")
        print('='*70)

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

            print(f"\nActivity stats:")
            print(f"  Duration: {df['time'].max()/60:.1f} min")
            print(f"  Distance: {df['distance'].max()/1000:.2f} km")
            print(f"  Elev gain: {np.diff(df['altitude']).clip(min=0).sum():.0f}m")
            print(f"  Data points: {len(df)}")

            # Segment
            segments = segment_by_terrain_transitions(df)

            print(f"\nSegments created: {len(segments)}")

            # Show segments
            print(f"\n{'#':>3s} {'Terrain':>8s} {'Length':>10s} {'Grade':>8s} "
                  f"{'D+':>6s} {'D-':>6s} {'Pace':>8s}")
            print("-" * 70)

            for i, seg in enumerate(segments[:20]):
                print(f"{i+1:3d} {seg['terrain_type']:>8s} "
                      f"{seg['segment_length_km']:>9.2f}km "
                      f"{seg['grade_mean']:>7.1f}% "
                      f"{seg['total_elevation_gain_m']:>5.0f}m "
                      f"{seg['total_elevation_loss_m']:>5.0f}m "
                      f"{seg['pace_min_per_km']:>7.2f}")

            if len(segments) > 20:
                print(f"... and {len(segments) - 20} more segments")

            # Statistics
            terrain_counts = pd.Series([s['terrain_type'] for s in segments]).value_counts()

            print(f"\nTerrain distribution:")
            for terrain, count in terrain_counts.items():
                avg_length = np.mean([s['segment_length_km'] for s in segments if s['terrain_type'] == terrain])
                print(f"  {terrain:10s}: {count:2d} segments, avg {avg_length:.2f}km")

            print(f"\nSegment length stats:")
            lengths = [s['segment_length_km'] for s in segments]
            print(f"  Min: {min(lengths):.2f}km")
            print(f"  Max: {max(lengths):.2f}km")
            print(f"  Mean: {np.mean(lengths):.2f}km")
            print(f"  Median: {np.median(lengths):.2f}km")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_segmentation()
