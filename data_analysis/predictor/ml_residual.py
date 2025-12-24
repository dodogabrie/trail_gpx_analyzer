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
    athlete_fingerprints: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Build a segment-level dataset for residual modeling.

    Features (13 total):
      Original (4): grade_mean, grade_std, abs_grade, cum_distance_km
      Temporal (2): prev_pace_ratio, grade_change
      Elevation (2): cum_elevation_gain_m, elevation_gain_rate
      Context (2): rolling_avg_grade_500m, distance_remaining_km
      User (3): user_endurance_score, user_recovery_rate, user_base_fitness
    Target:
      residual_multiplier = (actual_pace_ratio / baseline_ratio)
        where actual_pace_ratio = (pace / flat_pace)

    Args:
        processed_root: Path to processed athlete data
        global_curve: Global pace ratio curve
        segment_len_m: Segment length for training
        athlete_fingerprints: Dict mapping athlete_id -> fingerprint dict
            If None, uses neutral fingerprint [1.0, 0.0, 0.15] for all athletes
    """
    athlete_dirs = [
        p for p in processed_root.iterdir() if p.is_dir() and p.name.isdigit()
    ]

    # Default neutral fingerprint if none provided
    if athlete_fingerprints is None:
        athlete_fingerprints = {}

    rows: List[dict] = []
    for athlete_dir in athlete_dirs:
        athlete_id = athlete_dir.name

        # Get athlete fingerprint or use neutral default
        fingerprint = athlete_fingerprints.get(athlete_id, {
            'user_endurance_score': 1.0,
            'user_recovery_rate': 0.0,
            'user_base_fitness': 0.15
        })

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

                        # User features (3)
                        "user_endurance_score": fingerprint['user_endurance_score'],
                        "user_recovery_rate": fingerprint['user_recovery_rate'],
                        "user_base_fitness": fingerprint['user_base_fitness'],

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
    """Train Gradient Boosting model on residual multipliers with 13 features."""
    features = [
        # Original 4 features
        "grade_mean", "grade_std", "abs_grade", "cum_distance_km",
        # Temporal features (2)
        "prev_pace_ratio", "grade_change",
        # Elevation features (2)
        "cum_elevation_gain_m", "elevation_gain_rate",
        # Context features (2)
        "rolling_avg_grade_500m", "distance_remaining_km",
        # User features (3)
        "user_endurance_score", "user_recovery_rate", "user_base_fitness",
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
    user_fingerprint: Optional[dict] = None,
) -> float:
    """
    Predict route time (seconds) using baseline curve + ML residual model.

    PREDICTION ALGORITHM (Stage 3 of 3-stage pipeline):
    ===================================================

    For each 200m segment along the route:

    1. GET BASE PACE from personalized curve:
       - Extract segment grade (average over 200m)
       - Lookup pace_ratio from curve: pace_ratio = f(grade)
       - Calculate base_pace = flat_pace * pace_ratio
       - Example: flat_pace=5:30/km, grade=+10%, curve says ratio=1.35
                  -> base_pace = 5:30 * 1.35 = 7:25/km

    2. BUILD ML FEATURES (13 total):
       Terrain (3):
         - grade_mean: Average grade over segment
         - grade_std: Grade variability (rough terrain)
         - abs_grade: Absolute grade (steep up or down)

       Fatigue/Distance (2):
         - cum_distance_km: Distance covered so far (fatigue accumulates)
         - distance_remaining_km: Distance left (pacing strategy)

       Dynamics (3):
         - prev_pace_ratio: Pace from previous segment (momentum)
         - grade_change: Change in grade from previous segment (adaptation cost)
         - rolling_avg_grade_500m: Average grade over last 500m (trend context)

       Elevation (2):
         - cum_elevation_gain_m: Total climbing so far (cumulative fatigue)
         - elevation_gain_rate: Climbing rate in this segment (intensity)

       User Fingerprint (3):
         - user_endurance_score: How well user maintains pace over distance
         - user_recovery_rate: How quickly user recovers after steep sections
         - user_base_fitness: Overall fitness level

    3. ML MODEL PREDICTION:
       - Feed 13 features into Gradient Boosting model
       - Model outputs residual_multiplier (correction factor)
       - residual_multiplier > 1.0 means slower than curve predicts
       - residual_multiplier < 1.0 means faster than curve predicts
       - Example: At 40km into ultra, model predicts residual=1.15
                  (15% slower due to accumulated fatigue)

    4. CALCULATE FINAL PACE:
       - final_pace = base_pace * residual_multiplier
       - Convert pace to speed: speed_mps = 1000 / (final_pace * 60)
       - Segment time = 200m / speed_mps
       - Example: base_pace=7:25/km, residual=1.15
                  -> final_pace = 8:32/km -> 102 seconds for 200m

    5. UPDATE STATE for next segment:
       - Store current grade as prev_grade
       - Store current pace_ratio as prev_pace_ratio
       - Accumulate elevation gain

    6. RETURN total time = sum of all segment times

    Args:
        route_profile: DataFrame with columns distance_m (monotonic) and grade_percent.
                       Optional: altitude_m for elevation features.
        flat_pace_min_per_km: user's flat pace.
        global_curve: Global pace ratio curve (or personalized curve from Stage 2)
        model: Trained ML model (GradientBoostingRegressor)
        segment_len_m: Segment length for prediction (default 200m, matches training)
        user_fingerprint: Dict with user_endurance_score, user_recovery_rate, user_base_fitness
                          If None, uses neutral fingerprint [1.0, 0.0, 0.15]

    Returns:
        Total time in seconds
    """
    # Default neutral fingerprint if not provided
    if user_fingerprint is None:
        user_fingerprint = {
            'user_endurance_score': 1.0,
            'user_recovery_rate': 0.0,
            'user_base_fitness': 0.15
        }
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

        # === STEP 1: GET BASE PACE from curve ===
        seg_grade = grades[mask]
        grade_mean = float(np.nanmean(seg_grade))
        grade_std = float(np.nanstd(seg_grade))

        # Use personalized ratio if available (from Stage 2 anchor warping), else global median
        y_col = "personalized_ratio" if "personalized_ratio" in global_curve.columns else "median"

        baseline_ratio = float(
            np.interp(
                grade_mean,
                global_curve["grade"],
                global_curve[y_col],
                left=global_curve[y_col].iloc[0],
                right=global_curve[y_col].iloc[-1],
            )
        )
        if baseline_ratio <= 0:
            continue

        # === STEP 2: BUILD ML FEATURES (13 total) ===

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

        # Build feature DataFrame with EXACT same 13 features as training
        features = pd.DataFrame(
            {
                # Terrain features (3)
                "grade_mean": [grade_mean],  # Average grade over 200m
                "grade_std": [grade_std],  # Grade variability (rough terrain)
                "abs_grade": [abs(grade_mean)],  # Absolute grade magnitude

                # Fatigue/Distance features (2)
                "cum_distance_km": [start / 1000.0],  # Distance covered (fatigue accumulates)
                "distance_remaining_km": [distance_remaining_km],  # Distance left (pacing)

                # Dynamics features (3)
                "prev_pace_ratio": [prev_pace_ratio],  # Momentum from previous segment
                "grade_change": [grade_change],  # Adaptation cost to grade change
                "rolling_avg_grade_500m": [rolling_avg_grade_500m],  # Trend context

                # Elevation features (2)
                "cum_elevation_gain_m": [cum_elevation_gain],  # Cumulative climbing fatigue
                "elevation_gain_rate": [elevation_gain_rate],  # Climbing intensity

                # User fingerprint features (3)
                "user_endurance_score": [user_fingerprint['user_endurance_score']],
                "user_recovery_rate": [user_fingerprint['user_recovery_rate']],
                "user_base_fitness": [user_fingerprint['user_base_fitness']],
            }
        )

        # Reorder columns to match training order (CRITICAL for sklearn)
        feature_order = [
            "grade_mean", "grade_std", "abs_grade", "cum_distance_km",
            "prev_pace_ratio", "grade_change",
            "cum_elevation_gain_m", "elevation_gain_rate",
            "rolling_avg_grade_500m", "distance_remaining_km",
            "user_endurance_score", "user_recovery_rate", "user_base_fitness",
        ]
        features = features[feature_order]

        # === STEP 3: ML MODEL PREDICTION ===
        # Model outputs residual_multiplier (correction factor)
        # >1.0 = slower than curve, <1.0 = faster than curve
        residual_mult = float(model.predict(features)[0])

        # === STEP 4: CALCULATE FINAL PACE ===
        # Apply ML correction to baseline pace
        ratio = baseline_ratio * residual_mult
        pace_min_per_km = flat_pace_min_per_km * ratio

        if pace_min_per_km <= 0:
            continue

        # Convert pace to speed and calculate segment time
        speed_mps = 1000.0 / (pace_min_per_km * 60.0)
        seg_dist = segment_len_m
        total_time += seg_dist / speed_mps if speed_mps > 0 else 0.0

        # === STEP 5: UPDATE STATE for next segment ===
        prev_grade = grade_mean
        prev_pace_ratio = ratio

    return total_time
