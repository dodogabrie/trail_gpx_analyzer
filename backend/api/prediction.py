"""Prediction API endpoints.

Workflow:
1. GET /api/prediction/calibration-activities - List user's activities for calibration
2. POST /api/prediction/calibrate - Compute flat_pace from selected activity
3. POST /api/prediction/predict - Generate route time prediction
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify, current_app
from models import User, GPXFile, StravaActivity
from database import db
from api.auth import verify_jwt
from services.prediction_service import PredictionService
from services.strava_service import StravaService
from datetime import datetime
import requests

bp = Blueprint('prediction', __name__, url_prefix='/api/prediction')

# Initialize service (singleton)
prediction_service = None


def get_prediction_service():
    """Get or create prediction service instance."""
    global prediction_service
    if prediction_service is None:
        prediction_service = PredictionService()
    return prediction_service


def get_current_user():
    """Get current user from JWT token."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        # Fallback to default user for testing
        user = User.query.first()
        if not user:
            user = User(strava_user_id=999999, strava_username='test_user')
            db.session.add(user)
            db.session.commit()
        return user

    token = auth_header.split(' ')[1]
    user_id = verify_jwt(token)

    if not user_id:
        return None

    return User.query.get(user_id)


def get_strava_service():
    """Get Strava service instance."""
    return StravaService(
        current_app.config['STRAVA_CLIENT_ID'],
        current_app.config['STRAVA_CLIENT_SECRET'],
        current_app.config['STRAVA_REDIRECT_URI']
    )


@bp.route('/calibration-activities', methods=['GET'])
def get_calibration_activities():
    """Get user's Strava activities suitable for calibration.

    Query params:
        - gpx_id (optional): If provided, filter to similar distances
        - limit (optional): Max activities to return (default 50)

    Response:
        {
            'activities': [
                {
                    'id': int,
                    'strava_id': int,
                    'name': str,
                    'distance': float,
                    'start_date': str,
                    'has_streams': bool,
                    'recommended': bool  # True if similar to GPX distance
                },
                ...
            ],
            'total': int
        }
    """
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

        # Fetch activities from Strava
        after = service.get_timestamp_for_last_year()
        activities = service.fetch_activities(access_token, after)

        # Filter to runs only (type='Run')
        activities = [a for a in activities if a.get('type') == 'Run']

        # Get GPX distance if provided for similarity marking
        gpx_id = request.args.get('gpx_id', type=int)
        target_distance = None
        if gpx_id:
            gpx_file = GPXFile.query.filter_by(id=gpx_id, user_id=user.id).first()
            if gpx_file and gpx_file.data:
                target_distance = gpx_file.data['total_distance']

        # Format activities
        formatted = []
        for activity in activities:
            # Check if we have cached streams
            cached = StravaActivity.query.filter_by(
                user_id=user.id,
                strava_id=activity['id']
            ).first()

            recommended = False
            if target_distance:
                dist_diff = abs(activity['distance'] - target_distance)
                recommended = (dist_diff / target_distance) < 0.15

            formatted.append({
                'strava_id': activity['id'],
                'name': activity['name'],
                'distance': activity['distance'],
                'distance_km': round(activity['distance'] / 1000, 2),
                'start_date': activity['start_date'],
                'has_streams': cached is not None and cached.streams is not None,
                'recommended': recommended,
                'moving_time': activity.get('moving_time'),
                'elapsed_time': activity.get('elapsed_time')
            })

        # Sort: recommended first, then by date
        formatted.sort(key=lambda x: (not x['recommended'], x['start_date']), reverse=True)

        # Limit results
        limit = request.args.get('limit', 50, type=int)
        formatted = formatted[:limit]

        return jsonify({
            'activities': formatted,
            'total': len(formatted)
        })

    except Exception as e:
        current_app.logger.error(f"Fetch calibration activities error: {str(e)}")
        return jsonify({'error': 'Failed to fetch activities'}), 500


