import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify, current_app
from models import User, StravaActivity
from database import db
from api.utils import get_current_user
from services.strava_service import StravaService
from cryptography.fernet import InvalidToken

bp = Blueprint('strava', __name__, url_prefix='/api/strava')

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

