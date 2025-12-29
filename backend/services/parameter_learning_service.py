"""Parameter learning service for Tier 2 predictions.

Learns personalized physics model parameters from user's activity history.
Uses optimization to fit parameters that minimize prediction error.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from scipy.optimize import minimize
from database import db
from models import UserActivityResidual, UserLearnedParams
from services.physics_prediction_service import PhysicsPredictionService
from config.hybrid_config import (
    get_logger,
    DEFAULT_PARAMS,
    PARAM_BOUNDS,
    TIER_2_MIN_ACTIVITIES,
    REGULARIZATION_STRENGTH,
    OPTIMIZATION_MAX_ITER,
    OPTIMIZATION_TOLERANCE
)

logger = get_logger(__name__)

# Parameters to optimize (others kept fixed due to limited data)
OPTIMIZED_PARAMS = ['v_flat', 'k_up', 'k_tech', 'fatigue_alpha']


class ParameterLearningService:
    """Learn personalized physics parameters from user's activities.

    Tier 2 of the hybrid prediction system. Optimizes physics model
    parameters to minimize prediction error on user's historical activities.

    Uses scipy.optimize with L2 regularization to prevent overfitting.
    """

    def __init__(self):
        self.physics_service = PhysicsPredictionService()

    def should_train(self, user_id: int) -> bool:
        """Check if user has enough data for parameter learning.

        Args:
            user_id: User ID

        Returns:
            True if user has >= TIER_2_MIN_ACTIVITIES activities
        """
        count = UserActivityResidual.query.filter_by(user_id=user_id).count()
        return count >= TIER_2_MIN_ACTIVITIES

    def train_user_params(self, user_id: int) -> Optional[UserLearnedParams]:
        """Train personalized physics parameters for user.

        Args:
            user_id: User ID

        Returns:
            UserLearnedParams record if successful, None otherwise
        """
        try:
            # Get user's residual data
            residuals = (
                UserActivityResidual.query
                .filter_by(user_id=user_id)
                .order_by(UserActivityResidual.activity_date.desc())
                .all()
            )

            if len(residuals) < TIER_2_MIN_ACTIVITIES:
                logger.warning(f"User {user_id} has only {len(residuals)} activities (need {TIER_2_MIN_ACTIVITIES})")
                return None

            logger.info(f"Training Tier 2 parameters for user {user_id} with {len(residuals)} activities")

            # Prepare training data
            training_data = self._prepare_training_data(residuals)

            if not training_data:
                logger.error(f"No valid training data for user {user_id}")
                return None

            # Optimize parameters
            optimized_params, score = self._optimize_params(training_data)

            logger.info(f"Optimization complete for user {user_id}. MAE: {score:.4f}")
            logger.debug(f"Learned params for user {user_id}: {optimized_params}")

            # Save to database
            learned_params = UserLearnedParams.query.filter_by(user_id=user_id).first()

            if learned_params:
                # Update existing
                for key, value in optimized_params.items():
                    setattr(learned_params, key, value)
                learned_params.n_activities_used = len(residuals)
                learned_params.optimization_score = score
                learned_params.last_trained = datetime.utcnow()
                learned_params.version += 1
            else:
                # Create new
                learned_params = UserLearnedParams(
                    user_id=user_id,
                    **optimized_params,
                    n_activities_used=len(residuals),
                    optimization_score=score
                )
                db.session.add(learned_params)

            db.session.commit()

            logger.info(f"Parameters saved for user {user_id} (version {learned_params.version})")
            return learned_params

        except Exception as e:
            logger.exception(f"Error training parameters for user {user_id}: {e}")
            db.session.rollback()
            return None

    def _prepare_training_data(self, residuals: List[UserActivityResidual]) -> List[Dict]:
        """Prepare training data from residual records.

        Args:
            residuals: List of UserActivityResidual records

        Returns:
            List of training examples with features and targets
        """
        training_data = []

        for residual in residuals:
            # Apply recency weighting
            weight = residual.recency_weight

            for segment in residual.segments:
                training_data.append({
                    'distance_m': segment.get('distance_m', 0),
                    'grade_mean': segment.get('grade_mean', 0),
                    'grade_std': segment.get('grade_std', 0),
                    'actual_pace_ratio': segment.get('actual_pace_ratio', 1.0),
                    'weight': weight,
                    'activity_id': residual.activity_id,
                    'total_distance_km': residual.total_distance_km or 0,
                    'total_elevation_gain_m': residual.total_elevation_gain_m or 0
                })

        return training_data

    def _optimize_params(
        self,
        training_data: List[Dict],
        regularization_strength: float = 0.1
    ) -> Tuple[Dict[str, float], float]:
        """Optimize physics parameters using scipy.optimize.

        Minimizes: MAE(actual_pace, physics_pace) + λ * ||params - default||²

        Args:
            training_data: Training examples
            regularization_strength: L2 regularization strength

        Returns:
            Tuple of (optimized_params_dict, final_score)
        """
        # Initial guess (defaults)
        x0 = np.array([
            DEFAULT_PARAMS['v_flat'],
            DEFAULT_PARAMS['k_up'],
            DEFAULT_PARAMS['k_tech'],
            DEFAULT_PARAMS['fatigue_alpha']
        ])

        # Bounds
        bounds = [
            PARAM_BOUNDS['v_flat'],
            PARAM_BOUNDS['k_up'],
            PARAM_BOUNDS['k_tech'],
            PARAM_BOUNDS['fatigue_alpha']
        ]

        # Objective function
        def objective(params):
            v_flat, k_up, k_tech, fatigue_alpha = params

            errors = []
            weights = []

            for example in training_data:
                # Predict pace ratio using physics model with current params
                physics_pace_ratio = self._compute_physics_pace_ratio(
                    grade=example['grade_mean'],
                    v_flat=v_flat,
                    k_up=k_up,
                    k_tech=k_tech
                )

                # Compare to actual
                actual_pace_ratio = example['actual_pace_ratio']
                error = abs(actual_pace_ratio - physics_pace_ratio)

                errors.append(error)
                weights.append(example['weight'])

            # Weighted MAE
            weighted_errors = np.array(errors) * np.array(weights)
            mae = np.mean(weighted_errors)

            # L2 regularization (prevent overfitting)
            regularization = regularization_strength * np.sum((params - x0) ** 2)

            return mae + regularization

        # Optimize
        result = minimize(
            objective,
            x0,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': OPTIMIZATION_MAX_ITER, 'ftol': OPTIMIZATION_TOLERANCE}
        )

        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")

        # Extract optimized parameters
        v_flat, k_up, k_tech, fatigue_alpha = result.x

        optimized_params = {
            'v_flat': float(v_flat),
            'k_up': float(k_up),
            'k_tech': float(k_tech),
            'a_param': DEFAULT_PARAMS['a_param'],  # Keep fixed
            'k_terrain_up': DEFAULT_PARAMS['k_terrain_up'],
            'k_terrain_down': DEFAULT_PARAMS['k_terrain_down'],
            'k_terrain_flat': DEFAULT_PARAMS['k_terrain_flat'],
            'fatigue_alpha': float(fatigue_alpha)
        }

        # Compute final score (without regularization)
        final_score = self._compute_score(training_data, optimized_params)

        return optimized_params, final_score

    def _compute_physics_pace_ratio(
        self,
        grade: float,
        v_flat: float,
        k_up: float,
        k_tech: float
    ) -> float:
        """Compute physics pace ratio for a given grade and parameters.

        Simplified physics model: pace_ratio = f(grade, k_up, k_tech)

        Args:
            grade: Grade as fraction (e.g., 0.05 for 5%)
            v_flat: Flat velocity (m/s)
            k_up: Uphill coefficient
            k_tech: Technical coefficient

        Returns:
            Pace ratio (pace / flat_pace)
        """
        # Simplified Minetti-based model
        # For uphill: pace increases
        # For downhill: pace decreases (but less than uphill gains)

        if grade > 0:
            # Uphill: exponential slowdown
            pace_ratio = 1.0 + k_up * (np.exp(grade * 10) - 1) / 10
        elif grade < 0:
            # Downhill: logarithmic speedup (less gain than uphill loss)
            pace_ratio = 1.0 + 0.3 * np.log1p(-grade * 10) / 10
        else:
            pace_ratio = 1.0

        # Apply technical terrain factor
        pace_ratio *= k_tech

        return max(pace_ratio, 0.5)  # Floor at 0.5x (don't get too fast)

    def _compute_score(self, training_data: List[Dict], params: Dict[str, float]) -> float:
        """Compute MAE score for given parameters.

        Args:
            training_data: Training examples
            params: Physics parameters

        Returns:
            Mean Absolute Error (weighted by recency)
        """
        errors = []
        weights = []

        for example in training_data:
            physics_pace_ratio = self._compute_physics_pace_ratio(
                grade=example['grade_mean'],
                v_flat=params['v_flat'],
                k_up=params['k_up'],
                k_tech=params['k_tech']
            )

            actual_pace_ratio = example['actual_pace_ratio']
            error = abs(actual_pace_ratio - physics_pace_ratio)

            errors.append(error)
            weights.append(example['weight'])

        weighted_errors = np.array(errors) * np.array(weights)
        return float(np.mean(weighted_errors))

    def get_user_params(self, user_id: int) -> Optional[Dict[str, float]]:
        """Get learned parameters for user.

        Args:
            user_id: User ID

        Returns:
            Parameter dict if available, None otherwise
        """
        learned_params = UserLearnedParams.query.filter_by(user_id=user_id).first()

        if learned_params:
            return learned_params.to_dict()

        return None

    def get_or_default_params(self, user_id: int) -> Dict[str, float]:
        """Get user's learned params or defaults.

        Args:
            user_id: User ID

        Returns:
            Parameter dict (learned or default)
        """
        params = self.get_user_params(user_id)
        return params if params else DEFAULT_PARAMS.copy()
