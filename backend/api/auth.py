import sys
import os
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify, redirect, current_app
from models import User
from database import db
from services.strava_service import StravaService
from services.strava_sync_service import StravaSyncService
import jwt
from datetime import datetime, timedelta

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def get_strava_service():
    """Get configured Strava service instance."""
    return StravaService(
        current_app.config['STRAVA_CLIENT_ID'],
        current_app.config['STRAVA_CLIENT_SECRET'],
        current_app.config['STRAVA_REDIRECT_URI']
    )

def generate_jwt(user_id):
    """Generate JWT token for user."""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=current_app.config['JWT_EXPIRATION_HOURS'])
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

def verify_jwt(token):
    """Verify JWT token and return user_id."""
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@bp.route('/strava', methods=['GET'])
def get_strava_auth_url():
    """Get Strava authorization URL."""
    service = get_strava_service()
    auth_url = service.get_auth_url()
    return jsonify({'auth_url': auth_url})

@bp.route('/callback', methods=['GET'])
def handle_callback():
    """Handle OAuth callback from Strava."""
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return redirect(f"{current_app.config['CORS_ORIGINS'][0]}/auth-error?error={error}")

    if not code:
        return redirect(f"{current_app.config['CORS_ORIGINS'][0]}/auth-error?error=no_code")

    try:
        service = get_strava_service()
        token_data = service.exchange_code(code)

        athlete = token_data.get('athlete', {})
        strava_user_id = athlete.get('id')

        # Find or create user
        user = User.query.filter_by(strava_user_id=strava_user_id).first()

        if not user:
            user = User(
                strava_user_id=strava_user_id,
                strava_username=athlete.get('username'),
                email=athlete.get('email')
            )
            db.session.add(user)

        # Update tokens
        user.access_token = token_data['access_token']
        user.refresh_token = token_data['refresh_token']
        user.expires_at = token_data['expires_at']
        user.last_login = datetime.utcnow()

        db.session.commit()

        # Kick off background Strava sync + training on login
        try:
            StravaSyncService().sync_user_async(user.id)
        except Exception as e:
            current_app.logger.error(f"Failed to start Strava sync for user {user.id}: {str(e)}")

        # Generate JWT
        jwt_token = generate_jwt(user.id)

        # Redirect to frontend with token
        return redirect(f"{current_app.config['CORS_ORIGINS'][0]}/auth-success?token={jwt_token}")

    except requests.exceptions.HTTPError as e:
        current_app.logger.error(f"Strava API error: {e.response.text}")
        return redirect(f"{current_app.config['CORS_ORIGINS'][0]}/auth-error?error=exchange_failed")
    except Exception as e:
        current_app.logger.error(f"OAuth callback error: {str(e)}")
        return redirect(f"{current_app.config['CORS_ORIGINS'][0]}/auth-error?error=exchange_failed")

@bp.route('/status', methods=['GET'])
def auth_status():
    """Check authentication status."""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'authenticated': False}), 401

    token = auth_header.split(' ')[1]
    user_id = verify_jwt(token)

    if not user_id:
        return jsonify({'authenticated': False}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'authenticated': False}), 401

    return jsonify({
        'authenticated': True,
        'user': user.to_dict()
    })


@bp.route('/refresh', methods=['POST'])
def refresh_strava_token():
    """Refresh Strava access token."""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401

    token = auth_header.split(' ')[1]
    user_id = verify_jwt(token)

    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    try:
        service = get_strava_service()
        token_data = service.refresh_token(user.refresh_token)

        user.access_token = token_data['access_token']
        user.refresh_token = token_data['refresh_token']
        user.expires_at = token_data['expires_at']

        db.session.commit()

        return jsonify({'message': 'Token refreshed successfully'})

    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return jsonify({'error': 'Failed to refresh token'}), 500
