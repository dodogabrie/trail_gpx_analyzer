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
from api.auth import verify_jwt
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


def get_current_user():
    """Get current user from JWT token."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ')[1]
    user_id = verify_jwt(token)
    user = User.query.get(user_id)
    return user


@bp.route('/snapshots', methods=['GET'])
def get_snapshots():
    """Get performance snapshots for current user.

    Query params:
        period_type: 'weekly', 'monthly', or 'quarterly' (default: 'weekly')
        limit: Maximum number of snapshots to return (default: 12)

    Returns:
        {
            "snapshots": [
                {
                    "id": 123,
                    "period": "2025-W03",
                    "period_type": "weekly",
                    "start": "2025-01-13T00:00:00",
                    "end": "2025-01-20T00:00:00",
                    "flat_pace": 4.5,
                    "anchor_ratios": {"-30": 1.8, "0": 1.0, "30": 2.8},
                    "activity_count": 5,
                    "total_distance": 42.5,
                    "total_elevation": 850.0,
                    "low_confidence": false
                },
                ...
            ]
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    period_type = request.args.get('period_type', 'weekly')
    limit = int(request.args.get('limit', 12))

    tracker = get_performance_tracker()
    snapshots = tracker.get_snapshots(user.id, period_type, limit)

    return jsonify({
        'snapshots': [s.to_dict() for s in snapshots]
    })


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



@bp.route('/grade-model-comparison', methods=['GET'])
def get_grade_model_comparison():
    """Get comparison curves for all 3 model tiers.

    Returns:
        {
            "grades": [-30, -29, ..., 30],
            "tier1_pace": [5.2, ...],
            "tier2_pace": [4.8, ...],
            "tier3_pace": [4.9, ...],
            "has_tier2": true,
            "has_tier3": true
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        service = HybridPredictionService()
        data = service.generate_model_comparison(user.id)
        return jsonify(data)
    except Exception as e:
        print(f"Error generating model comparison: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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


@bp.route('/achievements/<int:achievement_id>/mark-read', methods=['POST'])
def mark_achievement_read(achievement_id):
    """Mark an achievement as notified/read.

    Returns:
        {"success": true}
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    achievement = UserAchievement.query.get(achievement_id)
    if not achievement:
        return jsonify({'error': 'Achievement not found'}), 404

    if achievement.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    achievement.mark_notified()
    db.session.commit()

    return jsonify({'success': True})


