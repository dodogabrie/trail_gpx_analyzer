"""Extrema-based segmentation (Garmin/Strava style).

Finds peaks and valleys in elevation profile, creates segments between them.

Run from backend directory:
    source venv/bin/activate
    python extrema_segmentation.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple
from scipy.signal import find_peaks, savgol_filter
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Parameters
ELEVATION_SMOOTHING_WINDOW = 51      # Savitzky-Golay filter window (must be odd)
ELEVATION_SMOOTHING_POLYORDER = 3    # Polynomial order for smoothing
MIN_PROMINENCE = 10                   # Minimum peak/valley prominence (meters)
MIN_SEGMENT_DISTANCE = 200           # Minimum segment distance (meters)
MIN_ELEVATION_CHANGE = 30            # Minimum elevation change to keep segment (meters)


def find_extrema(elevation: np.ndarray, distance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Find peaks and valleys in elevation profile.

    Args:
        elevation: Elevation array (meters)
        distance: Distance array (meters)

    Returns:
        (peak_indices, valley_indices)
    """
    # Smooth elevation to remove noise
    if len(elevation) < ELEVATION_SMOOTHING_WINDOW:
        elevation_smooth = elevation
    else:
        elevation_smooth = savgol_filter(
            elevation,
            window_length=ELEVATION_SMOOTHING_WINDOW,
            polyorder=ELEVATION_SMOOTHING_POLYORDER
        )

    # Find peaks (local maxima)
    peaks, peak_properties = find_peaks(
        elevation_smooth,
        prominence=MIN_PROMINENCE,
        distance=50  # Minimum distance between peaks (points)
    )

    # Find valleys (local minima) by inverting and finding peaks
    valleys, valley_properties = find_peaks(
        -elevation_smooth,
        prominence=MIN_PROMINENCE,
        distance=50
    )

    return peaks, valleys


def create_segments_from_extrema(
    df: pd.DataFrame,
    peaks: np.ndarray,
    valleys: np.ndarray
) -> List[Dict]:
    """Create segments from peaks and valleys.

    Strategy:
    1. Combine and sort all extrema
    2. Create segment between each consecutive pair
    3. Classify as uphill/downhill based on elevation change

    Args:
        df: Activity dataframe with distance, altitude, velocity, time
        peaks: Peak indices
        valleys: Valley indices

    Returns:
        List of segment dicts
    """
    # Combine extrema and sort by position
    all_extrema = []

    for idx in peaks:
        all_extrema.append({
            'index': idx,
            'type': 'peak',
            'elevation': df['altitude'].iloc[idx],
            'distance': df['distance'].iloc[idx]
        })

    for idx in valleys:
        all_extrema.append({
            'index': idx,
            'type': 'valley',
            'elevation': df['altitude'].iloc[idx],
            'distance': df['distance'].iloc[idx]
        })

    # Sort by index
    all_extrema.sort(key=lambda x: x['index'])

    # Add start and end points if needed
    if not all_extrema or all_extrema[0]['index'] > 10:
        all_extrema.insert(0, {
            'index': 0,
            'type': 'start',
            'elevation': df['altitude'].iloc[0],
            'distance': df['distance'].iloc[0]
        })

    if not all_extrema or all_extrema[-1]['index'] < len(df) - 10:
        all_extrema.append({
            'index': len(df) - 1,
            'type': 'end',
            'elevation': df['altitude'].iloc[-1],
            'distance': df['distance'].iloc[-1]
        })

    # Create segments between consecutive extrema
    segments = []

    for i in range(len(all_extrema) - 1):
        start_extremum = all_extrema[i]
        end_extremum = all_extrema[i + 1]

        # Extract segment data
        start_idx = start_extremum['index']
        end_idx = end_extremum['index']

        if end_idx - start_idx < 5:  # Too few points
            continue

        seg_df = df.iloc[start_idx:end_idx + 1]

        # Calculate segment features
        segment = extract_segment_features(seg_df, df)

        if segment is None:
            continue

        # Skip if too short or insignificant elevation change
        if (segment['segment_length_m'] < MIN_SEGMENT_DISTANCE or
            segment['abs_elevation_change'] < MIN_ELEVATION_CHANGE):
            continue

        # Add extrema info
        segment['start_type'] = start_extremum['type']
        segment['end_type'] = end_extremum['type']

        segments.append(segment)

    return segments


