import pandas as pd
import numpy as np

def calculate_segment_stats(points, start_index, end_index, threshold=1.0):
    """Calculate statistics for a selected segment.

    Args:
        points: List of point dictionaries
        start_index: Start index
        end_index: End index
        threshold: Minimum elevation change to count (meters), filters GPS noise
    """
    if start_index < 0 or end_index >= len(points) or start_index >= end_index:
        raise ValueError('Invalid index range')

    segment_points = points[start_index:end_index+1]
    df = pd.DataFrame(segment_points)

    # Smooth elevation with rolling average to reduce GPS noise
    window = min(5, len(df))
    df['elevation_smooth'] = df['elevation'].rolling(window=window, center=True, min_periods=1).mean()

    # Calculate D+/D- with threshold
    d_plus = 0
    d_minus = 0

    for i in range(1, len(df)):
        delta = df['elevation_smooth'].iloc[i] - df['elevation_smooth'].iloc[i-1]
        if delta > threshold:
            d_plus += delta
        elif delta < -threshold:
            d_minus += -delta

    total_distance = df['distance'].iloc[-1] - df['distance'].iloc[0]

    return {
        'distance': round(total_distance, 2),
        'elevation_gain': round(d_plus, 2),
        'elevation_loss': round(d_minus, 2),
        'start_index': start_index,
        'end_index': end_index
    }

def filter_points_by_distance(points, start_distance, end_distance):
    """Filter points by distance range."""
    return [p for p in points if start_distance <= p['distance'] <= end_distance]
