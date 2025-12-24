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


@bp.route('/refresh', methods=['POST'])
def refresh_snapshots():
    """Calculate/refresh performance snapshots for current user.

    Request body:
        {
            "period_type": "weekly",  // or "monthly", "quarterly"
            "num_periods": 4,  // Number of recent periods to calculate (default: 4)
            "force_recalculate": false
        }

    Returns:
        {
            "snapshots_created": 3,
            "snapshots": [...]
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}
    period_type = data.get('period_type', 'weekly')
    num_periods = data.get('num_periods', 4)
    force_recalculate = data.get('force_recalculate', False)

    tracker = get_performance_tracker()
    created_snapshots = []

    for offset in range(num_periods):
        try:
            snapshot = tracker.calculate_period_performance(
                user.id,
                period_type=period_type,
                offset=offset,
                force_recalculate=force_recalculate
            )
            if snapshot:
                created_snapshots.append(snapshot)
        except Exception as e:
            print(f"Error calculating snapshot for offset {offset}: {e}")
            import traceback
            traceback.print_exc()
            # Rollback to recover from database errors
            db.session.rollback()

    # Award achievements after calculating snapshots
    try:
        new_achievements = tracker.award_achievements(user.id)
    except Exception as e:
        print(f"Error awarding achievements: {e}")
        db.session.rollback()
        new_achievements = []

    return jsonify({
        'snapshots_created': len(created_snapshots),
        'snapshots': [s.to_dict() for s in created_snapshots],
        'new_achievements': [a.to_dict() for a in new_achievements]
    })

@bp.route('/fatigue', methods=['GET'])
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


@bp.route('/trends/<int:grade>', methods=['GET'])
@bp.route('/trends', methods=['GET'])
def get_grade_trend(grade=None):
    """Get performance trend for specific grade.

    Path params (deprecated):
        grade: Grade bucket (e.g., -30, -20, -10, 0, 10, 20, 30)

    Query params:
        grade: Grade bucket (e.g., -30, -20, -10, 0, 10, 20, 30) - preferred method
        periods: Number of periods to retrieve (default: 12)

    Returns:
        {
            "grade": 10,
            "trend": [
                {"date": "2025-W01", "pace": 5.2, "sample_count": 15},
                {"date": "2025-W02", "pace": 5.1, "sample_count": 18},
                ...
            ],
            "improvement_pct": -5.8,  // negative = faster
            "trend_direction": "improving"  // "improving", "declining", "stable"
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    # Accept grade from query param or path param
    if grade is None:
        grade = request.args.get('grade', type=int)
    if grade is None:
        return jsonify({'error': 'grade parameter required'}), 400

    periods = int(request.args.get('periods', 12))

    tracker = get_performance_tracker()
    trend = tracker.get_performance_trend(user.id, grade, periods)

    # Calculate improvement percentage and trend direction
    improvement_pct = None
    trend_direction = "stable"

    if len(trend) >= 2:
        first_pace = trend[0]['pace']
        last_pace = trend[-1]['pace']
        if first_pace and last_pace:
            improvement_pct = ((last_pace - first_pace) / first_pace) * 100
            if improvement_pct < -2:  # 2% faster
                trend_direction = "improving"
            elif improvement_pct > 2:  # 2% slower
                trend_direction = "declining"

    return jsonify({
        'grade': grade,
        'trend': trend,
        'improvement_pct': improvement_pct,
        'trend_direction': trend_direction
    })


@bp.route('/compare', methods=['GET'])
def compare_periods():
    """Compare two performance periods.

    Query params:
        current_id: ID of current/recent snapshot
        previous_id: ID of previous/older snapshot
        OR
        current_period: 'weekly', 'monthly' (default: most recent weekly)
        compare_to: 'last_week', 'last_month', '4_weeks_ago' (default: 'last_week')

    Returns:
        {
            "current": {
                "period": "2025-W03",
                "flat_pace": 4.5,
                "anchor_ratios": {...}
            },
            "comparison": {
                "period": "2025-W02",
                "flat_pace": 4.8,
                "anchor_ratios": {...}
            },
            "changes": {
                "flat_pace": -0.3,  // Absolute change
                "flat_pace_pct": -6.25,  // Percentage change
                "grades": {
                    "-30": {"change": -0.1, "pct": -5.5},
                    "0": {"change": -0.3, "pct": -6.25},
                    "30": {"change": -0.5, "pct": -17.8}
                }
            }
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    tracker = get_performance_tracker()

    # Get snapshots by ID or by period offset
    current_id = request.args.get('current_id', type=int)
    previous_id = request.args.get('previous_id', type=int)

    if current_id and previous_id:
        current = PerformanceSnapshot.query.get(current_id)
        previous = PerformanceSnapshot.query.get(previous_id)
    else:
        # Get by offset
        period_type = request.args.get('current_period', 'weekly')
        compare_to = request.args.get('compare_to', 'last_week')

        offset_map = {
            'last_week': 1,
            'last_month': 4,
            '4_weeks_ago': 4,
            '8_weeks_ago': 8
        }
        offset = offset_map.get(compare_to, 1)

        snapshots = tracker.get_snapshots(user.id, period_type, limit=offset+1)
        if len(snapshots) < 2:
            return jsonify({'error': 'Insufficient data for comparison'}), 400

        current = snapshots[0]
        previous = snapshots[min(offset, len(snapshots)-1)]

    if not current or not previous:
        return jsonify({'error': 'Snapshots not found'}), 404

    # Ensure both snapshots belong to current user
    if current.user_id != user.id or previous.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    changes = tracker.compare_periods(current, previous)

    return jsonify({
        'current': current.to_dict(),
        'comparison': previous.to_dict(),
        'changes': changes
    })


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


@bp.route('/stats', methods=['GET'])
def get_performance_stats():
    """Get overall performance statistics for current user.

    Returns:
        {
            "total_snapshots": 12,
            "total_achievements": 8,
            "current_streak": 5,
            "longest_streak": 8,
            "total_distance_km": 523.5,
            "total_elevation_m": 12500,
            "best_flat_pace": 4.2,
            "best_flat_pace_date": "2025-01-15"
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    tracker = get_performance_tracker()

    # Get all snapshots
    all_snapshots = PerformanceSnapshot.query.filter_by(
        user_id=user.id
    ).order_by(PerformanceSnapshot.period_start.desc()).all()

    # Calculate stats
    total_distance = sum(s.total_distance_km or 0 for s in all_snapshots)
    total_elevation = sum(s.total_elevation_m or 0 for s in all_snapshots)

    # Find best flat pace
    valid_snapshots = [s for s in all_snapshots if s.flat_pace]
    best_flat_pace = None
    best_flat_pace_date = None
    if valid_snapshots:
        best_snapshot = min(valid_snapshots, key=lambda s: s.flat_pace)
        best_flat_pace = best_snapshot.flat_pace
        best_flat_pace_date = best_snapshot.period_start.isoformat()

    # Current streak
    current_streak = tracker._count_consecutive_weeks(user.id)

    # Total achievements
    total_achievements = UserAchievement.query.filter_by(user_id=user.id).count()

    return jsonify({
        'total_snapshots': len(all_snapshots),
        'total_achievements': total_achievements,
        'current_streak': current_streak,
        'total_distance_km': total_distance,
        'total_elevation_m': total_elevation,
        'best_flat_pace': best_flat_pace,
        'best_flat_pace_date': best_flat_pace_date
    })
