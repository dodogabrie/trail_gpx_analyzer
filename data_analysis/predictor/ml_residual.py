"""
Optional ML residual model to refine the curve-based predictor.

Idea:
- Baseline: global grade→pace_ratio curve + user flat pace.
- Residual: learn a small correction multiplier per segment using tabular ML.
  target = (actual_ratio / baseline_ratio). If target > 1, user is slower than baseline at that segment; <1 means faster.

Model choice: GradientBoostingRegressor (scikit-learn) with simple features:
- grade_mean, grade_std, abs_grade
- cumulative_distance_km

Usage outline:
    from pathlib import Path
    import pandas as pd
    from predictor import build_global_curve, prepare_stream, load_streams, compute_flat_pace
    from ml_residual import build_training_dataset, train_residual_model, predict_time_with_model

    processed_root = Path("data_analysis/data/processed")
    global_curve = build_global_curve(processed_root)
    train_df = build_training_dataset(processed_root, global_curve, segment_len_m=200)
    model = train_residual_model(train_df)

    # For a user:
    user_stream = prepare_stream(load_streams(Path("..._streams.json")))
    flat_pace = compute_flat_pace(user_stream)
    # Build a route profile (distance_m, grade_percent), e.g., from GPX or build_route_profile_from_stream
    total_sec = predict_time_with_model(route_profile, flat_pace, global_curve, model)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

# Local imports
import sys

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.append(str(_THIS_DIR))

from predictor import (  # noqa: E402
    build_global_curve,
    compute_flat_pace,
    load_streams,
    prepare_stream,
)

SEGMENT_LEN_M_DEFAULT = 200.0
MIN_SAMPLES_PER_SEGMENT = 5


# ---- Data loading with distance ----

def load_streams_with_distance(streams_path: Path) -> Optional[pd.DataFrame]:
    """Load streams and keep distance/altitude fields if present."""
    try:
        with open(streams_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    required = {"velocity_smooth", "grade_smooth", "moving", "distance"}
    if not required.issubset(data):
        return None
    df_dict = {
        "velocity_smooth": data["velocity_smooth"],
        "grade_smooth": data["grade_smooth"],
        "moving": data["moving"],
        "distance": data["distance"],
    }
    # Optional altitude for elevation features
    if "altitude" in data:
        df_dict["altitude"] = data["altitude"]
    df = pd.DataFrame(df_dict)
    return df if not df.empty else None


def iter_athlete_streams_with_distance(athlete_dir: Path) -> Iterable[pd.DataFrame]:
    """Yield prepared DataFrames with distance for each activity of an athlete."""
    activities_path = athlete_dir / "activities.json"
    try:
        with open(activities_path) as f:
            activities = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    activity_ids = activities.get("activity_ids") or []
    for activity_id in activity_ids:
        streams_path = athlete_dir / f"{activity_id}_streams.json"
        df = load_streams_with_distance(streams_path)
        df = prepare_stream(df)
        if df is not None and "distance" in df.columns:
            yield df


# ---- Dataset builder ----

def build_training_dataset(
    processed_root: Path,
    global_curve: pd.DataFrame,
    segment_len_m: float = SEGMENT_LEN_M_DEFAULT,
) -> pd.DataFrame:
    """
    Build a segment-level dataset for residual modeling.

    Features (10 total):
      Original (4): grade_mean, grade_std, abs_grade, cum_distance_km
      Temporal (2): prev_pace_ratio, grade_change
      Elevation (2): cum_elevation_gain_m, elevation_gain_rate
      Context (2): rolling_avg_grade_500m, distance_remaining_km
    Target:
      residual_multiplier = (actual_pace_ratio / baseline_ratio)
        where actual_pace_ratio = (pace / flat_pace)
    """
    athlete_dirs = [
        p for p in processed_root.iterdir() if p.is_dir() and p.name.isdigit()
    ]
    rows: List[dict] = []
    for athlete_dir in athlete_dirs:
        for df in iter_athlete_streams_with_distance(athlete_dir):
            try:
                flat_pace = compute_flat_pace(df)
            except ValueError:
                continue  # skip activities without flat samples
            distances = df["distance"].to_numpy()
            grades = df["grade_smooth"].to_numpy()
            velocities = df["velocity_smooth"].to_numpy()

            # Check for altitude (optional)
            has_altitude = "altitude" in df.columns
            altitudes = df["altitude"].to_numpy() if has_altitude else None

            max_dist = distances.max()
            starts = np.arange(0, max_dist, segment_len_m)

            # State tracking across segments
            prev_grade = 0.0
            prev_pace_ratio = 1.0
            cum_elevation_gain = 0.0

            for start in starts:
                end = start + segment_len_m
                mask = (distances >= start) & (distances < end)
                if mask.sum() < MIN_SAMPLES_PER_SEGMENT:
                    continue
                seg_grade = grades[mask]
                seg_vel = velocities[mask]
                vel_mean = np.nanmean(seg_vel)
                if not np.isfinite(vel_mean) or vel_mean <= 0:
                    continue
                pace_min_per_km = 60.0 / (vel_mean * 3.6)
                if pace_min_per_km <= 0:
                    continue
                actual_ratio = pace_min_per_km / flat_pace

                grade_mean = float(np.nanmean(seg_grade))
                grade_std = float(np.nanstd(seg_grade))
                baseline_ratio = float(
                    np.interp(
                        grade_mean,
                        global_curve["grade"],
                        global_curve["median"],
                        left=global_curve["median"].iloc[0],
                        right=global_curve["median"].iloc[-1],
                    )
                )
                if baseline_ratio <= 0:
                    continue
                residual_mult = actual_ratio / baseline_ratio

                # === NEW FEATURES ===

                # Temporal: grade change
                grade_change = grade_mean - prev_grade

                # Elevation features
                if has_altitude:
                    seg_alt = altitudes[mask]
                    if len(seg_alt) > 1:
                        elev_diffs = np.diff(seg_alt)
                        seg_elev_gain = float(np.sum(elev_diffs[elev_diffs > 0]))
                        cum_elevation_gain += seg_elev_gain
                        elevation_gain_rate = seg_elev_gain / (segment_len_m / 1000.0)
                    else:
                        elevation_gain_rate = 0.0
                else:
                    elevation_gain_rate = 0.0

                # Rolling grade (look back 500m)
                rolling_500m_mask = (distances >= max(0, start - 500)) & (distances < start)
                if rolling_500m_mask.any():
                    rolling_avg_grade_500m = float(np.nanmean(grades[rolling_500m_mask]))
                else:
                    rolling_avg_grade_500m = grade_mean

                # Distance remaining
                distance_remaining_km = (max_dist - start) / 1000.0

                rows.append(
                    {
                        # Original 4 features
                        "grade_mean": grade_mean,
                        "grade_std": grade_std,
                        "abs_grade": abs(grade_mean),
                        "cum_distance_km": start / 1000.0,

                        # Temporal features (2)
                        "prev_pace_ratio": prev_pace_ratio,
                        "grade_change": grade_change,

                        # Elevation features (2)
                        "cum_elevation_gain_m": cum_elevation_gain,
                        "elevation_gain_rate": elevation_gain_rate,

                        # Context features (2)
                        "rolling_avg_grade_500m": rolling_avg_grade_500m,
                        "distance_remaining_km": distance_remaining_km,

                        # Target
                        "residual_mult": residual_mult,
                    }
                )

                # Update state for next segment
                prev_grade = grade_mean
                prev_pace_ratio = actual_ratio

    if not rows:
        raise ValueError("No training rows built.")
    return pd.DataFrame(rows)


# ---- Training ----

def train_residual_model(train_df: pd.DataFrame) -> GradientBoostingRegressor:
    """Train Gradient Boosting model on residual multipliers with 10 features."""
    features = [
        # Original 4 features
        "grade_mean", "grade_std", "abs_grade", "cum_distance_km",
        # Temporal features (2)
        "prev_pace_ratio", "grade_change",
        # Elevation features (2)
        "cum_elevation_gain_m", "elevation_gain_rate",
        # Context features (2)
        "rolling_avg_grade_500m", "distance_remaining_km",
    ]
    X = train_df[features]
    y = train_df["residual_mult"]
    model = GradientBoostingRegressor(
        n_estimators=250,  # Slightly increased for more features
        learning_rate=0.04,  # Slightly reduced for stability
        max_depth=4,  # Increased from 3 to capture feature interactions
        subsample=0.8,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=42,
    )
    model.fit(X, y)
    return model


# ---- Prediction ----

def predict_time_with_model(
    route_profile: pd.DataFrame,
    flat_pace_min_per_km: float,
    global_curve: pd.DataFrame,
    model: GradientBoostingRegressor,
    segment_len_m: float = SEGMENT_LEN_M_DEFAULT,
) -> float:
    """
    Predict route time (seconds) using baseline curve + ML residual model.

    route_profile: DataFrame with columns distance_m (monotonic) and grade_percent.
                   Optional: altitude_m for elevation features.
    flat_pace_min_per_km: user's flat pace.
    """
    if route_profile.empty:
        return 0.0
    distances = route_profile["distance_m"].to_numpy()
    grades = route_profile["grade_percent"].to_numpy()

    # Check for altitude
    has_altitude = "altitude_m" in route_profile.columns
    altitudes = route_profile["altitude_m"].to_numpy() if has_altitude else None

    max_dist = distances.max()
    total_time = 0.0

    # State tracking (same as training)
    prev_grade = 0.0
    prev_pace_ratio = 1.0
    cum_elevation_gain = 0.0

    starts = np.arange(0, max_dist, segment_len_m)
    for start in starts:
        end = start + segment_len_m
        mask = (distances >= start) & (distances < end)
        if not mask.any():
            continue

        seg_grade = grades[mask]
        grade_mean = float(np.nanmean(seg_grade))
        grade_std = float(np.nanstd(seg_grade))
        baseline_ratio = float(
            np.interp(
                grade_mean,
                global_curve["grade"],
                global_curve["median"],
                left=global_curve["median"].iloc[0],
                right=global_curve["median"].iloc[-1],
            )
        )
        if baseline_ratio <= 0:
            continue

        # === Compute SAME 10 features as training ===

        # Temporal: grade change
        grade_change = grade_mean - prev_grade

        # Elevation features
        if has_altitude:
            seg_alt = altitudes[mask]
            if len(seg_alt) > 1:
                elev_diffs = np.diff(seg_alt)
                seg_elev_gain = float(np.sum(elev_diffs[elev_diffs > 0]))
                cum_elevation_gain += seg_elev_gain
                elevation_gain_rate = seg_elev_gain / (segment_len_m / 1000.0)
            else:
                elevation_gain_rate = 0.0
        else:
            elevation_gain_rate = 0.0

        # Rolling grade (look back 500m)
        rolling_500m_mask = (distances >= max(0, start - 500)) & (distances < start)
        if rolling_500m_mask.any():
            rolling_avg_grade_500m = float(np.nanmean(grades[rolling_500m_mask]))
        else:
            rolling_avg_grade_500m = grade_mean

        # Distance remaining
        distance_remaining_km = (max_dist - start) / 1000.0

        # Build feature DataFrame with EXACT same 10 features as training
        features = pd.DataFrame(
            {
                # Original 4 features
                "grade_mean": [grade_mean],
                "grade_std": [grade_std],
                "abs_grade": [abs(grade_mean)],
                "cum_distance_km": [start / 1000.0],

                # Temporal features (2)
                "prev_pace_ratio": [prev_pace_ratio],
                "grade_change": [grade_change],

                # Elevation features (2)
                "cum_elevation_gain_m": [cum_elevation_gain],
                "elevation_gain_rate": [elevation_gain_rate],

                # Context features (2)
                "rolling_avg_grade_500m": [rolling_avg_grade_500m],
                "distance_remaining_km": [distance_remaining_km],
            }
        )

        residual_mult = float(model.predict(features)[0])
        ratio = baseline_ratio * residual_mult
        pace_min_per_km = flat_pace_min_per_km * ratio

        if pace_min_per_km <= 0:
            continue

        speed_mps = 1000.0 / (pace_min_per_km * 60.0)
        seg_dist = segment_len_m
        total_time += seg_dist / speed_mps if speed_mps > 0 else 0.0

        # Update state for next segment
        prev_grade = grade_mean
        prev_pace_ratio = ratio

    return total_time
