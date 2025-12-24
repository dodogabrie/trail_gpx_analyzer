"""Strava activity list cache model."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from datetime import datetime
import json


class StravaActivityCache(db.Model):
    """Cache for user's activity list from Strava.

    Stores snapshots of activity lists to avoid repeated API calls.
    Cache is considered stale after 24 hours.
    """
    __tablename__ = 'strava_activity_cache'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Activity list stored as JSON
    _activities = db.Column('activities', db.Text, nullable=False)

    # Cache metadata
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    after_timestamp = db.Column(db.Integer, nullable=True)  # Query parameter used
    activity_count = db.Column(db.Integer, nullable=False)

    @property
    def activities(self):
        """Parse JSON activities."""
        if self._activities:
            return json.loads(self._activities)
        return []

    @activities.setter
    def activities(self, value):
        """Store activities as JSON."""
        if value:
            self._activities = json.dumps(value)
            self.activity_count = len(value)
        else:
            self._activities = json.dumps([])
            self.activity_count = 0

    def is_stale(self, max_age_hours=24):
        """Check if cache is stale.

        Args:
            max_age_hours: Maximum age in hours before cache is considered stale

        Returns:
            True if cache is older than max_age_hours
        """
        age = datetime.utcnow() - self.fetched_at
        return age.total_seconds() > (max_age_hours * 3600)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'fetched_at': self.fetched_at.isoformat(),
            'activity_count': self.activity_count,
            'is_stale': self.is_stale()
        }
