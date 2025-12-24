import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from datetime import datetime
from cryptography.fernet import Fernet
from pathlib import Path

# Generate encryption key (store in .env in production)
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if ENCRYPTION_KEY:
    ENCRYPTION_KEY = ENCRYPTION_KEY.encode()
else:
    # Dev-friendly fallback: persist a stable key on disk to avoid invalidating
    # encrypted tokens every time the server restarts.
    key_path = Path(__file__).resolve().parents[1] / 'instance' / 'encryption_key'
    try:
        if key_path.exists():
            ENCRYPTION_KEY = key_path.read_bytes().strip()
        else:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            ENCRYPTION_KEY = Fernet.generate_key()
            key_path.write_bytes(ENCRYPTION_KEY)
            try:
                os.chmod(key_path, 0o600)
            except Exception:
                pass
            print(f"⚠️ ENCRYPTION_KEY not set; generated dev key at {key_path} (tokens will depend on this file)")
    except Exception:
        ENCRYPTION_KEY = Fernet.generate_key()

cipher = Fernet(ENCRYPTION_KEY)

class User(db.Model):
    """User model for multi-user support."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    strava_user_id = db.Column(db.Integer, unique=True, nullable=False)
    strava_username = db.Column(db.String(255))

    # Encrypted tokens
    _access_token = db.Column('access_token', db.LargeBinary, nullable=True)
    _refresh_token = db.Column('refresh_token', db.LargeBinary, nullable=True)
    expires_at = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)

    # User fingerprint for personalized predictions
    user_endurance_score = db.Column(db.Float, nullable=True)
    user_recovery_rate = db.Column(db.Float, nullable=True)
    user_base_fitness = db.Column(db.Float, nullable=True)
    fingerprint_calibrated_at = db.Column(db.DateTime, nullable=True)
    fingerprint_activity_count = db.Column(db.Integer, nullable=True)

    # User calibration profile (editable pace curve)
    saved_flat_pace = db.Column(db.Float, nullable=True)
    saved_anchor_ratios = db.Column(db.JSON, nullable=True)
    calibration_updated_at = db.Column(db.DateTime, nullable=True)
    calibration_activity_id = db.Column(db.Integer, nullable=True)

    # Relationships
    gpx_files = db.relationship('GPXFile', backref='user', lazy=True, cascade='all, delete-orphan')
    strava_activities = db.relationship('StravaActivity', backref='user', lazy=True, cascade='all, delete-orphan')

    @property
    def access_token(self):
        """Decrypt access token."""
        if self._access_token:
            return cipher.decrypt(self._access_token).decode()
        return None

    @access_token.setter
    def access_token(self, value):
        """Encrypt access token."""
        if value:
            self._access_token = cipher.encrypt(value.encode())
        else:
            self._access_token = None

    @property
    def refresh_token(self):
        """Decrypt refresh token."""
        if self._refresh_token:
            return cipher.decrypt(self._refresh_token).decode()
        return None

    @refresh_token.setter
    def refresh_token(self, value):
        """Encrypt refresh token."""
        if value:
            self._refresh_token = cipher.encrypt(value.encode())
        else:
            self._refresh_token = None

    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'strava_user_id': self.strava_user_id,
            'strava_username': self.strava_username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat(),
            'fingerprint': {
                'endurance_score': self.user_endurance_score,
                'recovery_rate': self.user_recovery_rate,
                'base_fitness': self.user_base_fitness,
                'calibrated_at': self.fingerprint_calibrated_at.isoformat() if self.fingerprint_calibrated_at else None,
                'activity_count': self.fingerprint_activity_count
            } if self.user_endurance_score is not None else None,
            'calibration': {
                'flat_pace': self.saved_flat_pace,
                'anchor_ratios': self.saved_anchor_ratios,
                'updated_at': self.calibration_updated_at.isoformat() if self.calibration_updated_at else None,
                'activity_id': self.calibration_activity_id
            } if self.saved_flat_pace is not None else None
        }

    def get_fingerprint_array(self):
        """Get fingerprint as array for ML model.

        Returns:
            List of [endurance_score, recovery_rate, base_fitness] or None if not calibrated
        """
        if self.user_endurance_score is None:
            return None
        return [
            float(self.user_endurance_score),
            float(self.user_recovery_rate),
            float(self.user_base_fitness)
        ]
