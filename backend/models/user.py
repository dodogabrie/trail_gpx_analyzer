import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from datetime import datetime
from cryptography.fernet import Fernet
import os

# Generate encryption key (store in .env in production)
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key()
else:
    ENCRYPTION_KEY = ENCRYPTION_KEY.encode()

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
            'last_login': self.last_login.isoformat()
        }
