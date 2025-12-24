"""Performance tracking service for dynamic star plot and gamification.

Calculates and stores user performance snapshots over time to enable:
- Historical performance tracking
- Trend analysis
- Achievement detection
- Dynamic star plot visualizations
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    User, PerformanceSnapshot, GradePerformanceHistory,
    UserAchievement, StravaActivity
)
from database import db
from services.cache_service import CacheService
from services.strava_service import StravaService
import numpy as np
import pandas as pd

# Import predictor logic for curve calculation
predictor_path = Path(__file__).resolve().parents[2] / 'data_analysis' / 'predictor'
sys.path.insert(0, str(predictor_path))
from predictor import (
    prepare_stream,
    compute_flat_pace,
    compute_anchor_ratios,
    ANCHOR_GRADES,
    ANCHOR_WINDOW,
    FLAT_BASE_RANGE,
    GRADE_BIN_WIDTH,
    MIN_POINTS_PER_BIN,
    MAX_GRADE_ABS
)

FATIGUE_BASELINE_KM = 2.0
FATIGUE_STEP_KM = 2.0
FATIGUE_MAX_KM_CAP = 50.0
FATIGUE_DISTANCE_WINDOW_KM = 1.0
FATIGUE_DISTANCE_WINDOW_FRACTION = 0.05  # widen window for longer distances
FATIGUE_MIN_POINTS_PER_ACTIVITY = 6
FATIGUE_MIN_ACTIVITIES_PER_POINT = 2

# Grade bands (percent). These are intentionally wide to improve sample density.
FATIGUE_GRADE_BANDS = [
    {"key": "vertical_downhill", "label": "Vertical Downhill", "min": -np.inf, "max": -15.0},
    {"key": "downhill", "label": "Downhill", "min": -15.0, "max": -2.0},
    {"key": "flat", "label": "Flat", "min": -2.0, "max": 2.0},
    {"key": "uphill", "label": "Uphill", "min": 2.0, "max": 15.0},
    {"key": "vertical_uphill", "label": "Vertical Uphill", "min": 15.0, "max": np.inf},
]

def _aligned_stream_df(streams: Dict) -> Optional[pd.DataFrame]:
    """Build a DataFrame from a Strava streams dict, robust to mismatched list lengths."""
    if not isinstance(streams, dict):
        return None
    distance = streams.get("distance")
    grade = streams.get("grade_smooth")
    velocity = streams.get("velocity_smooth")
    if not isinstance(distance, list) or not isinstance(grade, list) or not isinstance(velocity, list):
        return None

    lengths = [len(distance), len(grade), len(velocity)]
    moving = streams.get("moving")
    if isinstance(moving, list):
        lengths.append(len(moving))
    min_len = min(lengths) if lengths else 0
    if min_len <= 0:
        return None

    df = pd.DataFrame({
        "distance": distance[:min_len],
        "grade_smooth": grade[:min_len],
        "velocity_smooth": velocity[:min_len],
        "moving": (moving[:min_len] if isinstance(moving, list) else [True] * min_len),
    })
    return df

def _finite_or_none(value: float) -> Optional[float]:
    try:
        v = float(value)
    except Exception:
        return None
    return v if np.isfinite(v) else None

def _fit_saturating_exponential(
    *,
    distances_km: List[float],
    values: List[Optional[float]],
    weights: Optional[List[Optional[float]]] = None,
    min_points: int = 3,
) -> Optional[Dict]:
    """Fit y(d) = 1 + a * (1 - exp(-d/tau)) to (d, y) with weights.

    Uses a simple grid-search over tau and solves for a in closed-form (weighted least squares),
    then clamps a >= 0. Returns None if insufficient valid points.
    """
    if not distances_km or not values or len(distances_km) != len(values):
        return None

    ds = np.array([float(d) for d in distances_km], dtype=float)
    ys = np.array([np.nan if v is None else float(v) for v in values], dtype=float)
    ws = None
    if weights and len(weights) == len(values):
        ws = np.array([0.0 if w is None else float(w) for w in weights], dtype=float)
        ws = np.where(np.isfinite(ws) & (ws > 0), ws, 0.0)

    valid = np.isfinite(ds) & np.isfinite(ys)
    if ws is not None:
        valid = valid & (ws > 0)

    if int(valid.sum()) < min_points:
        return None

    d = ds[valid]
    y = ys[valid]
    w = ws[valid] if ws is not None else np.ones_like(y)

    # Search tau over a log grid (km). Keep it within a plausible range.
    tau_candidates = np.logspace(np.log10(0.5), np.log10(max(5.0, float(np.nanmax(d)) * 2.0)), num=60)

    best = None
    for tau in tau_candidates:
        x = 1.0 - np.exp(-d / tau)
        denom = np.sum(w * x * x)
        if denom <= 0:
            continue
        a = float(np.sum(w * x * (y - 1.0)) / denom)
        if not np.isfinite(a):
            continue
        a = max(0.0, a)
        y_hat = 1.0 + a * x
        sse = float(np.sum(w * (y - y_hat) ** 2))
        if best is None or sse < best["sse"]:
            best = {"a": a, "tau": float(tau), "sse": sse}

    if best is None:
        return None

    # Generate fitted values for all distances (even if some observed are missing).
    tau = best["tau"]
    a = best["a"]
    x_all = 1.0 - np.exp(-ds / tau)
    y_fit = (1.0 + a * x_all).tolist()
    return {"params": {"a": round(a, 6), "tau_km": round(tau, 4), "sse": round(best["sse"], 6)}, "values": y_fit}


class PerformanceTracker:
    """Service for tracking user performance over time."""

    def __init__(self, cache_service: CacheService = None, strava_service: StravaService = None):
        """Initialize performance tracker.

        Args:
            cache_service: Optional CacheService instance
            strava_service: Optional StravaService instance
        """
        self.cache_service = cache_service or CacheService()
        self.strava_service = strava_service

    def get_period_dates(self, period_type: str, offset: int = 0) -> Tuple[datetime, datetime]:
        """Calculate start and end dates for a period.

        Args:
            period_type: 'weekly', 'monthly', or 'quarterly'
            offset: Number of periods to go back (0 = current period)

        Returns:
            Tuple of (period_start, period_end)
        """
        now = datetime.utcnow()

        if period_type == 'weekly':
            # Get start of current week (Monday)
            days_since_monday = now.weekday()
            week_start = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            # Go back offset weeks
            period_start = week_start - timedelta(weeks=offset)
            period_end = period_start + timedelta(days=7)

        elif period_type == 'monthly':
            # Get start of current month
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Go back offset months
            target_month = month_start.month - offset
            target_year = month_start.year
            while target_month < 1:
                target_month += 12
                target_year -= 1
            period_start = month_start.replace(year=target_year, month=target_month)

            # Calculate end of month
            next_month = target_month + 1
            next_year = target_year
            if next_month > 12:
                next_month = 1
                next_year += 1
            period_end = period_start.replace(year=next_year, month=next_month)

        elif period_type == 'quarterly':
            # Get start of current quarter
            current_quarter = (now.month - 1) // 3
            quarter_start_month = current_quarter * 3 + 1
            quarter_start = now.replace(
                month=quarter_start_month, day=1,
                hour=0, minute=0, second=0, microsecond=0
            )
            # Go back offset quarters
            target_quarter = current_quarter - offset
            target_year = quarter_start.year
            while target_quarter < 0:
                target_quarter += 4
                target_year -= 1
            period_start = quarter_start.replace(
                year=target_year,
                month=(target_quarter * 3 + 1)
            )
            period_end = period_start + timedelta(days=90)  # Approximate

        else:
            raise ValueError(f"Invalid period_type: {period_type}")

        return period_start, period_end

    def get_activities_in_period(
        self,
        user: User,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict]:
        """Get user's activities within a time period.

        Args:
            user: User instance
            period_start: Start of period
            period_end: End of period

        Returns:
            List of activity dicts from cache/Strava
        """
        # Try to get from cache first
        cached_activities = self.cache_service.get_cached_activities(user.id)

        if cached_activities:
            # Filter by date range
            activities_in_period = [
                act for act in cached_activities
                if period_start.isoformat() <= act.get('start_date', '') < period_end.isoformat()
            ]
            if activities_in_period:
                print(f"✓ Found {len(activities_in_period)} cached activities in period")
                return activities_in_period

        # Fallback: use activities already persisted in the DB (no network required)
        try:
            from models import StravaActivity

            db_activities = (
                StravaActivity.query
                .filter_by(user_id=user.id)
                .filter(StravaActivity.start_date >= period_start)
                .filter(StravaActivity.start_date < period_end)
                .order_by(StravaActivity.start_date.desc())
                .all()
            )
            if db_activities:
                print(f"✓ Found {len(db_activities)} DB activities in period")
                return [
                    {
                        "id": int(a.strava_id),
                        "name": a.name,
                        "distance": a.distance,
                        "start_date": a.start_date.isoformat(),
                    }
                    for a in db_activities
                ]
        except Exception:
            pass

        # Fetch from Strava if not cached or cache is stale
        if self.strava_service and user.access_token:
            print(f"⚠️ Fetching activities from Strava for period {period_start.date()} to {period_end.date()}")
            after_timestamp = int(period_start.timestamp())
            activities = self.strava_service.fetch_activities(
                user.access_token,
                after_timestamp=after_timestamp
            )
            # Filter by end date
            activities_in_period = [
                act for act in activities
                if act.get('start_date', '') < period_end.isoformat()
            ]
            return activities_in_period

        return []

    def calculate_period_performance(
        self,
        user_id: int,
        period_type: str = 'weekly',
        offset: int = 0,
        force_recalculate: bool = False
    ) -> Optional[PerformanceSnapshot]:
        """Calculate performance snapshot for a time period.

        Args:
            user_id: User ID
            period_type: 'weekly', 'monthly', or 'quarterly'
            offset: Number of periods back (0 = current)
            force_recalculate: Recalculate even if snapshot exists

        Returns:
            PerformanceSnapshot instance or None if insufficient data
        """
        user = User.query.get(user_id)
        if not user:
            print(f"✗ User {user_id} not found")
            return None

        # Get period dates
        period_start, period_end = self.get_period_dates(period_type, offset)
        print(f"Calculating {period_type} performance for {period_start.date()} to {period_end.date()}")

        # Check if snapshot already exists
        if not force_recalculate:
            existing = PerformanceSnapshot.query.filter_by(
                user_id=user_id,
                period_type=period_type,
                period_start=period_start
            ).first()
            if existing:
                print(f"✓ Snapshot already exists (id={existing.id})")
                if existing.fatigue_curve is None:
                    print("  Backfilling missing fatigue_curve...")
                    try:
                        activities = self.get_activities_in_period(user, period_start, period_end)
                        if activities:
                            activity_streams = []
                            for act in activities:
                                activity_id = act.get('id')
                                if not activity_id:
                                    continue

                                streams = self.cache_service.get_cached_streams(user_id, activity_id)
                                if not streams and self.strava_service and user.access_token:
                                    streams = self.strava_service.download_streams(activity_id, user.access_token)
                                    start_date_str = act.get('start_date')
                                    start_date = (
                                        datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                                        if start_date_str
                                        else None
                                    )
                                    self.cache_service.cache_streams(
                                        user_id,
                                        activity_id,
                                        act.get('name'),
                                        act.get('distance'),
                                        start_date,
                                        streams
                                    )

                                if streams:
                                    activity_streams.append(streams)

                            if activity_streams:
                                existing.fatigue_curve = self._calculate_fatigue_curve(activity_streams, activities)
                                db.session.commit()
                                print("  ✓ fatigue_curve backfilled")
                            else:
                                print("  ✗ Could not backfill fatigue_curve (no streams)")
                        else:
                            print("  ✗ Could not backfill fatigue_curve (no activities)")
                    except Exception as e:
                        print(f"  ✗ Error backfilling fatigue_curve: {e}")
                        db.session.rollback()
                return existing

        # Get activities in period
        activities = self.get_activities_in_period(user, period_start, period_end)

        if not activities:
            print(f"✗ No activities found in period")
            return None

        print(f"✓ Found {len(activities)} activities in period")

        # Download streams for activities (use cache when available)
        activity_streams = []
        total_distance = 0
        total_elevation = 0

        for act in activities:
            activity_id = act.get('id')
            if not activity_id:
                continue

            # Get cached streams or download
            streams = self.cache_service.get_cached_streams(user_id, activity_id)

            if not streams and self.strava_service and user.access_token:
                print(f"  Downloading streams for activity {activity_id}...")
                streams = self.strava_service.download_streams(activity_id, user.access_token)
                # Cache the streams
                start_date_str = act.get('start_date')
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')) if start_date_str else None
                self.cache_service.cache_streams(
                    user_id,
                    activity_id,
                    act.get('name'),
                    act.get('distance'),
                    start_date,
                    streams
                )

            if streams:
                activity_streams.append(streams)
                total_distance += act.get('distance', 0) / 1000  # Convert to km
                total_elevation += act.get('total_elevation_gain', 0)

        if not activity_streams:
            print(f"✗ No valid activity streams found")
            return None

        print(f"✓ Processing {len(activity_streams)} activity streams")

        # Calculate pace-grade curve using predictor logic
        try:
            curve_data = self._calculate_curve_from_streams(activity_streams)
            if not curve_data:
                print(f"✗ Failed to calculate curve")
                return None

            flat_pace = curve_data['flat_pace']
            anchor_ratios = curve_data['anchor_ratios']
            grade_stats = curve_data['grade_stats']

            print(f"✓ Calculated performance: flat_pace={flat_pace:.2f} min/km")

        except Exception as e:
            print(f"✗ Error calculating curve: {e}")
            import traceback
            traceback.print_exc()
            return None

        # Calculate fatigue curve from activity streams
        fatigue_curve = self._calculate_fatigue_curve(activity_streams, activities)

        # Create snapshot
        snapshot = PerformanceSnapshot(
            user_id=user_id,
            snapshot_date=datetime.utcnow(),
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            flat_pace=flat_pace,
            anchor_ratios=anchor_ratios,
            activity_count=len(activities),
            total_distance_km=total_distance,
            total_elevation_m=total_elevation
        )
        snapshot.fatigue_curve = fatigue_curve

        db.session.add(snapshot)
        db.session.flush()  # Get snapshot.id

        # Add grade-specific performance history
        for grade, stats in grade_stats.items():
            grade_perf = GradePerformanceHistory(
                user_id=user_id,
                snapshot_id=snapshot.id,
                grade_bucket=grade,
                avg_pace=stats['avg_pace'],
                median_pace=stats['median_pace'],
                sample_count=stats['sample_count'],
                iqr_pace=stats.get('iqr_pace')
            )
            db.session.add(grade_perf)

        db.session.commit()
        print(f"✓ Created snapshot (id={snapshot.id})")

        return snapshot

    def _calculate_curve_from_streams(self, activity_streams: List[Dict]) -> Optional[Dict]:
        """Calculate pace-grade curve from activity streams.

        Args:
            activity_streams: List of activity stream dicts

        Returns:
            Dict with flat_pace, anchor_ratios, and grade_stats
        """
        # Convert streams to DataFrames and prepare them
        dfs = []
        for streams in activity_streams:
            # Convert dict to DataFrame
            required = {"velocity_smooth", "grade_smooth", "moving"}
            if not required.issubset(streams):
                continue

            df = pd.DataFrame({
                "velocity_smooth": streams["velocity_smooth"],
                "grade_smooth": streams["grade_smooth"],
                "moving": streams["moving"],
            })

            if df.empty:
                continue

            # Prepare stream (adds pace_min_per_km column)
            df = prepare_stream(df)
            if df is not None and len(df) > 0:
                dfs.append(df)

        if not dfs:
            return None

        # Concatenate all DataFrames
        df_all = pd.concat(dfs, ignore_index=True)

        # Compute flat pace
        try:
            flat_pace = compute_flat_pace(df_all)
        except ValueError as e:
            print(f"Error computing flat pace: {e}")
            return None

        # Compute anchor ratios
        anchor_ratios = compute_anchor_ratios(df_all, flat_pace, ANCHOR_GRADES)

        if not anchor_ratios:
            return None

        # Calculate grade-specific stats for storage (bin by grade and aggregate)
        df_filtered = df_all[
            df_all["grade_smooth"].between(-MAX_GRADE_ABS, MAX_GRADE_ABS, inclusive="both")
        ].copy()

        grade_bins = np.arange(-MAX_GRADE_ABS, MAX_GRADE_ABS + GRADE_BIN_WIDTH, GRADE_BIN_WIDTH)
        df_filtered["grade_bin"] = pd.cut(
            df_filtered["grade_smooth"], bins=grade_bins, include_lowest=True
        )

        binned = (
            df_filtered.groupby("grade_bin", observed=False)["pace_min_per_km"]
            .agg(["median", "mean", "count"])
            .reset_index()
        )
        binned = binned[binned["count"] >= MIN_POINTS_PER_BIN]

        if binned.empty:
            # Fallback: use anchor ratios directly
            grade_stats = {}
            for grade in ANCHOR_GRADES:
                if grade in anchor_ratios:
                    pace = flat_pace * anchor_ratios[grade]
                    grade_stats[grade] = {
                        'avg_pace': float(pace),
                        'median_pace': float(pace),
                        'sample_count': 0,
                        'iqr_pace': 0.0
                    }
        else:
            # Calculate stats from binned data
            binned["grade"] = binned["grade_bin"].apply(
                lambda interval: (interval.left + interval.right) / 2 if pd.notna(interval) else 0
            ).astype(float)

            grade_stats = {}
            for grade in ANCHOR_GRADES:
                # Find closest bin
                close_bins = binned[abs(binned["grade"] - grade) <= 2.0]
                if len(close_bins) > 0:
                    grade_stats[grade] = {
                        'avg_pace': float(close_bins["mean"].mean()),
                        'median_pace': float(close_bins["median"].median()),
                        'sample_count': int(close_bins["count"].sum()),
                        'iqr_pace': 0.0  # Simplified for now
                    }

        return {
            'flat_pace': float(flat_pace),
            'anchor_ratios': {str(int(k)): float(v) for k, v in anchor_ratios.items()},
            'grade_stats': grade_stats
        }

    def get_snapshots(
        self,
        user_id: int,
        period_type: str = 'weekly',
        limit: int = 12
    ) -> List[PerformanceSnapshot]:
        """Get recent performance snapshots for user.

        Args:
            user_id: User ID
            period_type: Filter by period type
            limit: Maximum number of snapshots to return

        Returns:
            List of PerformanceSnapshot instances, newest first
        """
        snapshots = PerformanceSnapshot.query.filter_by(
            user_id=user_id,
            period_type=period_type
        ).order_by(PerformanceSnapshot.period_start.desc()).limit(limit).all()

        return snapshots

    def get_performance_trend(
        self,
        user_id: int,
        grade: int,
        periods: int = 12
    ) -> List[Dict]:
        """Get performance trend for specific grade over time.

        Args:
            user_id: User ID
            grade: Grade bucket (e.g., -30, -20, -10, 0, 10, 20, 30)
            periods: Number of periods to retrieve

        Returns:
            List of dicts with date, pace, sample_count
        """
        grade_perfs = GradePerformanceHistory.query.join(
            PerformanceSnapshot
        ).filter(
            GradePerformanceHistory.user_id == user_id,
            GradePerformanceHistory.grade_bucket == grade
        ).order_by(
            PerformanceSnapshot.period_start.desc()
        ).limit(periods).all()

        trend = []
        for gp in reversed(grade_perfs):  # Reverse to get chronological order
            snapshot = gp.snapshot
            trend.append({
                'date': snapshot.get_period_label(),
                'pace': gp.median_pace or gp.avg_pace,
                'sample_count': gp.sample_count
            })

        return trend

    def compare_periods(
        self,
        snapshot1: PerformanceSnapshot,
        snapshot2: PerformanceSnapshot
    ) -> Dict:
        """Compare two performance snapshots.

        Args:
            snapshot1: First snapshot (typically current/recent)
            snapshot2: Second snapshot (typically older)

        Returns:
            Dict with improvements/declines by grade
        """
        changes = {
            'flat_pace': snapshot1.flat_pace - snapshot2.flat_pace,
            'flat_pace_pct': ((snapshot1.flat_pace - snapshot2.flat_pace) / snapshot2.flat_pace) * 100,
            'grades': {}
        }

        anchor1 = snapshot1.anchor_ratios
        anchor2 = snapshot2.anchor_ratios

        for grade_str in anchor1.keys():
            if grade_str in anchor2:
                pace1 = snapshot1.flat_pace * anchor1[grade_str]
                pace2 = snapshot2.flat_pace * anchor2[grade_str]
                change = pace1 - pace2
                pct_change = (change / pace2) * 100 if pace2 > 0 else 0

                changes['grades'][grade_str] = {
                    'change': change,
                    'pct': pct_change
                }

        return changes

    def detect_achievements(self, user_id: int) -> List[UserAchievement]:
        """Detect new achievements for user based on recent performance.

        Args:
            user_id: User ID

        Returns:
            List of newly detected (unsaved) UserAchievement instances
        """
        achievements = []

        # Get recent snapshots for comparison
        snapshots = self.get_snapshots(user_id, period_type='weekly', limit=8)

        if len(snapshots) < 2:
            # Need at least 2 snapshots to detect improvements
            return achievements

        current = snapshots[0]
        previous = snapshots[1]

        # Compare performance
        changes = self.compare_periods(current, previous)

        # 1. Improvement achievements (5% pace improvement)
        IMPROVEMENT_THRESHOLD = -5.0  # negative = faster

        # Flat pace improvement
        if changes['flat_pace_pct'] <= IMPROVEMENT_THRESHOLD:
            achievements.append(UserAchievement(
                user_id=user_id,
                achievement_type='improvement',
                achievement_name='Speed Demon',
                achievement_description=f"{abs(changes['flat_pace_pct']):.1f}% improvement on flat terrain",
                grade_category='flat',
                metric_value=abs(changes['flat_pace_pct'])
            ))

        # Grade-specific improvements
        for grade_str, change_data in changes['grades'].items():
            grade = int(grade_str)
            pct = change_data['pct']

            if pct <= IMPROVEMENT_THRESHOLD:
                # Determine achievement name based on grade
                if grade >= 15:
                    name = 'Climbing Master'
                    category = 'uphill'
                    desc = f"{abs(pct):.1f}% improvement on steep climbs ({grade}% grade)"
                elif grade <= -15:
                    name = 'Downhill Daredevil'
                    category = 'downhill'
                    desc = f"{abs(pct):.1f}% improvement on descents ({grade}% grade)"
                else:
                    continue  # Skip mild grades

                achievements.append(UserAchievement(
                    user_id=user_id,
                    achievement_type='improvement',
                    achievement_name=name,
                    achievement_description=desc,
                    grade_category=category,
                    metric_value=abs(pct)
                ))

        # 2. Consistency achievements (weekly streak)
        consecutive_weeks = self._count_consecutive_weeks(user_id)
        if consecutive_weeks >= 4 and not self._has_achievement(user_id, 'streak', 'Streak Champion'):
            achievements.append(UserAchievement(
                user_id=user_id,
                achievement_type='streak',
                achievement_name='Streak Champion',
                achievement_description=f"{consecutive_weeks} consecutive weeks with activities",
                metric_value=consecutive_weeks
            ))
        elif consecutive_weeks >= 3 and not self._has_achievement(user_id, 'streak', 'Week Warrior'):
            achievements.append(UserAchievement(
                user_id=user_id,
                achievement_type='streak',
                achievement_name='Week Warrior',
                achievement_description=f"{consecutive_weeks} weeks of consistent training",
                metric_value=consecutive_weeks
            ))

        # 3. Volume achievements
        if current.total_distance_km:
            if current.total_distance_km >= 200 and not self._has_achievement(user_id, 'volume', 'Distance Legend'):
                achievements.append(UserAchievement(
                    user_id=user_id,
                    achievement_type='volume',
                    achievement_name='Distance Legend',
                    achievement_description=f"Ran {current.total_distance_km:.1f}km this week",
                    metric_value=current.total_distance_km
                ))
            elif current.total_distance_km >= 100 and not self._has_achievement(user_id, 'volume', 'Century Runner'):
                achievements.append(UserAchievement(
                    user_id=user_id,
                    achievement_type='volume',
                    achievement_name='Century Runner',
                    achievement_description=f"Ran {current.total_distance_km:.1f}km this week",
                    metric_value=current.total_distance_km
                ))
            elif current.total_distance_km >= 50 and not self._has_achievement(user_id, 'volume', 'Distance Crusher'):
                achievements.append(UserAchievement(
                    user_id=user_id,
                    achievement_type='volume',
                    achievement_name='Distance Crusher',
                    achievement_description=f"Ran {current.total_distance_km:.1f}km this week",
                    metric_value=current.total_distance_km
                ))

        if current.total_elevation_m:
            if current.total_elevation_m >= 2000 and not self._has_achievement(user_id, 'volume', 'Elevation King'):
                achievements.append(UserAchievement(
                    user_id=user_id,
                    achievement_type='volume',
                    achievement_name='Elevation King',
                    achievement_description=f"Climbed {current.total_elevation_m:.0f}m this week",
                    metric_value=current.total_elevation_m
                ))

        # 4. Personal record achievements (best pace ever at grade)
        for grade in ANCHOR_GRADES:
            pr_achievement = self._check_personal_record(user_id, grade, snapshots)
            if pr_achievement:
                achievements.append(pr_achievement)

        return achievements

    def _count_consecutive_weeks(self, user_id: int) -> int:
        """Count consecutive weeks with activities.

        Args:
            user_id: User ID

        Returns:
            Number of consecutive weeks with at least 1 activity
        """
        snapshots = PerformanceSnapshot.query.filter_by(
            user_id=user_id,
            period_type='weekly'
        ).order_by(PerformanceSnapshot.period_start.desc()).limit(20).all()

        if not snapshots:
            return 0

        consecutive = 0
        for i, snapshot in enumerate(snapshots):
            if snapshot.activity_count > 0:
                consecutive += 1
            else:
                break  # Streak broken

        return consecutive

    def _has_achievement(self, user_id: int, achievement_type: str, achievement_name: str) -> bool:
        """Check if user already has a specific achievement.

        Args:
            user_id: User ID
            achievement_type: Achievement type
            achievement_name: Achievement name

        Returns:
            True if achievement already earned
        """
        existing = UserAchievement.query.filter_by(
            user_id=user_id,
            achievement_type=achievement_type,
            achievement_name=achievement_name
        ).first()

        return existing is not None

    def _check_personal_record(
        self,
        user_id: int,
        grade: int,
        recent_snapshots: List[PerformanceSnapshot]
    ) -> Optional[UserAchievement]:
        """Check if current performance is a personal record at grade.

        Args:
            user_id: User ID
            grade: Grade bucket
            recent_snapshots: List of recent snapshots (newest first)

        Returns:
            UserAchievement if PR detected, None otherwise
        """
        if not recent_snapshots:
            return None

        current = recent_snapshots[0]
        grade_str = str(grade)

        if grade_str not in current.anchor_ratios:
            return None

        current_pace = current.flat_pace * current.anchor_ratios[grade_str]

        # Get all historical performance at this grade
        all_grade_perfs = GradePerformanceHistory.query.filter_by(
            user_id=user_id,
            grade_bucket=grade
        ).all()

        if len(all_grade_perfs) <= 1:
            # Not enough history to determine PR
            return None

        # Find best historical pace (excluding current snapshot)
        best_historical_pace = None
        for gp in all_grade_perfs:
            if gp.snapshot_id != current.id:
                pace = gp.median_pace or gp.avg_pace
                if best_historical_pace is None or pace < best_historical_pace:
                    best_historical_pace = pace

        if best_historical_pace is None:
            return None

        # Check if current is better (faster) than historical best
        if current_pace < best_historical_pace * 0.98:  # 2% improvement threshold
            improvement_pct = ((best_historical_pace - current_pace) / best_historical_pace) * 100

            # Determine category
            if grade >= 10:
                category = 'uphill'
                name = f"Uphill PR ({grade}%)"
            elif grade <= -10:
                category = 'downhill'
                name = f"Downhill PR ({grade}%)"
            else:
                category = 'flat'
                name = f"Flat PR ({grade}%)"

            return UserAchievement(
                user_id=user_id,
                achievement_type='pr',
                achievement_name=name,
                achievement_description=f"New personal record at {grade}% grade: {current_pace:.2f} min/km ({improvement_pct:.1f}% faster)",
                grade_category=category,
                metric_value=current_pace
            )

        return None

    def award_achievements(self, user_id: int) -> List[UserAchievement]:
        """Detect and save new achievements for user.

        Args:
            user_id: User ID

        Returns:
            List of newly awarded UserAchievement instances
        """
        new_achievements = self.detect_achievements(user_id)

        for achievement in new_achievements:
            db.session.add(achievement)

        if new_achievements:
            db.session.commit()
            print(f"✓ Awarded {len(new_achievements)} new achievements")

        return new_achievements

    def get_achievements(
        self,
        user_id: int,
        include_notified: bool = True
    ) -> List[UserAchievement]:
        """Get all achievements for user.

        Args:
            user_id: User ID
            include_notified: Include already-notified achievements

        Returns:
            List of UserAchievement instances
        """
        query = UserAchievement.query.filter_by(user_id=user_id)

        if not include_notified:
            query = query.filter_by(notified=False)

        return query.order_by(UserAchievement.earned_at.desc()).all()

    def _calculate_fatigue_curve(
        self,
        activity_streams: List[Dict],
        activities: List[Dict]
    ) -> Optional[Dict]:
        """Calculate fatigue degradation curve from activity streams.

        This is an *absolute-distance* (km) aggregation so short runs don't affect long-run fatigue:
        - Define sample distances in km: baseline at ~2km, then 5km steps up to the max distance seen.
        - For each activity and grade, compute median pace near each sample distance (within a window).
        - Convert to ratios vs the baseline point (2km) for that same activity+grade.
        - Aggregate ratios across activities (median) for each distance and enforce monotonic non-decreasing.
        """
        if not activity_streams:
            return None

        # Determine max distance for context/labels (meters in activities)
        max_distance_m = max((act.get("distance", 0) or 0) for act in (activities or [])) if activities else 0
        if max_distance_m < 10000:
            return None
        max_distance_km = max_distance_m / 1000.0

        max_km = min(max_distance_km, FATIGUE_MAX_KM_CAP)
        if max_km <= FATIGUE_BASELINE_KM:
            return None

        # Build sample distances: baseline + fixed grid
        sample_distances_km: List[float] = [FATIGUE_BASELINE_KM]
        d = FATIGUE_BASELINE_KM + FATIGUE_STEP_KM
        max_points = 30
        while d <= max_km + 1e-9 and len(sample_distances_km) < max_points:
            sample_distances_km.append(float(d))
            d += FATIGUE_STEP_KM
        if len(sample_distances_km) < 2:
            return None

        # Per-band, per-distance, collect per-activity ratios
        ratios_by_band: Dict[str, List[List[Optional[float]]]] = {}
        activity_count_used = 0

        for streams in activity_streams:
            if not isinstance(streams, dict):
                continue
            if "distance" not in streams or "grade_smooth" not in streams or "velocity_smooth" not in streams:
                continue

            df = _aligned_stream_df(streams)
            if df.empty:
                continue

            df = prepare_stream(df)
            if df is None or len(df) == 0:
                continue

            total_dist_m = float(df["distance"].max() or 0)
            if total_dist_m < 10000:
                continue

            df = df[df["moving"] == True]
            if df.empty:
                continue

            # Only consider distances this activity can reach
            activity_max_km = total_dist_m / 1000.0
            if activity_max_km < FATIGUE_BASELINE_KM:
                continue

            # Baseline pace for this activity (grade-agnostic), near the start.
            # Using a grade-agnostic baseline avoids losing downhill/vertical bands that don't appear at baseline.
            baseline_window_km = max(FATIGUE_DISTANCE_WINDOW_KM, FATIGUE_BASELINE_KM * FATIGUE_DISTANCE_WINDOW_FRACTION)
            baseline_mask = (
                (df["distance"] >= (FATIGUE_BASELINE_KM - baseline_window_km) * 1000.0) &
                (df["distance"] <= (FATIGUE_BASELINE_KM + baseline_window_km) * 1000.0)
            )
            baseline_segment = df[baseline_mask]
            if len(baseline_segment) < FATIGUE_MIN_POINTS_PER_ACTIVITY:
                continue
            baseline_pace = float(np.median(baseline_segment["pace_min_per_km"]))
            if not np.isfinite(baseline_pace) or baseline_pace <= 0:
                continue

            per_band_paces: Dict[str, List[Optional[float]]] = {}
            for band in FATIGUE_GRADE_BANDS:
                paces: List[Optional[float]] = []
                for dist_km in sample_distances_km:
                    if dist_km > activity_max_km:
                        paces.append(None)
                        continue
                    window_km = max(FATIGUE_DISTANCE_WINDOW_KM, dist_km * FATIGUE_DISTANCE_WINDOW_FRACTION)
                    mask = (
                        (df["distance"] >= (dist_km - window_km) * 1000.0) &
                        (df["distance"] <= (dist_km + window_km) * 1000.0) &
                        (df["grade_smooth"] >= float(band["min"])) &
                        (df["grade_smooth"] < float(band["max"]))
                    )
                    segment = df[mask]
                    if len(segment) < FATIGUE_MIN_POINTS_PER_ACTIVITY:
                        paces.append(None)
                    else:
                        paces.append(float(np.median(segment["pace_min_per_km"])))
                per_band_paces[str(band["key"])] = paces

            # Convert to ratios vs baseline pace (grade-agnostic, near start)
            for band_key, paces in per_band_paces.items():
                ratios = []
                for pace in paces:
                    if pace is None or pace <= 0:
                        ratios.append(None)
                    else:
                        ratios.append(pace / baseline_pace)
                ratios_by_band.setdefault(band_key, []).append(ratios)

            activity_count_used += 1

        if activity_count_used < FATIGUE_MIN_ACTIVITIES_PER_POINT:
            return None

        bands_data: Dict[str, Dict] = {}
        for band_key, per_activity_ratios in ratios_by_band.items():
            # Aggregate per distance across activities
            aggregated: List[Optional[float]] = []
            counts: List[int] = []
            for idx in range(len(sample_distances_km)):
                vals = [r[idx] for r in per_activity_ratios if r[idx] is not None]
                counts.append(len(vals))
                if len(vals) < FATIGUE_MIN_ACTIVITIES_PER_POINT:
                    aggregated.append(None)
                else:
                    aggregated.append(float(np.median(vals)))

            # Enforce monotonic non-decreasing (fatigue shouldn't improve with distance)
            last = None
            monotonic = []
            for v in aggregated:
                if v is None:
                    monotonic.append(None)
                    continue
                if last is None:
                    last = v
                    monotonic.append(v)
                    continue
                if v < last:
                    monotonic.append(last)
                else:
                    monotonic.append(v)
                    last = v

            valid_count = sum(1 for v in monotonic if v is not None)
            if valid_count >= 2:
                # Normalize each band to start at 1.0 at km=0 for slope comparison.
                # NOTE: We keep per-band shapes unchanged; the km=0 anchor is added only at output time.
                first_idx = next((i for i, v in enumerate(monotonic) if v is not None), None)
                first_val = monotonic[first_idx] if first_idx is not None else None
                if first_val and first_val > 0:
                    monotonic = [(v / first_val) if v is not None else None for v in monotonic]

                # Fit a smooth, monotone saturating curve to the aggregated series.
                last_supported_idx = None
                for i in range(len(sample_distances_km) - 1, -1, -1):
                    if monotonic[i] is not None and (i < len(counts) and (counts[i] or 0) >= FATIGUE_MIN_ACTIVITIES_PER_POINT):
                        last_supported_idx = i
                        break

                fit = None
                if last_supported_idx is not None and last_supported_idx >= 2:
                    fit = _fit_saturating_exponential(
                        distances_km=sample_distances_km[: last_supported_idx + 1],
                        values=monotonic[: last_supported_idx + 1],
                        weights=counts[: last_supported_idx + 1],
                        min_points=3,
                    )
                    if fit:
                        fit_vals = fit.get("values") or []
                        # Don't extrapolate beyond the last supported point.
                        fit_vals = fit_vals[: last_supported_idx + 1] + [None] * (len(sample_distances_km) - (last_supported_idx + 1))
                        fit["values"] = [round(v, 4) if isinstance(v, (int, float)) else None for v in fit_vals]

                bands_data[band_key] = {
                    "degradation": [round(v, 4) if v is not None else None for v in monotonic],
                    "counts": counts,
                    "fit": fit,
                }

        if not bands_data:
            return None

        # Compute overall as the weighted mean across bands at each distance.
        overall_degradation: List[Optional[float]] = []
        overall_counts: List[int] = []
        for idx in range(len(sample_distances_km)):
            vals = []
            ws = []
            for bkey, b in bands_data.items():
                deg = b.get("degradation") or []
                cnts = b.get("counts") or []
                if idx >= len(deg) or idx >= len(cnts):
                    continue
                v = deg[idx]
                c = cnts[idx] or 0
                if v is None or c <= 0:
                    continue
                vals.append(float(v))
                ws.append(float(c))
            if not vals:
                overall_degradation.append(1.0 if idx == 0 else None)
                overall_counts.append(0)
            else:
                wsum = float(np.sum(ws))
                overall_counts.append(int(round(wsum)))
                overall_degradation.append(float(np.dot(vals, ws) / wsum))

        # Ensure overall starts from 1.0 at km=0
        if overall_degradation and overall_degradation[0] and overall_degradation[0] > 0:
            base = float(overall_degradation[0])
            overall_degradation = [(v / base) if v is not None else None for v in overall_degradation]
            overall_degradation[0] = 1.0

        # Fit overall with an explicit anchor at km=0 => 1.0 (strong weight).
        max_w = max(overall_counts) if overall_counts else 1
        overall_fit = _fit_saturating_exponential(
            distances_km=[0.0] + sample_distances_km,
            values=[1.0] + overall_degradation,
            weights=[max(1, max_w)] + overall_counts,
            min_points=3,
        )
        if overall_fit:
            fit_vals = overall_fit.get("values") or []
            overall_fit["values"] = [round(v, 4) if isinstance(v, (int, float)) else None for v in fit_vals]

        # Add a km=0 anchor to outputs without changing the existing per-band curves.
        out_sample_distances_km = [0.0] + sample_distances_km
        for band_key, b in list(bands_data.items()):
            b["degradation"] = [1.0] + (b.get("degradation") or [])
            b["counts"] = [0] + (b.get("counts") or [])
            if b.get("fit") and isinstance(b["fit"], dict) and isinstance(b["fit"].get("values"), list):
                b["fit"]["values"] = [1.0] + b["fit"]["values"]
            bands_data[band_key] = b

        overall_degradation = [1.0] + overall_degradation
        overall_counts = [0] + overall_counts

        return {
            "max_distance_km": round(max_distance_km, 2) if max_distance_km else None,
            "sample_distances": [round(d, 2) for d in out_sample_distances_km],
            "bands": bands_data,
            "overall": {
                "degradation": [round(v, 4) if v is not None else None for v in overall_degradation],
                "counts": overall_counts,
                "fit": overall_fit,
            },
            "meta": {
                "activities_used": activity_count_used,
                "min_activities_per_point": FATIGUE_MIN_ACTIVITIES_PER_POINT,
                "baseline_km": FATIGUE_BASELINE_KM,
                "distance_window_km": FATIGUE_DISTANCE_WINDOW_KM,
                "distance_window_fraction": FATIGUE_DISTANCE_WINDOW_FRACTION,
                # Keep this JSON-safe (no +/-Infinity) for frontend parsing.
                "grade_bands": [
                    {
                        "key": b["key"],
                        "label": b["label"],
                        "min": _finite_or_none(b["min"]),
                        "max": _finite_or_none(b["max"]),
                    }
                    for b in FATIGUE_GRADE_BANDS
                ],
            },
        }
