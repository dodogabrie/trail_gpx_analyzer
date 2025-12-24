from database import db
from datetime import datetime

class Prediction(db.Model):
    """Prediction result model."""
    __tablename__ = 'predictions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    gpx_file_id = db.Column(db.Integer, db.ForeignKey('gpx_files.id'), nullable=False)
    
    # Inputs used for prediction
    flat_pace = db.Column(db.Float, nullable=False)
    user_fingerprint = db.Column(db.JSON, nullable=True) # Snapshot of fingerprint used
    anchor_ratios = db.Column(db.JSON, nullable=True) # Snapshot of anchors used
    
    # Results
    total_time_seconds = db.Column(db.Float, nullable=False)
    predicted_segments = db.Column(db.JSON, nullable=False) # List of segments with times
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='predictions')
    gpx_file = db.relationship('GPXFile', backref='predictions')

    def to_dict(self):
        return {
            'id': self.id,
            'gpx_file_id': self.gpx_file_id,
            'flat_pace': self.flat_pace,
            'total_time_seconds': self.total_time_seconds,
            'total_time_formatted': self._format_time(self.total_time_seconds),
            'created_at': self.created_at.isoformat(),
            'segments': self.predicted_segments
        }
        
    @staticmethod
    def _format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
