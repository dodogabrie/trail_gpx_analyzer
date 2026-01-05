"""User activity residual model for hybrid prediction training data."""

from datetime import datetime
from database import db


class UserActivityResidual(db.Model):
    """Training data: physics vs actual performance per activity.

    Stores segment-level residuals comparing physics predictions to actual
    performance. Used to train per-user ML models for prediction refinement.

    Each activity is broken into segments (typically 200m), and for each segment
    we store:
    - Terrain features (grade, variability)
    - Fatigue features (cumulative distance, elevation)
    - Physics prediction (baseline pace ratio)
    - Actual performance (observed pace ratio)
    - Residual (actual / physics - target for ML)

    Privacy: Only contains data from individual user's own activities.
    """

    __tablename__ = 'user_activity_residuals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    activity_id = db.Column(db.String(50), nullable=False, index=True)

    # Activity metadata
    activity_date = db.Column(db.DateTime, nullable=False, index=True)
    total_distance_km = db.Column(db.Float)
    total_elevation_gain_m = db.Column(db.Float)
    activity_type = db.Column(db.String(50), default='Run')

    # Segment-level residuals (JSON array)
    # Each segment contains features + physics vs actual comparison:
    # {
    #   'distance_m': 200,
    #   'grade_mean': 5.2,
    #   'grade_std': 1.3,
    #   'abs_grade': 5.2,
    #   'cum_distance_km': 2.4,
    #   'distance_remaining_km': 8.1,
    #   'cum_elevation_gain_m': 150,
    #   'elevation_gain_rate': 75,  # m/km
    #   'prev_pace_ratio': 1.18,
    #   'grade_change': 2.1,
    #   'rolling_avg_grade_500m': 4.8,
    #   'physics_pace_ratio': 1.25,
    #   'actual_pace_ratio': 1.32,
    #   'residual': 1.056  # actual / physics
    # }
    segments = db.Column(db.JSON, nullable=False)

    # Physics model version (for invalidation when model changes)
    physics_model_version = db.Column(db.String(20), default='1.0', nullable=False)

    # Recency weight (exponential decay - more recent = higher weight)
    recency_weight = db.Column(db.Float, default=1.0)

    # Training inclusion (user can exclude outlier activities)
    excluded_from_training = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('activity_residuals', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_user_date', 'user_id', 'activity_date'),
        db.Index('idx_user_version', 'user_id', 'physics_model_version'),
    )

    def __repr__(self):
        return f'<UserActivityResidual user_id={self.user_id} activity_id={self.activity_id} segments={len(self.segments or [])}>'

    @property
    def segment_count(self):
        """Get number of segments in this activity."""
        return len(self.segments) if self.segments else 0

    @property
    def days_ago(self):
        """Get number of days since activity."""
        return (datetime.utcnow() - self.activity_date).days if self.activity_date else None
