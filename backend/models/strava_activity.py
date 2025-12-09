import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from datetime import datetime
import json

class StravaActivity(db.Model):
    """Strava activity model."""
    __tablename__ = 'strava_activities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    strava_id = db.Column(db.BigInteger, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    distance = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)

    # Streams stored as JSON
    _streams = db.Column('streams', db.Text, nullable=True)

    downloaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def streams(self):
        """Parse JSON streams."""
        if self._streams:
            return json.loads(self._streams)
        return None

    @streams.setter
    def streams(self, value):
        """Store streams as JSON."""
        if value:
            self._streams = json.dumps(value)
        else:
            self._streams = None

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'strava_id': self.strava_id,
            'name': self.name,
            'distance': self.distance,
            'start_date': self.start_date.isoformat(),
            'has_streams': self._streams is not None,
            'downloaded_at': self.downloaded_at.isoformat()
        }
