"""Grade-specific performance history model."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from datetime import datetime


class GradePerformanceHistory(db.Model):
    """Detailed grade-specific performance tracking.

    Stores pace statistics for each grade bucket (e.g., -30%, -20%, ..., +30%)
    within a performance snapshot period.

    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        snapshot_id: Foreign key to performance_snapshots table
        grade_bucket: Grade value (e.g., -30, -20, -10, 0, 10, 20, 30)
        avg_pace: Average pace at this grade (min/km)
        sample_count: Number of data points at this grade
        median_pace: Median pace at this grade (min/km)
        iqr_pace: Interquartile range of pace
        created_at: Timestamp of creation
    """
    __tablename__ = 'grade_performance_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    snapshot_id = db.Column(db.Integer, db.ForeignKey('performance_snapshots.id'), nullable=True)

    # Grade bucket (e.g., -30, -20, -10, 0, 10, 20, 30)
    grade_bucket = db.Column(db.Integer, nullable=False)

    # Performance statistics
    avg_pace = db.Column(db.Float, nullable=False)
    sample_count = db.Column(db.Integer, nullable=False)
    median_pace = db.Column(db.Float, nullable=True)
    iqr_pace = db.Column(db.Float, nullable=True)  # Interquartile range

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def get_grade_category(self):
        """Get grade category (uphill, flat, downhill).

        Returns:
            String: 'uphill', 'flat', or 'downhill'
        """
        if self.grade_bucket > 5:
            return 'uphill'
        elif self.grade_bucket < -5:
            return 'downhill'
        else:
            return 'flat'

    def is_high_confidence(self, min_samples=10):
        """Check if this grade bucket has enough samples.

        Args:
            min_samples: Minimum sample count for high confidence

        Returns:
            True if sample_count >= min_samples
        """
        return self.sample_count >= min_samples

    def to_dict(self):
        """Convert to dictionary.

        Returns:
            Dict representation suitable for JSON serialization
        """
        return {
            'id': self.id,
            'snapshot_id': self.snapshot_id,
            'grade': self.grade_bucket,
            'category': self.get_grade_category(),
            'avg_pace': self.avg_pace,
            'median_pace': self.median_pace,
            'iqr_pace': self.iqr_pace,
            'sample_count': self.sample_count,
            'high_confidence': self.is_high_confidence(),
            'created_at': self.created_at.isoformat()
        }
