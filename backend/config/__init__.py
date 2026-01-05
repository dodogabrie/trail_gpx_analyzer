from pathlib import Path
import os
from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")

class Config:
    """Flask configuration."""
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    _DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "instance" / "gpx_analyzer.db"
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{_DEFAULT_DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Strava OAuth
    STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
    STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
    STRAVA_REDIRECT_URI = os.getenv('STRAVA_REDIRECT_URI', 'http://localhost:5000/api/auth/callback')
    STRAVA_ENABLED = bool(STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET)

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')

    # File upload
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '../data/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-change-in-production')
    JWT_EXPIRATION_HOURS = 24
