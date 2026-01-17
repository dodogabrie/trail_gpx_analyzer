"""Performance tracking API endpoints.

Provides endpoints for:
- Historical performance snapshots
- Performance trends by grade
- Achievement tracking
- Period comparison
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify
from models import User, PerformanceSnapshot, GradePerformanceHistory, UserAchievement
from database import db
from api.utils import get_current_user
from services.performance_tracker import PerformanceTracker
from services.cache_service import CacheService
from services.strava_service import StravaService
from datetime import datetime, timedelta

bp = Blueprint('performance', __name__, url_prefix='/api/performance')

# Initialize services (singletons)
performance_tracker = None
cache_service = None
strava_service = None


def get_performance_tracker():
    """Get or create performance tracker instance."""
    global performance_tracker, cache_service, strava_service
    if performance_tracker is None:
        if cache_service is None:
            cache_service = CacheService()
        if strava_service is None:
            from flask import current_app
            client_id = current_app.config.get('STRAVA_CLIENT_ID')
            client_secret = current_app.config.get('STRAVA_CLIENT_SECRET')
            redirect_uri = current_app.config.get('STRAVA_REDIRECT_URI')
            strava_service = StravaService(client_id, client_secret, redirect_uri)

        performance_tracker = PerformanceTracker(cache_service, strava_service)
    return performance_tracker


def get_fatigue_curve():
    """Compute a rolling-window fatigue curve from recent activities.

    Query params:
        weeks: Rolling window in weeks (default: 12)
        limit: Max activities to consider (default: 50)

    Returns:
        { "fatigue_curve": {...} }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    weeks = int(request.args.get('weeks', 12))
    limit = int(request.args.get('limit', 50))
    cutoff = datetime.utcnow() - timedelta(days=weeks * 7)

    from models import StravaActivity
    # Avoid ORDER BY on large rows (streams TEXT) which can force SQLite temp files.
    activity_ids = [
        row[0]
        for row in (
            db.session.query(StravaActivity.id)
            .filter_by(user_id=user.id)
            .filter(StravaActivity.start_date >= cutoff)
            .filter(StravaActivity._streams.isnot(None))
            .order_by(StravaActivity.start_date.desc())
            .limit(limit)
            .all()
        )
    ]
    activities_q = []
    if activity_ids:
        activities_q = StravaActivity.query.filter(StravaActivity.id.in_(activity_ids)).all()

    activity_streams = []
    activities_meta = []
    # Ensure deterministic ordering in Python (since the IN() query is unordered)
    activities_q.sort(key=lambda a: a.start_date, reverse=True)
    for a in activities_q:
        streams = a.streams
        if not streams:
            continue
        activity_streams.append(streams)
        activities_meta.append({
            'id': int(a.strava_id),
            'distance': float(a.distance or 0),
            'start_date': a.start_date.isoformat()
        })

    tracker = get_performance_tracker()
    curve = tracker._calculate_fatigue_curve(activity_streams, activities_meta)

    return jsonify({'fatigue_curve': curve})



@bp.route('/achievements', methods=['GET'])
def get_achievements():
    """Get achievements for current user.

    Query params:
        unread_only: Return only unnotified achievements (default: false)

    Returns:
        {
            "achievements": [
                {
                    "id": 45,
                    "type": "improvement",
                    "name": "Uphill Champion",
                    "description": "10% improvement on climbs (+20% grade)",
                    "category": "uphill",
                    "category_icon": "⛰️",
                    "icon": "📈",
                    "value": 10.5,
                    "earned_at": "2025-01-15T12:00:00",
                    "notified": false
                },
                ...
            ],
            "total_count": 12,
            "new_count": 2
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    unread_only = request.args.get('unread_only', 'false').lower() == 'true'

    tracker = get_performance_tracker()
    achievements = tracker.get_achievements(user.id, include_notified=not unread_only)

    new_count = sum(1 for a in achievements if not a.notified)

    return jsonify({
        'achievements': [a.to_dict() for a in achievements],
        'total_count': len(achievements),
        'new_count': new_count
    })
