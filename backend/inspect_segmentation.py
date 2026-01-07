"""Inspect how activities are segmented.

Shows detailed segmentation breakdown per activity.

Run from backend directory:
    source venv/bin/activate
    python inspect_segmentation.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import numpy as np
import pandas as pd
from pathlib import Path

print("=" * 70)
print("Activity Segmentation Inspector")
print("=" * 70)

data_dir = Path("data/strava_cache/streams/2")
activity_files = list(data_dir.glob("*.json"))

print(f"\nFound {len(activity_files)} activity files")

segment_duration = 100  # seconds per segment

# Process activities and track segments per activity
activity_stats = []
total_segments = 0
activities_processed = 0

print(f"\nSegmentation: {segment_duration} seconds per segment")
print("\n" + "-" * 70)

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
            print(f"{idx+1:2d}. {activity_file.name[:15]:15s} SKIPPED (too short: {len(df)} points)")
            continue

        duration_min = df['time'].max() / 60
        distance_km = df['distance'].max() / 1000
        total_distance = df['distance'].max()

        # Count segments
        segment_count = 0
        segments_detail = []

        for i in range(0, int(df['time'].max()), segment_duration):
            segment = df[(df['time'] >= i) & (df['time'] < i + segment_duration)]

            if len(segment) < 20:
                continue

            velocity_values = segment['velocity'].values
            if velocity_values.mean() < 0.5:  # Skip stopped segments
                continue

            segment_count += 1
            segments_detail.append({
                'start_time': i,
                'end_time': min(i + segment_duration, df['time'].max()),
                'points': len(segment),
                'avg_velocity': velocity_values.mean(),
                'avg_grade': segment['grade'].mean()
            })

        if segment_count > 0:
            activities_processed += 1
            total_segments += segment_count

            activity_stats.append({
                'file': activity_file.name,
                'duration_min': duration_min,
                'distance_km': distance_km,
                'points': len(df),
                'segments': segment_count,
                'segments_detail': segments_detail
            })

            print(f"{idx+1:2d}. {activity_file.name[:15]:15s} | "
                  f"{duration_min:5.1f}min | {distance_km:5.2f}km | "
                  f"{len(df):4d} pts | {segment_count:3d} segments")

    except Exception as e:
        print(f"{idx+1:2d}. {activity_file.name[:15]:15s} ERROR: {str(e)[:40]}")
        continue

print("\n" + "=" * 70)
print(f"Summary: {activities_processed} activities processed, {total_segments} total segments")
print(f"Average: {total_segments/activities_processed:.1f} segments per activity")
print("=" * 70)

# Show detailed segmentation for first activity
if activity_stats:
    print("\n" + "-" * 70)
    print("Detailed view of first activity:")
    print("-" * 70)

    first = activity_stats[0]
    print(f"\nFile: {first['file']}")
    print(f"Duration: {first['duration_min']:.1f} minutes")
    print(f"Distance: {first['distance_km']:.2f} km")
    print(f"Data points: {first['points']}")
    print(f"Segments created: {first['segments']}")

    print(f"\n{'Seg':>3s} {'Time Range':>15s} {'Duration':>10s} {'Points':>8s} {'Velocity':>10s} {'Grade':>8s}")
    print("-" * 70)

    for i, seg in enumerate(first['segments_detail'][:20]):  # Show first 20 segments
        time_range = f"{seg['start_time']}-{seg['end_time']}s"
        duration = seg['end_time'] - seg['start_time']
        print(f"{i+1:3d} {time_range:>15s} {duration:10.0f}s {seg['points']:8d} "
              f"{seg['avg_velocity']:10.2f} m/s {seg['avg_grade']:8.1f}%")

    if len(first['segments_detail']) > 20:
        print(f"... and {len(first['segments_detail']) - 20} more segments")

# Show distribution
print("\n" + "-" * 70)
print("Segments per activity distribution:")
print("-" * 70)

segments_per_activity = [a['segments'] for a in activity_stats]
print(f"Min:    {min(segments_per_activity)} segments")
print(f"Max:    {max(segments_per_activity)} segments")
print(f"Mean:   {np.mean(segments_per_activity):.1f} segments")
print(f"Median: {np.median(segments_per_activity):.1f} segments")

# Show histogram
print("\nHistogram:")
bins = [0, 10, 20, 30, 40, 50, 100, 200]
for i in range(len(bins)-1):
    count = sum(1 for s in segments_per_activity if bins[i] <= s < bins[i+1])
    bar = '█' * count
    print(f"{bins[i]:3d}-{bins[i+1]:3d} segments: {count:3d} activities {bar}")

print("\n" + "=" * 70)
print(f"Train/Test Split Calculation:")
print("=" * 70)
print(f"Total segments: {total_segments}")
print(f"Train (80%):    {int(total_segments * 0.8)}")
print(f"Test (20%):     {int(total_segments * 0.2)}")
print("\nIf you expected more, possible reasons:")
print("  - Segments with avg velocity < 0.5 m/s are filtered (stopped)")
print("  - Segments with < 20 data points are filtered")
print("  - Activities with < 50 points are skipped")
print("  - Some activity files had parsing errors")
