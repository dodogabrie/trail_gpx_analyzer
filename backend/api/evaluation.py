"""Model evaluation API endpoints.

Provides endpoints for running leave-one-out model evaluation.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, jsonify
from api.utils import get_current_user
from services.model_evaluation_service import ModelEvaluationService

bp = Blueprint('evaluation', __name__, url_prefix='/api/evaluation')

# Service instance
evaluation_service = None


def get_evaluation_service():
    """Get or create evaluation service instance."""
    global evaluation_service
    if evaluation_service is None:
        evaluation_service = ModelEvaluationService()
    return evaluation_service


@bp.route('/run', methods=['POST'])
def run_evaluation():
    """Run leave-one-out evaluation for current user.

    Trains on all activities except the longest one, then evaluates
    prediction accuracy on that held-out activity.

    Returns:
        JSON with evaluation results including:
        - target_activity: Info about the held-out activity
        - general_statistics: Overall MAE, RMSE, R2, time error
        - slope_segment_errors: Errors binned by slope (-30% to +30%)
        - output_file: Path to saved JSON file
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    service = get_evaluation_service()
    result = service.evaluate_user(user.id)

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result), 200


@bp.route('/status', methods=['GET'])
def get_status():
    """Get current evaluation progress status.

    Returns:
        JSON with current status including:
        - status: idle, running, completed, error
        - current_step: Current step name
        - progress_percent: Overall progress (0-100)
        - message: Current status message
        - total_activities: Number of activities being processed
        - training_activities: Number of activities used for training
        - target_activity_id: ID of activity being predicted
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    service = get_evaluation_service()
    status = service.get_status(user.id)

    return jsonify(status), 200


@bp.route('/results', methods=['GET'])
def list_results():
    """List available evaluation results for current user.

    Returns:
        JSON with list of evaluation result files
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    from services.model_evaluation_service import EVALUATION_OUTPUT_DIR

    # List files for this user
    results = []
    if os.path.exists(EVALUATION_OUTPUT_DIR):
        prefix = f'user_{user.id}_evaluation_'
        for filename in os.listdir(EVALUATION_OUTPUT_DIR):
            if filename.startswith(prefix) and filename.endswith('.json'):
                filepath = os.path.join(EVALUATION_OUTPUT_DIR, filename)
                results.append({
                    'filename': filename,
                    'path': filepath,
                    'created_at': os.path.getmtime(filepath)
                })

    # Sort by creation time (newest first)
    results.sort(key=lambda x: x['created_at'], reverse=True)

    return jsonify({'results': results}), 200


@bp.route('/results/<filename>', methods=['GET'])
def get_result(filename):
    """Get a specific evaluation result.

    Args:
        filename: Name of the evaluation result file

    Returns:
        JSON with full evaluation results
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    from services.model_evaluation_service import EVALUATION_OUTPUT_DIR
    import json

    # Validate filename belongs to user
    expected_prefix = f'user_{user.id}_evaluation_'
    if not filename.startswith(expected_prefix):
        return jsonify({'error': 'Access denied'}), 403

    filepath = os.path.join(EVALUATION_OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    with open(filepath, 'r') as f:
        result = json.load(f)

    return jsonify(result), 200
