#!/usr/bin/env python3
"""Test script to verify backend setup is correct."""

print("Testing backend imports...")

try:
    from database import db
    print("✓ database.db imported")
except Exception as e:
    print(f"✗ database.db failed: {e}")

try:
    from models import User, GPXFile, StravaActivity
    print("✓ models imported")
except Exception as e:
    print(f"✗ models failed: {e}")

try:
    from services.gpx_parser import parse_gpx_file
    from services.data_processor import process_gpx_data
    from services.stats_service import calculate_segment_stats
    from services.strava_service import StravaService
    print("✓ services imported")
except Exception as e:
    print(f"✗ services failed: {e}")

try:
    from api import auth, gpx, strava, analysis
    print("✓ API endpoints imported")
except Exception as e:
    print(f"✗ API endpoints failed: {e}")

try:
    from app import create_app
    app = create_app()
    print(f"✓ Flask app created")
    print(f"✓ Registered blueprints: {[bp.name for bp in app.blueprints.values()]}")
except Exception as e:
    print(f"✗ Flask app failed: {e}")

print("\n=== Backend setup complete! ===")
print("\nNext steps:")
print("1. Create .env file: cp .env.example .env")
print("2. Edit .env with your Strava credentials")
print("3. Run: python app.py")
print("4. Test: curl http://localhost:5000/api/health")
