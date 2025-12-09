import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify, current_app
from models import User, StravaActivity, GPXFile
from database import db
from api.auth import verify_jwt
from services.strava_service import StravaService
from datetime import datetime

bp = Blueprint('strava', __name__, url_prefix='/api/strava')

def get_current_user():
    """Get current user from JWT token."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ')[1]
    user_id = verify_jwt(token)

    if not user_id:
        return None

    return User.query.get(user_id)

def get_strava_service():
    """Get configured Strava service instance."""
    return StravaService(
        current_app.config['STRAVA_CLIENT_ID'],
        current_app.config['STRAVA_CLIENT_SECRET'],
        current_app.config['STRAVA_REDIRECT_URI']
    )

@bp.route('/activities', methods=['GET'])
def get_activities():
    """Fetch user activities from Strava."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        service = get_strava_service()

        # Ensure token is valid
        access_token, refresh_token, expires_at = service.get_valid_token(
            user.access_token,
            user.refresh_token,
            user.expires_at
        )

        # Update user tokens if refreshed
        if access_token != user.access_token:
            user.access_token = access_token
            user.refresh_token = refresh_token
            user.expires_at = expires_at
            db.session.commit()

        # Get query parameters
        after = request.args.get('after', type=int)
        if not after:
            after = service.get_timestamp_for_last_year()

        # Fetch activities
        activities = service.fetch_activities(access_token, after)

        return jsonify({
            'activities': activities,
            'total': len(activities)
        })

    except Exception as e:
        current_app.logger.error(f"Fetch activities error: {str(e)}")
        return jsonify({'error': 'Failed to fetch activities'}), 500

@bp.route('/match', methods=['POST'])
def match_activities():
    """Find activities matching a GPX file's distance."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    gpx_id = data.get('gpx_id')
    tolerance = data.get('tolerance', 0.1)

    if not gpx_id:
        return jsonify({'error': 'gpx_id is required'}), 400

    gpx_file = GPXFile.query.filter_by(id=gpx_id, user_id=user.id).first()
    if not gpx_file:
        return jsonify({'error': 'GPX file not found'}), 404

    try:
        service = get_strava_service()

        # Ensure token is valid
        access_token, refresh_token, expires_at = service.get_valid_token(
            user.access_token,
            user.refresh_token,
            user.expires_at
        )

        # Update tokens if refreshed
        if access_token != user.access_token:
            user.access_token = access_token
            user.refresh_token = refresh_token
            user.expires_at = expires_at
            db.session.commit()

        # Fetch activities
        after = service.get_timestamp_for_last_year()
        activities = service.fetch_activities(access_token, after)

        # Filter by distance
        target_distance = gpx_file.data['total_distance']
        matching = service.filter_activities_by_length(activities, target_distance, tolerance)

        return jsonify({
            'matching_activities': matching,
            'total': len(matching),
            'target_distance': target_distance
        })

    except Exception as e:
        current_app.logger.error(f"Match activities error: {str(e)}")
        return jsonify({'error': 'Failed to match activities'}), 500

@bp.route('/activities/<int:activity_id>/download', methods=['POST'])
def download_activity_streams(activity_id):
    """Download streams for a specific activity."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        service = get_strava_service()

        # Ensure token is valid
        access_token, refresh_token, expires_at = service.get_valid_token(
            user.access_token,
            user.refresh_token,
            user.expires_at
        )

        # Update tokens if refreshed
        if access_token != user.access_token:
            user.access_token = access_token
            user.refresh_token = refresh_token
            user.expires_at = expires_at
            db.session.commit()

        # Download streams
        streams = service.download_streams(activity_id, access_token)

        # Check if activity already exists
        strava_activity = StravaActivity.query.filter_by(
            user_id=user.id,
            strava_id=activity_id
        ).first()

        if not strava_activity:
            # Fetch activity details
            import requests
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(
                f'{service.API_URL}/activities/{activity_id}',
                headers=headers
            )
            response.raise_for_status()
            activity_data = response.json()

            strava_activity = StravaActivity(
                user_id=user.id,
                strava_id=activity_id,
                name=activity_data['name'],
                distance=activity_data['distance'],
                start_date=datetime.fromisoformat(activity_data['start_date'].replace('Z', '+00:00'))
            )
            db.session.add(strava_activity)

        # Update streams
        strava_activity.streams = streams
        db.session.commit()

        return jsonify({
            'message': 'Streams downloaded successfully',
            'activity': strava_activity.to_dict()
        })

    except Exception as e:
        current_app.logger.error(f"Download streams error: {str(e)}")
        return jsonify({'error': 'Failed to download streams'}), 500

@bp.route('/activities/<int:activity_id>/streams', methods=['GET'])
def get_activity_streams(activity_id):
    """Get cached streams for an activity."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    strava_activity = StravaActivity.query.filter_by(
        user_id=user.id,
        strava_id=activity_id
    ).first()

    if not strava_activity:
        return jsonify({'error': 'Activity not found'}), 404

    if not strava_activity.streams:
        return jsonify({'error': 'No streams available'}), 404

    return jsonify({
        'activity': strava_activity.to_dict(),
        'streams': strava_activity.streams
    })
