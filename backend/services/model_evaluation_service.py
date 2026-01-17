"""Model evaluation service for leave-one-out testing.

Trains on all activities except the longest one, then evaluates prediction
accuracy on that held-out activity. Outputs detailed error statistics to JSON.
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from database import db
from models import UserActivityResidual, StravaActivity, UserLearnedParams, UserResidualModel
from services.physics_prediction_service import PhysicsPredictionService
from services.parameter_learning_service import ParameterLearningService
from config.hybrid_config import (
    get_logger,
    TIER_2_MIN_ACTIVITIES,
    TIER_3_MIN_ACTIVITIES,
    MIN_SEGMENTS_FOR_TIER3,
    GBM_CONFIG,
    ML_FEATURE_NAMES,
    ML_RESIDUAL_CLIP_MIN,
    ML_RESIDUAL_CLIP_MAX,
    DEFAULT_PARAMS
)

logger = get_logger(__name__)

# Output directory for evaluation results
EVALUATION_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'evaluation_results'
)

# Slope bins for error analysis (grade in %)
SLOPE_BINS = {
    '-30': (-float('inf'), -25),
    '-20': (-25, -15),
    '-10': (-15, -5),
    '0': (-5, 5),
    '10': (5, 15),
    '20': (15, 25),
    '30': (25, float('inf'))
}

# Feature names alias
FEATURES = ML_FEATURE_NAMES


class ModelEvaluationService:
    """Evaluate model prediction accuracy on held-out activities.

    Implements leave-one-out evaluation where the longest activity (by distance
    + elevation score) is held out for testing while training on all others.
    """

    def __init__(self):
        self.physics_service = PhysicsPredictionService()
        self.parameter_service = ParameterLearningService()

    def evaluate_user(self, user_id: int) -> Dict:
        """Run full evaluation for a user.

        Finds longest activity, trains on others, predicts, and calculates errors.

        Args:
            user_id: User ID

        Returns:
            Evaluation results dict with general and slope-binned errors
        """
        try:
            logger.info(f"Starting evaluation for user {user_id}")

            # Get all residuals for the user
            all_residuals = (
                UserActivityResidual.query
                .filter_by(user_id=user_id, excluded_from_training=False)
                .order_by(UserActivityResidual.activity_date.desc())
                .all()
            )

            if len(all_residuals) < TIER_2_MIN_ACTIVITIES + 1:
                return {
                    'error': f'Insufficient activities ({len(all_residuals)}). Need at least {TIER_2_MIN_ACTIVITIES + 1}.'
                }

            # Find longest activity
            target_activity = self._find_longest_activity(all_residuals)
            logger.info(f"Target activity: {target_activity.activity_id} "
                       f"(dist={target_activity.total_distance_km:.1f}km, "
                       f"elev={target_activity.total_elevation_gain_m:.0f}m)")

            # Train on other activities
            training_residuals = [r for r in all_residuals if r.activity_id != target_activity.activity_id]
            logger.info(f"Training on {len(training_residuals)} activities")

            # Train Tier 2 params
            learned_params = self._train_params_on_subset(training_residuals)
            if not learned_params:
                learned_params = DEFAULT_PARAMS.copy()
                logger.warning("Parameter learning failed, using defaults")

            # Train GBM model if enough data
            gbm_model = None
            tier_used = 'tier_2'
            if len(training_residuals) >= TIER_3_MIN_ACTIVITIES:
                gbm_model = self._train_gbm_on_subset(training_residuals)
                if gbm_model:
                    tier_used = 'tier_3'
                    logger.info("GBM model trained successfully")
                else:
                    logger.warning("GBM training failed, using Tier 2 only")

            # Predict on target activity
            predictions = self._predict_target_activity(
                target_activity, learned_params, gbm_model
            )

            if not predictions:
                return {'error': 'Prediction failed for target activity'}

            # Calculate errors
            general_stats = self._calculate_general_statistics(predictions)
            slope_errors = self._calculate_slope_errors(predictions)

            # Build result
            result = {
                'evaluation_info': {
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'model_type': tier_used
                },
                'target_activity': {
                    'activity_id': target_activity.activity_id,
                    'distance_km': target_activity.total_distance_km,
                    'elevation_gain_m': target_activity.total_elevation_gain_m,
                    'score': self._compute_activity_score(target_activity),
                    'date': target_activity.activity_date.isoformat() if target_activity.activity_date else None,
                    'n_segments': len(target_activity.segments)
                },
                'training_info': {
                    'n_activities_used': len(training_residuals),
                    'n_segments_used': sum(len(r.segments) for r in training_residuals),
                    'tier_achieved': tier_used
                },
                'general_statistics': general_stats,
                'slope_segment_errors': slope_errors
            }

            # Add GBM diagnostics if trained
            if gbm_model:
                result['model_diagnostics'] = self._get_gbm_diagnostics(gbm_model, training_residuals)

            # Save to file
            output_path = self._save_results(user_id, result)
            result['output_file'] = output_path

            logger.info(f"Evaluation complete for user {user_id}. Saved to {output_path}")
            return result

        except Exception as e:
            logger.exception(f"Evaluation failed for user {user_id}: {e}")
            return {'error': str(e)}

    def _find_longest_activity(self, residuals: List[UserActivityResidual]) -> UserActivityResidual:
        """Find activity with highest score (distance_km + elevation/100).

        Args:
            residuals: List of activity residual records

        Returns:
            Activity with highest score
        """
        return max(residuals, key=self._compute_activity_score)

    def _compute_activity_score(self, residual: UserActivityResidual) -> float:
        """Compute activity score for ranking.

        Args:
            residual: Activity residual record

        Returns:
            Score = distance_km + (elevation_gain_m / 100)
        """
        distance_km = residual.total_distance_km or 0
        elevation_m = residual.total_elevation_gain_m or 0
        return distance_km + (elevation_m / 100)

    def _train_params_on_subset(
        self,
        residuals: List[UserActivityResidual]
    ) -> Optional[Dict]:
        """Train Tier 2 parameters on a subset of activities.

        Args:
            residuals: Training residuals (excluding held-out activity)

        Returns:
            Learned parameters dict or None
        """
        if len(residuals) < TIER_2_MIN_ACTIVITIES:
            return None

        try:
            # Use parameter learning service logic but on custom subset
            training_examples = []

            for residual in residuals:
                for segment in residual.segments:
                    if segment.get('actual_pace_ratio') and segment.get('grade_mean') is not None:
                        training_examples.append({
                            'grade_mean': segment['grade_mean'],
                            'actual_pace_ratio': segment['actual_pace_ratio'],
                            'recency_weight': residual.recency_weight
                        })

            if len(training_examples) < 20:
                return None

            # Simplified parameter learning (use defaults with v_flat calibration)
            # Full optimization would require copying more from ParameterLearningService
            pace_ratios = [ex['actual_pace_ratio'] for ex in training_examples
                         if abs(ex['grade_mean']) < 2]  # Near-flat segments

            if pace_ratios:
                avg_flat_pace_ratio = np.mean(pace_ratios)
                # Estimate v_flat from average flat pace ratio
                v_flat = DEFAULT_PARAMS['v_flat'] / avg_flat_pace_ratio
                v_flat = np.clip(v_flat, 2.0, 5.0)
            else:
                v_flat = DEFAULT_PARAMS['v_flat']

            params = DEFAULT_PARAMS.copy()
            params['v_flat'] = float(v_flat)

            return params

        except Exception as e:
            logger.error(f"Parameter training failed: {e}")
            return None

    def _train_gbm_on_subset(
        self,
        residuals: List[UserActivityResidual]
    ) -> Optional[GradientBoostingRegressor]:
        """Train GBM model on a subset of activities.

        Args:
            residuals: Training residuals (excluding held-out activity)

        Returns:
            Trained GBM model or None
        """
        try:
            # Prepare training data
            X, y, weights = self._prepare_training_data(residuals)

            if len(X) < MIN_SEGMENTS_FOR_TIER3:
                logger.warning(f"Insufficient segments: {len(X)} < {MIN_SEGMENTS_FOR_TIER3}")
                return None

            # Train model (no validation split needed for evaluation)
            model = GradientBoostingRegressor(**GBM_CONFIG)
            model.fit(X, y, sample_weight=weights)

            return model

        except Exception as e:
            logger.error(f"GBM training failed: {e}")
            return None

    def _prepare_training_data(
        self,
        residuals: List[UserActivityResidual]
    ) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        """Prepare training data from residual records.

        Args:
            residuals: List of UserActivityResidual records

        Returns:
            Tuple of (X, y, weights)
        """
        rows = []

        for residual in residuals:
            prev_grade = 0.0
            prev_pace_ratio = 1.0
            cum_elevation_gain = 0.0
            total_distance = residual.total_distance_km * 1000 if residual.total_distance_km else 0

            for segment in residual.segments:
                distance_m = segment.get('distance_m', 0)
                grade_mean = segment.get('grade_mean', 0)
                grade_std = segment.get('grade_std', 0)
                physics_pace_ratio = segment.get('physics_pace_ratio', 1.0)
                actual_pace_ratio = segment.get('actual_pace_ratio', 1.0)
                elevation_gain = segment.get('elevation_gain', 0)

                # Compute residual
                residual_mult = actual_pace_ratio / physics_pace_ratio if physics_pace_ratio > 0 else 1.0

                # Skip outliers
                if residual_mult < 0.5 or residual_mult > 2.0:
                    continue

                # Compute features
                grade_change = grade_mean - prev_grade
                distance_remaining_km = (total_distance - distance_m) / 1000 if total_distance > 0 else 0
                cum_elevation_gain += elevation_gain
                elevation_gain_rate = elevation_gain / 0.2 if elevation_gain > 0 else 0

                row = {
                    'grade_mean': grade_mean,
                    'grade_std': grade_std,
                    'abs_grade': abs(grade_mean),
                    'cum_distance_km': distance_m / 1000,
                    'distance_remaining_km': distance_remaining_km,
                    'prev_pace_ratio': prev_pace_ratio,
                    'grade_change': grade_change,
                    'cum_elevation_gain_m': cum_elevation_gain,
                    'elevation_gain_rate': elevation_gain_rate,
                    'rolling_avg_grade_500m': grade_mean,
                    'residual': residual_mult,
                    'weight': residual.recency_weight
                }

                rows.append(row)
                prev_grade = grade_mean
                prev_pace_ratio = actual_pace_ratio

        df = pd.DataFrame(rows)
        X = df[FEATURES]
        y = df['residual'].values
        weights = df['weight'].values

        return X, y, weights

    def _predict_target_activity(
        self,
        target: UserActivityResidual,
        learned_params: Dict,
        gbm_model: Optional[GradientBoostingRegressor]
    ) -> List[Dict]:
        """Generate predictions for target activity segments.

        Args:
            target: Target activity residual record
            learned_params: Learned physics parameters
            gbm_model: Trained GBM model (or None for Tier 2 only)

        Returns:
            List of segment predictions with actual values
        """
        predictions = []
        flat_pace_ratio_base = 1.0  # Normalized to flat pace

        v_flat = learned_params.get('v_flat', DEFAULT_PARAMS['v_flat'])
        flat_pace_min_km = (1000.0 / v_flat) / 60.0

        prev_grade = 0.0
        prev_pace_ratio = 1.0
        cum_elevation_gain = 0.0
        total_distance = target.total_distance_km * 1000 if target.total_distance_km else 0

        for segment in target.segments:
            distance_m = segment.get('distance_m', 0)
            grade_mean = segment.get('grade_mean', 0)
            grade_std = segment.get('grade_std', 0)
            physics_pace_ratio = segment.get('physics_pace_ratio', 1.0)
            actual_pace_ratio = segment.get('actual_pace_ratio', 1.0)
            elevation_gain = segment.get('elevation_gain', 0)

            # Build features for ML prediction
            grade_change = grade_mean - prev_grade
            distance_remaining_km = (total_distance - distance_m) / 1000 if total_distance > 0 else 0
            cum_elevation_gain += elevation_gain
            elevation_gain_rate = elevation_gain / 0.2 if elevation_gain > 0 else 0

            features = {
                'grade_mean': grade_mean,
                'grade_std': grade_std,
                'abs_grade': abs(grade_mean),
                'cum_distance_km': distance_m / 1000,
                'distance_remaining_km': distance_remaining_km,
                'prev_pace_ratio': prev_pace_ratio,
                'grade_change': grade_change,
                'cum_elevation_gain_m': cum_elevation_gain,
                'elevation_gain_rate': elevation_gain_rate,
                'rolling_avg_grade_500m': grade_mean
            }

            # Predict
            residual_mult = 1.0
            if gbm_model:
                X = pd.DataFrame([features])[FEATURES]
                residual_mult = gbm_model.predict(X)[0]
                residual_mult = np.clip(residual_mult, ML_RESIDUAL_CLIP_MIN, ML_RESIDUAL_CLIP_MAX)
                predicted_pace_ratio = physics_pace_ratio * residual_mult
            else:
                # Tier 2: Use physics directly
                predicted_pace_ratio = physics_pace_ratio

            # Store prediction with actual
            predictions.append({
                'distance_m': distance_m,
                'grade_mean': grade_mean,
                'predicted_pace_ratio': float(predicted_pace_ratio),
                'actual_pace_ratio': float(actual_pace_ratio),
                'physics_pace_ratio': float(physics_pace_ratio),
                'residual_mult': float(residual_mult)
            })

            prev_grade = grade_mean
            prev_pace_ratio = actual_pace_ratio

        return predictions

    def _calculate_general_statistics(self, predictions: List[Dict]) -> Dict:
        """Calculate overall prediction error statistics.

        Args:
            predictions: List of segment predictions

        Returns:
            Dict with MAE, RMSE, R2, and time error metrics
        """
        predicted = np.array([p['predicted_pace_ratio'] for p in predictions])
        actual = np.array([p['actual_pace_ratio'] for p in predictions])

        mae = float(mean_absolute_error(actual, predicted))
        rmse = float(np.sqrt(mean_squared_error(actual, predicted)))
        r2 = float(r2_score(actual, predicted)) if len(actual) > 1 else 0.0

        # Estimate time error (assuming 200m segments)
        segment_length_km = 0.2
        predicted_time_sec = sum(p['predicted_pace_ratio'] * segment_length_km * 60 for p in predictions)
        actual_time_sec = sum(p['actual_pace_ratio'] * segment_length_km * 60 for p in predictions)

        time_error_sec = predicted_time_sec - actual_time_sec
        time_error_pct = (time_error_sec / actual_time_sec * 100) if actual_time_sec > 0 else 0

        return {
            'mae_pace_ratio': mae,
            'rmse_pace_ratio': rmse,
            'r2_score': r2,
            'total_time_predicted_sec': float(predicted_time_sec),
            'total_time_actual_sec': float(actual_time_sec),
            'total_time_error_sec': float(time_error_sec),
            'total_time_error_percent': float(time_error_pct),
            'n_segments_evaluated': len(predictions)
        }

    def _calculate_slope_errors(self, predictions: List[Dict]) -> Dict:
        """Calculate prediction errors binned by slope.

        Args:
            predictions: List of segment predictions

        Returns:
            Dict with error metrics per slope bin
        """
        slope_errors = {}

        for bin_name, (low, high) in SLOPE_BINS.items():
            # Filter segments by grade (grade_mean is in %)
            bin_predictions = [
                p for p in predictions
                if low <= p['grade_mean'] < high
            ]

            if not bin_predictions:
                slope_errors[bin_name] = {
                    'mae': None,
                    'rmse': None,
                    'n_segments': 0,
                    'avg_predicted_pace_ratio': None,
                    'avg_actual_pace_ratio': None
                }
                continue

            predicted = np.array([p['predicted_pace_ratio'] for p in bin_predictions])
            actual = np.array([p['actual_pace_ratio'] for p in bin_predictions])

            errors = np.abs(predicted - actual)

            slope_errors[bin_name] = {
                'mae': float(np.mean(errors)),
                'rmse': float(np.sqrt(np.mean(errors ** 2))),
                'n_segments': len(bin_predictions),
                'avg_predicted_pace_ratio': float(np.mean(predicted)),
                'avg_actual_pace_ratio': float(np.mean(actual))
            }

        return slope_errors

    def _get_gbm_diagnostics(
        self,
        model: GradientBoostingRegressor,
        residuals: List[UserActivityResidual]
    ) -> Dict:
        """Get GBM model diagnostics.

        Args:
            model: Trained GBM model
            residuals: Training residuals

        Returns:
            Dict with feature importance and training metrics
        """
        # Feature importance
        feature_importance = {
            feature: float(importance)
            for feature, importance in zip(FEATURES, model.feature_importances_)
        }

        # Training metrics (on full training set)
        X, y, weights = self._prepare_training_data(residuals)
        y_pred = model.predict(X)

        return {
            'train_mae': float(mean_absolute_error(y, y_pred)),
            'train_rmse': float(np.sqrt(mean_squared_error(y, y_pred))),
            'train_r2': float(r2_score(y, y_pred)),
            'n_estimators': model.n_estimators,
            'feature_importance': feature_importance
        }

    def _save_results(self, user_id: int, result: Dict) -> str:
        """Save evaluation results to JSON file.

        Args:
            user_id: User ID
            result: Evaluation results dict

        Returns:
            Path to saved file
        """
        # Ensure output directory exists
        os.makedirs(EVALUATION_OUTPUT_DIR, exist_ok=True)

        # Generate filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f'user_{user_id}_evaluation_{timestamp}.json'
        filepath = os.path.join(EVALUATION_OUTPUT_DIR, filename)

        # Save
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        return filepath
