"""Prediction API endpoints.

Workflow:
1. GET /api/prediction/calibration-activities - List user's activities for calibration
2. POST /api/prediction/calibrate - Compute flat_pace from selected activity
3. POST /api/prediction/predict - Generate route time prediction
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify, current_app, send_file
from models import User, GPXFile, StravaActivity, StravaActivityCache, Prediction
from database import db
from api.utils import get_current_user
from services.strava_service import StravaService
from services.cache_service import CacheService
from datetime import datetime, timedelta, timezone
from cryptography.fernet import InvalidToken
import requests

bp = Blueprint('prediction', __name__, url_prefix='/api/prediction')

# Initialize services (singletons)
cache_service = None


def get_cache_service():
    """Get or create cache service instance."""
    global cache_service
    if cache_service is None:
        cache_service = CacheService()
    return cache_service


def get_strava_service():
    """Get Strava service instance."""
    return StravaService(
        current_app.config['STRAVA_CLIENT_ID'],
        current_app.config['STRAVA_CLIENT_SECRET'],
        current_app.config['STRAVA_REDIRECT_URI']
    )

def _parse_strava_datetime(value: str) -> datetime:
    """Parse Strava ISO datetimes (typically ending in 'Z')."""
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _select_fingerprint_activity_ids(
    *,
    calibration_activity_id: int,
    activities: list,
    months: int = 3,
    max_longest_runs: int = 10,
) -> list:
    """Select activities for user fingerprint extraction.

    Includes the calibration activity plus the longest runs from the last ~N months.
    Returns unique Strava activity IDs in priority order.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(months * 30))
    recent_runs = []
    for a in activities or []:
        if a.get('type') != 'Run':
            continue
        try:
            start_date = _parse_strava_datetime(a.get('start_date'))
        except Exception:
            continue
        if start_date < cutoff:
            continue
        dist = a.get('distance') or 0
        if dist <= 0:
            continue
        recent_runs.append(a)

    recent_runs.sort(key=lambda x: x.get('distance', 0), reverse=True)

    selected = [int(calibration_activity_id)]
    for run in recent_runs[:max_longest_runs]:
        rid = run.get('id')
        if rid is None:
            continue
        rid = int(rid)
        if rid not in selected:
            selected.append(rid)

    return selected


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
        cache = get_cache_service()

        # Try to get cached activities first
        cached_activities = cache.get_cached_activities(user.id, max_age_hours=24)

        if cached_activities:
            # Use cached data
            print(f"✓ Using cached activities for user {user.id}")
            activities = cached_activities
        else:
            # Fetch from Strava
            print(f"⚠️ No cache, fetching from Strava for user {user.id}")
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

            # Cache the fetched activities
            cache.cache_activities(user.id, activities, after_timestamp=after)

        # Filter to runs only (type='Run')
        activities = [a for a in activities if a.get('type') == 'Run']

        # Get GPX route info if provided for similarity scoring
        gpx_id = request.args.get('gpx_id', type=int)
        target_distance = None
        target_elevation = None
        if gpx_id:
            gpx_file = GPXFile.query.filter_by(id=gpx_id, user_id=user.id).first()
            if gpx_file and gpx_file.data:
                target_distance = gpx_file.data.get('total_distance')
                target_elevation = gpx_file.data.get('total_ascent', 0)

        # Format activities with similarity scoring
        formatted = []
        for activity in activities:
            # Check if we have cached streams
            cached = StravaActivity.query.filter_by(
                user_id=user.id,
                strava_id=activity['id']
            ).first()

            # Calculate similarity score for ultra trail matching
            similarity_score = 0.0
            recommended = False

            if target_distance:
                act_distance = activity['distance']
                act_elevation = activity.get('total_elevation_gain', 0)

                # 1. Distance similarity (0-1, weight: 40%)
                dist_diff_pct = abs(act_distance - target_distance) / max(target_distance, 1)
                distance_sim = max(0, 1 - dist_diff_pct)

                # 2. Elevation similarity (0-1, weight: 30%)
                elevation_sim = 0.5  # Neutral if no elevation data
                if target_elevation and target_elevation > 100:  # Route has significant elevation
                    elev_diff_pct = abs(act_elevation - target_elevation) / max(target_elevation, 1)
                    elevation_sim = max(0, 1 - elev_diff_pct)

                # 3. Effort type bonus (weight: 30%)
                # For long routes (>25km), prioritize long runs over daily workouts
                effort_bonus = 0.5  # Neutral default
                if target_distance > 25000:  # Long route (>25km)
                    if act_distance > 20000:  # Long run
                        effort_bonus = 1.0  # Strong preference
                    elif act_distance < 15000:  # Short workout
                        effort_bonus = 0.2  # Penalize

                # For ultra routes (>40km), heavily prioritize ultra-distance activities
                if target_distance > 40000:  # Ultra route
                    if act_distance > 35000:  # Ultra-distance run
                        effort_bonus = 1.0
                    elif act_distance < 25000:  # Not ultra-distance
                        effort_bonus = 0.1  # Strong penalty

                # Combined similarity score (0-1)
                similarity_score = (
                    distance_sim * 0.4 +
                    elevation_sim * 0.3 +
                    effort_bonus * 0.3
                )

                # Recommended if score > 0.6
                recommended = similarity_score > 0.6

            formatted.append({
                'strava_id': activity['id'],
                'name': activity['name'],
                'distance': activity['distance'],
                'distance_km': round(activity['distance'] / 1000, 2),
                'elevation_gain': activity.get('total_elevation_gain', 0),
                'start_date': activity['start_date'],
                'has_streams': cached is not None and cached.streams is not None,
                'recommended': recommended,
                'similarity_score': round(similarity_score, 3),
                'moving_time': activity.get('moving_time'),
                'elapsed_time': activity.get('elapsed_time')
            })

        # Sort by similarity score (best matches first), then by date
        formatted.sort(key=lambda x: (x['similarity_score'], x['start_date']), reverse=True)

        # Limit results
        limit = request.args.get('limit', 50, type=int)
        formatted = formatted[:limit]

        return jsonify({
            'activities': formatted,
            'total': len(formatted)
        })

    except InvalidToken:
        return jsonify({'error': 'Strava tokens are invalid (cannot decrypt). Please reconnect Strava.'}), 401
    except Exception as e:
        current_app.logger.error(f"Fetch calibration activities error: {str(e)}")
        return jsonify({'error': 'Failed to fetch activities'}), 500

