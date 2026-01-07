"""Activity segmentation service using extrema-based approach.

Finds peaks and valleys in elevation profile to create natural segments.
Replaces fixed-distance segmentation with terrain-aware variable-length segments.
"""

import numpy as np
from typing import List, Dict, Tuple
from scipy.signal import find_peaks, savgol_filter

from config.hybrid_config import get_logger

logger = get_logger(__name__)

# Segmentation parameters
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
    peaks, _ = find_peaks(
        elevation_smooth,
        prominence=MIN_PROMINENCE,
        distance=50  # Minimum distance between peaks (points)
    )

    # Find valleys (local minima) by inverting and finding peaks
    valleys, _ = find_peaks(
        -elevation_smooth,
        prominence=MIN_PROMINENCE,
        distance=50
    )

    return peaks, valleys


def segment_activity_by_extrema(streams: Dict) -> List[Dict]:
    """Segment activity using extrema-based approach (Garmin/Strava style).

    Finds peaks and valleys in elevation, creates segments between them.
    Each segment represents a natural terrain feature (climb, descent, etc.).

    Args:
        streams: Activity streams dict with keys:
            - distance: Distance array (meters)
            - altitude: Elevation array (meters)
            - velocity_smooth: Velocity array (m/s)
            - grade_smooth: Grade array (%)
            - time: Time array (seconds)

    Returns:
        List of segment dicts with features compatible with ML model
    """
    distances = np.array(streams['distance'])
    altitudes = np.array(streams['altitude'])
    velocities = np.array(streams.get('velocity_smooth', []))
    grades = np.array(streams.get('grade_smooth', []))
    times = np.array(streams.get('time', []))
    heartrates = np.array(streams.get('heartrate', []))

    if len(distances) < 100 or len(velocities) == 0:
        logger.warning("Insufficient data for segmentation")
        return []

    # Find peaks and valleys
    peaks, valleys = find_extrema(altitudes, distances)

    logger.debug(f"Found {len(peaks)} peaks, {len(valleys)} valleys")

    # Combine and sort all extrema
    all_extrema = []

    for idx in peaks:
        all_extrema.append({
            'index': idx,
            'type': 'peak',
            'elevation': altitudes[idx],
            'distance': distances[idx]
        })

    for idx in valleys:
        all_extrema.append({
            'index': idx,
            'type': 'valley',
            'elevation': altitudes[idx],
            'distance': distances[idx]
        })

    # Sort by position
    all_extrema.sort(key=lambda x: x['index'])

    # Add start/end if needed
    if not all_extrema or all_extrema[0]['index'] > 10:
        all_extrema.insert(0, {
            'index': 0,
            'type': 'start',
            'elevation': altitudes[0],
            'distance': distances[0]
        })

    if not all_extrema or all_extrema[-1]['index'] < len(distances) - 10:
        all_extrema.append({
            'index': len(distances) - 1,
            'type': 'end',
            'elevation': altitudes[-1],
            'distance': distances[-1]
        })

    # Create segments between consecutive extrema
    segments = []

    for i in range(len(all_extrema) - 1):
        start_extremum = all_extrema[i]
        end_extremum = all_extrema[i + 1]

        start_idx = start_extremum['index']
        end_idx = end_extremum['index']

        if end_idx - start_idx < 5:
            continue

        # Extract segment data
        seg_distances = distances[start_idx:end_idx + 1]
        seg_altitudes = altitudes[start_idx:end_idx + 1]
        seg_velocities = velocities[start_idx:end_idx + 1]
        seg_grades = grades[start_idx:end_idx + 1] if len(grades) > 0 else np.zeros(end_idx - start_idx + 1)
        seg_times = times[start_idx:end_idx + 1] if len(times) > 0 else np.arange(end_idx - start_idx + 1)
        seg_heartrates = heartrates[start_idx:end_idx + 1] if len(heartrates) > 0 else np.array([])

        # Calculate segment metrics
        segment_length_m = seg_distances[-1] - seg_distances[0]
        net_elevation_change = seg_altitudes[-1] - seg_altitudes[0]

        # Skip if too short or insignificant
        if (segment_length_m < MIN_SEGMENT_DISTANCE or
            abs(net_elevation_change) < MIN_ELEVATION_CHANGE):
            continue

        # Total D+ and D-
        elev_changes = np.diff(seg_altitudes)
        total_d_plus = float(np.sum(elev_changes[elev_changes > 0]))
        total_d_minus = float(np.abs(np.sum(elev_changes[elev_changes < 0])))

        # Average velocity and pace
        velocity_mean = float(np.mean(seg_velocities))

        if velocity_mean <= 0:
            continue

        pace_min_per_km = 60.0 / (velocity_mean * 3.6)

        # Grade metrics
        grade_mean = (net_elevation_change / segment_length_m * 100) if segment_length_m > 0 else 0
        grade_std = float(np.std(seg_grades)) if len(seg_grades) > 0 else 0.0

        # Heartrate metrics
        hr_mean = None
        if len(seg_heartrates) > 0:
            # Filter out zeros and invalid values
            valid_hr = seg_heartrates[(seg_heartrates > 0) & (seg_heartrates < 220)]
            if len(valid_hr) > 0:
                hr_mean = float(np.mean(valid_hr))

        # Build segment dict (compatible with existing ML features)
        segment = {
            # Distance/position
            'distance_m': float(seg_distances[0]),
            'length_m': float(segment_length_m),

            # Grade features
            'grade_mean': float(grade_mean),
            'grade_std': grade_std,

            # Performance
            'actual_pace_min_km': pace_min_per_km,

            # Heartrate (effort indicator)
            'avg_heartrate': hr_mean,

            # Elevation
            'elevation_gain': total_d_plus,
            'elevation_loss': total_d_minus,
            'net_elevation_change': float(net_elevation_change),

            # Metadata for debugging
            'start_idx': start_idx,
            'end_idx': end_idx,
            'num_points': end_idx - start_idx
        }

        segments.append(segment)

    logger.info(f"Created {len(segments)} segments using extrema-based approach")

    return segments
