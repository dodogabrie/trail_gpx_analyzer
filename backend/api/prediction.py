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
from api.auth import verify_jwt
from services.prediction_service import PredictionService
from services.strava_service import StravaService
from services.cache_service import CacheService
from datetime import datetime, timedelta, timezone
from cryptography.fernet import InvalidToken
import requests

bp = Blueprint('prediction', __name__, url_prefix='/api/prediction')

# Initialize services (singletons)
prediction_service = None
cache_service = None


def get_prediction_service():
    """Get or create prediction service instance."""
    global prediction_service
    if prediction_service is None:
        prediction_service = PredictionService()
    return prediction_service


def get_cache_service():
    """Get or create cache service instance."""
    global cache_service
    if cache_service is None:
        cache_service = CacheService()
    return cache_service


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
        formatted.sort(key=lambda x: (x['recommended'], x['start_date']), reverse=True)

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

    debug = bool(current_app.config.get('DEBUG', False))
    stage = 'init'

    try:
        stage = 'get_cache_service'
        cache = get_cache_service()

        # Try to get cached streams (DB + filesystem)
        stage = 'get_cached_streams'
        streams = cache.get_cached_streams(user.id, activity_id)

        if streams:
            # Get activity from DB
            stage = 'get_cached_activity_db'
            strava_activity = StravaActivity.query.filter_by(
                user_id=user.id,
                strava_id=activity_id
            ).first()
            if not strava_activity:
                # If filesystem cache exists without a DB row, still proceed.
                dist = 0
                try:
                    dist = float(max(streams.get('distance') or [0]))
                except Exception:
                    dist = 0
                strava_activity = StravaActivity(
                    user_id=user.id,
                    strava_id=activity_id,
                    name=f'Activity {activity_id}',
                    distance=dist,
                    start_date=datetime.utcnow()
                )
                strava_activity.streams = streams
        else:
            # Download from Strava
            print(f"⚠️ No cached streams, downloading from Strava for activity {activity_id}")
            stage = 'get_strava_service'
            service = get_strava_service()

            # Ensure token is valid
            stage = 'get_valid_token'
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
            stage = 'download_streams'
            streams = service.download_streams(activity_id, access_token)

            # Fetch activity details
            stage = 'fetch_activity_details'
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(
                f'{service.API_URL}/activities/{activity_id}',
                headers=headers,
                timeout=20
            )
            response.raise_for_status()
            activity_data = response.json()

            # Cache streams (DB + filesystem)
            stage = 'cache_streams'
            strava_activity = cache.cache_streams(
                user_id=user.id,
                activity_id=activity_id,
                activity_name=activity_data.get('name') or f'Activity {activity_id}',
                distance=activity_data.get('distance') or 0,
                start_date=_parse_strava_datetime(activity_data.get('start_date')),
                streams=streams
            )

        # Calibrate using prediction service
        stage = 'calibrate_from_activity'
        pred_service = get_prediction_service()
        flat_pace, diagnostics = pred_service.calibrate_from_activity(strava_activity.streams)

        # Get anchor ratios from diagnostics
        anchor_ratios = diagnostics.get('anchor_ratios', {})

        # Compute anchor quality (sample counts)
        anchor_sample_counts = pred_service.compute_anchor_quality(strava_activity.streams, anchor_ratios)

        # Add sample counts to diagnostics
        diagnostics['anchor_sample_counts'] = anchor_sample_counts

        # Get global curve for frontend visualization
        global_curve = pred_service.get_global_curve_for_frontend()

        # Prepare calibration activity visualization data
        calibration_activity_streams = pred_service.prepare_calibration_activity_viz(strava_activity.streams)

        # Best-effort: generate + persist user fingerprint using calibration activity
        # plus the longest runs from the last ~3 months (for more stable endurance modeling).
        try:
            if not user.access_token or not user.refresh_token or not user.expires_at:
                diagnostics['fingerprint_skipped_reason'] = 'missing_strava_tokens'
                raise RuntimeError("Missing Strava tokens; cannot fetch additional activity streams for fingerprint")

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

            cached_activities = cache.get_cached_activities(user.id, max_age_hours=24)
            if cached_activities is None:
                # Cache a last-year list (same policy as /calibration-activities)
                after = service.get_timestamp_for_last_year()
                cached_activities = service.fetch_activities(access_token, after)
                cache.cache_activities(user.id, cached_activities, after_timestamp=after)

            selected_ids = _select_fingerprint_activity_ids(
                calibration_activity_id=int(activity_id),
                activities=cached_activities,
                months=3
            )

            meta_by_id = {}
            for a in cached_activities or []:
                if a.get('id') is None:
                    continue
                meta_by_id[int(a['id'])] = a

            streams_list = []
            used_ids = []
            for aid in selected_ids:
                # Prefer cached streams
                cached_streams = cache.get_cached_streams(user.id, aid)
                if cached_streams:
                    streams_list.append(cached_streams)
                    used_ids.append(aid)
                    continue

                meta = meta_by_id.get(aid)
                if not meta:
                    continue

                try:
                    downloaded = service.download_streams(aid, access_token)
                    if not downloaded:
                        continue
                    cache.cache_streams(
                        user_id=user.id,
                        activity_id=aid,
                        activity_name=meta.get('name') or f"Activity {aid}",
                        distance=meta.get('distance') or 0,
                        start_date=_parse_strava_datetime(meta.get('start_date')),
                        streams=downloaded
                    )
                    streams_list.append(downloaded)
                    used_ids.append(aid)
                except Exception as e:
                    print(f"⚠️ Fingerprint: failed streams download for {aid}: {repr(e)}")

            if len(streams_list) < 3:
                diagnostics['fingerprint_skipped_reason'] = 'insufficient_streams'
                diagnostics['fingerprint_activity_ids'] = used_ids
            else:
                fingerprint = pred_service.generate_user_fingerprint(streams_list)
                if fingerprint:
                    user.user_endurance_score = fingerprint['user_endurance_score']
                    user.user_recovery_rate = fingerprint['user_recovery_rate']
                    user.user_base_fitness = fingerprint['user_base_fitness']
                    user.fingerprint_calibrated_at = datetime.utcnow()
                    user.fingerprint_activity_count = len(streams_list)
                    db.session.commit()

                    diagnostics['user_fingerprint'] = fingerprint
                    diagnostics['fingerprint_activity_ids'] = used_ids
                else:
                    diagnostics['fingerprint_skipped_reason'] = 'fingerprint_extraction_failed'
                    diagnostics['fingerprint_activity_ids'] = used_ids
        except Exception as e:
            current_app.logger.exception("Fingerprint generation skipped during calibration")
            diagnostics.setdefault('fingerprint_skipped_reason', 'exception')
            if debug:
                diagnostics['fingerprint_error'] = repr(e)
            print(f"⚠️ Fingerprint generation skipped: {repr(e)}")

        return jsonify({
            'flat_pace_min_per_km': flat_pace,
            'anchor_ratios': {str(k): float(v) for k, v in anchor_ratios.items()},
            'diagnostics': diagnostics,
            'global_curve': global_curve,
            'calibration_activity_streams': calibration_activity_streams,
            'activity': {
                'id': strava_activity.strava_id,
                'name': strava_activity.name,
                'distance_km': round(strava_activity.distance / 1000, 2)
            }
        })

    except ValueError as e:
        return jsonify({'error': f'Calibration failed: {str(e)}', 'stage': stage}), 400
    except InvalidToken as e:
        current_app.logger.exception("Calibration failed: cannot decrypt stored Strava tokens")
        payload = {
            'error': 'Strava tokens are invalid (cannot decrypt). Please reconnect Strava.',
            'stage': stage
        }
        if debug:
            payload['details'] = repr(e)
        return jsonify(payload), 401
    except requests.exceptions.RequestException as e:
        current_app.logger.exception("Calibration error while calling Strava")
        payload = {
            'error': 'Calibration failed due to Strava request error',
            'stage': stage
        }
        if debug:
            status_code = getattr(getattr(e, 'response', None), 'status_code', None)
            response_text = getattr(getattr(e, 'response', None), 'text', None)
            payload['details'] = {
                'exception': repr(e),
                'status_code': status_code,
                'response_text': (response_text[:400] if isinstance(response_text, str) else None)
            }
        return jsonify(payload), 502
    except Exception as e:
        current_app.logger.exception("Calibration error")
        payload = {'error': 'Failed to calibrate', 'stage': stage}
        if debug:
            payload['details'] = repr(e)
        return jsonify(payload), 500


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


