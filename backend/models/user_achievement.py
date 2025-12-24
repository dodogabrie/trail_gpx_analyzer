"""User achievement model for gamification."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from datetime import datetime


class UserAchievement(db.Model):
    """Track user achievements for gamification.

    Stores badges and milestones earned by users based on their
    performance improvements, consistency, and volume.

    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        achievement_type: Type of achievement (improvement, streak, volume, pr)
        achievement_name: Human-readable achievement name
        achievement_description: Description of what was achieved
        grade_category: Optional terrain category (uphill, downhill, flat)
        metric_value: Numerical value associated with achievement
        earned_at: Timestamp when achievement was earned
        notified: Whether user has been notified
    """
    __tablename__ = 'user_achievements'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Achievement details
    achievement_type = db.Column(db.String(50), nullable=False)  # improvement, streak, volume, pr
    achievement_name = db.Column(db.String(100), nullable=False)
    achievement_description = db.Column(db.Text, nullable=True)

    # Optional category and value
    grade_category = db.Column(db.String(20), nullable=True)  # uphill, downhill, flat
    metric_value = db.Column(db.Float, nullable=True)

    # Metadata
    earned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notified = db.Column(db.Boolean, default=False, nullable=False)

    def get_icon(self):
        """Get emoji icon for achievement type.

        Returns:
            String emoji representing the achievement
        """
        icons = {
            'improvement': '📈',
            'streak': '🔥',
            'volume': '💪',
            'pr': '🏆'
        }
        return icons.get(self.achievement_type, '⭐')

    def get_category_icon(self):
        """Get emoji icon for grade category.

        Returns:
            String emoji representing the terrain category
        """
        if self.grade_category == 'uphill':
            return '⛰️'
        elif self.grade_category == 'downhill':
            return '🏔️'
        elif self.grade_category == 'flat':
            return '🏃'
        return ''

    def mark_notified(self):
        """Mark achievement as notified."""
        self.notified = True

    def to_dict(self):
        """Convert to dictionary.

        Returns:
            Dict representation suitable for JSON serialization
        """
        return {
            'id': self.id,
            'type': self.achievement_type,
            'name': self.achievement_name,
            'description': self.achievement_description,
            'category': self.grade_category,
            'category_icon': self.get_category_icon(),
            'icon': self.get_icon(),
            'value': self.metric_value,
            'earned_at': self.earned_at.isoformat(),
            'notified': self.notified
        }
