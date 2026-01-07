"""Recollect residuals with new extrema-based segmentation.

Clears old residuals and re-extracts with new segmentation approach.

Run from backend directory:
    source venv/bin/activate
    python recollect_residuals.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from database import db
from models import UserActivityResidual, StravaActivity
from services.user_residual_service import UserResidualService

print("=" * 70)
print("Recollecting Residuals with New Segmentation")
print("=" * 70)

# Initialize Flask app context - use actual config
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    USER_ID = 2  # Change if needed

    # Step 1: Count old residuals
    print(f"\n[1] Checking existing residuals for user {USER_ID}...")
    old_residuals = UserActivityResidual.query.filter_by(user_id=USER_ID).all()
    print(f"  Found {len(old_residuals)} existing residual records")

    if old_residuals:
        # Count segments from residual data
        old_segment_count = sum(len(r.segments) if r.segments else 0 for r in old_residuals)
        print(f"  Total segments (old): {old_segment_count}")

    # Step 2: Confirm deletion
    if old_residuals:
        print(f"\n[2] This will DELETE {len(old_residuals)} residual records")
        response = input("  Continue? (yes/no): ")

        if response.lower() != 'yes':
            print("  Aborted.")
            sys.exit(0)

        # Delete old residuals
        print(f"  Deleting old residuals...")
        UserActivityResidual.query.filter_by(user_id=USER_ID).delete()
        db.session.commit()
        print(f"  ✓ Deleted {len(old_residuals)} records")
    else:
        print("\n[2] No existing residuals to delete")

    # Step 3: Get user's Strava activities
    print(f"\n[3] Finding Strava activities for user {USER_ID}...")
    activities = (
        StravaActivity.query
        .filter_by(user_id=USER_ID)
        .order_by(StravaActivity.start_date.desc())
        .all()
    )

    print(f"  Found {len(activities)} activities")

    if not activities:
        print("  No activities found. Exiting.")
        sys.exit(0)

    # Step 4: Re-collect residuals with new segmentation
    print(f"\n[4] Re-collecting residuals with NEW extrema-based segmentation...")
    print(f"  This may take a few minutes...")

    service = UserResidualService()
    success_count = 0
    total_segments = 0

    for i, activity in enumerate(activities):
        try:
            # Collect residuals for this activity
            residual = service.collect_residuals_from_activity(
                user_id=USER_ID,
                activity_id=activity.strava_id
            )

            if residual:
                success_count += 1
                total_segments += len(residual.segments) if residual.segments else 0

                if (i + 1) % 10 == 0:
                    print(f"  Processed {i+1}/{len(activities)} activities, "
                          f"{total_segments} segments so far...")
        except Exception as e:
            print(f"  Warning: Failed to process activity {activity.strava_id}: {e}")
            continue

    print(f"\n  ✓ Successfully processed {success_count}/{len(activities)} activities")
    print(f"  ✓ Total segments collected: {total_segments}")

    # Step 5: Summary
    print(f"\n[5] Summary:")
    new_residuals = UserActivityResidual.query.filter_by(user_id=USER_ID).all()
    print(f"  New residual records: {len(new_residuals)}")
    print(f"  Total segments: {total_segments}")

    if len(old_residuals) > 0:
        print(f"\n  Comparison:")
        print(f"    OLD: {old_segment_count} segments from {len(old_residuals)} activities "
              f"(~{old_segment_count/len(old_residuals):.0f} seg/activity)")
        print(f"    NEW: {total_segments} segments from {len(new_residuals)} activities "
              f"(~{total_segments/len(new_residuals):.0f} seg/activity)")

        reduction = (1 - total_segments/old_segment_count) * 100 if old_segment_count > 0 else 0
        print(f"    Reduction: {reduction:.1f}%")

    print("\n" + "=" * 70)
    print("✓ Re-collection complete!")
    print("=" * 70)

    print("\nNext steps:")
    print("  1. Retrain GBM model with new segments")
    print("  2. Or trigger training via sync/login")
