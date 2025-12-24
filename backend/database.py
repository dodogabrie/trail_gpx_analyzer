from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

def init_db(app):
    """Initialize database with app context."""
    db.init_app(app)

    # Import all models so SQLAlchemy knows about them
    from models import User, GPXFile, StravaActivity, StravaActivityCache, Prediction

    with app.app_context():
        db.create_all()
