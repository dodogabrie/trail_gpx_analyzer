"""Smart variable-length segmentation with 4 terrain types.

Terrain types:
- UPHILL: Sustained positive grade
- DOWNHILL: Sustained negative grade
- FLAT: Low grade, low variance
- ROLLING: Mixed up/down (significant both D+ and D-)

Run from backend directory:
    source venv/bin/activate
    python smart_segmentation.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple

# Segmentation parameters
GRADE_UH_THRESHOLD = 2.0      # > 2% = uphill tendency (for initial classification)
GRADE_DH_THRESHOLD = -2.0     # < -2% = downhill tendency (for initial classification)
MIN_SEGMENT_LENGTH_M = 200    # Minimum 200m per segment
UH_ELEVATION_THRESHOLD = 100  # Need 100m+ elevation gain to be classified as uphill
DH_ELEVATION_THRESHOLD = 100  # Need 100m+ elevation loss to be classified as downhill
ROLLING_ELEV_THRESHOLD = 30   # D+ and D- both > 30m = rolling
MERGE_GRADE_DIFF_MAX = 5.0    # Merge if grade difference < 5%
GRADE_SMOOTHING_WINDOW = 10   # Smooth grade signal


def classify_terrain_type(segment_data: Dict) -> str:
    """Classify segment terrain type based on elevation + grade.

    Priority:
    1. UPHILL: (D+ >= 100m) OR (D+ >= 50m AND avg_grade > 5%)
    2. DOWNHILL: (D- >= 100m) OR (D- >= 50m AND avg_grade < -5%)
    3. ROLLING: Both D+ > 30m AND D- > 30m
    4. FLAT: Everything else

    Args:
        segment_data: Dict with grade_mean, total_elevation_gain_m, total_elevation_loss_m

    Returns:
        'uphill', 'downhill', 'flat', or 'rolling'
    """
    d_plus = segment_data['total_elevation_gain_m']
    d_minus = segment_data['total_elevation_loss_m']
    grade_mean = segment_data['grade_mean']

    # Uphill: major elevation gain OR significant gain with steep grade
    is_uphill = (
        (d_plus >= UH_ELEVATION_THRESHOLD and d_minus < DH_ELEVATION_THRESHOLD) or
        (d_plus >= 50 and d_minus < 50 and grade_mean > 5.0)
    )
    if is_uphill:
        return 'uphill'

    # Downhill: major elevation loss OR significant loss with steep grade
    is_downhill = (
        (d_minus >= DH_ELEVATION_THRESHOLD and d_plus < UH_ELEVATION_THRESHOLD) or
        (d_minus >= 50 and d_plus < 50 and grade_mean < -5.0)
    )
    if is_downhill:
        return 'downhill'

    # Rolling: both significant D+ and D-
    if d_plus > ROLLING_ELEV_THRESHOLD and d_minus > ROLLING_ELEV_THRESHOLD:
        return 'rolling'

    # Everything else is flat
    return 'flat'


def should_merge_segments(seg1: Dict, seg2: Dict, aggressive: bool = False) -> bool:
    """Check if two consecutive segments should be merged.

    Merge if:
    - Same terrain type AND
    - (Aggressive mode: always merge) OR
    - (Normal mode: grade difference < threshold OR either segment is tiny)

    Args:
        seg1, seg2: Segment dicts
        aggressive: If True, merge all same-type neighbors

    Returns:
        True if should merge
    """
    # Must be same terrain type
    if seg1['terrain_type'] != seg2['terrain_type']:
        return False

    # Aggressive mode: always merge same type
    if aggressive:
        return True

    # Merge if either segment is tiny (< min length)
    if (seg1['segment_length_m'] < MIN_SEGMENT_LENGTH_M or
        seg2['segment_length_m'] < MIN_SEGMENT_LENGTH_M):
        return True

    # Check gradient difference
    grade_diff = abs(seg1['grade_mean'] - seg2['grade_mean'])

    if grade_diff > MERGE_GRADE_DIFF_MAX:
        return False

    return True


def merge_two_segments(seg1: Dict, seg2: Dict, df: pd.DataFrame) -> Dict:
    """Merge two segments into one.

    Args:
        seg1, seg2: Segments to merge
        df: Full activity dataframe

    Returns:
        Merged segment dict
    """
    # Get combined data range
    start_idx = seg1['start_idx']
    end_idx = seg2['end_idx']
    combined_df = df.iloc[start_idx:end_idx]

    # Extract features from combined segment
    return extract_segment_features(
        combined_df,
        df,
        start_idx=start_idx,
        end_idx=end_idx
    )


def extract_segment_features(
    seg_df: pd.DataFrame,
    full_df: pd.DataFrame,
    start_idx: int = None,
    end_idx: int = None
) -> Dict:
    """Extract features from segment.

    Args:
        seg_df: Segment dataframe
        full_df: Full activity dataframe
        start_idx, end_idx: Original indices

    Returns:
        Feature dict
    """
    if len(seg_df) < 5:
        return None

    start_dist = seg_df['distance'].iloc[0]
    end_dist = seg_df['distance'].iloc[-1]
    segment_length_m = end_dist - start_dist

    if segment_length_m < 10:  # Too short
        return None

    # Grade
    grade_values = seg_df['grade'].values
    grade_mean = float(np.mean(grade_values))
    grade_std = float(np.std(grade_values))

    # Elevation
    if 'altitude' in seg_df.columns:
        elev_changes = np.diff(seg_df['altitude'].values)
        d_plus = float(np.sum(elev_changes[elev_changes > 0]))
        d_minus = float(np.abs(np.sum(elev_changes[elev_changes < 0])))
    else:
        d_plus = 0.0
        d_minus = 0.0

    # Velocity/pace
    velocity_values = seg_df['velocity'].values
    velocity_mean = float(np.mean(velocity_values))

    if velocity_mean <= 0:
        return None

    pace_min_per_km = 60.0 / (velocity_mean * 3.6)

    # Duration
    duration_s = float(seg_df['time'].iloc[-1] - seg_df['time'].iloc[0])

    # Context
    total_distance_km = full_df['distance'].max() / 1000
    cum_distance_km = start_dist / 1000

    # Cumulative elevation
    cum_d_plus = 0.0
    if 'altitude' in full_df.columns and start_dist > 0:
        prior_df = full_df[full_df['distance'] < start_dist]
        if len(prior_df) > 1:
            prior_elev_changes = np.diff(prior_df['altitude'].values)
            cum_d_plus = float(np.sum(prior_elev_changes[prior_elev_changes > 0]))

    segment_data = {
        'grade_mean': grade_mean,
        'grade_std': grade_std,
        'total_elevation_gain_m': d_plus,
        'total_elevation_loss_m': d_minus,
        'segment_length_m': segment_length_m,
        'segment_length_km': segment_length_m / 1000,
        'start_distance_m': start_dist,
        'end_distance_m': end_dist,
        'duration_s': duration_s,
        'pace_min_per_km': pace_min_per_km,
        'velocity_m_s': velocity_mean,
        'cum_distance_km': cum_distance_km,
        'distance_remaining_km': total_distance_km - cum_distance_km,
        'cum_elevation_gain_m': cum_d_plus,
        'start_idx': start_idx if start_idx is not None else 0,
        'end_idx': end_idx if end_idx is not None else len(seg_df),
        'num_points': len(seg_df)
    }

    # Classify terrain
    segment_data['terrain_type'] = classify_terrain_type(segment_data)

    # Add ML features
    segment_data['abs_grade'] = float(np.mean(np.abs(grade_values)))
    segment_data['grade_change'] = grade_values[-1] - grade_values[0] if len(grade_values) > 1 else 0.0
    segment_data['elevation_gain_rate'] = (d_plus / segment_length_m * 1000) if segment_length_m > 0 else 0.0
    segment_data['rolling_avg_grade_500m'] = grade_mean
    segment_data['prev_pace_ratio'] = 1.0

    return segment_data


def segment_activity(df: pd.DataFrame) -> List[Dict]:
    """Segment activity with smart merging strategy.

    Steps:
    1. Smooth grade signal
    2. Classify each point (UH/DH/Flat)
    3. Group consecutive same-type points
    4. Extract features and classify segments (including ROLLING)
    5. Merge consecutive same-type segments if appropriate
    6. Enforce minimum segment length

    Args:
        df: Activity dataframe

    Returns:
        List of segment dicts
    """
    if len(df) < 30:
        return []

    # Step 1: Smooth grade
    df = df.copy()
    df['grade_smooth'] = df['grade'].rolling(
        window=GRADE_SMOOTHING_WINDOW,
        center=True,
        min_periods=1
    ).mean()

    # Step 2: Classify each point
    df['point_type'] = 'flat'
    df.loc[df['grade_smooth'] > GRADE_UH_THRESHOLD, 'point_type'] = 'uphill'
    df.loc[df['grade_smooth'] < GRADE_DH_THRESHOLD, 'point_type'] = 'downhill'

    # Step 3: Group consecutive same-type points
    df['type_change'] = (df['point_type'] != df['point_type'].shift()).astype(int)
    df['group_id'] = df['type_change'].cumsum()

    # Step 4: Extract segments
    segments = []

    for group_id, group_df in df.groupby('group_id'):
        segment = extract_segment_features(
            group_df,
            df,
            start_idx=group_df.index[0],
            end_idx=group_df.index[-1] + 1
        )

        if segment:
            segments.append(segment)

    if not segments:
        return []

    # Step 5: AGGRESSIVE merge - merge all consecutive same-type segments first
    # This handles the case where tiny segments block merging
    merged = True
    max_iterations = 20  # Prevent infinite loops
    iteration = 0

    while merged and iteration < max_iterations:
        merged = False
        new_segments = []
        i = 0

        while i < len(segments):
            if i < len(segments) - 1 and should_merge_segments(segments[i], segments[i+1], aggressive=True):
                # Merge with next
                merged_seg = merge_two_segments(segments[i], segments[i+1], df)
                if merged_seg:
                    new_segments.append(merged_seg)
                    merged = True
                else:
                    # Merge failed, keep both
                    new_segments.append(segments[i])
                    new_segments.append(segments[i+1])
                i += 2
            else:
                new_segments.append(segments[i])
                i += 1

        segments = new_segments
        iteration += 1

    # Step 6: Now check if we need to split any segments that are too heterogeneous
    # (e.g., merged segments with grade difference > threshold AND both are long)
    final_segments = []

    for seg in segments:
        # If segment is very long AND has high grade variance, might want to keep it
        # For now, accept all merged segments
        if seg['segment_length_m'] >= MIN_SEGMENT_LENGTH_M or len(final_segments) == 0:
            final_segments.append(seg)
        else:
            # Tiny segment: merge with previous if possible
            if final_segments and should_merge_segments(final_segments[-1], seg, aggressive=True):
                final_segments[-1] = merge_two_segments(final_segments[-1], seg, df)
            else:
                final_segments.append(seg)

    return final_segments


def test_segmentation():
    """Test smart segmentation."""

    print("=" * 70)
    print("Smart Variable-Length Segmentation")
    print("=" * 70)

    print(f"\nParameters:")
    print(f"  Terrain types: UPHILL, DOWNHILL, FLAT, ROLLING")
    print(f"  Min segment: {MIN_SEGMENT_LENGTH_M}m")
    print(f"  Uphill: D+ >= {UH_ELEVATION_THRESHOLD}m")
    print(f"  Downhill: D- >= {DH_ELEVATION_THRESHOLD}m")
    print(f"  Rolling: D+ and D- both > {ROLLING_ELEV_THRESHOLD}m")
    print(f"  Merge if grade diff < {MERGE_GRADE_DIFF_MAX}%")

    data_dir = Path("data/strava_cache/streams/2")
    activity_files = list(data_dir.glob("*.json"))[:5]

    for idx, activity_file in enumerate(activity_files):
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

            print(f"\nActivity: {df['time'].max()/60:.1f}min, "
                  f"{df['distance'].max()/1000:.2f}km, "
                  f"{len(df)} points")

            segments = segment_activity(df)

            print(f"\nSegments: {len(segments)}")
            print(f"\n{'#':>3s} {'Type':>8s} {'Length':>8s} {'Grade':>7s} "
                  f"{'D+':>6s} {'D-':>6s} {'Pace':>7s}")
            print("-" * 56)

            for i, seg in enumerate(segments):
                print(f"{i+1:3d} {seg['terrain_type']:>8s} "
                      f"{seg['segment_length_km']:>7.2f}km "
                      f"{seg['grade_mean']:>6.1f}% "
                      f"{seg['total_elevation_gain_m']:>5.0f}m "
                      f"{seg['total_elevation_loss_m']:>5.0f}m "
                      f"{seg['pace_min_per_km']:>6.2f}")

            # Stats
            terrain_counts = pd.Series([s['terrain_type'] for s in segments]).value_counts()
            print(f"\nTerrain distribution:")
            for terrain, count in terrain_counts.items():
                avg_len = np.mean([s['segment_length_km'] for s in segments if s['terrain_type'] == terrain])
                print(f"  {terrain:8s}: {count:2d} segs, avg {avg_len:.2f}km")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("Complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_segmentation()
