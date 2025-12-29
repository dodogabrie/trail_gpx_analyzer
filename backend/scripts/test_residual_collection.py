#!/usr/bin/env python3
"""Test script for residual collection from real activities.

Tests the UserResidualService by collecting residuals from existing
StravaActivity records in the database.

Usage:
    python scripts/test_residual_collection.py [--user-id USER_ID] [--limit N]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db
from models import User, StravaActivity, UserActivityResidual
from services.user_residual_service import UserResidualService
import argparse


def test_residual_collection(user_id=None, limit=5):
    """Test residual collection on existing activities.

    Args:
        user_id: Specific user ID to test (default: first user)
        limit: Maximum number of activities to process
    """
    app = create_app()

    with app.app_context():
        # Get user
        if user_id:
            user = User.query.get(user_id)
        else:
            user = User.query.first()

        if not user:
            print("❌ No user found in database")
            return

        print(f"Testing residual collection for user: {user.email} (ID: {user.id})")
        print("=" * 60)

        # Get activities with streams
        activities = (
            StravaActivity.query
            .filter_by(user_id=user.id)
            .filter(StravaActivity._streams.isnot(None))
            .order_by(StravaActivity.start_date.desc())
            .limit(limit)
            .all()
        )

        if not activities:
            print("❌ No activities with streams found")
            return

        print(f"Found {len(activities)} activities with streams\n")

        # Test residual collection
        residual_service = UserResidualService()
        success_count = 0
        fail_count = 0

        for i, activity in enumerate(activities, 1):
            print(f"\n[{i}/{len(activities)}] Activity {activity.strava_id}: {activity.name}")
            print(f"  Date: {activity.start_date}")
            print(f"  Distance: {activity.distance / 1000:.1f} km")

            try:
                # Check if residual already exists
                existing = UserActivityResidual.query.filter_by(
                    user_id=user.id,
                    activity_id=str(activity.strava_id)
                ).first()

                if existing:
                    print(f"  ⚠️  Residual already exists ({existing.segment_count} segments)")
                    print(f"  Deleting and recreating...")
                    db.session.delete(existing)
                    db.session.commit()

                # Collect residuals
                residual = residual_service.collect_residuals_from_activity(
                    user_id=user.id,
                    activity_id=str(activity.strava_id),
                    activity_streams=activity.streams,
                    activity_metadata={
                        'start_date': activity.start_date.isoformat(),
                        'type': 'Run',
                        'distance': activity.distance
                    }
                )

                if residual:
                    print(f"  ✓ Collected {residual.segment_count} segments")
                    print(f"    Recency weight: {residual.recency_weight:.3f}")
                    print(f"    Days ago: {residual.days_ago}")

                    # Show sample residuals
                    if residual.segments and len(residual.segments) > 0:
                        sample = residual.segments[0]
                        print(f"    Sample segment:")
                        print(f"      Grade: {sample['grade_mean']:.2f}%")
                        print(f"      Physics pace ratio: {sample['physics_pace_ratio']:.3f}")
                        print(f"      Actual pace ratio: {sample['actual_pace_ratio']:.3f}")
                        print(f"      Residual: {sample['residual']:.3f}")

                    success_count += 1
                else:
                    print(f"  ❌ Failed to collect residuals")
                    fail_count += 1

            except Exception as e:
                print(f"  ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                fail_count += 1

        # Summary
        print("\n" + "=" * 60)
        print(f"SUMMARY:")
        print(f"  Success: {success_count}/{len(activities)}")
        print(f"  Failed: {fail_count}/{len(activities)}")

        # Check total residuals for user
        total_residuals = UserActivityResidual.query.filter_by(user_id=user.id).count()
        total_segments = residual_service.get_training_segment_count(user.id)

        print(f"\nUser training data:")
        print(f"  Total activities with residuals: {total_residuals}")
        print(f"  Total training segments: {total_segments}")

        if total_residuals >= 5:
            print(f"\n✓ User has enough data for Tier 2 (Parameter Learning)")
        if total_residuals >= 15:
            print(f"✓ User has enough data for Tier 3 (Residual ML)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test residual collection')
    parser.add_argument('--user-id', type=int, help='User ID to test')
    parser.add_argument('--limit', type=int, default=5, help='Max activities to process')

    args = parser.parse_args()

    test_residual_collection(user_id=args.user_id, limit=args.limit)