@bp.route('/generate-fingerprint', methods=['POST'])
def generate_fingerprint():
    """Generate user fingerprint from recent activities.
    
    Request body:
        {
            'limit': int (optional, default 3),
            'months': int (optional, default 3),
            'activity_ids': [int] (optional list of Strava IDs)
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get parameters
    data = request.get_json() or {}
    limit = int(data.get('limit', 3))
    months = int(data.get('months', 3))
    activity_ids = data.get('activity_ids') # Optional list of Strava IDs
    
    try:
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
            
        streams_list = []
        
        if activity_ids:
            # Fetch specific activities
            for aid in activity_ids:
                try:
                    streams = service.download_streams(aid, access_token)
                    if streams:
                        streams_list.append(streams)
                except Exception as e:
                    print(f"Failed to download stream for {aid}: {e}")
        else:
            # Fetch last ~N months and select the longest runs (more stable fingerprint)
            after = int((datetime.now(timezone.utc) - timedelta(days=int(months * 30))).timestamp())
            activities = service.fetch_activities(access_token, after)
            runs = [a for a in activities if a.get('type') == 'Run' and a.get('distance', 0) > 0]

            # Sort by distance descending
            runs.sort(key=lambda x: x.get('distance', 0), reverse=True)
            target_runs = runs[:limit]
            
            print(f"Fetching streams for {len(target_runs)} auto-selected activities...")
            
            for run in target_runs:
                try:
                    streams = service.download_streams(run['id'], access_token)
                    if streams:
                        streams_list.append(streams)
                except Exception as e:
                    print(f"Failed to download stream for {run['id']}: {e}")
        
        if len(streams_list) < 3:
             return jsonify({
                 'error': f'Need at least 3 valid activities with streams (found {len(streams_list)}). Try selecting more or longer activities (>10km).'
             }), 400
             
        # Generate fingerprint
        pred_service = get_prediction_service()
        fingerprint = pred_service.generate_user_fingerprint(streams_list)
        
        if not fingerprint:
            return jsonify({'error': 'Could not extract fingerprint from activities (insufficient data quality)'}), 400
            
        # Save to user
        user.user_endurance_score = fingerprint['user_endurance_score']
        user.user_recovery_rate = fingerprint['user_recovery_rate']
        user.user_base_fitness = fingerprint['user_base_fitness']
        user.fingerprint_calibrated_at = datetime.utcnow()
        user.fingerprint_activity_count = len(streams_list)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Fingerprint generated successfully',
            'fingerprint': fingerprint
        })
        
    except InvalidToken:
        return jsonify({'error': 'Strava tokens are invalid (cannot decrypt). Please reconnect Strava.'}), 401
    except Exception as e:
        current_app.logger.error(f"Fingerprint generation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to generate fingerprint: {str(e)}'}), 500


@bp.route('/<int:prediction_id>', methods=['GET'])
def get_prediction(prediction_id):
    """Get a stored prediction."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    prediction = Prediction.query.filter_by(id=prediction_id, user_id=user.id).first()
    if not prediction:
        return jsonify({'error': 'Prediction not found'}), 404

    return jsonify(prediction.to_dict())


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
            cum_time_at_seg_start.append(cum_time_at_seg_start[-1] + s['time_seconds'])
            
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
            seg_duration = seg['time_seconds']
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
@bp.route('/cache/status', methods=['GET'])
def get_cache_status():
    """Get cache status for current user.

    Response:
        {
            'activity_list_cache': {
                'exists': bool,
                'fetched_at': str,
                'activity_count': int,
                'is_stale': bool
            },
            'cached_streams': [
                {
                    'activity_id': int,
                    'activity_name': str,
                    'downloaded_at': str,
                    'has_filesystem_cache': bool
                }
            ]
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    cache = get_cache_service()

    # Check activity list cache
    list_cache = StravaActivityCache.query.filter_by(user_id=user.id).first()

    activity_list_status = None
    if list_cache:
        activity_list_status = {
            'exists': True,
            'fetched_at': list_cache.fetched_at.isoformat(),
            'activity_count': list_cache.activity_count,
            'is_stale': list_cache.is_stale()
        }
    else:
        activity_list_status = {'exists': False}

    # Check cached streams
    cached_streams = []
    stream_activities = StravaActivity.query.filter_by(user_id=user.id).all()

    for activity in stream_activities:
        cache_path = cache.get_stream_cache_path(user.id, activity.strava_id)
        cached_streams.append({
            'activity_id': activity.strava_id,
            'activity_name': activity.name,
            'downloaded_at': activity.downloaded_at.isoformat(),
            'has_db_cache': activity.streams is not None,
            'has_filesystem_cache': cache_path.exists()
        })

    return jsonify({
        'activity_list_cache': activity_list_status,
        'cached_streams': cached_streams,
        'total_cached_streams': len(cached_streams)
    })


@bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear caches for current user.

    Request body (optional):
        {
            'clear_activity_list': bool (default true),
            'clear_streams': bool (default false)
        }

    Response:
        {
            'cleared_activity_list': bool,
            'cleared_streams_count': int
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    clear_activity_list = data.get('clear_activity_list', True)
    clear_streams = data.get('clear_streams', False)

    result = {
        'cleared_activity_list': False,
        'cleared_streams_count': 0
    }

    # Clear activity list cache
    if clear_activity_list:
        deleted = StravaActivityCache.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        result['cleared_activity_list'] = deleted > 0

    # Clear streams cache
    if clear_streams:
        deleted = StravaActivity.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        result['cleared_streams_count'] = deleted

        # Also clear filesystem cache
        cache = get_cache_service()
        user_streams_dir = cache.streams_dir / str(user.id)
        if user_streams_dir.exists():
            import shutil
            shutil.rmtree(user_streams_dir)
            user_streams_dir.mkdir()

    return jsonify(result)


@bp.route('/predict', methods=['POST'])
def predict():
    """Predict time for a GPX route using calibrated flat pace.

    Request body:
        {
            'gpx_id': int,
            'flat_pace_min_per_km': float,
            'cached_activities': list (optional) - Pre-fetched activities to avoid Strava API call
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
    anchor_ratios = data.get('anchor_ratios') # Optional anchor ratios for warping
    cached_activities = data.get('cached_activities') # Optional pre-fetched activities

    print(f"GPX ID: {gpx_id}")
    print(f"Flat Pace: {flat_pace} min/km")
    if anchor_ratios:
        print(f"Received {len(anchor_ratios)} anchors for personalization")
    if cached_activities:
        print(f"Using {len(cached_activities)} cached activities (skip Strava fetch)")

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
        
        # Get user fingerprint if available
        user_fingerprint = None
        if user.user_endurance_score is not None:
            user_fingerprint = {
                'user_endurance_score': user.user_endurance_score,
                'user_recovery_rate': user.user_recovery_rate,
                'user_base_fitness': user.user_base_fitness
            }
            print(f"✓ Using stored user fingerprint: {user_fingerprint}")
        else:
            print("ℹ️ No user fingerprint found, using defaults")

        # Generate prediction
        print("\n[2/4] Generating prediction...")
        print(f"  - Converting GPX to route profile...")
        prediction = pred_service.predict_route_time(
            gpx_file.data, 
            flat_pace,
            user_fingerprint=user_fingerprint,
            anchor_ratios=anchor_ratios
        )
        print(f"✓ Prediction complete: {prediction['total_time_formatted']}")

        # Find similar activities
        print("\n[3/4] Finding similar activities...")

        if cached_activities:
            # Use cached activities from frontend
            print(f"  - Using {len(cached_activities)} cached activities (no Strava fetch)")
            activities = cached_activities
        else:
            # Fetch from Strava
            print("  - No cached activities, fetching from Strava...")
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
            activities = service.fetch_activities(access_token, after)
            print(f"  - Found {len(activities)} activities")

        print("\n[4/4] Filtering similar activities...")
        similar = pred_service.find_similar_activities(gpx_file.data, activities)
        print(f"✓ Found {len(similar)} similar activities")

        print(f"    → Elevation gain: {prediction['statistics']['total_elevation_gain_m']:.1f} m")

        # Save prediction
        print(f"    → Saving prediction to database...")
        db_prediction = Prediction(
            user_id=user.id,
            gpx_file_id=gpx_file.id,
            flat_pace=flat_pace,
            user_fingerprint=user_fingerprint,
            anchor_ratios=anchor_ratios,
            total_time_seconds=prediction['total_time_seconds'],
            predicted_segments=prediction['segments']
        )
        db.session.add(db_prediction)
        db.session.commit()
        print(f"    ✓ Prediction saved (ID: {db_prediction.id})")

        return jsonify({
            'prediction_id': db_prediction.id,
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
