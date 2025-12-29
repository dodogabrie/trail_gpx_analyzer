"""Input validation schemas for API endpoints.

Provides validation functions for request data without external dependencies.
"""

from typing import Dict, Any, List, Optional, Tuple
from config.hybrid_config import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Raised when validation fails."""
    def __init__(self, errors: Dict[str, str]):
        self.errors = errors
        super().__init__(str(errors))


def validate_predict_request(data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, str]]]:
    """Validate prediction request data.

    Args:
        data: Request data dict

    Returns:
        Tuple of (is_valid, errors_dict)
    """
    errors = {}

    # Required: gpx_id
    if 'gpx_id' not in data:
        errors['gpx_id'] = 'Missing required field'
    elif not isinstance(data['gpx_id'], int) or data['gpx_id'] <= 0:
        errors['gpx_id'] = 'Must be a positive integer'

    # Optional: force_tier
    if 'force_tier' in data:
        valid_tiers = ['physics', 'parameter_learning', 'residual_ml']
        if data['force_tier'] not in valid_tiers:
            errors['force_tier'] = f'Must be one of: {", ".join(valid_tiers)}'

    # Optional: include_diagnostics
    if 'include_diagnostics' in data:
        if not isinstance(data['include_diagnostics'], bool):
            errors['include_diagnostics'] = 'Must be a boolean'

    return (len(errors) == 0, errors if errors else None)


def validate_gpx_points(points: List[Dict]) -> Tuple[bool, Optional[str]]:
    """Validate GPX points structure.

    Args:
        points: List of point dicts

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(points, list):
        return (False, 'Points must be a list')

    if len(points) < 2:
        return (False, 'Need at least 2 points')

    for i, point in enumerate(points):
        if not isinstance(point, dict):
            return (False, f'Point {i} must be a dict')

        required_fields = ['distance', 'elevation']
        for field in required_fields:
            if field not in point:
                return (False, f'Point {i} missing required field: {field}')

            if not isinstance(point[field], (int, float)):
                return (False, f'Point {i}.{field} must be a number')

    return (True, None)


def validate_tier_string(tier: str) -> Tuple[bool, Optional[str]]:
    """Validate tier string.

    Args:
        tier: Tier identifier string

    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_tiers = ['physics', 'parameter_learning', 'residual_ml']

    if tier not in valid_tiers:
        return (False, f'Invalid tier. Must be one of: {", ".join(valid_tiers)}')

    return (True, None)


def validate_positive_integer(value: Any, field_name: str) -> Tuple[bool, Optional[str]]:
    """Validate that value is a positive integer.

    Args:
        value: Value to validate
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(value, int):
        return (False, f'{field_name} must be an integer')

    if value <= 0:
        return (False, f'{field_name} must be positive')

    return (True, None)


def validate_optional_boolean(value: Any, field_name: str) -> Tuple[bool, Optional[str]]:
    """Validate optional boolean field.

    Args:
        value: Value to validate
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        return (True, None)

    if not isinstance(value, bool):
        return (False, f'{field_name} must be a boolean')

    return (True, None)


def create_error_response(errors: Dict[str, str], status_code: int = 400) -> Tuple[Dict, int]:
    """Create standardized error response.

    Args:
        errors: Dict of field -> error message
        status_code: HTTP status code

    Returns:
        Tuple of (response_dict, status_code)
    """
    return ({
        'error': 'Validation failed',
        'details': errors
    }, status_code)


def log_validation_error(endpoint: str, errors: Dict[str, str]):
    """Log validation errors.

    Args:
        endpoint: API endpoint path
        errors: Validation errors
    """
    logger.warning(f"Validation failed for {endpoint}: {errors}")
