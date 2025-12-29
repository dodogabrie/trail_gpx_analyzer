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
from api.auth import verify_jwt
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


def get_current_user():
    """Get current user from JWT token."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        # Dev fallback
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
            "include_diagnostics": true  // Optional: include detailed diagnostics
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
            include_diagnostics=include_diagnostics
        )

        if 'error' in result:
            return jsonify(result), 500

        # Save prediction to database
        from models import Prediction

        # Extract metadata for storage
        metadata = result.get('metadata', {})
        flat_pace = None

        # Try to extract flat pace from user params
        if 'diagnostics' in result and 'learned_params' in result['diagnostics']:
            v_flat = result['diagnostics']['learned_params'].get('v_flat')
            if v_flat:
                flat_pace = (1000.0 / v_flat) / 60.0  # Convert m/s to min/km

        db_prediction = Prediction(
            user_id=user.id,
            gpx_file_id=gpx_file.id,
            flat_pace=flat_pace,
            user_fingerprint={
                'tier': metadata.get('tier'),
                'method': metadata.get('method'),
                'activities_used': metadata.get('activities_used')
            },
            total_time_seconds=result['total_time_seconds'],
            predicted_segments=result.get('segments', [])
        )
        db.session.add(db_prediction)
        db.session.commit()

        return jsonify({
            'prediction_id': db_prediction.id,
            'prediction': result,
            'metadata': metadata,
            'diagnostics': result.get('diagnostics') if include_diagnostics else None
        })

    except Exception as e:
        logger.exception(f"Error in API endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/train-params', methods=['POST'])
def train_params():
    """Manually trigger parameter training for user.

    Useful for forcing retraining after adding new activities.

    Returns:
        {
            "success": true,
            "learned_params": {
                "v_flat": 3.25,
                "k_up": 1.15,
                ...
            },
            "n_activities_used": 8,
            "optimization_score": 0.042,
            "confidence_level": "MEDIUM_HIGH"
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        parameter_service = ParameterLearningService()

        # Check if user has enough data
        if not parameter_service.should_train(user.id):
            residual_service = UserResidualService()
            training_data = residual_service.get_user_training_data(user.id, min_activities=0)
            return jsonify({
                'error': f'Insufficient data for parameter learning. You have {len(training_data)} activities, need at least 5.'
            }), 400

        # Train parameters
        learned_params = parameter_service.train_user_params(user.id)

        if not learned_params:
            return jsonify({'error': 'Training failed'}), 500

        return jsonify({
            'success': True,
            'learned_params': learned_params.to_dict(),
            'n_activities_used': learned_params.n_activities_used,
            'optimization_score': learned_params.optimization_score,
            'confidence_level': learned_params.confidence_level,
            'last_trained': learned_params.last_trained.isoformat()
        })

    except Exception as e:
        logger.exception(f"Error in API endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@bp.route('/training-data-summary', methods=['GET'])
def training_data_summary():
    """Get summary of user's training data.

    Returns:
        {
            "total_activities": 8,
            "total_segments": 1240,
            "date_range": {
                "oldest": "2024-06-15T10:00:00",
                "newest": "2025-12-20T08:30:00"
            },
            "tier_eligible": "TIER_2_PARAMETER_LEARNING"
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    residual_service = UserResidualService()
    training_data = residual_service.get_user_training_data(user.id, min_activities=0)

    if not training_data:
        return jsonify({
            'total_activities': 0,
            'total_segments': 0,
            'tier_eligible': 'TIER_1_PHYSICS'
        })

    total_segments = sum(len(r.segments) for r in training_data)
    oldest = min(r.activity_date for r in training_data)
    newest = max(r.activity_date for r in training_data)

    # Determine tier eligibility
    hybrid_service = HybridPredictionService()
    tier_status = hybrid_service.get_user_tier_status(user.id)

    return jsonify({
        'total_activities': len(training_data),
        'total_segments': total_segments,
        'date_range': {
            'oldest': oldest.isoformat(),
            'newest': newest.isoformat()
        },
        'tier_eligible': tier_status['current_tier'],
        'next_tier': tier_status['next_tier'],
        'progress_to_next_tier_pct': tier_status['progress_to_next_tier_pct']
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
            'confidence_level': trained_model.confidence_level,
            'last_trained': trained_model.last_trained.isoformat()
        })

    except Exception as e:
        logger.exception(f"Error in API endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500
