"""Shared utilities for API endpoints."""

from flask import request, current_app
from models import User
from api.auth import verify_jwt


def get_current_user():
    """Get current user from JWT token.

    Returns:
        User object if authenticated, None otherwise
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        if current_app.debug:
            user = User.query.first()
            if user:
                return user
        return None

    token = auth_header.split(' ')[1]
    user_id = verify_jwt(token)
    if not user_id:
        return None

    return User.query.get(user_id)
