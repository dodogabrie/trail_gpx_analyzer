"""Test script to verify PredictionService loads correctly.

Run from backend directory:
    source venv/bin/activate
    python test_prediction_service.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing PredictionService initialization...")
print("-" * 50)

try:
    from services.prediction_service import PredictionService
    print("✓ Import successful")

    print("\nInitializing service (this may take 5-30 seconds)...")
    service = PredictionService()
    print("✓ Service initialized")

    print(f"\n✓ Global curve loaded: {len(service.global_curve)} grade bins")
    print(f"✓ ML model loaded: {service.model is not None}")

    # Test basic prediction
    print("\nTesting with sample data...")
    test_gpx = {
        'points': [
            {'elevation': 100, 'distance': 0},
            {'elevation': 105, 'distance': 100},
            {'elevation': 110, 'distance': 200},
            {'elevation': 108, 'distance': 300},
            {'elevation': 112, 'distance': 400},
            {'elevation': 115, 'distance': 500},
            {'elevation': 113, 'distance': 600},
            {'elevation': 116, 'distance': 700},
            {'elevation': 120, 'distance': 800},
            {'elevation': 118, 'distance': 900},
            {'elevation': 122, 'distance': 1000},
        ],
        'total_distance': 1000
    }

    profile = service.gpx_to_route_profile(test_gpx)
    print(f"✓ GPX conversion: {len(profile)} segments")

    result = service.predict_route_time(test_gpx, 5.0)
    print(f"✓ Prediction successful: {result['total_time_formatted']}")

    print("\n" + "=" * 50)
    print("✓ All tests passed! Service is ready.")
    print("=" * 50)

except FileNotFoundError as e:
    print(f"\n✗ ERROR: {e}")
    print("\nTo fix:")
    print("  1. Train ML model: python ../data_analysis/predictor/train.py")
    print("  2. Cache global curve: python scripts/cache_global_curve.py")
    sys.exit(1)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
