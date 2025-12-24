"""Cache service for Strava data.

Handles caching of:
- Activity streams (DB + filesystem JSON)
- Activity lists (DB only)
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import StravaActivity, StravaActivityCache
from database import db
from datetime import datetime
import json


class CacheService:
    """Service for managing Strava data cache."""

    def __init__(self, cache_dir='data/strava_cache'):
        """Initialize cache service.

        Args:
            cache_dir: Directory for filesystem cache
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.streams_dir = self.cache_dir / 'streams'
        self.streams_dir.mkdir(exist_ok=True)

    def get_stream_cache_path(self, user_id, activity_id):
        """Get filesystem path for activity stream cache.

        Args:
            user_id: User ID
            activity_id: Strava activity ID

        Returns:
            Path object for the cache file
        """
        user_dir = self.streams_dir / str(user_id)
        user_dir.mkdir(exist_ok=True)
        return user_dir / f'{activity_id}.json'

    def get_cached_streams(self, user_id, activity_id):
        """Get cached streams for an activity.

        Checks both DB and filesystem. Returns None if not found.

        Args:
            user_id: User ID
            activity_id: Strava activity ID

        Returns:
            Streams dict or None if not cached
        """
        # Check database first
        db_activity = StravaActivity.query.filter_by(
            user_id=user_id,
            strava_id=activity_id
        ).first()

        if db_activity and db_activity.streams:
            print(f"✓ Found streams in DB for activity {activity_id}")
            return db_activity.streams

        # Check filesystem
        cache_path = self.get_stream_cache_path(user_id, activity_id)
        if cache_path.exists():
            print(f"✓ Found streams in filesystem for activity {activity_id}")
            with open(cache_path, 'r') as f:
                streams = json.load(f)

            # Store in DB for faster access next time
            if db_activity:
                db_activity.streams = streams
                db.session.commit()
            else:
                print(f"⚠️ Warning: Filesystem cache exists but no DB entry for activity {activity_id}")

            return streams

        print(f"✗ No cached streams for activity {activity_id}")
        return None

    def cache_streams(self, user_id, activity_id, activity_name, distance, start_date, streams):
        """Cache activity streams in both DB and filesystem.

        Args:
            user_id: User ID
            activity_id: Strava activity ID
            activity_name: Activity name
            distance: Activity distance in meters
            start_date: Activity start date (datetime)
            streams: Streams dict

        Returns:
            StravaActivity object
        """
        # Save to filesystem
        cache_path = self.get_stream_cache_path(user_id, activity_id)
        with open(cache_path, 'w') as f:
            json.dump(streams, f)
        print(f"✓ Saved streams to filesystem: {cache_path}")

        # Save to database
        db_activity = StravaActivity.query.filter_by(
            user_id=user_id,
            strava_id=activity_id
        ).first()

        if db_activity:
            # Update existing
            db_activity.streams = streams
            db_activity.downloaded_at = datetime.utcnow()
        else:
            # Create new
            db_activity = StravaActivity(
                user_id=user_id,
                strava_id=activity_id,
                name=activity_name,
                distance=distance,
                start_date=start_date
            )
            db_activity.streams = streams
            db.session.add(db_activity)

        db.session.commit()
        print(f"✓ Saved streams to DB for activity {activity_id}")

        return db_activity

    def get_cached_activities(self, user_id, max_age_hours=24):
        """Get cached activity list for user.

        Args:
            user_id: User ID
            max_age_hours: Maximum cache age in hours

        Returns:
            List of activities or None if cache is stale/missing
        """
        cache = StravaActivityCache.query.filter_by(user_id=user_id).first()

        if not cache:
            print(f"✗ No activity list cache for user {user_id}")
            return None

        if cache.is_stale(max_age_hours):
            print(f"⚠️ Activity list cache is stale (age: {(datetime.utcnow() - cache.fetched_at).total_seconds() / 3600:.1f}h)")
            return None

        print(f"✓ Using cached activity list ({cache.activity_count} activities, age: {(datetime.utcnow() - cache.fetched_at).total_seconds() / 3600:.1f}h)")
        return cache.activities

    def cache_activities(self, user_id, activities, after_timestamp=None):
        """Cache activity list for user.

        Args:
            user_id: User ID
            activities: List of activity dicts from Strava API
            after_timestamp: Optional timestamp filter used in query

        Returns:
            StravaActivityCache object
        """
        cache = StravaActivityCache.query.filter_by(user_id=user_id).first()

        if cache:
            # Update existing
            cache.activities = activities
            cache.fetched_at = datetime.utcnow()
            cache.after_timestamp = after_timestamp
        else:
            # Create new
            cache = StravaActivityCache(
                user_id=user_id,
                after_timestamp=after_timestamp
            )
            cache.activities = activities
            db.session.add(cache)

        db.session.commit()
        print(f"✓ Cached {len(activities)} activities for user {user_id}")

        return cache

    def clear_stale_caches(self, max_age_hours=168):
        """Clear old caches from database.

        Args:
            max_age_hours: Age threshold in hours (default 7 days)
        """
        from datetime import timedelta

        threshold = datetime.utcnow() - timedelta(hours=max_age_hours)

        # Clear old activity list caches
        deleted = StravaActivityCache.query.filter(
            StravaActivityCache.fetched_at < threshold
        ).delete()

        db.session.commit()
        print(f"✓ Cleared {deleted} stale activity list caches")

        return deleted
