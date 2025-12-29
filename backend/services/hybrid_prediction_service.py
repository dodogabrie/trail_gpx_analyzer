"""Hybrid prediction service - orchestrates between prediction tiers.

Routes predictions through appropriate tier based on user's activity count:
- Tier 1 (0-4 activities): Pure physics baseline
- Tier 2 (5-14 activities): Physics with learned parameters
- Tier 3 (15+ activities): Physics + ML residual corrections

Privacy-compliant: Only uses individual user's own activity data.
"""

from typing import Dict, List, Optional
import numpy as np
from models import UserActivityResidual
from services.physics_prediction_service import PhysicsPredictionService
from services.parameter_learning_service import ParameterLearningService
from services.user_residual_service import UserResidualService
from services.residual_ml_service import ResidualMLService
from config.hybrid_config import (
    get_logger,
    TIER_2_MIN_ACTIVITIES,
    TIER_3_MIN_ACTIVITIES,
    CONFIDENCE_THRESHOLDS
)

logger = get_logger(__name__)


class HybridPredictionService:
    """Orchestrates hybrid predictions across tiers.

    Automatically selects the best prediction method based on available data.
    """

    def __init__(self):
        self.physics_service = PhysicsPredictionService()
        self.parameter_service = ParameterLearningService()
        self.residual_service = UserResidualService()
        self.ml_service = ResidualMLService()

    def predict(
        self,
        user_id: int,
        gpx_points: List[Dict],
        force_tier: Optional[str] = None,
        include_diagnostics: bool = False
    ) -> Dict:
        """Predict route time using best available method.

        Args:
            user_id: User ID
            gpx_points: Route points [{distance, elevation}, ...]
            force_tier: Force specific tier ('physics', 'parameter_learning', 'residual_ml')
            include_diagnostics: Include detailed diagnostics in response

        Returns:
            Prediction dict with metadata about method used
        """
        # Determine tier
        if force_tier:
            tier = self._validate_force_tier(force_tier, user_id)
        else:
            tier = self._determine_tier(user_id)

        logger.info(f"Using {tier} for user {user_id}")

        # Route to appropriate prediction method
        if tier == 'TIER_1_PHYSICS':
            result = self._predict_tier1(user_id, gpx_points, include_diagnostics)
        elif tier == 'TIER_2_PARAMETER_LEARNING':
            result = self._predict_tier2(user_id, gpx_points, include_diagnostics)
        elif tier == 'TIER_3_RESIDUAL_ML':
            result = self._predict_tier3(user_id, gpx_points, include_diagnostics)
        else:
            raise ValueError(f"Unknown tier: {tier}")

        return result

    def _determine_tier(self, user_id: int) -> str:
        """Determine appropriate tier based on user's activity count.

        Args:
            user_id: User ID

        Returns:
            Tier identifier string
        """
        activity_count = UserActivityResidual.query.filter_by(user_id=user_id).count()

        if activity_count >= TIER_3_MIN_ACTIVITIES:
            return 'TIER_3_RESIDUAL_ML'
        elif activity_count >= TIER_2_MIN_ACTIVITIES:
            return 'TIER_2_PARAMETER_LEARNING'
        else:
            return 'TIER_1_PHYSICS'

    def _validate_force_tier(self, force_tier: str, user_id: int) -> str:
        """Validate forced tier has sufficient data.

        Args:
            force_tier: Requested tier
            user_id: User ID

        Returns:
            Validated tier (may downgrade if insufficient data)
        """
        tier_map = {
            'physics': 'TIER_1_PHYSICS',
            'parameter_learning': 'TIER_2_PARAMETER_LEARNING',
            'residual_ml': 'TIER_3_RESIDUAL_ML'
        }

        tier = tier_map.get(force_tier, 'TIER_1_PHYSICS')

        # Check if user has enough data for requested tier
        activity_count = UserActivityResidual.query.filter_by(user_id=user_id).count()

        if tier == 'TIER_3_RESIDUAL_ML' and activity_count < TIER_3_MIN_ACTIVITIES:
            logger.info(f"Insufficient data for Tier 3 (user {user_id}: {activity_count} < {TIER_3_MIN_ACTIVITIES}), downgrading")
            tier = 'TIER_2_PARAMETER_LEARNING' if activity_count >= TIER_2_MIN_ACTIVITIES else 'TIER_1_PHYSICS'

        if tier == 'TIER_2_PARAMETER_LEARNING' and activity_count < TIER_2_MIN_ACTIVITIES:
            logger.info(f"Insufficient data for Tier 2 (user {user_id}: {activity_count} < {TIER_2_MIN_ACTIVITIES}), downgrading")
            tier = 'TIER_1_PHYSICS'

        return tier

    def _predict_tier1(
        self,
        user_id: int,
        gpx_points: List[Dict],
        include_diagnostics: bool
    ) -> Dict:
        """Tier 1: Pure physics prediction.

        Uses default or single-activity calibrated physics parameters.

        Args:
            user_id: User ID
            gpx_points: Route points
            include_diagnostics: Include diagnostics

        Returns:
            Prediction with metadata
        """
        # Use default params or single-activity calibration
        user_params = self.parameter_service.get_or_default_params(user_id)

        # Run physics prediction
        physics_result = self.physics_service.predict(
            gpx_points,
            user_params,
            user_id=user_id
        )

        if 'error' in physics_result:
            return physics_result

        # Add metadata
        activity_count = UserActivityResidual.query.filter_by(user_id=user_id).count()

        result = {
            **physics_result,
            'metadata': {
                'tier': 'TIER_1_PHYSICS',
                'method': 'physics_baseline',
                'confidence': 'MEDIUM',
                'activities_used': activity_count,
                'description': f'Physics model with default parameters (based on {activity_count} activities)'
            }
        }

        if include_diagnostics:
            result['diagnostics'] = {
                'tier': 'TIER_1_PHYSICS',
                'user_params': user_params,
                'activity_count': activity_count
            }

        return result

    def _predict_tier2(
        self,
        user_id: int,
        gpx_points: List[Dict],
        include_diagnostics: bool
    ) -> Dict:
        """Tier 2: Physics with learned parameters.

        Uses optimized physics parameters learned from user's activities.

        Args:
            user_id: User ID
            gpx_points: Route points
            include_diagnostics: Include diagnostics

        Returns:
            Prediction with metadata
        """
        # Get or train learned parameters
        learned_params = self.parameter_service.get_user_params(user_id)

        if not learned_params:
            # Train if not already trained
            logger.info(f"No learned params found for user {user_id}, training Tier 2...")
            trained = self.parameter_service.train_user_params(user_id)
            if trained:
                learned_params = trained.to_dict()
            else:
                # Fallback to Tier 1
                logger.warning(f"Tier 2 training failed for user {user_id}, falling back to Tier 1")
                return self._predict_tier1(user_id, gpx_points, include_diagnostics)

        # Run physics prediction with learned params
        physics_result = self.physics_service.predict(
            gpx_points,
            learned_params,
            user_id=user_id
        )

        if 'error' in physics_result:
            return physics_result

        # Add metadata
        activity_count = UserActivityResidual.query.filter_by(user_id=user_id).count()

        result = {
            **physics_result,
            'metadata': {
                'tier': 'TIER_2_PARAMETER_LEARNING',
                'method': 'physics_personalized',
                'confidence': 'MEDIUM_HIGH',
                'activities_used': activity_count,
                'description': f'Physics model with personalized parameters learned from your {activity_count} activities'
            }
        }

        if include_diagnostics:
            # Get learned params record for diagnostics
            from models import UserLearnedParams
            learned_record = UserLearnedParams.query.filter_by(user_id=user_id).first()

            result['diagnostics'] = {
                'tier': 'TIER_2_PARAMETER_LEARNING',
                'learned_params': learned_params,
                'optimization_score': learned_record.optimization_score if learned_record else None,
                'confidence_level': learned_record.confidence_level if learned_record else 'UNKNOWN',
                'activity_count': activity_count
            }

        return result

    def _predict_tier3(
        self,
        user_id: int,
        gpx_points: List[Dict],
        include_diagnostics: bool
    ) -> Dict:
        """Tier 3: Physics + ML residual corrections.

        Uses learned parameters + GBM model for residual corrections.

        Args:
            user_id: User ID
            gpx_points: Route points
            include_diagnostics: Include diagnostics

        Returns:
            Prediction with metadata
        """
        # Get or train learned parameters
        learned_params = self.parameter_service.get_user_params(user_id)

        if not learned_params:
            logger.info(f"No learned params for user {user_id}, training Tier 2...")
            trained = self.parameter_service.train_user_params(user_id)
            if trained:
                learned_params = trained.to_dict()
            else:
                logger.warning(f"Tier 2 training failed for user {user_id}, falling back to Tier 2 baseline")
                return self._predict_tier2(user_id, gpx_points, include_diagnostics)

        # Get or train GBM model
        gbm_model = self.ml_service.get_user_model(user_id)

        if not gbm_model:
            logger.info(f"No GBM model for user {user_id}, training Tier 3...")
            trained_model = self.ml_service.train_user_model(user_id)
            if trained_model:
                gbm_model = self.ml_service.get_user_model(user_id)
            else:
                logger.warning(f"Tier 3 GBM training failed for user {user_id}, falling back to Tier 2")
                return self._predict_tier2(user_id, gpx_points, include_diagnostics)

        # Run physics prediction with learned params (baseline)
        physics_result = self.physics_service.predict(
            gpx_points,
            learned_params,
            user_id=user_id
        )

        if 'error' in physics_result:
            return physics_result

        # Prepare segments for ML prediction (build features)
        segments_with_features = self._build_ml_features(physics_result['segments'])

        # Predict residual multipliers
        residual_multipliers = self.ml_service.predict_residual_corrections(
            gbm_model,
            segments_with_features
        )

        # Apply ML corrections to physics predictions
        corrected_segments = []
        total_time_seconds = 0

        for i, (seg, residual_mult) in enumerate(zip(physics_result['segments'], residual_multipliers)):
            # Correct pace with ML prediction
            corrected_pace = seg['pace_min_km'] * residual_mult
            corrected_time = (seg['length_m'] / 1000) / (60 / corrected_pace) if corrected_pace > 0 else 0

            corrected_seg = {
                **seg,
                'pace_min_km': corrected_pace,
                'time_s': corrected_time,
                'ml_correction': residual_mult
            }

            corrected_segments.append(corrected_seg)
            total_time_seconds += corrected_time

        # Rebuild aggregated segments for display (200m to larger groups)
        # For simplicity, use the existing segments structure
        physics_result['segments'] = corrected_segments
        physics_result['total_time_seconds'] = total_time_seconds

        # Reformat time
        hours = int(total_time_seconds // 3600)
        minutes = int((total_time_seconds % 3600) // 60)
        seconds = int(total_time_seconds % 60)
        physics_result['total_time_formatted'] = f"{hours}:{minutes:02d}:{seconds:02d}"

        # Update confidence interval (still ±5% for now)
        ci_lower = total_time_seconds * 0.95
        ci_upper = total_time_seconds * 1.05
        physics_result['confidence_interval'] = {
            'lower_seconds': ci_lower,
            'upper_seconds': ci_upper,
            'lower_formatted': f"{int(ci_lower//3600)}:{int((ci_lower%3600)//60):02d}:{int(ci_lower%60):02d}",
            'upper_formatted': f"{int(ci_upper//3600)}:{int((ci_upper%3600)//60):02d}:{int(ci_upper%60):02d}"
        }

        # Add metadata
        activity_count = UserActivityResidual.query.filter_by(user_id=user_id).count()

        result = {
            **physics_result,
            'metadata': {
                'tier': 'TIER_3_RESIDUAL_ML',
                'method': 'physics_ml_hybrid',
                'confidence': self._get_confidence_level('TIER_3_RESIDUAL_ML', activity_count),
                'activities_used': activity_count,
                'description': f'Physics model with ML corrections trained on your {activity_count} activities'
            }
        }

        if include_diagnostics:
            from models import UserLearnedParams, UserResidualModel
            learned_record = UserLearnedParams.query.filter_by(user_id=user_id).first()
            ml_record = UserResidualModel.query.filter_by(user_id=user_id).first()

            result['diagnostics'] = {
                'tier': 'TIER_3_RESIDUAL_ML',
                'learned_params': learned_params,
                'ml_model_metrics': ml_record.metrics if ml_record else None,
                'ml_feature_importance': ml_record.feature_importance if ml_record else None,
                'ml_segments_trained': ml_record.n_segments_trained if ml_record else None,
                'avg_ml_correction': float(np.mean(residual_multipliers)),
                'ml_correction_range': [float(np.min(residual_multipliers)), float(np.max(residual_multipliers))],
                'activity_count': activity_count
            }

        return result

    def _build_ml_features(self, segments: List[Dict]) -> List[Dict]:
        """Build ML features for segments.

        Args:
            segments: Physics prediction segments

        Returns:
            Segments enriched with ML features
        """
        enriched_segments = []

        prev_grade = 0.0
        prev_pace_ratio = 1.0
        cum_elevation_gain = 0.0

        # Compute total distance
        total_distance_m = segments[-1]['distance_m'] + segments[-1]['length_m'] if segments else 0

        for i, seg in enumerate(segments):
            distance_m = seg['distance_m']
            grade = seg.get('grade', 0)
            length_m = seg.get('length_m', 200)

            # Compute features
            grade_change = grade - prev_grade
            distance_remaining_km = (total_distance_m - distance_m) / 1000

            # Estimate elevation gain from grade
            elevation_gain = max(0, grade * length_m) if grade > 0 else 0
            cum_elevation_gain += elevation_gain
            elevation_gain_rate = elevation_gain / (length_m / 1000) if length_m > 0 else 0

            # Rolling average grade (simplified: use current grade)
            rolling_avg_grade_500m = grade

            enriched_seg = {
                **seg,
                'grade_mean': grade,
                'grade_std': 0.01,  # Placeholder (physics segments are uniform)
                'abs_grade': abs(grade),
                'cum_distance_km': distance_m / 1000,
                'distance_remaining_km': distance_remaining_km,
                'prev_pace_ratio': prev_pace_ratio,
                'grade_change': grade_change,
                'cum_elevation_gain_m': cum_elevation_gain,
                'elevation_gain_rate': elevation_gain_rate,
                'rolling_avg_grade_500m': rolling_avg_grade_500m
            }

            enriched_segments.append(enriched_seg)

            # Update state
            prev_grade = grade
            # Pace ratio = pace / flat_pace (approximate from segment pace)
            prev_pace_ratio = 1.0  # Placeholder

        return enriched_segments

    def get_user_tier_status(self, user_id: int) -> Dict:
        """Get user's current tier status and progress.

        Args:
            user_id: User ID

        Returns:
            Status dict with tier info and progress
        """
        activity_count = UserActivityResidual.query.filter_by(user_id=user_id).count()
        current_tier = self._determine_tier(user_id)

        # Calculate progress to next tier
        if current_tier == 'TIER_1_PHYSICS':
            next_tier = 'TIER_2_PARAMETER_LEARNING'
            activities_needed = TIER_2_MIN_ACTIVITIES - activity_count
            progress_pct = (activity_count / TIER_2_MIN_ACTIVITIES) * 100
        elif current_tier == 'TIER_2_PARAMETER_LEARNING':
            next_tier = 'TIER_3_RESIDUAL_ML'
            activities_needed = TIER_3_MIN_ACTIVITIES - activity_count
            progress_pct = (activity_count / TIER_3_MIN_ACTIVITIES) * 100
        else:
            next_tier = None
            activities_needed = 0
            progress_pct = 100

        # Get learned params if available
        from models import UserLearnedParams
        learned_params = UserLearnedParams.query.filter_by(user_id=user_id).first()

        return {
            'current_tier': current_tier,
            'activity_count': activity_count,
            'next_tier': next_tier,
            'activities_needed_for_next_tier': activities_needed,
            'progress_to_next_tier_pct': round(progress_pct, 1),
            'has_learned_params': learned_params is not None,
            'last_trained': learned_params.last_trained.isoformat() if learned_params else None,
            'confidence_level': self._get_confidence_level(current_tier, activity_count)
        }

    def _get_confidence_level(self, tier: str, activity_count: int) -> str:
        """Determine confidence level based on tier and activity count.

        Args:
            tier: Current tier
            activity_count: Number of activities

        Returns:
            Confidence level string
        """
        if tier == 'TIER_1_PHYSICS':
            return 'MEDIUM'
        elif tier == 'TIER_2_PARAMETER_LEARNING':
            if activity_count >= 10:
                return 'HIGH'
            else:
                return 'MEDIUM_HIGH'
        elif tier == 'TIER_3_RESIDUAL_ML':
            if activity_count >= 25:
                return 'VERY_HIGH'
            else:
                return 'HIGH'
        else:
            return 'UNKNOWN'