def extract_segment_features(seg_df: pd.DataFrame, full_df: pd.DataFrame) -> Dict:
    """Extract features from segment.

    Args:
        seg_df: Segment dataframe
        full_df: Full activity dataframe

    Returns:
        Feature dict or None if invalid
    """
    if len(seg_df) < 5:
        return None

    # Distance and length
    start_dist = seg_df['distance'].iloc[0]
    end_dist = seg_df['distance'].iloc[-1]
    segment_length_m = end_dist - start_dist

    if segment_length_m < 10:
        return None

    # Elevation change
    start_elev = seg_df['altitude'].iloc[0]
    end_elev = seg_df['altitude'].iloc[-1]
    net_elevation_change = end_elev - start_elev

    # Total D+ and D-
    elev_changes = np.diff(seg_df['altitude'].values)
    total_d_plus = float(np.sum(elev_changes[elev_changes > 0]))
    total_d_minus = float(np.abs(np.sum(elev_changes[elev_changes < 0])))

    # Classify terrain
    if net_elevation_change > 10 and total_d_plus > total_d_minus:
        terrain_type = 'uphill'
    elif net_elevation_change < -10 and total_d_minus > total_d_plus:
        terrain_type = 'downhill'
    elif total_d_plus > 30 and total_d_minus > 30:
        terrain_type = 'rolling'
    else:
        terrain_type = 'flat'

    # Grade
    grade_mean = (net_elevation_change / segment_length_m * 100) if segment_length_m > 0 else 0
    grade_values = seg_df['grade'].values if 'grade' in seg_df.columns else np.full(len(seg_df), grade_mean)
    grade_std = float(np.std(grade_values))

    # Velocity and pace
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
    if start_dist > 0:
        prior_df = full_df[full_df['distance'] < start_dist]
        if len(prior_df) > 1:
            prior_elev_changes = np.diff(prior_df['altitude'].values)
            cum_d_plus = float(np.sum(prior_elev_changes[prior_elev_changes > 0]))

    return {
        # Terrain type
        'terrain_type': terrain_type,

        # Segment metrics
        'segment_length_m': segment_length_m,
        'segment_length_km': segment_length_m / 1000,
        'duration_s': duration_s,

        # Elevation
        'net_elevation_change_m': net_elevation_change,
        'abs_elevation_change': abs(net_elevation_change),
        'total_elevation_gain_m': total_d_plus,
        'total_elevation_loss_m': total_d_minus,
        'start_elevation_m': start_elev,
        'end_elevation_m': end_elev,

        # Grade
        'grade_mean': grade_mean,
        'grade_std': grade_std,
        'abs_grade': abs(grade_mean),
        'grade_change': grade_values[-1] - grade_values[0] if len(grade_values) > 1 else 0.0,
        'elevation_gain_rate': (total_d_plus / segment_length_m * 1000) if segment_length_m > 0 else 0.0,
        'rolling_avg_grade_500m': grade_mean,

        # Performance
        'pace_min_per_km': pace_min_per_km,
        'velocity_m_s': velocity_mean,

        # Context
        'cum_distance_km': cum_distance_km,
        'distance_remaining_km': total_distance_km - cum_distance_km,
        'cum_elevation_gain_m': cum_d_plus,
        'prev_pace_ratio': 1.0,

        # Metadata
        'start_distance_m': start_dist,
        'end_distance_m': end_dist,
        'num_points': len(seg_df)
    }


def segment_activity(df: pd.DataFrame) -> List[Dict]:
    """Segment activity using extrema-based approach.

    Args:
        df: Activity dataframe with distance, altitude, velocity, time, grade

    Returns:
        List of segment dicts
    """
    if len(df) < 100:
        return []

    # Find peaks and valleys
    peaks, valleys = find_extrema(
        df['altitude'].values,
        df['distance'].values
    )

    print(f"  Found {len(peaks)} peaks, {len(valleys)} valleys")

    # Create segments
    segments = create_segments_from_extrema(df, peaks, valleys)

    return segments


