"""Hybrid prediction API endpoints.

Unified prediction API using tiered approach:
- Tier 1: Physics baseline
- Tier 2: Learned parameters
- Tier 3: ML residual corrections
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify, current_app
from models import User, GPXFile
from database import db
from api.utils import get_current_user
from api.validation import (
    validate_predict_request,
    validate_gpx_points,
    create_error_response,
    log_validation_error
)
from services.hybrid_prediction_service import HybridPredictionService
from services.parameter_learning_service import ParameterLearningService
from services.user_residual_service import UserResidualService
from services.residual_ml_service import ResidualMLService
from config.hybrid_config import get_logger

logger = get_logger(__name__)

bp = Blueprint('hybrid', __name__, url_prefix='/api/hybrid')


@bp.route('/tier-status', methods=['GET'])
def get_tier_status():
    """Get user's current prediction tier and progress.

    Returns:
        {
            "current_tier": "TIER_2_PARAMETER_LEARNING",
            "activity_count": 8,
            "next_tier": "TIER_3_RESIDUAL_ML",
            "activities_needed_for_next_tier": 7,
            "progress_to_next_tier_pct": 53.3,
            "has_learned_params": true,
            "last_trained": "2025-12-26T10:30:00",
            "confidence_level": "MEDIUM_HIGH"
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    hybrid_service = HybridPredictionService()
    status = hybrid_service.get_user_tier_status(user.id)

    return jsonify(status)


@bp.route('/predict', methods=['POST'])
def predict():
    """Unified hybrid prediction endpoint.

    Body:
        {
            "gpx_id": 123,
            "force_tier": "parameter_learning",  // Optional: physics, parameter_learning, residual_ml
            "include_diagnostics": true,  // Optional: include detailed diagnostics
            "effort": "training"  // Optional: race, training, recovery (default: training)
        }

    Returns:
        {
            "prediction_id": 456,
            "prediction": {
                "total_time_seconds": 7234,
                "total_time_formatted": "2:00:34",
                "confidence_interval": {...},
                "segments": [...],
                "statistics": {...}
            },
            "metadata": {
                "tier": "TIER_2_PARAMETER_LEARNING",
                "method": "physics_personalized",
                "confidence": "MEDIUM_HIGH",
                "activities_used": 8,
                "description": "Physics model with personalized parameters..."
            },
            "diagnostics": {...}  // If include_diagnostics=true
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data:
        return create_error_response({'request': 'Request body must be JSON'})

    # Validate request data
    is_valid, errors = validate_predict_request(data)
    if not is_valid:
        log_validation_error('/api/hybrid/predict', errors)
        return create_error_response(errors)

    gpx_id = data['gpx_id']
    force_tier = data.get('force_tier')
    include_diagnostics = data.get('include_diagnostics', False)
    effort = data.get('effort', 'training')  # Default to training effort

    # Get GPX file
    gpx_file = GPXFile.query.filter_by(id=gpx_id, user_id=user.id).first()
    if not gpx_file or not gpx_file.data:
        return jsonify({'error': 'GPX file not found'}), 404

    points = gpx_file.data.get('points', [])

    # Validate GPX points structure
    is_valid, error_msg = validate_gpx_points(points)
    if not is_valid:
        logger.warning(f"Invalid GPX points for file {gpx_id}: {error_msg}")
        return jsonify({'error': error_msg}), 400

    try:
        # Run hybrid prediction
        hybrid_service = HybridPredictionService()
        result = hybrid_service.predict(
            user_id=user.id,
            gpx_points=points,
            force_tier=force_tier,
            include_diagnostics=include_diagnostics,
            effort=effort
        )

        if 'error' in result:
            return jsonify(result), 500

        # Extract metadata and format response
        metadata = result.get('metadata', {})
        segments = result.get('segments', [])

        # Extract flat pace from user params
        flat_pace = None
        if 'user_params' in result:
            v_flat = result['user_params'].get('v_flat')
            if v_flat:
                flat_pace = (1000.0 / v_flat) / 60.0  # Convert m/s to min/km
        elif 'diagnostics' in result and 'learned_params' in result['diagnostics']:
            v_flat = result['diagnostics']['learned_params'].get('v_flat')
            if v_flat:
                flat_pace = (1000.0 / v_flat) / 60.0  # Convert m/s to min/km
        if flat_pace is None:
            flat_pace = 6.0  # Default

        # Calculate elevation gain from segments
        total_elevation_gain = 0.0
        if segments:
            for seg in segments:
                if seg.get('grade', 0) > 0:  # Only uphill
                    total_elevation_gain += seg.get('length_m', 0) * seg.get('grade', 0)

        # Format total time
        total_time_sec = result['total_time_seconds']
        h = int(total_time_sec // 3600)
        m = int((total_time_sec % 3600) // 60)
        s = int(total_time_sec % 60)
        total_time_formatted = f"{h:02d}:{m:02d}:{s:02d}"

        # Confidence interval - tier-specific
        tier = metadata.get('tier', 'TIER_1_PHYSICS')

        if tier == 'TIER_3_RESIDUAL_ML' and 'confidence_interval' in result:
            # Use variance-based CI from ML model (proper statistical CI)
            ci_data = result['confidence_interval']
            ci_lower = ci_data.get('lower_seconds', total_time_sec * 0.94)
            ci_upper = ci_data.get('upper_seconds', total_time_sec * 1.06)
        elif tier == 'TIER_2_PARAMETER_LEARNING':
            # Moderate uncertainty - personalized params but no ML
            ci_lower = total_time_sec * 0.92
            ci_upper = total_time_sec * 1.08
        else:
            # Tier 1 - highest uncertainty (default params)
            ci_lower = total_time_sec * 0.88
            ci_upper = total_time_sec * 1.12

        ci_lower_formatted = f"{int(ci_lower//3600):02d}:{int((ci_lower%3600)//60):02d}:{int(ci_lower%60):02d}"
        ci_upper_formatted = f"{int(ci_upper//3600):02d}:{int((ci_upper%3600)//60):02d}:{int(ci_upper%60):02d}"

        # Transform segments to frontend format (MapView expects end_km, avg_grade_percent, etc.)
        formatted_segments = []
        cumulative_time = 0
        for i, seg in enumerate(segments):
            cumulative_time += seg.get('time_s', 0)

            # Calculate end_km from distance_m + length_m
            distance_m = seg.get('distance_m', 0)
            length_m = seg.get('length_m', 0)
            end_km = (distance_m + length_m) / 1000.0
            start_km = distance_m / 1000.0

            # Format cumulative time
            hours = int(cumulative_time // 3600)
            mins = int((cumulative_time % 3600) // 60)
            secs = int(cumulative_time % 60)
            time_formatted = f"{hours}:{mins:02d}:{secs:02d}"

            # Convert grade to percentage
            grade = seg.get('grade', 0)
            avg_grade_percent = grade * 100

            # Get pace
            avg_pace_min_per_km = seg.get('pace_min_km', 6.0)

            formatted_segments.append({
                'distance_m': distance_m,
                'length_m': length_m,
                'grade': grade,
                'time_s': seg.get('time_s', 0),
                'pace_min_km': avg_pace_min_per_km,
                # Frontend-expected fields
                'start_km': round(start_km, 2),
                'end_km': round(end_km, 2),
                'avg_grade_percent': round(avg_grade_percent, 1),
                'avg_pace_min_per_km': round(avg_pace_min_per_km, 2),
                'time_formatted': time_formatted
            })

        # Format prediction response to match frontend expectations
        formatted_prediction = {
            'total_time_seconds': total_time_sec,
            'total_time_formatted': total_time_formatted,
            'confidence_interval': {
                'lower_seconds': ci_lower,
                'upper_seconds': ci_upper,
                'lower_formatted': ci_lower_formatted,
                'upper_formatted': ci_upper_formatted
            },
            'segments': formatted_segments,
            'raw_segments': formatted_segments,
            'statistics': {
                'total_distance_km': formatted_segments[-1]['end_km'] if formatted_segments else 0,
                'total_elevation_gain_m': total_elevation_gain,
                'flat_pace_min_per_km': flat_pace
            },
            'metadata': metadata  # Add metadata to prediction object
        }

        # Save prediction to database
        from models import Prediction
        db_prediction = Prediction(
            user_id=user.id,
            gpx_file_id=gpx_file.id,
            flat_pace=flat_pace,
            user_fingerprint={
                'tier': metadata.get('tier'),
                'method': metadata.get('method'),
                'activities_used': metadata.get('activities_used')
            },
            total_time_seconds=total_time_sec,
            predicted_segments=formatted_segments
        )
        db.session.add(db_prediction)
        db.session.commit()

        return jsonify({
            'prediction_id': db_prediction.id,
            'prediction': formatted_prediction,
            'metadata': metadata,
            'diagnostics': result.get('diagnostics') if include_diagnostics else None
        })

    except Exception as e:
        logger.exception(f"Error in API endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/training-activities', methods=['GET'])
def get_training_activities():
    """Get list of downloaded activities with training status.

    Returns list of activities showing which are included/excluded from training.
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    from models import UserActivityResidual
    activities = UserActivityResidual.query.filter_by(user_id=user.id).order_by(
        UserActivityResidual.activity_date.desc()
    ).all()

    activity_list = []
    for act in activities:
        activity_list.append({
            'id': act.id,
            'activity_id': act.activity_id,
            'activity_date': act.activity_date.isoformat(),
            'distance_km': act.total_distance_km,
            'elevation_gain_m': act.total_elevation_gain_m,
            'activity_type': act.activity_type,
            'segment_count': act.segment_count,
            'excluded_from_training': act.excluded_from_training,
            'recency_weight': act.recency_weight
        })

    return jsonify({
        'activities': activity_list,
        'total': len(activity_list),
        'included_count': sum(1 for a in activity_list if not a['excluded_from_training']),
        'excluded_count': sum(1 for a in activity_list if a['excluded_from_training'])
    })


@bp.route('/training-activities/<int:residual_id>/toggle', methods=['POST'])
def toggle_activity_training(residual_id):
    """Toggle whether an activity is included in training.

    Args:
        residual_id: UserActivityResidual ID
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    from models import UserActivityResidual
    residual = UserActivityResidual.query.filter_by(id=residual_id, user_id=user.id).first()

    if not residual:
        return jsonify({'error': 'Activity not found'}), 404

    # Toggle exclusion
    residual.excluded_from_training = not residual.excluded_from_training
    db.session.commit()

    logger.info(f"Activity {residual.activity_id} {'excluded from' if residual.excluded_from_training else 'included in'} training for user {user.id}")

    return jsonify({
        'success': True,
        'activity_id': residual.activity_id,
        'excluded_from_training': residual.excluded_from_training
    })


@bp.route('/train-ml-model', methods=['POST'])
def train_ml_model():
    """Manually trigger GBM model training for Tier 3.

    Requires 15+ activities with residuals.

    Returns:
        {
            "success": true,
            "n_activities_used": 18,
            "n_segments_trained": 2340,
            "metrics": {
                "train_mae": 0.032,
                "val_mae": 0.041,
                "train_r2": 0.78,
                "val_r2": 0.72
            },
            "feature_importance": {
                "grade_mean": 0.35,
                "cum_distance_km": 0.22,
                ...
            }
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        ml_service = ResidualMLService()

        # Check if user has enough data
        if not ml_service.should_train(user.id):
            residual_service = UserResidualService()
            training_data = residual_service.get_user_training_data(user.id, min_activities=0)
            return jsonify({
                'error': f'Insufficient data for ML training. You have {len(training_data)} activities, need at least 15.'
            }), 400

        # Train GBM model
        trained_model = ml_service.train_user_model(user.id)

        if not trained_model:
            return jsonify({'error': 'Training failed'}), 500

        return jsonify({
            'success': True,
            'n_activities_used': trained_model.n_activities_used,
            'n_segments_trained': trained_model.n_segments_trained,
            'metrics': trained_model.metrics,
            'feature_importance': trained_model.feature_importance,
            'residual_variance': trained_model.residual_variance,
            'confidence_level': trained_model.confidence_level,
            'last_trained': trained_model.last_trained.isoformat()
        })

    except Exception as e:
        logger.exception(f"Error in API endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500
