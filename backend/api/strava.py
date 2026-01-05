import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify, current_app
from models import User, StravaActivity, GPXFile
from database import db
from api.auth import verify_jwt
from services.strava_service import StravaService
from services.user_residual_service import UserResidualService
from datetime import datetime
from cryptography.fernet import InvalidToken

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
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'

        if not after:
            after = service.get_timestamp_for_last_year()

        # Try to use cached activities first
        from services.cache_service import CacheService
        cache_service = CacheService()

        activities = None
        if not force_refresh:
            activities = cache_service.get_cached_activities(user.id, max_age_hours=24)

        # Fetch from Strava if no cache or force refresh
        if activities is None:
            activities = service.fetch_activities(access_token, after)
            # Cache the fetched activities
            cache_service.cache_activities(user.id, activities, after)

        # Check which activities have streams downloaded
        activity_ids = [a['id'] for a in activities]
        downloaded_activities = StravaActivity.query.filter(
            StravaActivity.user_id == user.id,
            StravaActivity.strava_id.in_(activity_ids)
        ).all()

        downloaded_ids = {a.strava_id: (a.streams is not None) for a in downloaded_activities}

        # Add has_streams field to each activity
        for activity in activities:
            activity['has_streams'] = downloaded_ids.get(activity['id'], False)
            activity['strava_id'] = activity['id']  # Normalize field name

        return jsonify({
            'activities': activities,
            'total': len(activities)
        })

    except InvalidToken:
        return jsonify({'error': 'Strava tokens are invalid (cannot decrypt). Please reconnect Strava.'}), 401
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

    except InvalidToken:
        return jsonify({'error': 'Strava tokens are invalid (cannot decrypt). Please reconnect Strava.'}), 401
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

        # Collect residuals for hybrid prediction training
        try:
            residual_service = UserResidualService()
            residual_service.collect_residuals_from_activity(
                user_id=user.id,
                activity_id=str(activity_id),
                activity_streams=streams,
                activity_metadata={
                    'start_date': activity_data.get('start_date'),
                    'type': activity_data.get('type', 'Run'),
                    'distance': activity_data.get('distance'),
                }
            )
            print(f"[STRAVA] Residuals collected for activity {activity_id}")
        except Exception as e:
            # Don't fail request if residual collection fails
            print(f"[STRAVA] Failed to collect residuals: {e}")

        return jsonify({
            'message': 'Streams downloaded successfully',
            'activity': strava_activity.to_dict()
        })

    except InvalidToken:
        return jsonify({'error': 'Strava tokens are invalid (cannot decrypt). Please reconnect Strava.'}), 401
    except Exception as e:
        current_app.logger.error(f"Download streams error: {str(e)}")
        return jsonify({'error': 'Failed to download streams'}), 500

@bp.route('/activities/batch-download', methods=['POST'])
def batch_download_activities():
    """Download streams for multiple activities (for training hybrid model)."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        activity_ids = data.get('activity_ids', [])
        limit = min(len(activity_ids), data.get('limit', 20))  # Max 20 at a time

        if not activity_ids:
            return jsonify({'error': 'No activity IDs provided'}), 400

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

        results = {
            'success': [],
            'failed': [],
            'skipped': []
        }

        import requests
        headers = {'Authorization': f'Bearer {access_token}'}
        residual_service = UserResidualService()

        for i, activity_id in enumerate(activity_ids[:limit]):
            try:
                # Check if already downloaded
                existing = StravaActivity.query.filter_by(
                    user_id=user.id,
                    strava_id=activity_id
                ).first()

                if existing and existing.streams:
                    results['skipped'].append({
                        'id': activity_id,
                        'reason': 'Already downloaded'
                    })
                    continue

                # Download streams
                streams = service.download_streams(activity_id, access_token)

                # Fetch activity details if needed
                if not existing:
                    response = requests.get(
                        f'{service.API_URL}/activities/{activity_id}',
                        headers=headers
                    )
                    response.raise_for_status()
                    activity_data = response.json()

                    existing = StravaActivity(
                        user_id=user.id,
                        strava_id=activity_id,
                        name=activity_data['name'],
                        distance=activity_data['distance'],
                        start_date=datetime.fromisoformat(activity_data['start_date'].replace('Z', '+00:00'))
                    )
                    db.session.add(existing)
                else:
                    # Fetch for residual collection
                    response = requests.get(
                        f'{service.API_URL}/activities/{activity_id}',
                        headers=headers
                    )
                    activity_data = response.json()

                # Update streams
                existing.streams = streams
                db.session.commit()

                # Collect residuals
                try:
                    residual_service.collect_residuals_from_activity(
                        user_id=user.id,
                        activity_id=str(activity_id),
                        activity_streams=streams,
                        activity_metadata={
                            'start_date': activity_data.get('start_date'),
                            'type': activity_data.get('type', 'Run'),
                            'distance': activity_data.get('distance'),
                        }
                    )
                except Exception as e:
                    print(f"[BATCH] Residual collection failed for {activity_id}: {e}")

                results['success'].append({
                    'id': activity_id,
                    'name': existing.name
                })

            except Exception as e:
                results['failed'].append({
                    'id': activity_id,
                    'error': str(e)
                })
                print(f"[BATCH] Failed to download {activity_id}: {e}")

        # Check tier status after downloads
        from services.hybrid_prediction_service import HybridPredictionService
        hybrid_service = HybridPredictionService()
        tier_info = hybrid_service.get_user_tier_status(user.id)

        return jsonify({
            'message': f'Batch download complete',
            'results': results,
            'tier_status': tier_info
        })

    except InvalidToken:
        return jsonify({'error': 'Strava tokens are invalid. Please reconnect Strava.'}), 401
    except Exception as e:
        current_app.logger.error(f"Batch download error: {str(e)}")
        return jsonify({'error': 'Batch download failed'}), 500

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