def plot_segmentation(df: pd.DataFrame, segments: List[Dict], peaks: np.ndarray, valleys: np.ndarray, activity_name: str):
    """Plot elevation profile with segmentation.

    Args:
        df: Activity dataframe
        segments: List of segment dicts
        peaks: Peak indices
        valleys: Valley indices
        activity_name: Name for plot title
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    distance_km = df['distance'].values / 1000
    elevation = df['altitude'].values

    # Plot elevation profile
    ax.plot(distance_km, elevation, 'k-', linewidth=1, alpha=0.3, label='Elevation')

    # Color segments
    colors = {
        'uphill': '#d62728',      # Red
        'downhill': '#2ca02c',    # Green
        'flat': '#7f7f7f',        # Gray
        'rolling': '#ff7f0e'      # Orange
    }

    for seg in segments:
        start_idx = np.searchsorted(df['distance'].values, seg['start_distance_m'])
        end_idx = np.searchsorted(df['distance'].values, seg['end_distance_m'])

        seg_dist = distance_km[start_idx:end_idx+1]
        seg_elev = elevation[start_idx:end_idx+1]

        color = colors.get(seg['terrain_type'], 'gray')
        ax.plot(seg_dist, seg_elev, color=color, linewidth=3, alpha=0.7)

    # Mark peaks and valleys
    if len(peaks) > 0:
        ax.scatter(distance_km[peaks], elevation[peaks],
                  c='red', s=100, marker='^', zorder=5,
                  edgecolors='darkred', linewidths=2, label='Peaks')

    if len(valleys) > 0:
        ax.scatter(distance_km[valleys], elevation[valleys],
                  c='blue', s=100, marker='v', zorder=5,
                  edgecolors='darkblue', linewidths=2, label='Valleys')

    # Labels and formatting
    ax.set_xlabel('Distance (km)', fontsize=12)
    ax.set_ylabel('Elevation (m)', fontsize=12)
    ax.set_title(f'Extrema-Based Segmentation: {activity_name}', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)

    # Legend for terrain types
    legend_elements = [
        mpatches.Patch(color=colors['uphill'], label='Uphill'),
        mpatches.Patch(color=colors['downhill'], label='Downhill'),
        mpatches.Patch(color=colors['rolling'], label='Rolling'),
        mpatches.Patch(color=colors['flat'], label='Flat'),
        plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='red',
                   markersize=10, label='Peaks', markeredgecolor='darkred', markeredgewidth=2),
        plt.Line2D([0], [0], marker='v', color='w', markerfacecolor='blue',
                   markersize=10, label='Valleys', markeredgecolor='darkblue', markeredgewidth=2)
    ]

    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)

    plt.tight_layout()

    # Save plot
    output_file = f"segmentation_{activity_name}.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"  Plot saved: {output_file}")

    plt.close()


def test_segmentation():
    """Test extrema-based segmentation."""

    print("=" * 70)
    print("Extrema-Based Segmentation (Garmin/Strava Style)")
    print("=" * 70)

    print(f"\nParameters:")
    print(f"  Min prominence: {MIN_PROMINENCE}m")
    print(f"  Min segment distance: {MIN_SEGMENT_DISTANCE}m")
    print(f"  Min elevation change: {MIN_ELEVATION_CHANGE}m")

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
                  f"{np.diff(df['altitude']).clip(min=0).sum():.0f}m D+")

            # Find extrema
            peaks, valleys = find_extrema(
                df['altitude'].values,
                df['distance'].values
            )

            # Create segments
            segments = create_segments_from_extrema(df, peaks, valleys)

            print(f"\nSegments: {len(segments)}\n")
            print(f"{'#':>3s} {'Type':>8s} {'Length':>8s} {'Net Δ':>8s} "
                  f"{'D+':>6s} {'D-':>6s} {'Grade':>7s} {'Pace':>7s}")
            print("-" * 70)

            for i, seg in enumerate(segments):
                print(f"{i+1:3d} {seg['terrain_type']:>8s} "
                      f"{seg['segment_length_km']:>7.2f}km "
                      f"{seg['net_elevation_change_m']:>7.0f}m "
                      f"{seg['total_elevation_gain_m']:>5.0f}m "
                      f"{seg['total_elevation_loss_m']:>5.0f}m "
                      f"{seg['grade_mean']:>6.1f}% "
                      f"{seg['pace_min_per_km']:>6.2f}")

            # Stats
            terrain_counts = pd.Series([s['terrain_type'] for s in segments]).value_counts()
            print(f"\nTerrain distribution:")
            for terrain, count in terrain_counts.items():
                total_dist = sum(s['segment_length_km'] for s in segments if s['terrain_type'] == terrain)
                print(f"  {terrain:8s}: {count:2d} segments, {total_dist:.2f}km total")

            # Plot
            plot_segmentation(df, segments, peaks, valleys, activity_file.stem)

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("Complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_segmentation()
