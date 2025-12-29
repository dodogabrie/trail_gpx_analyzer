"""User learned parameters model for Tier 2 predictions."""

from datetime import datetime
from database import db


class UserLearnedParams(db.Model):
    """Tier 2: Learned physics parameters from user activities.

    Stores personalized physics model parameters optimized from user's
    historical activities. These parameters are learned by fitting the
    physics model to minimize prediction error on the user's actual
    performance data.

    Uses Bayesian optimization or gradient descent to find optimal:
    - v_flat: User's flat terrain velocity
    - k_up: Uphill slowdown coefficient
    - k_tech: Technical terrain coefficient
    - fatigue_alpha: Fatigue accumulation rate
    - terrain coefficients: Surface-specific adjustments

    Privacy: Only uses individual user's own activities for learning.
    """

    __tablename__ = 'user_learned_params'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    # Learned physics parameters
    v_flat = db.Column(db.Float, nullable=False)  # Flat velocity (m/s)
    k_up = db.Column(db.Float, default=1.0)  # Uphill coefficient
    k_tech = db.Column(db.Float, default=1.0)  # Technical terrain coefficient
    a_param = db.Column(db.Float, default=3.0)  # Power law parameter
    k_terrain_up = db.Column(db.Float, default=1.08)  # Uphill terrain factor
    k_terrain_down = db.Column(db.Float, default=1.12)  # Downhill terrain factor
    k_terrain_flat = db.Column(db.Float, default=1.05)  # Flat terrain factor
    fatigue_alpha = db.Column(db.Float, default=0.3)  # Fatigue accumulation rate

    # Training metadata
    n_activities_used = db.Column(db.Integer, nullable=False)
    optimization_score = db.Column(db.Float)  # MSE or MAE from optimization

    # Confidence intervals (optional - for uncertainty quantification)
    # {'v_flat': 0.05, 'k_up': 0.1, 'fatigue_alpha': 0.02}
    param_uncertainties = db.Column(db.JSON)

    last_trained = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    version = db.Column(db.Integer, default=1)

    # Relationships
    user = db.relationship('User', backref=db.backref('learned_params', uselist=False))

    def __repr__(self):
        return f'<UserLearnedParams user_id={self.user_id} v_flat={self.v_flat:.2f} activities={self.n_activities_used}>'

    def to_dict(self):
        """Convert to dictionary for prediction service."""
        return {
            'v_flat': self.v_flat,
            'k_up': self.k_up,
            'k_tech': self.k_tech,
            'a_param': self.a_param,
            'k_terrain_up': self.k_terrain_up,
            'k_terrain_down': self.k_terrain_down,
            'k_terrain_flat': self.k_terrain_flat,
            'fatigue_alpha': self.fatigue_alpha
        }

    @property
    def confidence_level(self):
        """Compute confidence level based on training data size."""
        if self.n_activities_used < 5:
            return 'LOW'
        elif self.n_activities_used < 10:
            return 'MEDIUM'
        else:
            return 'HIGH'
