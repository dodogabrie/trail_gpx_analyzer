#!/usr/bin/env python3
"""Migration script to add performance tracking tables to existing database.

Run this after updating the code to add the PerformanceSnapshot,
GradePerformanceHistory, and UserAchievement models.

This enables:
- Historical performance tracking over time
- Grade-specific performance analysis
- Gamification with achievements
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from database import db
from models import PerformanceSnapshot, GradePerformanceHistory, UserAchievement


def migrate():
    """Create performance tracking tables in existing database."""
    app = create_app()

    with app.app_context():
        print("Creating performance tracking tables...")
        print()

        try:
            # Create all tables (will skip existing ones)
            db.create_all()

            print("✓ Migration complete!")
            print()
            print("Created tables:")
            print("  - performance_snapshots")
            print("    Stores weekly/monthly performance calibrations")
            print()
            print("  - grade_performance_history")
            print("    Stores detailed pace stats for each grade bucket")
            print()
            print("  - user_achievements")
            print("    Stores earned badges and milestones")
            print()
            print("Next steps:")
            print("  1. Use PerformanceTracker service to calculate snapshots")
            print("  2. Set up weekly cron job to auto-calculate snapshots")
            print("  3. Use achievement detection to award badges")
            print()

        except Exception as e:
            print(f"✗ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return 1

    return 0


if __name__ == '__main__':
    exit(migrate())
