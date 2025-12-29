from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

def init_db(app):
    """Initialize database with app context."""
    db.init_app(app)

    # Import all models so SQLAlchemy knows about them for migrations
    from models import (
        User, GPXFile, StravaActivity, StravaActivityCache, Prediction,
        PerformanceSnapshot, GradePerformanceHistory, UserAchievement,
        UserActivityResidual, UserLearnedParams, UserResidualModel
    )
