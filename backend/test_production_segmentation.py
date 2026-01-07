"""Test production segmentation integration.

Verifies that extrema-based segmentation works with production code.

Run from backend directory:
    source venv/bin/activate
    python test_production_segmentation.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import numpy as np
from pathlib import Path

print("=" * 70)
print("Testing Production Segmentation Integration")
print("=" * 70)

# Test 1: Import new service
print("\n[1] Testing imports...")
try:
    from services.segmentation_service import segment_activity_by_extrema
    print("  ✓ segmentation_service imported")
except Exception as e:
    print(f"  ✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Load sample activity
print("\n[2] Loading sample activity...")
data_dir = Path("data/strava_cache/streams/2")
activity_files = list(data_dir.glob("*.json"))

if not activity_files:
    print("  ✗ No activity files found")
    sys.exit(1)

activity_file = activity_files[3]  # Use 4th activity
print(f"  ✓ Loaded: {activity_file.name}")

with open(activity_file) as f:
    activity_data = json.load(f)

# Convert to streams format
streams = {
    'distance': activity_data['distance'],
    'altitude': activity_data['altitude'],
    'velocity_smooth': activity_data['velocity_smooth'],
    'grade_smooth': activity_data['grade_smooth'],
    'time': activity_data['time']
}

print(f"  ✓ Activity: {len(streams['distance'])} points, "
      f"{streams['distance'][-1]/1000:.2f}km")

# Test 3: Run segmentation
print("\n[3] Running extrema-based segmentation...")
try:
    segments = segment_activity_by_extrema(streams)
    print(f"  ✓ Created {len(segments)} segments")
except Exception as e:
    print(f"  ✗ Segmentation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Verify segment structure
print("\n[4] Verifying segment features...")
required_keys = [
    'distance_m', 'length_m', 'grade_mean', 'grade_std',
    'actual_pace_min_km', 'elevation_gain'
]

if not segments:
    print("  ✗ No segments created")
    sys.exit(1)

first_seg = segments[0]
missing_keys = [key for key in required_keys if key not in first_seg]

if missing_keys:
    print(f"  ✗ Missing keys: {missing_keys}")
    print(f"  Available keys: {list(first_seg.keys())}")
    sys.exit(1)
else:
    print(f"  ✓ All required keys present")

# Test 5: Display sample segments
print("\n[5] Sample segments:")
print(f"\n{'#':>3s} {'Dist':>8s} {'Length':>8s} {'Grade':>8s} "
      f"{'D+':>6s} {'Pace':>8s}")
print("-" * 50)

for i, seg in enumerate(segments[:10]):
    print(f"{i+1:3d} {seg['distance_m']/1000:>7.2f}km "
          f"{seg['length_m']:>7.0f}m "
          f"{seg['grade_mean']:>7.1f}% "
          f"{seg['elevation_gain']:>5.0f}m "
          f"{seg['actual_pace_min_km']:>7.2f}")

if len(segments) > 10:
    print(f"... and {len(segments) - 10} more segments")

# Test 6: Compare with old segmentation
print("\n[6] Comparing with fixed 200m segmentation...")

# Simulate old method
old_segment_count = int(streams['distance'][-1] / 200)
print(f"  Old method (200m fixed): ~{old_segment_count} segments")
print(f"  New method (extrema):     {len(segments)} segments")
print(f"  Reduction: {(1 - len(segments)/old_segment_count)*100:.1f}%")

# Test 7: Statistics
print("\n[7] Segment statistics:")
lengths = [s['length_m'] for s in segments]
grades = [s['grade_mean'] for s in segments]
d_plus_values = [s['elevation_gain'] for s in segments]

print(f"  Segment length: {min(lengths):.0f}m - {max(lengths):.0f}m "
      f"(avg {np.mean(lengths):.0f}m)")
print(f"  Grade range: {min(grades):.1f}% - {max(grades):.1f}% "
      f"(avg {np.mean(grades):.1f}%)")
print(f"  Total D+: {sum(d_plus_values):.0f}m")

print("\n" + "=" * 70)
print("✓ All tests passed! Production integration successful.")
print("=" * 70)

print("\nNext steps:")
print("  1. Test with full app: python app.py")
print("  2. Monitor logs for 'extrema-based approach'")
print("  3. Verify predictions still work")
print("  4. Compare GBM performance with new segmentation")
