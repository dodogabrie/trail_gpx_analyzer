"""Service for route time prediction using ML model.

Architecture:
- Loads pre-trained global_curve and ML model at initialization
- Converts between application data formats and predictor formats
- Handles calibration (flat_pace computation from Strava activity)
- Generates predictions with confidence intervals
- Finds similar activities for context
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from typing import Dict, List, Tuple, Optional

# Add predictor to path
PREDICTOR_PATH = Path(__file__).resolve().parents[2] / "data_analysis" / "predictor"
sys.path.insert(0, str(PREDICTOR_PATH))

from predictor import (
    build_global_curve,
    prepare_stream,
    compute_flat_pace,
    compute_anchor_ratios,
    personalize_curve
)
from ml_residual import predict_time_with_model


class PredictionService:
    """Service for route time prediction."""

    SEGMENT_LENGTH_M = 50.0  # GPX resampling resolution
    PREDICTION_SEGMENT_LENGTH_M = 200.0  # Must match training (200m)
    MODEL_PATH = PREDICTOR_PATH / "residual_model.joblib"
    PROCESSED_DATA_PATH = Path(__file__).resolve().parents[2] / "data_analysis" / "data" / "processed"

    def __init__(self):
        """Initialize service with global curve and ML model."""
        self.global_curve = None
        self.model = None
        self._load_resources()

    def _load_resources(self):
        """Load global curve and trained model."""
        # Try to load pre-cached curve first (fast)
        curve_json_path = PREDICTOR_PATH / "global_curve.json"
        if curve_json_path.exists():
            import json
            with open(curve_json_path) as f:
                data = json.load(f)
            self.global_curve = pd.DataFrame(data)
        else:
            # Fallback: build from processed data (slow)
            if self.PROCESSED_DATA_PATH.exists():
                print("Building global curve from processed data (this may take ~30s)...")
                self.global_curve = build_global_curve(self.PROCESSED_DATA_PATH)
            else:
                raise FileNotFoundError(f"No global curve data available. Need either {curve_json_path} or {self.PROCESSED_DATA_PATH}")

        # Load ML model
        if self.MODEL_PATH.exists():
            self.model = joblib.load(self.MODEL_PATH)
        else:
            raise FileNotFoundError(f"ML model not found at {self.MODEL_PATH}. Run: python data_analysis/predictor/train.py")

    def gpx_to_route_profile(self, gpx_data: Dict) -> pd.DataFrame:
        """Convert GPX data to route_profile format required by predictor.

        Args:
            gpx_data: Dict from GPXFile.data with structure:
                {
                    'points': [{'lat', 'lon', 'elevation', 'distance', 'time'}, ...],
                    'bounds': {...},
                    'total_distance': float
                }

        Returns:
            DataFrame with columns: distance_m, grade_percent

        Raises:
            ValueError: If GPX data is insufficient
        """
        points = gpx_data['points']

        if len(points) < 10:
            raise ValueError("GPX data insufficient for prediction (need at least 10 points)")

        # Extract arrays
        distances = np.array([p['distance'] for p in points])
        elevations = np.array([p['elevation'] for p in points])

        # Calculate grade between consecutive points
        grades = []
        for i in range(len(distances)):
            if i == 0:
                grades.append(0.0)
            else:
                dist_diff = distances[i] - distances[i-1]
                elev_diff = elevations[i] - elevations[i-1]
                if dist_diff > 0:
                    grade = (elev_diff / dist_diff) * 100.0
                    grades.append(np.clip(grade, -40, 40))  # Clip to predictor limits
                else:
                    grades.append(grades[-1] if grades else 0.0)

        # Resample to fixed segment size (50m)
        target_distances = np.arange(0, distances[-1], self.SEGMENT_LENGTH_M)
        interp_grades = np.interp(target_distances, distances, grades)
        interp_elevations = np.interp(target_distances, distances, elevations)

        return pd.DataFrame({
            'distance_m': target_distances,
            'grade_percent': interp_grades,
            'altitude_m': interp_elevations  # For elevation features in ML model
        })

    def strava_streams_to_predictor_format(self, streams: Dict) -> pd.DataFrame:
        """Convert Strava activity streams to predictor stream format.

        Args:
            streams: Dict from StravaActivity.streams with keys:
                time, distance, altitude, velocity_smooth, grade_smooth, moving

        Returns:
            DataFrame ready for prepare_stream() and compute_flat_pace()

        Raises:
            ValueError: If streams data is invalid
        """
        required_keys = ['distance', 'velocity_smooth', 'grade_smooth', 'moving']
        for key in required_keys:
            if key not in streams:
                raise ValueError(f"Missing required stream: {key}")

        df = pd.DataFrame({
            'distance': streams['distance'],
            'velocity_smooth': streams['velocity_smooth'],
            'grade_smooth': streams['grade_smooth'],
            'moving': streams['moving']
        })

        # Apply predictor's prepare_stream processing
        return prepare_stream(df)

    def calibrate_from_activity(self, streams: Dict) -> Tuple[float, Dict]:
        """Calibrate user's flat pace from a Strava activity.

        Args:
            streams: Strava activity streams dict

        Returns:
            Tuple of (flat_pace_min_per_km, diagnostics_dict)

        Raises:
            ValueError: If calibration fails (no flat samples, etc.)
        """
        df = self.strava_streams_to_predictor_format(streams)

        if df is None or df.empty:
            raise ValueError("Invalid streams data for calibration")

        flat_pace = compute_flat_pace(df)

        if flat_pace is None or flat_pace <= 0:
            raise ValueError("Could not compute flat pace - no flat terrain samples found")

        # Compute diagnostics
        anchor_ratios = compute_anchor_ratios(df, flat_pace)

        diagnostics = {
            'flat_pace_min_per_km': float(flat_pace),
            'anchor_count': len(anchor_ratios),
            'anchor_grades': list(anchor_ratios.keys()),
            'activity_distance_km': float(df['distance'].max() / 1000) if 'distance' in df.columns else None
        }

        return flat_pace, diagnostics

    def predict_route_time(
        self,
        gpx_data: Dict,
        flat_pace_min_per_km: float
    ) -> Dict:
        """Predict time for a GPX route using calibrated flat pace.

        Args:
            gpx_data: GPX data dict
            flat_pace_min_per_km: User's calibrated flat pace

        Returns:
            Dict with prediction results:
            {
                'total_time_seconds': float,
                'total_time_formatted': str (HH:MM:SS),
                'confidence_interval': {'lower': float, 'upper': float},
                'segments': [{'distance_m': float, 'grade': float, 'time_seconds': float}, ...],
                'statistics': {
                    'total_distance_km': float,
                    'total_elevation_gain_m': float,
                    'avg_grade_percent': float,
                    'flat_pace_min_per_km': float
                }
            }

        Raises:
            ValueError: If prediction fails
        """
        print("    → Converting GPX to route profile...")
        route_profile = self.gpx_to_route_profile(gpx_data)
        print(f"    → Route profile: {len(route_profile)} segments")

        # Predict using ML model
        print(f"    → Running ML model prediction...")
        print(f"       Route profile shape: {route_profile.shape}")
        print(f"       Flat pace: {flat_pace_min_per_km} min/km")
        print(f"       Distance range: {route_profile['distance_m'].min():.1f} to {route_profile['distance_m'].max():.1f} m")
        print(f"       Grade range: {route_profile['grade_percent'].min():.1f} to {route_profile['grade_percent'].max():.1f} %")

        total_time_sec = predict_time_with_model(
            route_profile,
            flat_pace_min_per_km,
            self.global_curve,
            self.model,
            segment_len_m=self.PREDICTION_SEGMENT_LENGTH_M  # Use 200m (training size)
        )
        print(f"    → ML prediction: {total_time_sec:.1f} seconds")

        if total_time_sec <= 0 or pd.isna(total_time_sec):
            print(f"    ⚠️ WARNING: Invalid prediction result: {total_time_sec}")
            raise ValueError(f"Prediction returned invalid result: {total_time_sec}")

        # Calculate confidence interval (based on conservative +/- 10% estimate)
        print(f"    → Calculating confidence interval...")
        ci_lower = total_time_sec * 0.90
        ci_upper = total_time_sec * 1.10

        # Generate segment breakdown
        print(f"    → Generating segment breakdown...")
        segments = self._generate_segment_breakdown(
            route_profile,
            flat_pace_min_per_km
        )
        print(f"    → Generated {len(segments)} display segments")

        # Calculate statistics
        print(f"    → Calculating elevation statistics...")
        points = gpx_data['points']
        elevations = [p['elevation'] for p in points]
        elev_gain = sum(max(0, elevations[i] - elevations[i-1])
                       for i in range(1, len(elevations)))
        print(f"    → Elevation gain: {elev_gain:.1f} m")

        return {
            'total_time_seconds': float(total_time_sec),
            'total_time_formatted': self._format_time(total_time_sec),
            'confidence_interval': {
                'lower_seconds': float(ci_lower),
                'upper_seconds': float(ci_upper),
                'lower_formatted': self._format_time(ci_lower),
                'upper_formatted': self._format_time(ci_upper)
            },
            'segments': segments,
            'statistics': {
                'total_distance_km': float(route_profile['distance_m'].max() / 1000),
                'total_elevation_gain_m': float(elev_gain),
                'avg_grade_percent': float(route_profile['grade_percent'].mean()),
                'flat_pace_min_per_km': float(flat_pace_min_per_km)
            }
        }

    def _generate_segment_breakdown(
        self,
        route_profile: pd.DataFrame,
        flat_pace: float,
        use_gradient_splits: bool = True
    ) -> List[Dict]:
        """Generate per-segment time breakdown using actual ML predictions.

        Args:
            route_profile: Route profile with distance_m, grade_percent, altitude_m
            flat_pace: User's flat pace in min/km
            use_gradient_splits: If True, split by grade changes; if False, use 1km segments

        Returns:
            List of segment dicts with distance, grade, time (from actual ML model)
        """
        # Run full ML prediction to get accurate times per 200m segment
        distances = route_profile['distance_m'].to_numpy()
        grades = route_profile['grade_percent'].to_numpy()
        has_altitude = 'altitude_m' in route_profile.columns
        altitudes = route_profile['altitude_m'].to_numpy() if has_altitude else None

        max_dist = distances.max()

        # Track predictions per 200m segment
        segment_times = []  # (start_m, end_m, time_sec, avg_grade)

        # State tracking (same as prediction)
        prev_grade = 0.0
        prev_pace_ratio = 1.0
        cum_elevation_gain = 0.0

        starts = np.arange(0, max_dist, self.PREDICTION_SEGMENT_LENGTH_M)
        for start in starts:
            end = start + self.PREDICTION_SEGMENT_LENGTH_M
            mask = (distances >= start) & (distances < end)
            if not mask.any():
                continue

            seg_grade = grades[mask]
            grade_mean = float(np.nanmean(seg_grade))
            grade_std = float(np.nanstd(seg_grade))

            baseline_ratio = float(
                np.interp(
                    grade_mean,
                    self.global_curve['grade'],
                    self.global_curve['median'],
                    left=self.global_curve['median'].iloc[0],
                    right=self.global_curve['median'].iloc[-1],
                )
            )
            if baseline_ratio <= 0:
                continue

            # Compute same features as prediction
            grade_change = grade_mean - prev_grade

            if has_altitude:
                seg_alt = altitudes[mask]
                if len(seg_alt) > 1:
                    elev_diffs = np.diff(seg_alt)
                    seg_elev_gain = float(np.sum(elev_diffs[elev_diffs > 0]))
                    cum_elevation_gain += seg_elev_gain
                    elevation_gain_rate = seg_elev_gain / (self.PREDICTION_SEGMENT_LENGTH_M / 1000.0)
                else:
                    elevation_gain_rate = 0.0
            else:
                elevation_gain_rate = 0.0

            rolling_500m_mask = (distances >= max(0, start - 500)) & (distances < start)
            if rolling_500m_mask.any():
                rolling_avg_grade_500m = float(np.nanmean(grades[rolling_500m_mask]))
            else:
                rolling_avg_grade_500m = grade_mean

            distance_remaining_km = (max_dist - start) / 1000.0

            features = pd.DataFrame({
                "grade_mean": [grade_mean],
                "grade_std": [grade_std],
                "abs_grade": [abs(grade_mean)],
                "cum_distance_km": [start / 1000.0],
                "prev_pace_ratio": [prev_pace_ratio],
                "grade_change": [grade_change],
                "cum_elevation_gain_m": [cum_elevation_gain],
                "elevation_gain_rate": [elevation_gain_rate],
                "rolling_avg_grade_500m": [rolling_avg_grade_500m],
                "distance_remaining_km": [distance_remaining_km],
            })

            residual_mult = float(self.model.predict(features)[0])
            ratio = baseline_ratio * residual_mult
            pace_min_per_km = flat_pace * ratio

            if pace_min_per_km > 0:
                speed_mps = 1000.0 / (pace_min_per_km * 60.0)
                seg_time = self.PREDICTION_SEGMENT_LENGTH_M / speed_mps
                segment_times.append((start, end, seg_time, grade_mean))

            prev_grade = grade_mean
            prev_pace_ratio = ratio

        # Choose segmentation strategy
        if use_gradient_splits:
            return self._create_gradient_splits(segment_times, max_dist)
        else:
            return self._create_km_splits(segment_times, max_dist)

    def _create_gradient_splits(
        self,
        segment_times: List[Tuple[float, float, float, float]],
        max_dist: float
    ) -> List[Dict]:
        """Create splits based on grade changes (more useful for pacing).

        Groups consecutive 200m segments with similar grades.
        Splits when grade changes by >5% or direction reverses.
        """
        if not segment_times:
            return []

        splits = []
        current_split_start = segment_times[0][0]
        current_split_segments = [segment_times[0]]

        for i in range(1, len(segment_times)):
            prev_seg = segment_times[i-1]
            curr_seg = segment_times[i]

            prev_grade = prev_seg[3]
            curr_grade = curr_seg[3]

            # Split conditions:
            # 1. Grade change > 5%
            # 2. Sign change (climb→descent or vice versa)
            # 3. Segment would be too long (>5km)
            grade_change = abs(curr_grade - prev_grade)
            sign_change = (prev_grade * curr_grade < 0) and (abs(prev_grade) > 2 or abs(curr_grade) > 2)
            current_length = curr_seg[1] - current_split_start

            if grade_change > 5.0 or sign_change or current_length > 5000:
                # Finish current split
                split_info = self._finalize_split(current_split_segments, current_split_start, len(splits) + 1)
                splits.append(split_info)

                # Start new split
                current_split_start = curr_seg[0]
                current_split_segments = [curr_seg]
            else:
                # Continue current split
                current_split_segments.append(curr_seg)

        # Add final split
        if current_split_segments:
            split_info = self._finalize_split(current_split_segments, current_split_start, len(splits) + 1)
            splits.append(split_info)

        return splits

    def _finalize_split(
        self,
        segments: List[Tuple[float, float, float, float]],
        start_m: float,
        split_num: int
    ) -> Dict:
        """Compute summary stats for a gradient-based split."""
        total_time = sum(seg[2] for seg in segments)
        total_dist = segments[-1][1] - start_m
        avg_grade = float(np.mean([seg[3] for seg in segments]))

        # Classify terrain
        if avg_grade > 8:
            terrain = "Steep Climb"
        elif avg_grade > 3:
            terrain = "Climb"
        elif avg_grade > -3:
            terrain = "Flat"
        elif avg_grade > -8:
            terrain = "Descent"
        else:
            terrain = "Steep Descent"

        pace_min_per_km = (total_time / 60.0) / (total_dist / 1000.0) if total_dist > 0 else 0

        return {
            'split_number': split_num,
            'start_km': round(start_m / 1000, 2),
            'end_km': round(segments[-1][1] / 1000, 2),
            'distance_km': round(total_dist / 1000, 2),
            'avg_grade_percent': round(avg_grade, 1),
            'terrain_type': terrain,
            'time_seconds': float(total_time),
            'time_formatted': self._format_time(total_time),
            'avg_pace_min_per_km': round(pace_min_per_km, 2)
        }

    def _create_km_splits(
        self,
        segment_times: List[Tuple[float, float, float, float]],
        max_dist: float
    ) -> List[Dict]:
        """Create traditional 1km splits (original method)."""
        km_segments = []
        km_segment_size = 1000.0
        num_km = int(max_dist / km_segment_size) + 1

        for km in range(num_km):
            start_m = km * km_segment_size
            end_m = (km + 1) * km_segment_size

            # Find all 200m segments that overlap with this km
            km_time = 0.0
            km_grades = []
            for seg_start, seg_end, seg_time, seg_grade in segment_times:
                # Check if segment overlaps with this km
                overlap_start = max(start_m, seg_start)
                overlap_end = min(end_m, seg_end)
                if overlap_start < overlap_end:
                    overlap_fraction = (overlap_end - overlap_start) / (seg_end - seg_start)
                    km_time += seg_time * overlap_fraction
                    km_grades.append(seg_grade)

            if km_time > 0:
                avg_grade = float(np.mean(km_grades)) if km_grades else 0.0
                pace_min_per_km = km_time / 60.0  # time in seconds for 1km

                km_segments.append({
                    'segment_km': km + 1,
                    'distance_m': float(min(km_segment_size, max_dist - start_m)),
                    'avg_grade_percent': avg_grade,
                    'time_seconds': float(km_time),
                    'time_formatted': self._format_time(km_time)
                })

        return km_segments

    def find_similar_activities(
        self,
        gpx_data: Dict,
        user_activities: List[Dict],
        tolerance: float = 0.15
    ) -> List[Dict]:
        """Find user's activities similar to the target GPX route.

        Args:
            gpx_data: Target GPX data
            user_activities: List of user's Strava activities
            tolerance: Distance tolerance (default 15%)

        Returns:
            List of matching activities sorted by distance similarity
        """
        target_distance = gpx_data['total_distance']
        min_dist = target_distance * (1 - tolerance)
        max_dist = target_distance * (1 + tolerance)

        matches = [
            activity for activity in user_activities
            if min_dist <= activity.get('distance', 0) <= max_dist
        ]

        # Sort by distance proximity
        matches.sort(key=lambda a: abs(a['distance'] - target_distance))

        return matches[:10]  # Return top 10

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as HH:MM:SS.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