@bp.route('/save-calibration', methods=['POST'])
def save_calibration():
    """Save user-edited calibration to profile.

    Request body:
        {
            'flat_pace_min_per_km': float,
            'anchor_ratios': {'-30': 0.45, ...},
            'calibration_activity_id': int (Strava ID)
        }

    Response:
        {
            'message': 'Calibration saved',
            'user': {
                'saved_flat_pace': float,
                'calibration_updated_at': str (ISO format)
            }
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    flat_pace = data.get('flat_pace_min_per_km')
    anchor_ratios = data.get('anchor_ratios')

    # Validate flat_pace
    if not flat_pace or flat_pace <= 0 or flat_pace > 20:
        return jsonify({'error': 'Invalid flat_pace (must be 0-20 min/km)'}), 400

    # Validate anchor_ratios
    if not anchor_ratios or len(anchor_ratios) < 3:
        return jsonify({'error': 'Need at least 3 anchor ratios'}), 400

    # Validate ratios are in reasonable range
    for grade, ratio in anchor_ratios.items():
        if ratio < 0.3 or ratio > 6.0:
            return jsonify({'error': f'Invalid ratio {ratio} at grade {grade} (must be 0.3-6.0)'}), 400

    try:
        # Save to user
        user.saved_flat_pace = float(flat_pace)
        user.saved_anchor_ratios = {str(k): float(v) for k, v in anchor_ratios.items()}
        user.calibration_updated_at = datetime.utcnow()
        user.calibration_activity_id = data.get('calibration_activity_id')

        db.session.commit()

        return jsonify({
            'message': 'Calibration saved',
            'user': {
                'saved_flat_pace': user.saved_flat_pace,
                'calibration_updated_at': user.calibration_updated_at.isoformat() if user.calibration_updated_at else None,
                'calibration_activity_id': user.calibration_activity_id
            }
        })

    except Exception as e:
        current_app.logger.error(f"Save calibration error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to save calibration'}), 500

@bp.route('/<int:prediction_id>/export', methods=['GET'])
def export_prediction_gpx(prediction_id):
    """Export prediction as GPX with timestamps (Virtual Partner)."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    prediction = Prediction.query.filter_by(id=prediction_id, user_id=user.id).first()
    if not prediction:
        return jsonify({'error': 'Prediction not found'}), 404
        
    gpx_db_file = prediction.gpx_file
    if not gpx_db_file or not gpx_db_file.data:
        return jsonify({'error': 'Original GPX data missing'}), 404
        
    try:
        import gpxpy
        import gpxpy.gpx
        from datetime import datetime, timedelta
        import io
        
        points = gpx_db_file.data['points']
        segments = prediction.predicted_segments
        
        # Create new GPX
        new_gpx = gpxpy.gpx.GPX()

        # Add annotations as waypoints
        annotations = prediction.annotations or {'annotations': []}
        for ann in annotations.get('annotations', []):
            waypoint = gpxpy.gpx.GPXWaypoint(
                latitude=ann['lat'],
                longitude=ann['lon'],
                name=ann['label']
            )
            waypoint.description = ann.get('description', '')

            # Set symbol and type based on annotation type
            if ann['type'] == 'aid_station':
                waypoint.symbol = 'Water Source'
                waypoint.type = 'Water Source'
            else:  # generic
                waypoint.symbol = 'Generic'
                waypoint.type = 'Generic'

            new_gpx.waypoints.append(waypoint)

        # Create track
        gpx_track = gpxpy.gpx.GPXTrack()
        new_gpx.tracks.append(gpx_track)
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        
        # Start time (now + 1 hour buffer, or just arbitrary)
        # Virtual Partners usually just need relative time, but GPX requires absolute.
        # We'll start at 2025-01-01 08:00:00
        start_time = datetime(2025, 1, 1, 8, 0, 0)
        current_time = start_time
        
        # Helper to find speed/pace for a given distance
        # Segments are sorted by distance
        # We'll iterate through points and match them to segments
        
        seg_idx = 0
        current_segment = segments[0]
        
        for i, point in enumerate(points):
            dist_km = point['distance'] / 1000.0
            
            # Find correct segment
            # Advance segment if we passed its end
            while seg_idx < len(segments) - 1 and dist_km > segments[seg_idx]['end_km']:
                seg_idx += 1
                current_segment = segments[seg_idx]
            
            # Calculate time to reach this point
            # This is tricky because segments are averages. 
            # Better approach: 
            # 1. We have cumulative time for start of each segment? No, we have segment duration.
            # 2. We can build a cumulative time map.
            
            # Let's rebuild cumulative time for segment starts
            pass 
        
        # Re-approach: Pre-calculate cumulative time at each segment boundary
        cum_time_at_seg_start = [0.0]
        for s in segments:
            # Handle both time_s and time_seconds keys
            seg_time = s.get('time_s') or s.get('time_seconds', 0)
            cum_time_at_seg_start.append(cum_time_at_seg_start[-1] + seg_time)
            
        # Now interpolate for each point
        seg_idx = 0
        for p in points:
            dist_km = p['distance'] / 1000.0
            
            # Find segment index
            while seg_idx < len(segments) - 1 and dist_km > segments[seg_idx]['end_km']:
                seg_idx += 1
            
            seg = segments[seg_idx]
            seg_start_km = seg['start_km']
            seg_end_km = seg['end_km']
            seg_duration = seg.get('time_s') or seg.get('time_seconds', 0)
            seg_start_time = cum_time_at_seg_start[seg_idx]
            
            # Interpolate within segment
            if seg_end_km > seg_start_km:
                fraction = (dist_km - seg_start_km) / (seg_end_km - seg_start_km)
                fraction = max(0, min(1, fraction)) # Clamp
                point_time_sec = seg_start_time + (fraction * seg_duration)
            else:
                point_time_sec = seg_start_time
                
            # Create GPX point
            dt = start_time + timedelta(seconds=point_time_sec)
            
            new_point = gpxpy.gpx.GPXTrackPoint(
                latitude=p['lat'],
                longitude=p['lon'],
                elevation=p['elevation'],
                time=dt
            )
            gpx_segment.points.append(new_point)
            
        # Generate string
        xml = new_gpx.to_xml()
        
        # Send file
        mem_file = io.BytesIO()
        mem_file.write(xml.encode('utf-8'))
        mem_file.seek(0)
        
        filename = f"predicted_{gpx_db_file.original_filename}"
        
        return send_file(
            mem_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/gpx+xml'
        )

    except Exception as e:
        current_app.logger.error(f"Export error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Export failed: {str(e)}'}), 500
@bp.route('/<int:prediction_id>/annotations', methods=['PUT'])
def update_annotations(prediction_id):
    """Update annotations for a prediction.

    Request body:
        {
            "annotations": [
                {
                    "id": "uuid",
                    "type": "aid_station" | "time_target",
                    "distance_km": 12.5,
                    "lat": 43.95882,
                    "lon": 10.91863,
                    "label": "Aid Station 1",
                    "time_target_seconds": 3661,  // optional, only for time_target
                    "created_at": "ISO-8601"
                }
            ]
        }

    Returns:
        {
            "success": true,
            "annotations": [...]
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    prediction = Prediction.query.filter_by(id=prediction_id, user_id=user.id).first()
    if not prediction:
        return jsonify({'error': 'Prediction not found'}), 404

    data = request.get_json()
    annotations = data.get('annotations', [])

    # Validate structure
    for ann in annotations:
        required = ['id', 'type', 'distance_km', 'lat', 'lon', 'label']
        if not all(k in ann for k in required):
            return jsonify({'error': 'Invalid annotation structure - missing required fields'}), 400
        if ann['type'] not in ['aid_station', 'generic']:
            return jsonify({'error': 'Invalid annotation type'}), 400

    prediction.annotations = {'annotations': annotations}
    db.session.commit()

    return jsonify({'success': True, 'annotations': annotations})


@bp.route('/<int:prediction_id>/annotations', methods=['GET'])
def get_annotations(prediction_id):
    """Get annotations for a prediction.

    Returns:
        {
            "annotations": [...]
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    prediction = Prediction.query.filter_by(id=prediction_id, user_id=user.id).first()
    if not prediction:
        return jsonify({'error': 'Prediction not found'}), 404

    annotations = prediction.annotations or {'annotations': []}
    return jsonify(annotations)
