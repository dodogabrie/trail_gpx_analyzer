import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from datetime import datetime
import json

class GPXFile(db.Model):
    """GPX file model."""
    __tablename__ = 'gpx_files'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)

    # Parsed data stored as JSON
    _data = db.Column('data', db.Text, nullable=True)

    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def data(self):
        """Parse JSON data."""
        if self._data:
            return json.loads(self._data)
        return None

    @data.setter
    def data(self, value):
        """Store data as JSON."""
        if value:
            self._data = json.dumps(value)
        else:
            self._data = None

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'upload_date': self.upload_date.isoformat(),
            'has_data': self._data is not None
        }
