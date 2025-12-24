#!/usr/bin/env python3
"""Migration script to add cache table to existing database.

Run this after updating the code to add the StravaActivityCache model.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from database import db
from models import StravaActivityCache

def migrate():
    """Create cache table in existing database."""
    app = create_app()

    with app.app_context():
        print("Creating strava_activity_cache table...")

        try:
            db.create_all()
            print("✓ Migration complete!")
            print("  - strava_activity_cache table created")

        except Exception as e:
            print(f"✗ Migration failed: {e}")
            return 1

    return 0

if __name__ == '__main__':
    exit(migrate())
