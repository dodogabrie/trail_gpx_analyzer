"""Sync status model for tracking background Strava sync progress."""

from database import db
from datetime import datetime


class SyncStatus(db.Model):
    """Tracks progress of background Strava sync for users."""
    __tablename__ = 'sync_status'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)

    # Status: idle, syncing, completed, error
    status = db.Column(db.String(50), default='idle', nullable=False)

    # Current step: selecting_activities, downloading_streams, training_tier2, training_tier3
    current_step = db.Column(db.String(100), nullable=True)

    # Progress tracking
    total_activities = db.Column(db.Integer, default=0)
    downloaded_activities = db.Column(db.Integer, default=0)

    # Messages
    message = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary for API response."""
        return {
            'status': self.status,
            'current_step': self.current_step,
            'total_activities': self.total_activities,
            'downloaded_activities': self.downloaded_activities,
            'progress_percent': int((self.downloaded_activities / self.total_activities * 100)) if self.total_activities > 0 else 0,
            'message': self.message,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
