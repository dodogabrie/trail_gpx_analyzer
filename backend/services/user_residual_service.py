"""User residual collection service for hybrid prediction training.

Collects physics vs actual performance data from user's completed activities.
This data is used to train per-user ML models for prediction refinement.
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from database import db
from models import UserActivityResidual
from services.physics_prediction_service import PhysicsPredictionService
from services.segmentation_service import segment_activity_by_extrema
from config.hybrid_config import (
    get_logger,
    CURRENT_PHYSICS_MODEL_VERSION,
    RECENCY_HALF_LIFE_DAYS,
    SEGMENT_LENGTH_M
)

logger = get_logger(__name__)


class UserResidualService:
    """Collect and manage per-user prediction residuals.

    Compares physics predictions to actual performance on completed activities.
    Stores segment-level features and residuals for ML training.

    Privacy: Only processes individual user's own activity data.
    """

    def __init__(self):
        self.physics_service = PhysicsPredictionService()

    def collect_residuals_from_activity(
        self,
        user_id: int,
        activity_id: str,
        activity_streams: Dict,
        activity_metadata: Optional[Dict] = None
    ) -> Optional[UserActivityResidual]:
        """Collect residuals from a completed activity.

        Compares physics prediction to actual performance segment-by-segment.

        Args:
            user_id: User ID
            activity_id: Strava activity ID
            activity_streams: Activity streams dict with keys:
                - distance: cumulative distance (m)
                - velocity_smooth: smoothed velocity (m/s)
                - grade_smooth: smoothed grade (fraction)
                - altitude: elevation (m) - optional
                - moving: boolean array - optional
            activity_metadata: Optional metadata (date, distance, elevation)

        Returns:
            UserActivityResidual record if successful, None otherwise
        """
        try:
            # Validate required streams
            required = {'distance', 'velocity_smooth', 'grade_smooth'}
            if not required.issubset(activity_streams.keys()):
                logger.warning(f"Missing required streams for activity {activity_id}: {required - activity_streams.keys()}")
                return None

            # Prepare stream for physics prediction
            stream_df = self.physics_service.prepare_streams_for_calibration([activity_streams])
            if not stream_df:
                logger.error(f"Failed to prepare streams for activity {activity_id}")
                return None

            stream_df = stream_df[0]  # Get first (only) dataframe

            # Calibrate user params from this activity (for baseline physics)
            user_params = self.physics_service.calibrate([activity_streams])

            # Build route profile from activity (same as physics would see)
            points = self._build_route_profile_from_streams(activity_streams)

            if not points or len(points) < 2:
                logger.warning(f"Insufficient points for activity {activity_id}: {len(points) if points else 0} points")
                return None

            # Run physics prediction
            physics_result = self.physics_service.predict(points, user_params, user_id=user_id)

            if 'error' in physics_result:
                logger.error(f"Physics prediction failed for activity {activity_id}: {physics_result['error']}")
                return None

            # Extract actual performance from streams
            actual_segments = self._extract_actual_segments(activity_streams)

            if not actual_segments:
                logger.error(f"Failed to extract actual segments from activity {activity_id}")
                return None

            # Align physics and actual segments, compute residuals
            residual_segments = self._compute_residuals(
                physics_result['segments'],
                actual_segments,
                user_params['v_flat']
            )

            if not residual_segments:
                logger.warning(f"No residual segments computed for activity {activity_id}")
                return None

            # Extract metadata
            activity_date = activity_metadata.get('start_date') if activity_metadata else datetime.utcnow()
            if isinstance(activity_date, str):
                activity_date = datetime.fromisoformat(activity_date.replace('Z', '+00:00'))

            total_distance_km = activity_streams['distance'][-1] / 1000.0 if activity_streams.get('distance') else None

            total_elevation_gain_m = None
            if 'altitude' in activity_streams and len(activity_streams['altitude']) > 1:
                elev_diffs = np.diff(activity_streams['altitude'])
                total_elevation_gain_m = float(np.sum(elev_diffs[elev_diffs > 0]))

            # Compute recency weight
            recency_weight = self._compute_recency_weight(activity_date)

            # Create residual record
            residual = UserActivityResidual(
                user_id=user_id,
                activity_id=str(activity_id),
                activity_date=activity_date,
                total_distance_km=total_distance_km,
                total_elevation_gain_m=total_elevation_gain_m,
                activity_type=activity_metadata.get('type', 'Run') if activity_metadata else 'Run',
                segments=residual_segments,
                physics_model_version=CURRENT_PHYSICS_MODEL_VERSION,
                recency_weight=recency_weight
            )

            db.session.add(residual)
            db.session.commit()

            logger.info(f"Collected {len(residual_segments)} segments from activity {activity_id} (user {user_id})")
            return residual

        except Exception as e:
            logger.exception(f"Error collecting residuals from activity {activity_id}: {e}")
            db.session.rollback()
            return None

    def _build_route_profile_from_streams(self, streams: Dict) -> List[Dict]:
        """Build route profile (distance, elevation) from activity streams.

        Args:
            streams: Activity streams dict

        Returns:
            List of points [{distance, elevation}, ...]
        """
        distances = streams.get('distance', [])

        # Try to get elevation from altitude or compute from grade
        if 'altitude' in streams:
            elevations = streams['altitude']
        else:
            # Approximate elevation from grade (less accurate)
            grades = streams.get('grade_smooth', [])
            elevations = [0]
            for i in range(1, len(distances)):
                dist_delta = distances[i] - distances[i-1]
                elev_delta = dist_delta * grades[i-1] if i-1 < len(grades) else 0
                elevations.append(elevations[-1] + elev_delta)

        if len(distances) != len(elevations):
            logger.warning(f"Mismatched distances ({len(distances)}) and elevations ({len(elevations)})")
            return []

        return [
            {'distance': float(d), 'elevation': float(e)}
            for d, e in zip(distances, elevations)
        ]

    def _extract_actual_segments(self, streams: Dict, segment_len_m: float = SEGMENT_LENGTH_M) -> List[Dict]:
        """Extract actual performance segments from activity streams.

        Uses extrema-based segmentation (peaks/valleys) instead of fixed distance.

        Args:
            streams: Activity streams
            segment_len_m: DEPRECATED - kept for compatibility but not used

        Returns:
            List of segment dicts with actual performance metrics
        """
        # Use new extrema-based segmentation
        try:
            segments = segment_activity_by_extrema(streams)
            logger.info(f"Extracted {len(segments)} segments using extrema-based approach")
            return segments
        except Exception as e:
            logger.error(f"Extrema segmentation failed: {e}, falling back to fixed segmentation")
            # Fallback to old fixed-distance segmentation
            return self._extract_segments_fixed_distance(streams, segment_len_m)

    def _extract_segments_fixed_distance(self, streams: Dict, segment_len_m: float) -> List[Dict]:
        """DEPRECATED: Fixed-distance segmentation (fallback only).

        Args:
            streams: Activity streams
            segment_len_m: Segment length in meters

        Returns:
            List of segment dicts
        """
        distances = np.array(streams['distance'])
        velocities = np.array(streams['velocity_smooth'])
        grades = np.array(streams['grade_smooth'])

        has_altitude = 'altitude' in streams
        altitudes = np.array(streams['altitude']) if has_altitude else None

        segments = []
        max_dist = distances.max()
        starts = np.arange(0, max_dist, segment_len_m)

        for start in starts:
            end = start + segment_len_m
            mask = (distances >= start) & (distances < end)

            if mask.sum() < 5:
                continue

            seg_vel = velocities[mask]
            seg_grade = grades[mask]

            vel_mean = float(np.nanmean(seg_vel))
            grade_mean = float(np.nanmean(seg_grade))
            grade_std = float(np.nanstd(seg_grade))

            if not np.isfinite(vel_mean) or vel_mean <= 0:
                continue

            pace_min_per_km = 60.0 / (vel_mean * 3.6)

            elevation_gain = 0.0
            if has_altitude:
                seg_alt = altitudes[mask]
                if len(seg_alt) > 1:
                    elev_diffs = np.diff(seg_alt)
                    elevation_gain = float(np.sum(elev_diffs[elev_diffs > 0]))

            segments.append({
                'distance_m': float(start),
                'length_m': float(min(segment_len_m, max_dist - start)),
                'grade_mean': grade_mean,
                'grade_std': grade_std,
                'actual_pace_min_km': pace_min_per_km,
                'elevation_gain': elevation_gain
            })

        return segments

    def _compute_residuals(
        self,
        physics_segments: List[Dict],
        actual_segments: List[Dict],
        user_flat_pace_m_s: float
    ) -> List[Dict]:
        """Compute residuals between physics and actual performance.

        Args:
            physics_segments: Segments from physics prediction
            actual_segments: Segments from actual activity
            user_flat_pace_m_s: User's flat velocity (m/s) for normalization

        Returns:
            List of segment dicts with features and residuals
        """
        residuals = []

        # Convert flat velocity to flat pace
        flat_pace_min_km = (1000.0 / user_flat_pace_m_s) / 60.0

        # Align segments by distance
        for actual_seg in actual_segments:
            dist = actual_seg['distance_m']

            # Find matching physics segment (closest by distance)
            physics_seg = min(
                physics_segments,
                key=lambda p: abs(p['distance_m'] - dist)
            )

            # Skip if segments don't align well
            if abs(physics_seg['distance_m'] - dist) > 50:  # 50m tolerance
                continue

            # Compute pace ratios (pace / flat_pace)
            physics_pace_ratio = physics_seg['pace_min_km'] / flat_pace_min_km
            actual_pace_ratio = actual_seg['actual_pace_min_km'] / flat_pace_min_km

            # Residual = actual / physics
            residual = actual_pace_ratio / physics_pace_ratio if physics_pace_ratio > 0 else 1.0

            # Build feature dict for ML training
            residuals.append({
                'distance_m': dist,
                'grade_mean': actual_seg['grade_mean'],
                'grade_std': actual_seg['grade_std'],
                'abs_grade': abs(actual_seg['grade_mean']),
                'physics_pace_ratio': float(physics_pace_ratio),
                'actual_pace_ratio': float(actual_pace_ratio),
                'residual': float(residual),
                'elevation_gain': actual_seg.get('elevation_gain', 0.0)
            })

        return residuals

    def _compute_recency_weight(
        self,
        activity_date: datetime,
        reference_date: Optional[datetime] = None,
        half_life_days: int = RECENCY_HALF_LIFE_DAYS
    ) -> float:
        """Compute recency weight for activity using exponential decay.

        Args:
            activity_date: Date of activity
            reference_date: Reference date (default: now)
            half_life_days: Number of days for weight to decay to 50%

        Returns:
            Recency weight between 0.1 and 1.0
        """
        if reference_date is None:
            reference_date = datetime.utcnow()

        # Ensure both datetimes are naive for comparison
        if activity_date.tzinfo is not None:
            activity_date = activity_date.replace(tzinfo=None)
        if reference_date.tzinfo is not None:
            reference_date = reference_date.replace(tzinfo=None)

        days_ago = (reference_date - activity_date).days
        decay_rate = np.log(2) / half_life_days
        weight = np.exp(-decay_rate * days_ago)

        # Floor at 0.1 (don't completely discard old data)
        return max(float(weight), 0.1)

    def get_user_training_data(
        self,
        user_id: int,
        min_activities: int = 5,
        physics_version: Optional[str] = None
    ) -> List[UserActivityResidual]:
        """Get user's residual data for training.

        Args:
            user_id: User ID
            min_activities: Minimum number of activities required
            physics_version: Filter by physics model version (default: current)

        Returns:
            List of UserActivityResidual records
        """
        if physics_version is None:
            physics_version = CURRENT_PHYSICS_MODEL_VERSION

        residuals = (
            UserActivityResidual.query
            .filter_by(
                user_id=user_id,
                physics_model_version=physics_version,
                excluded_from_training=False  # Only include non-excluded activities
            )
            .order_by(UserActivityResidual.activity_date.desc())
            .all()
        )

        if len(residuals) < min_activities:
            logger.debug(f"User {user_id} has only {len(residuals)} activities (need {min_activities})")
            return []

        return residuals

    def get_training_segment_count(self, user_id: int) -> int:
        """Get total number of training segments for user.

        Args:
            user_id: User ID

        Returns:
            Total segment count across all activities
        """
        residuals = self.get_user_training_data(user_id, min_activities=0)
        return sum(len(r.segments) for r in residuals)
