"""Performance snapshot model for tracking user progress over time."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from datetime import datetime
import json


class PerformanceSnapshot(db.Model):
    """Track user's performance calibration over time periods.

    Stores weekly/monthly snapshots of user's pace-grade curve to enable
    trend analysis and gamification features.

    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        snapshot_date: Date when snapshot was created
        period_type: Type of period (weekly, monthly, quarterly)
        period_start: Start date of the period
        period_end: End date of the period
        flat_pace: User's flat terrain pace (min/km)
        anchor_ratios: Pace ratios at key grades (JSON)
        activity_count: Number of activities in period
        total_distance_km: Total distance covered in period
        total_elevation_m: Total elevation gain in period
        created_at: Timestamp of creation
    """
    __tablename__ = 'performance_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Period information
    snapshot_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    period_type = db.Column(db.String(20), nullable=False)  # weekly, monthly, quarterly
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)

    # Performance metrics (similar to user.saved_flat_pace and saved_anchor_ratios)
    flat_pace = db.Column(db.Float, nullable=False)
    _anchor_ratios = db.Column('anchor_ratios', db.Text, nullable=False)

    # Activity statistics for period
    activity_count = db.Column(db.Integer, nullable=False, default=0)
    total_distance_km = db.Column(db.Float, nullable=True)
    total_elevation_m = db.Column(db.Float, nullable=True)

    # Fatigue curve (adaptive based on user's max distance)
    # Format: {
    #   'max_distance_km': 80,
    #   'sample_distances': [0, 32, 64],  # 0%, 40%, 80% of max
    #   'grades': {
    #     '0': {'degradation': [1.0, 1.03, 1.08]},
    #     '10': {'degradation': [1.0, 1.05, 1.15]},
    #     ...
    #   }
    # }
    _fatigue_curve = db.Column('fatigue_curve', db.Text, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    grade_performances = db.relationship('GradePerformanceHistory', backref='snapshot',
                                        lazy=True, cascade='all, delete-orphan')

    @property
    def anchor_ratios(self):
        """Parse JSON anchor_ratios.

        Returns:
            Dict mapping grade (as string) to pace ratio
            Example: {"-30": 2.5, "-20": 2.0, "0": 1.0, "30": 2.8}
        """
        if self._anchor_ratios:
            return json.loads(self._anchor_ratios)
        return {}

    @anchor_ratios.setter
    def anchor_ratios(self, value):
        """Store anchor_ratios as JSON.

        Args:
            value: Dict mapping grade to pace ratio
        """
        if value:
            self._anchor_ratios = json.dumps(value)
        else:
            self._anchor_ratios = json.dumps({})

    @property
    def fatigue_curve(self):
        """Parse JSON fatigue_curve.

        Returns:
            Dict with max_distance_km, sample_distances, and grades
        """
        if self._fatigue_curve:
            return json.loads(self._fatigue_curve)
        return None

    @fatigue_curve.setter
    def fatigue_curve(self, value):
        """Store fatigue_curve as JSON.

        Args:
            value: Dict with fatigue curve data
        """
        if value:
            self._fatigue_curve = json.dumps(value)
        else:
            self._fatigue_curve = None

    def get_period_label(self):
        """Get human-readable period label.

        Returns:
            String like "2025-W03" for weekly, "2025-01" for monthly
        """
        if self.period_type == 'weekly':
            # Get ISO week number
            week_num = self.period_start.isocalendar()[1]
            return f"{self.period_start.year}-W{week_num:02d}"
        elif self.period_type == 'monthly':
            return f"{self.period_start.year}-{self.period_start.month:02d}"
        elif self.period_type == 'quarterly':
            quarter = (self.period_start.month - 1) // 3 + 1
            return f"{self.period_start.year}-Q{quarter}"
        return str(self.snapshot_date.date())

    def is_low_confidence(self, min_activities=2):
        """Check if snapshot has low confidence due to few activities.

        Args:
            min_activities: Minimum activities for high confidence

        Returns:
            True if activity_count < min_activities
        """
        return self.activity_count < min_activities

    def to_dict(self):
        """Convert to dictionary.

        Returns:
            Dict representation suitable for JSON serialization
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'period': self.get_period_label(),
            'period_type': self.period_type,
            'start': self.period_start.isoformat(),
            'end': self.period_end.isoformat(),
            'flat_pace': self.flat_pace,
            'anchor_ratios': self.anchor_ratios,
            'activity_count': self.activity_count,
            'total_distance': self.total_distance_km,
            'total_elevation': self.total_elevation_m,
            'fatigue_curve': self.fatigue_curve,
            'low_confidence': self.is_low_confidence(),
            'created_at': self.created_at.isoformat()
        }
