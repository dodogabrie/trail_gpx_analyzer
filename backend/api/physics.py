from flask import Blueprint, request, jsonify, current_app
from services.physics_prediction_service import PhysicsPredictionService
from services.strava_service import StravaService
from services.cache_service import CacheService
from models import User, GPXFile, StravaActivity, Prediction
from database import db
from api.auth import verify_jwt

bp = Blueprint('physics', __name__, url_prefix='/api/physics')

# Service Singleton
_physics_service = None
def get_physics_service():
    global _physics_service
    if _physics_service is None:
        _physics_service = PhysicsPredictionService()
    return _physics_service

def get_strava_service():
    return StravaService(
        current_app.config['STRAVA_CLIENT_ID'],
        current_app.config['STRAVA_CLIENT_SECRET'],
        current_app.config['STRAVA_REDIRECT_URI']
    )

def get_cache_service():
    return CacheService()

def get_current_user():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        # Dev fallback
        if current_app.debug:
            user = User.query.first()
            if user: return user
        return None
        
    token = auth_header.split(' ')[1]
    user_id = verify_jwt(token)
    if not user_id: return None
    return User.query.get(user_id)

@bp.route('/calibrate', methods=['POST'])
def calibrate():
    """
    Calibrate from a single activity (ML-compatible format).

    Body: { "activity_id": 123 }

    Returns ML-compatible format with flat_pace_min_per_km
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    activity_id = data.get('activity_id')

    if not activity_id:
        return jsonify({'error': 'activity_id required'}), 400

    strava_service = get_strava_service()
    cache_service = get_cache_service()
    physics_service = get_physics_service()

    # Refresh token if needed
    if user.access_token:
        try:
            access_token, refresh_token, expires_at = strava_service.get_valid_token(
                user.access_token, user.refresh_token, user.expires_at
            )
            if access_token != user.access_token:
                user.access_token = access_token
                user.refresh_token = refresh_token
                user.expires_at = expires_at
                db.session.commit()
        except Exception:
            return jsonify({'error': 'Strava auth failed'}), 401
    else:
        return jsonify({'error': 'User not connected to Strava'}), 401

    # Fetch streams for the activity
    streams = cache_service.get_cached_streams(user.id, activity_id)
    if not streams:
        try:
            streams = strava_service.download_streams(activity_id, user.access_token)
        except Exception as e:
            return jsonify({'error': f'Failed to fetch activity streams: {str(e)}'}), 400

    if not streams:
        return jsonify({'error': 'No streams available for this activity'}), 400

    # Run Calibration
    try:
        params = physics_service.calibrate([streams])

        # Convert v_flat (m/s) to flat_pace (min/km) for ML compatibility
        v_flat = params['v_flat']
        flat_pace_min_per_km = (1000 / v_flat) / 60

        # Store params in user session/profile
        user.physics_params = params
        db.session.commit()

        # Return ML-compatible format
        return jsonify({
            'flat_pace_min_per_km': flat_pace_min_per_km,
            'anchor_ratios': {
                '-30': params['k_terrain_down'],  # Rough mapping
                '-20': params['k_terrain_down'],
                '-10': params['k_terrain_down'],
                '0': params['k_terrain_flat'],
                '10': params['k_up'],
                '20': params['k_up'],
                '30': params['k_up']
            },
            'diagnostics': {
                'method': 'physics_model',
                'params': params
            },
            'activity': {
                'id': activity_id,
                'name': f'Activity {activity_id}',
                'distance_km': streams.get('distance', [0])[-1] / 1000 if streams.get('distance') else 0
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@bp.route('/predict', methods=['POST'])
def predict():
    """
    Predict route time using Physics Model (ML-compatible format).

    Body: {
        "gpx_id": 123,
        "flat_pace_min_per_km": 5.0,
        "anchor_ratios": {...},  # Optional
        "cached_activities": [...],  # Optional
        "split_level": 5  # Optional, 1-10, controls segment granularity (default: 5)
    }

    Returns exact ML format for frontend compatibility.
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    gpx_id = data.get('gpx_id')
    flat_pace_min_per_km = data.get('flat_pace_min_per_km')
    cached_activities = data.get('cached_activities', [])
    split_level = data.get('split_level', 5)  # 1-10 range, default = 5

    print(f"[DEBUG] Received split_level from frontend: {split_level}")

    if not gpx_id:
        return jsonify({'error': 'gpx_id required'}), 400

    if not flat_pace_min_per_km:
        return jsonify({'error': 'flat_pace_min_per_km required'}), 400

    gpx_file = GPXFile.query.filter_by(id=gpx_id, user_id=user.id).first()
    if not gpx_file or not gpx_file.data:
        return jsonify({'error': 'GPX not found'}), 404

    points = gpx_file.data.get('points', [])

    # Get physics params from user profile or reconstruct from flat pace
    if hasattr(user, 'physics_params') and user.physics_params:
        user_params = user.physics_params
    else:
        # Fallback: use defaults with calibrated flat pace
        v_flat = 1000 / (flat_pace_min_per_km * 60)  # Convert min/km to m/s
        user_params = {
            'v_flat': v_flat,
            'k_up': 1.0,
            'k_tech': 1.0,
            'a_param': 3.0,
            'k_terrain_up': 1.08,
            'k_terrain_down': 1.12,
            'k_terrain_flat': 1.05
        }

    physics_service = get_physics_service()
    result = physics_service.predict(points, user_params, user_id=user.id)

    if 'error' in result:
        return jsonify(result), 500

    # Transform to ML-compatible format
    total_time_sec = result['total_time_seconds']

    # Format time as HH:MM:SS
    hours = int(total_time_sec // 3600)
    minutes = int((total_time_sec % 3600) // 60)
    seconds = int(total_time_sec % 60)
    total_time_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"

    # Confidence interval (physics model is deterministic, so use ±5%)
    ci_lower = total_time_sec * 0.95
    ci_upper = total_time_sec * 1.05
    ci_lower_formatted = f"{int(ci_lower//3600)}:{int((ci_lower%3600)//60):02d}:{int(ci_lower%60):02d}"
    ci_upper_formatted = f"{int(ci_upper//3600)}:{int((ci_upper%3600)//60):02d}:{int(ci_upper%60):02d}"

    # First, group 50m physics segments into 200m segments (like ML prediction segments)
    def aggregate_to_200m_segments(segments):
        """Aggregate 50m segments into 200m segments to match ML model."""
        if not segments:
            return []

        aggregated = []
        current_batch = []
        batch_start_dist = 0

        for seg in segments:
            if not current_batch:
                batch_start_dist = seg['distance_m']
                current_batch = [seg]
            else:
                # Check if adding this segment would exceed 200m
                batch_length = seg['distance_m'] + seg['length_m'] - batch_start_dist
                if batch_length >= 200:
                    # Finalize current batch
                    total_time = sum(s['time_s'] for s in current_batch)
                    total_dist = sum(s['length_m'] for s in current_batch)
                    avg_grade = sum(s['grade'] * s['length_m'] for s in current_batch) / total_dist if total_dist > 0 else 0

                    aggregated.append({
                        'distance_m': batch_start_dist,
                        'length_m': total_dist,
                        'grade': avg_grade,
                        'time_s': total_time,
                        'pace_min_km': (total_time / (total_dist / 1000)) / 60 if total_dist > 0 else 0
                    })
                    # Start new batch
                    batch_start_dist = seg['distance_m']
                    current_batch = [seg]
                else:
                    current_batch.append(seg)

        # Add final batch
        if current_batch:
            total_time = sum(s['time_s'] for s in current_batch)
            total_dist = sum(s['length_m'] for s in current_batch)
            avg_grade = sum(s['grade'] * s['length_m'] for s in current_batch) / total_dist if total_dist > 0 else 0

            aggregated.append({
                'distance_m': batch_start_dist,
                'length_m': total_dist,
                'grade': avg_grade,
                'time_s': total_time,
                'pace_min_km': (total_time / (total_dist / 1000)) / 60 if total_dist > 0 else 0
            })

        return aggregated

    # Then apply gradient-based grouping on 200m segments
    def group_segments_by_gradient(segments, gradient_threshold=5.0, max_segment_length=5000, sign_change_min_grade=2.0):
        """Group segments by grade changes.

        Args:
            segments: List of 200m segments
            gradient_threshold: Grade change threshold in % (e.g., 5.0 means 5%)
            max_segment_length: Max length of a group in meters
            sign_change_min_grade: Minimum grade % to trigger sign change split

        Returns:
            List of grouped segments
        """
        if not segments:
            return []

        grouped = []
        current_group = [segments[0]]
        current_start = segments[0]['distance_m']

        for i in range(1, len(segments)):
            prev = segments[i-1]
            curr = segments[i]

            prev_grade = prev['grade'] * 100
            curr_grade = curr['grade'] * 100

            # Split conditions:
            # 1. Grade change > threshold
            # 2. Sign change (climb→descent or vice versa) - only if grades are significant
            # 3. Segment would be too long
            grade_change = abs(curr_grade - prev_grade)
            sign_change = (prev_grade * curr_grade < 0) and (abs(prev_grade) > sign_change_min_grade or abs(curr_grade) > sign_change_min_grade)
            current_length = curr['distance_m'] - current_start

            should_split = False
            split_reason = None

            if grade_change > gradient_threshold:
                should_split = True
                split_reason = f"grade_change ({grade_change:.1f}% > {gradient_threshold}%)"
            elif sign_change:
                should_split = True
                split_reason = f"sign_change ({prev_grade:.1f}% -> {curr_grade:.1f}%)"
            elif current_length > max_segment_length:
                should_split = True
                split_reason = f"length ({current_length:.0f}m > {max_segment_length}m)"

            if should_split:
                # Finalize current group
                grouped.append(current_group)
                current_group = [curr]
                current_start = curr['distance_m']
            else:
                current_group.append(curr)

        # Add final group
        if current_group:
            grouped.append(current_group)

        return grouped

    # Aggregate to 200m segments for frontend display
    print(f"[DEBUG] Raw 50m physics segments: {len(result['segments'])}")
    segments_200m = aggregate_to_200m_segments(result['segments'])
    print(f"[DEBUG] Aggregated to {len(segments_200m)} 200m segments")

    # Convert to frontend format (without grouping - grouping done on frontend)
    raw_segments_for_frontend = []
    for seg in segments_200m:
        raw_segments_for_frontend.append({
            'distance_m': seg['distance_m'],
            'length_m': seg['length_m'],
            'grade': seg['grade'],
            'time_s': seg['time_s'],
            'pace_min_km': seg['pace_min_km']
        })

    # For backward compatibility, still create default grouped segments
    # Using medium split level (3 out of 1-3)
    default_gradient_threshold = 3.0  # Medium sensitivity
    default_max_length = 5000
    default_sign_change_min = 3.0

    segment_groups = group_segments_by_gradient(segments_200m, default_gradient_threshold, default_max_length, default_sign_change_min)
    print(f"[DEBUG] Default grouping into {len(segment_groups)} display splits")

    ml_segments = []
    cumulative_time = 0

    for split_num, group in enumerate(segment_groups, 1):
        group_time = sum(s['time_s'] for s in group)
        group_dist = sum(s['length_m'] for s in group)
        avg_grade = sum(s['grade'] for s in group) / len(group)
        avg_pace = group_time / (group_dist / 1000) / 60

        cumulative_time += group_time
        start_km = group[0]['distance_m'] / 1000
        end_km = (group[-1]['distance_m'] + group[-1]['length_m']) / 1000

        hours = int(cumulative_time // 3600)
        mins = int((cumulative_time % 3600) // 60)
        secs = int(cumulative_time % 60)

        if avg_grade > 0.08:
            terrain = "Steep Climb"
        elif avg_grade > 0.03:
            terrain = "Climb"
        elif avg_grade > -0.03:
            terrain = "Flat"
        elif avg_grade > -0.08:
            terrain = "Descent"
        else:
            terrain = "Steep Descent"

        ml_segments.append({
            'split_number': split_num,
            'segment_km': int(end_km),
            'start_km': round(start_km, 2),
            'end_km': round(end_km, 2),
            'avg_grade_percent': round(avg_grade * 100, 1),
            'avg_pace_min_per_km': round(avg_pace, 2),
            'time_formatted': f"{hours}:{mins:02d}:{secs:02d}",
            'terrain': terrain,
            'distance_m': round(group_dist, 1)
        })

    # Calculate elevation gain from SMOOTHED/RESAMPLED data (like ML model)
    ELEVATION_THRESHOLD_M = 0.5
    total_elevation_gain = 0

    if 'resampled_elevations' in result:
        elevations = result['resampled_elevations']
        elev_gain = sum(max(0, elevations[i] - elevations[i-1])
                       for i in range(1, len(elevations))
                       if abs(elevations[i] - elevations[i-1]) >= ELEVATION_THRESHOLD_M)
        total_elevation_gain = float(elev_gain)
    else:
        # Fallback to raw points (not ideal)
        if points and len(points) > 1:
            for i in range(1, len(points)):
                elev_change = points[i].get('elevation', 0) - points[i-1].get('elevation', 0)
                if abs(elev_change) >= ELEVATION_THRESHOLD_M and elev_change > 0:
                    total_elevation_gain += elev_change

    # Build ML-compatible response
    prediction = {
        'total_time_seconds': total_time_sec,
        'total_time_formatted': total_time_formatted,
        'confidence_interval': {
            'lower_seconds': ci_lower,
            'upper_seconds': ci_upper,
            'lower_formatted': ci_lower_formatted,
            'upper_formatted': ci_upper_formatted
        },
        'segments': ml_segments,  # Default grouped segments for display
        'raw_segments': raw_segments_for_frontend,  # Raw 200m segments for frontend grouping
        'statistics': {
            'total_distance_km': result['segments'][-1]['distance_m'] / 1000 if result['segments'] else 0,
            'total_elevation_gain_m': float(total_elevation_gain),
            'avg_grade_percent': sum(s['avg_grade_percent'] for s in ml_segments) / len(ml_segments) if ml_segments else 0,
            'flat_pace_min_per_km': flat_pace_min_per_km
        }
    }

    # Find similar activities (use cached if provided)
    from services.prediction_service import PredictionService
    pred_service = PredictionService()
    similar_activities = pred_service.find_similar_activities(gpx_file.data, cached_activities)

    # Save prediction to database
    db_prediction = Prediction(
        user_id=user.id,
        gpx_file_id=gpx_file.id,
        flat_pace=flat_pace_min_per_km,
        user_fingerprint={'physics_params': user_params},
        total_time_seconds=total_time_sec,
        predicted_segments=ml_segments
    )
    db.session.add(db_prediction)
    db.session.commit()

    return jsonify({
        'prediction_id': db_prediction.id,
        'prediction': prediction,
        'similar_activities': similar_activities[:5]
    })