@bp.route('/calibrate', methods=['POST'])
def calibrate():
    """Calibrate user's flat pace from a Strava activity.

    Request body:
        {
            'activity_id': int (Strava activity ID)
        }

    Response:
        {
            'flat_pace_min_per_km': float,
            'diagnostics': {
                'anchor_count': int,
                'anchor_grades': [float, ...],
                'activity_distance_km': float
            }
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    activity_id = data.get('activity_id')

    if not activity_id:
        return jsonify({'error': 'activity_id is required'}), 400

    try:
        # Check if we have cached streams
        strava_activity = StravaActivity.query.filter_by(
            user_id=user.id,
            strava_id=activity_id
        ).first()

        # If not cached, download streams
        if not strava_activity or not strava_activity.streams:
            service = get_strava_service()

            # Ensure token is valid
            access_token, refresh_token, expires_at = service.get_valid_token(
                user.access_token,
                user.refresh_token,
                user.expires_at
            )

            if access_token != user.access_token:
                user.access_token = access_token
                user.refresh_token = refresh_token
                user.expires_at = expires_at
                db.session.commit()

            # Download streams
            streams = service.download_streams(activity_id, access_token)

            # Fetch activity details
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(
                f'{service.API_URL}/activities/{activity_id}',
                headers=headers
            )
            response.raise_for_status()
            activity_data = response.json()

            # Cache in database
            if not strava_activity:
                strava_activity = StravaActivity(
                    user_id=user.id,
                    strava_id=activity_id,
                    name=activity_data['name'],
                    distance=activity_data['distance'],
                    start_date=datetime.fromisoformat(activity_data['start_date'].replace('Z', '+00:00'))
                )
                db.session.add(strava_activity)

            strava_activity.streams = streams
            db.session.commit()

        # Calibrate using prediction service
        pred_service = get_prediction_service()
        flat_pace, diagnostics = pred_service.calibrate_from_activity(strava_activity.streams)

        return jsonify({
            'flat_pace_min_per_km': flat_pace,
            'diagnostics': diagnostics,
            'activity': {
                'id': strava_activity.strava_id,
                'name': strava_activity.name,
                'distance_km': round(strava_activity.distance / 1000, 2)
            }
        })

    except ValueError as e:
        return jsonify({'error': f'Calibration failed: {str(e)}'}), 400
    except Exception as e:
        current_app.logger.error(f"Calibration error: {str(e)}")
        return jsonify({'error': 'Failed to calibrate'}), 500


@bp.route('/predict', methods=['POST'])
def predict():
    """Predict time for a GPX route using calibrated flat pace.

    Request body:
        {
            'gpx_id': int,
            'flat_pace_min_per_km': float
        }

    Response:
        {
            'prediction': {
                'total_time_seconds': float,
                'total_time_formatted': str,
                'confidence_interval': {'lower_seconds', 'upper_seconds', ...},
                'segments': [...],
                'statistics': {...}
            },
            'similar_activities': [...]
        }
    """
    print("\n" + "="*60)
    print("PREDICTION REQUEST RECEIVED")
    print("="*60)

    user = get_current_user()
    if not user:
        print("ERROR: Unauthorized")
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    gpx_id = data.get('gpx_id')
    flat_pace = data.get('flat_pace_min_per_km')

    print(f"GPX ID: {gpx_id}")
    print(f"Flat Pace: {flat_pace} min/km")

    if not gpx_id or not flat_pace:
        print("ERROR: Missing required fields")
        return jsonify({'error': 'gpx_id and flat_pace_min_per_km are required'}), 400

    # Validate flat_pace
    if flat_pace <= 0 or flat_pace > 20:
        print("ERROR: Invalid flat_pace")
        return jsonify({'error': 'Invalid flat_pace (must be 0-20 min/km)'}), 400

    # Get GPX file
    print(f"Fetching GPX file {gpx_id} for user {user.id}...")
    gpx_file = GPXFile.query.filter_by(id=gpx_id, user_id=user.id).first()
    if not gpx_file:
        print("ERROR: GPX file not found")
        return jsonify({'error': 'GPX file not found'}), 404

    if not gpx_file.data:
        print("ERROR: No GPX data available")
        return jsonify({'error': 'No GPX data available'}), 404

    print(f"GPX file found: {gpx_file.original_filename}")
    print(f"Total distance: {gpx_file.data.get('total_distance', 0)} m")

    try:
        print("\n[1/4] Getting prediction service...")
        pred_service = get_prediction_service()
        print("✓ Prediction service ready")

        # Generate prediction
        print("\n[2/4] Generating prediction...")
        print(f"  - Converting GPX to route profile...")
        prediction = pred_service.predict_route_time(gpx_file.data, flat_pace)
        print(f"✓ Prediction complete: {prediction['total_time_formatted']}")

        # Find similar activities
        print("\n[3/4] Fetching similar activities...")
        service = get_strava_service()
        access_token, refresh_token, expires_at = service.get_valid_token(
            user.access_token,
            user.refresh_token,
            user.expires_at
        )

        if access_token != user.access_token:
            user.access_token = access_token
            user.refresh_token = refresh_token
            user.expires_at = expires_at
            db.session.commit()
            print("  - Refreshed Strava tokens")

        after = service.get_timestamp_for_last_year()
        print(f"  - Fetching activities from Strava...")
        activities = service.fetch_activities(access_token, after)
        print(f"  - Found {len(activities)} activities")

        print("\n[4/4] Finding similar activities...")
        similar = pred_service.find_similar_activities(gpx_file.data, activities)
        print(f"✓ Found {len(similar)} similar activities")

        print("\n" + "="*60)
        print("PREDICTION SUCCESSFUL - Sending response")
        print("="*60 + "\n")

        return jsonify({
            'prediction': prediction,
            'similar_activities': similar[:5]  # Top 5
        })

    except Exception as e:
        print("\n" + "!"*60)
        print(f"ERROR: {str(e)}")
        print("!"*60)
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"Prediction error: {str(e)}")
        return jsonify({'error': f'Prediction failed: {str(e)}'}), 500
