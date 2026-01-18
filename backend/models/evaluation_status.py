"""Evaluation status model for tracking model evaluation progress."""

from database import db
from datetime import datetime


class EvaluationStatus(db.Model):
    """Tracks progress of model evaluation for users.

    Provides real-time progress updates during the leave-one-out evaluation
    process, enabling frontend progress bar display.
    """
    __tablename__ = 'evaluation_status'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)

    # Status: idle, running, completed, error
    status = db.Column(db.String(50), default='idle', nullable=False)

    # Current step: loading_activities, finding_target, training_params, training_gbm, predicting, calculating_errors
    current_step = db.Column(db.String(100), nullable=True)

    # Progress tracking
    total_steps = db.Column(db.Integer, default=6)
    current_step_number = db.Column(db.Integer, default=0)

    # Activity info
    total_activities = db.Column(db.Integer, default=0)
    training_activities = db.Column(db.Integer, default=0)
    target_activity_id = db.Column(db.String(50), nullable=True)
    target_activity_name = db.Column(db.String(255), nullable=True)

    # Segment progress (for detailed progress)
    total_segments = db.Column(db.Integer, default=0)
    processed_segments = db.Column(db.Integer, default=0)

    # Messages
    message = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary for API response."""
        # Calculate overall progress percent
        if self.status == 'completed':
            progress_percent = 100
        elif self.status == 'idle':
            progress_percent = 0
        elif self.total_steps > 0:
            progress_percent = int((self.current_step_number / self.total_steps) * 100)
        else:
            progress_percent = 0

        return {
            'status': self.status,
            'current_step': self.current_step,
            'current_step_number': self.current_step_number,
            'total_steps': self.total_steps,
            'progress_percent': progress_percent,
            'total_activities': self.total_activities,
            'training_activities': self.training_activities,
            'target_activity_id': self.target_activity_id,
            'target_activity_name': self.target_activity_name,
            'total_segments': self.total_segments,
            'processed_segments': self.processed_segments,
            'message': self.message,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

    def reset(self):
        """Reset status for new evaluation."""
        self.status = 'idle'
        self.current_step = None
        self.current_step_number = 0
        self.total_activities = 0
        self.training_activities = 0
        self.target_activity_id = None
        self.target_activity_name = None
        self.total_segments = 0
        self.processed_segments = 0
        self.message = None
        self.error_message = None
        self.started_at = None
        self.completed_at = None
