"""User residual model for Tier 3 ML predictions."""

from datetime import datetime
from database import db


class UserResidualModel(db.Model):
    """Tier 3: Trained ML model for residual corrections.

    Stores a trained GradientBoostingRegressor that learns to predict
    residual corrections on top of the physics baseline. The model is
    trained exclusively on the user's own activity data.

    The model predicts a residual_multiplier which adjusts the physics
    prediction:
        final_pace = physics_pace * residual_multiplier

    Features used (10):
        - Terrain: grade_mean, grade_std, abs_grade
        - Fatigue: cum_distance_km, distance_remaining_km, cum_elevation_gain_m
        - Dynamics: prev_pace_ratio, grade_change, elevation_gain_rate
        - Context: rolling_avg_grade_500m

    Privacy: Model trained only on individual user's own activities.
    """

    __tablename__ = 'user_residual_models'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    # Serialized model (joblib compressed)
    model_blob = db.Column(db.LargeBinary, nullable=False)

    # Training metadata
    n_activities_used = db.Column(db.Integer, nullable=False)
    n_segments_trained = db.Column(db.Integer)

    # Model performance metrics (on validation set)
    # {'mae': 0.05, 'rmse': 0.08, 'r2': 0.82, 'val_mae': 0.06}
    metrics = db.Column(db.JSON)

    # Feature importance (for explainability)
    # {'grade_mean': 0.25, 'cum_distance_km': 0.18, ...}
    feature_importance = db.Column(db.JSON)

    # Model configuration (hyperparameters used)
    # {'n_estimators': 100, 'max_depth': 3, 'learning_rate': 0.05}
    model_config = db.Column(db.JSON)

    last_trained = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    version = db.Column(db.Integer, default=1)

    # Relationships
    user = db.relationship('User', backref=db.backref('residual_model', uselist=False))

    def __repr__(self):
        return f'<UserResidualModel user_id={self.user_id} activities={self.n_activities_used} mae={self.metrics.get("mae") if self.metrics else "N/A"}>'

    @property
    def confidence_level(self):
        """Compute confidence level based on training data and performance."""
        if self.n_activities_used < 10:
            return 'LOW'
        elif self.n_activities_used < 20:
            return 'MEDIUM'
        elif self.metrics and self.metrics.get('mae', 1.0) < 0.08:
            return 'HIGH'
        else:
            return 'MEDIUM_HIGH'

    @property
    def mae_percent(self):
        """Get MAE as percentage (for display)."""
        if self.metrics and 'mae' in self.metrics:
            return self.metrics['mae'] * 100
        return None
