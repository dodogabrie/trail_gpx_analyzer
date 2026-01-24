import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from .physics_model.calibration import calibrate_user_params, DEFAULT_PARAMS
from .physics_model.pipeline import (
    run_physics_prediction,
    DEFAULT_ULTRA_BETA,
    DEFAULT_ULTRA_GAMMA
)
from .physics_model.fatigue_calibration import (
    calibrate_fatigue_alpha_from_curve,
    calibrate_ultra_fatigue_params
)

class PhysicsPredictionService:
    def __init__(self):
        pass

    def prepare_streams_for_calibration(self, raw_activities_streams: List[Dict]) -> List[pd.DataFrame]:
        """
        Convert raw Strava stream dicts into DataFrames expected by calibration.
        """
        dfs = []
        for s in raw_activities_streams:
            try:
                # Basic validation
                if 'distance' not in s or 'velocity_smooth' not in s or 'grade_smooth' not in s:
                    continue
                
                # Create DF
                df = pd.DataFrame({
                    'distance': s['distance'],
                    'velocity_smooth': s['velocity_smooth'],
                    'grade_smooth': s['grade_smooth'],
                    'moving': s.get('moving', [True]*len(s['distance']))
                })
                dfs.append(df)
            except Exception as e:
                print(f"Error preparing stream: {e}")
                continue
        return dfs

    def calibrate(self, activity_streams: List[Dict]) -> Dict[str, float]:
        """
        Calibrate user parameters from a list of activity streams.
        """
        if not activity_streams:
            return DEFAULT_PARAMS
            
        dfs = self.prepare_streams_for_calibration(activity_streams)
        if not dfs:
            return DEFAULT_PARAMS
            
        return calibrate_user_params(dfs)

    def get_personalized_fatigue_alpha(self, user_id: int, route_distance_km: float = 20.0) -> float:
        """Get personalized fatigue_alpha from user's performance data.

        Args:
            user_id: User ID
            route_distance_km: Expected route distance for calibration

        Returns:
            Calibrated fatigue_alpha or default (0.3)
        """
        try:
            from models import PerformanceSnapshot

            # Get most recent snapshot with fatigue curve
            snapshot = (
                PerformanceSnapshot.query
                .filter_by(user_id=user_id)
                .filter(PerformanceSnapshot._fatigue_curve.isnot(None))
                .order_by(PerformanceSnapshot.snapshot_date.desc())
                .first()
            )

            if not snapshot:
                print(f"[FATIGUE] No performance snapshots with fatigue curves found for user {user_id}")
                print(f"[FATIGUE] Run /api/performance/refresh to generate fatigue curves from activity data")
                return 0.3

            if not snapshot.fatigue_curve:
                print(f"[FATIGUE] Snapshot found but no fatigue_curve data")
                return 0.3

            print(f"[FATIGUE] Found fatigue curve from snapshot {snapshot.id} ({snapshot.get_period_label()})")

            # Debug: print curve format
            curve = snapshot.fatigue_curve
            has_new_format = curve and 'overall' in curve and curve.get('overall', {}).get('fit', {}).get('params')
            has_legacy_format = curve and 'grades' in curve

            if has_new_format:
                print(f"[FATIGUE] Using NEW format with exponential fit")
            elif has_legacy_format:
                print(f"[FATIGUE] Using LEGACY format (grades-based)")
            else:
                print(f"[FATIGUE] Unknown format: {list(curve.keys()) if curve else 'None'}")

            fatigue_alpha = calibrate_fatigue_alpha_from_curve(
                snapshot.fatigue_curve,
                route_distance_km
            )

            print(f"[FATIGUE] Calibrated alpha={fatigue_alpha:.3f} for {route_distance_km:.1f}km")

            return fatigue_alpha

        except Exception as e:
            print(f"[FATIGUE] Error getting personalized fatigue: {e}")
            import traceback
            traceback.print_exc()
            return 0.3

    def get_personalized_ultra_params(
        self,
        user_id: int,
        user_params: Dict[str, float]
    ) -> Dict[str, float]:
        """Get personalized ultra fatigue parameters from user's race history.

        Queries user's Strava activities for ultra-distance races (>42km)
        and calibrates ultra_beta and ultra_gamma based on their performance.

        Args:
            user_id: User ID
            user_params: User's calibrated physics parameters (for v_flat)

        Returns:
            Dict with 'ultra_beta' and 'ultra_gamma' (defaults if no ultra data)
        """
        defaults = {
            'ultra_beta': DEFAULT_ULTRA_BETA,
            'ultra_gamma': DEFAULT_ULTRA_GAMMA
        }

        try:
            from models import StravaActivity

            # Query for ultra-distance activities (>42km)
            ultra_activities = (
                StravaActivity.query
                .filter_by(user_id=user_id)
                .filter(StravaActivity.distance > 42000)  # > 42km in meters
                .order_by(StravaActivity.distance.desc())
                .limit(20)  # Top 20 longest activities
                .all()
            )

            if not ultra_activities:
                print(f"[ULTRA] No ultra-distance activities found for user {user_id}")
                print(f"[ULTRA] Using default params: beta={defaults['ultra_beta']}, gamma={defaults['ultra_gamma']}")
                return defaults

            print(f"[ULTRA] Found {len(ultra_activities)} ultra-distance activities")

            # Extract race results from activities
            race_results = []
            for activity in ultra_activities:
                try:
                    streams = activity.streams
                    if not streams:
                        continue

                    # Calculate elapsed time from time stream
                    time_stream = streams.get('time', [])
                    if not time_stream:
                        continue

                    elapsed_seconds = max(time_stream) - min(time_stream)
                    distance_km = activity.distance / 1000.0
                    time_hours = elapsed_seconds / 3600.0

                    # Sanity check: reasonable pace (3-20 min/km average)
                    avg_pace_min_km = (time_hours * 60) / distance_km
                    if avg_pace_min_km < 3 or avg_pace_min_km > 20:
                        print(f"[ULTRA] Skipping {activity.name}: unrealistic pace {avg_pace_min_km:.1f} min/km")
                        continue

                    race_results.append({
                        'distance_km': distance_km,
                        'time_hours': time_hours,
                        'name': activity.name
                    })
                    print(f"[ULTRA] Activity: {activity.name} - {distance_km:.1f}km in {time_hours:.1f}h ({avg_pace_min_km:.1f} min/km)")

                except Exception as e:
                    print(f"[ULTRA] Error processing activity {activity.id}: {e}")
                    continue

            if len(race_results) < 2:
                print(f"[ULTRA] Need at least 2 valid ultra activities for calibration")
                print(f"[ULTRA] Using default params: beta={defaults['ultra_beta']}, gamma={defaults['ultra_gamma']}")
                return defaults

            # Calibrate ultra params from race results
            calibrated = calibrate_ultra_fatigue_params(race_results, user_params)
            print(f"[ULTRA] Calibrated from {len(race_results)} activities: beta={calibrated['ultra_beta']}, gamma={calibrated['ultra_gamma']}")

            return calibrated

        except Exception as e:
            print(f"[ULTRA] Error getting personalized ultra params: {e}")
            import traceback
            traceback.print_exc()
            return defaults

    def predict(
        self,
        gpx_points: List[Dict],
        user_params: Dict[str, float],
        user_id: Optional[int] = None,
        ultra_beta: float = DEFAULT_ULTRA_BETA,
        ultra_gamma: float = DEFAULT_ULTRA_GAMMA
    ) -> Dict:
        """
        Predict time for a GPX route.

        Uses a two-phase fatigue model:
        - Phase 1: Base eccentric fatigue (linear, unchanged for <42km)
        - Phase 2: Ultra-distance multiplier (exponential, activates >42km)

        Args:
            gpx_points: List of dicts {'distance', 'elevation'} (cumulative distance)
            user_params: Physics parameters
            user_id: Optional user ID for personalized fatigue calibration
            ultra_beta: Ultra fatigue intensity coefficient (default 0.4)
            ultra_gamma: Non-linearity exponent for ultra fatigue (default 1.5)

        Returns:
            Prediction result dict
        """
        if not gpx_points:
            return {'error': 'No GPX points'}
            
        # Convert to DataFrame
        df = pd.DataFrame(gpx_points)
        
        # Ensure we have distance and elevation columns
        if 'distance' not in df.columns or 'elevation' not in df.columns:
            # Maybe they are named differently in parsed GPX? 
            # The parsing service usually returns 'distance' (cumulative) and 'elevation'.
            # Let's check keys if needed, but assuming standard format from our other services.
            pass
            
        # Resample to 50m intervals (SAME AS ML MODEL) for consistent elevation
        # This is crucial for matching ML model's elevation calculations
        try:
            max_dist = df['distance'].max()
            new_dist = np.arange(0, max_dist, 50.0) # 50m steps (matches ML model)

            new_elev = np.interp(new_dist, df['distance'], df['elevation'])

            resampled_df = pd.DataFrame({
                'distance': new_dist,
                'elevation': new_elev
            })

            # Get personalized fatigue parameters if user_id provided
            fatigue_alpha = 0.3  # Default
            route_distance_km = max_dist / 1000.0

            # Determine effective ultra params
            effective_ultra_beta = ultra_beta
            effective_ultra_gamma = ultra_gamma

            if user_id:
                fatigue_alpha = self.get_personalized_fatigue_alpha(user_id, route_distance_km)
                print(f"[FATIGUE] Using personalized fatigue_alpha={fatigue_alpha:.3f} for {route_distance_km:.1f}km route")

                # Get personalized ultra params for ultra-distance routes
                if route_distance_km > 42:
                    ultra_params = self.get_personalized_ultra_params(user_id, user_params)
                    effective_ultra_beta = ultra_params['ultra_beta']
                    effective_ultra_gamma = ultra_params['ultra_gamma']
                    print(f"[ULTRA] Using personalized ultra params for {route_distance_km:.1f}km route")

            result = run_physics_prediction(
                resampled_df,
                user_params,
                fatigue_alpha=fatigue_alpha,
                ultra_beta=effective_ultra_beta,
                ultra_gamma=effective_ultra_gamma
            )

            # Log fatigue diagnostics
            if 'diagnostics' in result:
                diag = result['diagnostics']
                print(f"[FATIGUE] === Fatigue Diagnostics ===")
                print(f"[FATIGUE] Alpha: {diag.get('fatigue_alpha', 'N/A'):.3f}")
                print(f"[FATIGUE] Ultra beta: {diag.get('ultra_beta', 'N/A'):.3f}")
                print(f"[FATIGUE] Ultra gamma: {diag.get('ultra_gamma', 'N/A'):.3f}")
                print(f"[FATIGUE] Route: {diag.get('total_distance_km', 'N/A'):.1f}km")
                print(f"[FATIGUE] Final eccentric load: {diag.get('final_eccentric_load', 0):.1f}")
                print(f"[FATIGUE] Final base fatigue: {diag.get('final_base_fatigue', 1.0):.3f}")
                print(f"[FATIGUE] Final ultra multiplier: {diag.get('final_ultra_multiplier', 1.0):.3f} ({(diag.get('final_ultra_multiplier', 1.0) - 1.0) * 100:.1f}% from ultra)")
                print(f"[FATIGUE] Final fatigue factor: {diag.get('final_fatigue_factor', 1.0):.3f} ({(diag.get('final_fatigue_factor', 1.0) - 1.0) * 100:.1f}% slower)")
                print(f"[FATIGUE] Max fatigue factor: {diag.get('max_fatigue_factor', 1.0):.3f}")
                print(f"[FATIGUE] Max ultra multiplier: {diag.get('max_ultra_multiplier', 1.0):.3f}")
                print(f"[FATIGUE] Avg slowdown: {diag.get('avg_fatigue_slowdown_pct', 0):.2f}%")

                max_fatigue_segs = diag.get('segments_with_max_fatigue', [])
                if max_fatigue_segs:
                    print(f"[FATIGUE] Top fatigued segments:")
                    for i, seg in enumerate(max_fatigue_segs[:3], 1):
                        print(f"[FATIGUE]   {i}. {seg['distance_km']:.1f}km, grade={seg['grade_pct']:.1f}%, factor={seg['fatigue_factor']:.3f} (base={seg.get('base_fatigue', 'N/A'):.3f}, ultra={seg.get('ultra_multiplier', 'N/A'):.3f}), pace={seg['pace_min_km']:.2f}min/km")

            # Add resampled elevation profile for accurate elevation gain calculation
            result['resampled_elevations'] = new_elev.tolist()
            result['resampled_distances'] = new_dist.tolist()
            result['user_params'] = user_params
            result['fatigue_alpha'] = fatigue_alpha
            result['ultra_beta'] = effective_ultra_beta
            result['ultra_gamma'] = effective_ultra_gamma

            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
