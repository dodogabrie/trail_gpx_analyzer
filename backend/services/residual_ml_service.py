"""Residual ML service for Tier 3 predictions.

Trains GradientBoostingRegressor on user's residuals to predict corrections
on top of physics baseline. Uses learned parameters + ML residual model.
"""

import numpy as np
import pandas as pd
import joblib
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from database import db
from models import UserActivityResidual, UserResidualModel, UserLearnedParams
from services.parameter_learning_service import ParameterLearningService
from config.hybrid_config import (
    get_logger,
    TIER_3_MIN_ACTIVITIES,
    MIN_SEGMENTS_FOR_TIER3,
    GBM_CONFIG,
    GBM_VALIDATION_SPLIT,
    ML_FEATURE_NAMES,
    ML_RESIDUAL_CLIP_MIN,
    ML_RESIDUAL_CLIP_MAX
)

logger = get_logger(__name__)

# Feature list alias
FEATURES = ML_FEATURE_NAMES


class ResidualMLService:
    """Train and use GBM models for residual corrections.

    Tier 3 of the hybrid prediction system. Trains GradientBoostingRegressor
    to predict residual multipliers on top of physics baseline.

    Privacy: Only uses individual user's own activity data.
    """

    def __init__(self):
        self.parameter_service = ParameterLearningService()

    def should_train(self, user_id: int) -> bool:
        """Check if user has enough data for GBM training.

        Args:
            user_id: User ID

        Returns:
            True if user has >= TIER_3_MIN_ACTIVITIES activities
        """
        count = UserActivityResidual.query.filter_by(user_id=user_id).count()
        return count >= TIER_3_MIN_ACTIVITIES

    def train_user_model(self, user_id: int) -> Optional[UserResidualModel]:
        """Train GBM residual model for user.

        Args:
            user_id: User ID

        Returns:
            UserResidualModel record if successful, None otherwise
        """
        try:
            # Get user's residual data
            residuals = (
                UserActivityResidual.query
                .filter_by(user_id=user_id)
                .order_by(UserActivityResidual.activity_date.desc())
                .all()
            )

            if len(residuals) < TIER_3_MIN_ACTIVITIES:
                logger.warning(f"User {user_id} has only {len(residuals)} activities (need {TIER_3_MIN_ACTIVITIES})")
                return None

            logger.info(f"Training Tier 3 GBM model for user {user_id} with {len(residuals)} activities")

            # Prepare training data
            X, y, weights = self._prepare_training_data(residuals)

            if len(X) < MIN_SEGMENTS_FOR_TIER3:  # Minimum segments needed
                logger.warning(f"Insufficient segments for user {user_id}: {len(X)} (need {MIN_SEGMENTS_FOR_TIER3}+)")
                return None

            logger.info(f"Training on {len(X)} segments for user {user_id}")

            # Train model
            model, metrics, feature_importance = self._train_gbm(X, y, weights)

            logger.info(f"GBM training complete for user {user_id}. Validation MAE: {metrics['val_mae']:.4f}, R²: {metrics['val_r2']:.3f}")

            # Compute residual variance (std) for effort-based predictions
            residual_std = float(np.std(y))
            logger.info(f"Residual variance (σ) for user {user_id}: {residual_std:.4f}")

            # Serialize model
            model_blob = self._serialize_model(model)

            # Save to database
            residual_model = UserResidualModel.query.filter_by(user_id=user_id).first()

            if residual_model:
                # Update existing
                residual_model.model_blob = model_blob
                residual_model.n_activities_used = len(residuals)
                residual_model.n_segments_trained = len(X)
                residual_model.metrics = metrics
                residual_model.feature_importance = feature_importance
                residual_model.model_config = GBM_CONFIG
                residual_model.residual_variance = residual_std
                residual_model.last_trained = datetime.utcnow()
                residual_model.version += 1
            else:
                # Create new
                residual_model = UserResidualModel(
                    user_id=user_id,
                    model_blob=model_blob,
                    n_activities_used=len(residuals),
                    n_segments_trained=len(X),
                    metrics=metrics,
                    feature_importance=feature_importance,
                    model_config=GBM_CONFIG,
                    residual_variance=residual_std
                )
                db.session.add(residual_model)

            db.session.commit()

            logger.info(f"GBM model saved for user {user_id} (version {residual_model.version})")
            return residual_model

        except Exception as e:
            logger.exception(f"Error training GBM model for user {user_id}: {e}")
            db.session.rollback()
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
                X: Feature DataFrame
                y: Target residuals
                weights: Sample weights (recency-weighted)
        """
        rows = []

        for residual in residuals:
            # State tracking across segments within activity
            prev_grade = 0.0
            prev_pace_ratio = 1.0
            cum_elevation_gain = 0.0

            total_distance = residual.total_distance_km * 1000 if residual.total_distance_km else 0

            for i, segment in enumerate(residual.segments):
                # Extract segment data
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
                elevation_gain_rate = elevation_gain / 0.2 if elevation_gain > 0 else 0  # 200m segment = 0.2km

                # Rolling avg grade (use previous segments if available)
                # For simplicity, use current grade as proxy
                rolling_avg_grade_500m = grade_mean

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
                    'rolling_avg_grade_500m': rolling_avg_grade_500m,
                    'residual': residual_mult,
                    'weight': residual.recency_weight
                }

                rows.append(row)

                # Update state
                prev_grade = grade_mean
                prev_pace_ratio = actual_pace_ratio

        if not rows:
            raise ValueError("No training rows built")

        df = pd.DataFrame(rows)

        X = df[FEATURES]
        y = df['residual'].values
        weights = df['weight'].values

        return X, y, weights

    def _train_gbm(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        weights: np.ndarray
    ) -> Tuple[GradientBoostingRegressor, Dict, Dict]:
        """Train GradientBoostingRegressor.

        Args:
            X: Features
            y: Targets (residual multipliers)
            weights: Sample weights

        Returns:
            Tuple of (model, metrics, feature_importance)
        """
        # Hold out most recent 20% for validation (temporal split)
        split_idx = int(len(X) * 0.8)

        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        w_train, w_val = weights[:split_idx], weights[split_idx:]

        # Train model
        model = GradientBoostingRegressor(**GBM_CONFIG)
        model.fit(X_train, y_train, sample_weight=w_train)

        # Evaluate
        y_train_pred = model.predict(X_train)
        y_val_pred = model.predict(X_val)

        metrics = {
            'train_mae': float(mean_absolute_error(y_train, y_train_pred)),
            'val_mae': float(mean_absolute_error(y_val, y_val_pred)),
            'train_rmse': float(np.sqrt(mean_squared_error(y_train, y_train_pred))),
            'val_rmse': float(np.sqrt(mean_squared_error(y_val, y_val_pred))),
            'train_r2': float(r2_score(y_train, y_train_pred)),
            'val_r2': float(r2_score(y_val, y_val_pred))
        }

        # Feature importance
        feature_importance = {
            feature: float(importance)
            for feature, importance in zip(FEATURES, model.feature_importances_)
        }

        return model, metrics, feature_importance

    def _serialize_model(self, model: GradientBoostingRegressor) -> bytes:
        """Serialize model to bytes using joblib.

        Args:
            model: Trained model

        Returns:
            Serialized model bytes
        """
        buffer = BytesIO()
        joblib.dump(model, buffer, compress=3)
        return buffer.getvalue()

    def _deserialize_model(self, model_blob: bytes) -> GradientBoostingRegressor:
        """Deserialize model from bytes.

        Args:
            model_blob: Serialized model bytes

        Returns:
            Loaded model
        """
        buffer = BytesIO(model_blob)
        return joblib.load(buffer)

    def get_user_model(self, user_id: int) -> Optional[GradientBoostingRegressor]:
        """Load user's trained GBM model.

        Args:
            user_id: User ID

        Returns:
            Loaded model if available, None otherwise
        """
        residual_model = UserResidualModel.query.filter_by(user_id=user_id).first()

        if not residual_model:
            return None

        try:
            return self._deserialize_model(residual_model.model_blob)
        except Exception as e:
            logger.error(f"Error loading GBM model from database: {e}")
            return None

    def predict_residual_corrections(
        self,
        model: GradientBoostingRegressor,
        segments: List[Dict]
    ) -> List[float]:
        """Predict residual multipliers for segments.

        Args:
            model: Trained GBM model
            segments: List of segment dicts with features

        Returns:
            List of residual multipliers (one per segment)
        """
        # Build feature DataFrame
        feature_rows = []

        for segment in segments:
            feature_rows.append({
                feature: segment.get(feature, 0)
                for feature in FEATURES
            })

        X = pd.DataFrame(feature_rows)

        # Predict
        residuals = model.predict(X)

        # Clip to reasonable range
        residuals = np.clip(residuals, ML_RESIDUAL_CLIP_MIN, ML_RESIDUAL_CLIP_MAX)

        return residuals.tolist()
