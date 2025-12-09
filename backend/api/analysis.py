import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify
from models import User, GPXFile
from database import db
from api.auth import verify_jwt
from services.stats_service import calculate_segment_stats, filter_points_by_distance

bp = Blueprint('analysis', __name__, url_prefix='/api/analysis')

def get_current_user():
    """Get current user from JWT token."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        # TEMPORARY: Get or create default user for testing
        user = User.query.first()
        if not user:
            user = User(strava_user_id=999999, strava_username='test_user')
            db.session.add(user)
            db.session.commit()
        return user

    token = auth_header.split(' ')[1]
    user_id = verify_jwt(token)

    if not user_id:
        # Fallback to default user
        user = User.query.first()
        if not user:
            user = User(strava_user_id=999999, strava_username='test_user')
            db.session.add(user)
            db.session.commit()
        return user

    return User.query.get(user_id)

@bp.route('/stats', methods=['POST'])
def calculate_stats():
    """Calculate statistics for a segment."""
    user = get_current_user()

    data = request.get_json()
    gpx_id = data.get('gpx_id')
    start_index = data.get('start_index')
    end_index = data.get('end_index')

    if not all([gpx_id is not None, start_index is not None, end_index is not None]):
        return jsonify({'error': 'gpx_id, start_index, and end_index are required'}), 400

    gpx_file = GPXFile.query.filter_by(id=gpx_id, user_id=user.id).first()
    if not gpx_file:
        return jsonify({'error': 'GPX file not found'}), 404

    if not gpx_file.data:
        return jsonify({'error': 'No data available'}), 404

    try:
        points = gpx_file.data['points']
        stats = calculate_segment_stats(points, start_index, end_index)
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/segment', methods=['POST'])
def get_segment():
    """Get segment data for a distance range."""
    user = get_current_user()

    data = request.get_json()
    gpx_id = data.get('gpx_id')
    start_distance = data.get('start_distance')
    end_distance = data.get('end_distance')

    if not all([gpx_id is not None, start_distance is not None, end_distance is not None]):
        return jsonify({'error': 'gpx_id, start_distance, and end_distance are required'}), 400

    gpx_file = GPXFile.query.filter_by(id=gpx_id, user_id=user.id).first()
    if not gpx_file:
        return jsonify({'error': 'GPX file not found'}), 404

    if not gpx_file.data:
        return jsonify({'error': 'No data available'}), 404

    try:
        points = gpx_file.data['points']
        segment_points = filter_points_by_distance(points, start_distance, end_distance)
        return jsonify({'points': segment_points})

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/point/<int:index>', methods=['POST'])
def get_point(index):
    """Get a specific point by index."""
    user = get_current_user()

    data = request.get_json()
    gpx_id = data.get('gpx_id')

    if gpx_id is None:
        return jsonify({'error': 'gpx_id is required'}), 400

    gpx_file = GPXFile.query.filter_by(id=gpx_id, user_id=user.id).first()
    if not gpx_file:
        return jsonify({'error': 'GPX file not found'}), 404

    if not gpx_file.data:
        return jsonify({'error': 'No data available'}), 404

    points = gpx_file.data['points']

    if index < 0 or index >= len(points):
        return jsonify({'error': 'Index out of range'}), 400

    return jsonify({'point': points[index]})
