"""
Route-time predictor: STAGE 2 - Curve Personalization

This module handles STAGE 2 of the 3-stage prediction pipeline:
Personalizing the global pace-grade curve using user anchor points.

FULL PIPELINE CONTEXT:
=====================

STAGE 1: User Fingerprint (user_fingerprint.py)
  - Extract user fitness metrics from 10-50 historical activities
  - Output: user_endurance_score, user_recovery_rate, user_base_fitness

STAGE 2: Curve Personalization (THIS MODULE)
  - Build global pace-grade curve from all athletes
  - Calibrate user's flat pace from recent activity
  - Extract anchor pace ratios at key grades [-10%, 0%, +10%, etc]
  - Warp global curve to match user's anchors
  - Output: Personalized pace_ratio = f(grade) function

STAGE 3: ML Residual Prediction (ml_residual.py)
  - Use personalized curve + user fingerprint + ML model
  - Predict segment-by-segment with fatigue/dynamics corrections
  - Output: Total race time

THIS MODULE'S ROLE (STAGE 2):
============================

1. Build global curve from all athletes:
   - Normalize each athlete by flat pace (median pace on -1% to +1% grade)
   - Bin by grade and aggregate median + IQR across athletes
   - Result: Global pace_ratio = f(grade) baseline

2. Calibrate user with anchor grades:
   - Compute user's flat pace from recent activity
   - Extract pace ratios at anchor grades (pace/flat_pace) using 2% grade window
   - Example anchors: [-30%, -20%, -10%, 0%, +10%, +20%, +30%]

3. Personalize curve:
   - Warp global curve to match user's anchor ratios
   - Smooth interpolation between anchors
   - Result: Personalized curve specific to user's current form

WHY CURVE PERSONALIZATION?
=========================
The global curve represents average athlete behavior, but users vary:
- Some are stronger uphill climbers
- Some are faster downhill runners
- Recent training affects current performance

Anchors capture user's CURRENT performance at key grades.
Warping the curve makes predictions match user's actual capabilities.

LIMITATION: Curve only models steady-state pace at each grade.
STAGE 3 (ML) adds corrections for fatigue, recovery, and dynamics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Configuration defaults
GRADE_BIN_WIDTH = 1  # percent
SMOOTH_WINDOW = 5
FLAT_BASE_RANGE = (-1.0, 1.0)  # percent
MIN_POINTS_PER_BIN = 10  # per activity bin
MIN_ATHLETES_PER_BIN = 5
MAX_GRADE_ABS = 40
ANCHOR_GRADES = [-30, -20, -10, 0, 10, 20, 30]
ANCHOR_WINDOW = 2.0  # percent band around each anchor for user calibration


# ---- Utilities ----

def _safe_load_json(path: Path) -> Optional[dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _smooth_series(series: pd.Series, window: int = SMOOTH_WINDOW) -> pd.Series:
    return series.rolling(window=window, center=True, min_periods=1).mean()


# ---- Data loading ----

def load_streams(streams_path: Path) -> Optional[pd.DataFrame]:
    """Load a streams JSON file into a DataFrame."""
    data = _safe_load_json(streams_path)
    if not data:
        return None
    required = {"velocity_smooth", "grade_smooth", "moving"}
    if not required.issubset(data):
        return None
    df = pd.DataFrame(
        {
            "velocity_smooth": data["velocity_smooth"],
            "grade_smooth": data["grade_smooth"],
            "moving": data["moving"],
        }
    )
    return df if not df.empty else None


def iter_athlete_streams(athlete_dir: Path) -> Iterable[pd.DataFrame]:
    """Yield prepared DataFrames for each activity of an athlete."""
    activities_path = athlete_dir / "activities.json"
    activities = _safe_load_json(activities_path)
    if not activities:
        return []

    # Handle both JSON formats: {"activity_ids": [...]} and {"activities": [{"id": ...}, ...]}
    activity_ids = activities.get("activity_ids")
    if activity_ids is None and "activities" in activities:
        activity_ids = [act["id"] for act in activities["activities"]]
    if not activity_ids:
        return []

    for activity_id in activity_ids:
        streams_path = athlete_dir / f"{activity_id}_streams.json"
        df = load_streams(streams_path)
        df = prepare_stream(df)
        if df is not None:
            yield df


# ---- Preprocessing ----

def prepare_stream(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Clean and augment a single activity's stream."""
    if df is None or df.empty:
        return None
    if "moving" in df.columns and df["moving"].notna().any():
        df = df[df["moving"] == True]  # noqa: E712
    if df.empty:
        return None
    df = df.copy()
    df["velocity_smooth"] = _smooth_series(df["velocity_smooth"])
    df["grade_smooth"] = _smooth_series(df["grade_smooth"])
    df["velocity_kmh"] = df["velocity_smooth"] * 3.6
    df["pace_min_per_km"] = np.where(
        df["velocity_kmh"] > 0, 60.0 / df["velocity_kmh"], np.nan
    )
    df = df[np.isfinite(df["pace_min_per_km"]) & np.isfinite(df["grade_smooth"])]
    return df if not df.empty else None


# ---- Global curve ----

def build_global_curve(processed_root: Path) -> pd.DataFrame:
    """Build global normalized pace curve across all athletes."""
    athlete_dirs = [
        p for p in processed_root.iterdir() if p.is_dir() and p.name.isdigit()
    ]
    curves: List[pd.DataFrame] = []
    for athlete_dir in athlete_dirs:
        curve = _athlete_curve(athlete_dir)
        if curve is not None:
            curves.append(curve)
    if not curves:
        raise ValueError("No athlete curves available.")

    per_athlete = pd.concat(curves, ignore_index=True)
    summary = (
        per_athlete.groupby("grade", observed=False)["pace_ratio"]
        .agg(
            median="median",
            p25=lambda x: x.quantile(0.25),
            p75=lambda x: x.quantile(0.75),
            count="count",
        )
        .reset_index()
        .sort_values("grade")
    )
    summary = summary[summary["count"] >= MIN_ATHLETES_PER_BIN]
    for col in ["median", "p25", "p75"]:
        summary[col] = (
            summary[col]
            .rolling(window=3, center=True, min_periods=1)
            .median()
        )
    return summary


def _athlete_curve(athlete_dir: Path) -> Optional[pd.DataFrame]:
    """Compute normalized pace ratio per grade bin for one athlete."""
    all_points = []
    for df in iter_athlete_streams(athlete_dir):
        all_points.append(df[["grade_smooth", "pace_min_per_km"]])
    if not all_points:
        return None
    df_all = pd.concat(all_points, ignore_index=True)
    df_all = df_all[
        df_all["grade_smooth"].between(-MAX_GRADE_ABS, MAX_GRADE_ABS, inclusive="both")
    ]
    if df_all.empty:
        return None

    flat_mask = df_all["grade_smooth"].between(*FLAT_BASE_RANGE, inclusive="both")
    if not flat_mask.any():
        return None
    flat_baseline = df_all.loc[flat_mask, "pace_min_per_km"].median()
    if not np.isfinite(flat_baseline) or flat_baseline <= 0:
        return None

    grade_bins = np.arange(-MAX_GRADE_ABS, MAX_GRADE_ABS + GRADE_BIN_WIDTH, GRADE_BIN_WIDTH)
    df_all["grade_bin"] = pd.cut(
        df_all["grade_smooth"], bins=grade_bins, include_lowest=True
    )
    binned = (
        df_all.groupby("grade_bin", observed=False)["pace_min_per_km"]
        .agg(["median", "count"])
        .reset_index()
    )
    binned = binned[binned["count"] >= MIN_POINTS_PER_BIN]
    if binned.empty:
        return None

    binned["grade"] = binned["grade_bin"].apply(
        lambda interval: (interval.left + interval.right) / 2
    )
    binned["pace_ratio"] = binned["median"] / flat_baseline
    binned["athlete_id"] = athlete_dir.name
    return binned[["athlete_id", "grade", "pace_ratio", "count"]]


# ---- User calibration ----

def compute_flat_pace(df: pd.DataFrame) -> float:
    mask = df["grade_smooth"].between(*FLAT_BASE_RANGE, inclusive="both")
    if not mask.any():
        raise ValueError("No flat samples to compute flat pace.")
    flat_pace = df.loc[mask, "pace_min_per_km"].median()
    if not np.isfinite(flat_pace) or flat_pace <= 0:
        raise ValueError("Flat pace is not finite.")
    return float(flat_pace)


def compute_anchor_ratios(
    df: pd.DataFrame,
    flat_pace: float,
    anchors: Sequence[float] = ANCHOR_GRADES,
    window: float = ANCHOR_WINDOW,
) -> Dict[float, float]:
    ratios: Dict[float, float] = {}
    for anchor in anchors:
        mask = df["grade_smooth"].between(anchor - window, anchor + window, inclusive="both")
        if not mask.any():
            continue
        pace = df.loc[mask, "pace_min_per_km"].median()
        if np.isfinite(pace) and pace > 0:
            ratios[anchor] = pace / flat_pace
    return ratios


# ---- Personalization ----

def personalize_curve(
    global_curve: pd.DataFrame,
    anchor_ratios: Dict[float, float],
) -> pd.DataFrame:
    """Warp the global curve to match user anchor ratios."""
    if not anchor_ratios:
        raise ValueError("No anchor ratios provided.")
    # Interpolate global ratios at anchor grades
    global_interp = np.interp(
        list(anchor_ratios.keys()),
        global_curve["grade"],
        global_curve["median"],
    )
    multipliers = []
    for (anchor, user_ratio), g_ratio in zip(anchor_ratios.items(), global_interp):
        if g_ratio > 0:
            multipliers.append((anchor, user_ratio / g_ratio))
    if not multipliers:
        raise ValueError("Anchors could not be mapped to global curve.")

    anchors_sorted = sorted(multipliers, key=lambda x: x[0])
    anchor_grades = [a for a, _ in anchors_sorted]
    anchor_mults = [m for _, m in anchors_sorted]

    interp_mult = np.interp(
        global_curve["grade"],
        anchor_grades,
        anchor_mults,
        left=anchor_mults[0],
        right=anchor_mults[-1],
    )
    personalized = global_curve.copy()
    personalized["personalized_ratio"] = personalized["median"] * interp_mult
    personalized["multiplier"] = interp_mult
    return personalized


# ---- Prediction ----

def predict_time_seconds(
    route_profile: pd.DataFrame,
    flat_pace_min_per_km: float,
    personalized_curve: pd.DataFrame,
) -> float:
    """
    Predict total time (seconds) for a route.

    route_profile: DataFrame with columns distance_m (monotonic) and grade_percent.
    flat_pace_min_per_km: user's flat pace.
    personalized_curve: DataFrame from personalize_curve (must contain grade, personalized_ratio).
    """
    if route_profile.empty:
        return 0.0
    grades = route_profile["grade_percent"].to_numpy()
    distances = route_profile["distance_m"].diff().fillna(route_profile["distance_m"]).clip(lower=0).to_numpy()

    ratios = np.interp(
        grades,
        personalized_curve["grade"],
        personalized_curve["personalized_ratio"],
        left=personalized_curve["personalized_ratio"].iloc[0],
        right=personalized_curve["personalized_ratio"].iloc[-1],
    )
    # pace_min_per_km -> speed m/s = 1000 / (pace_min_per_km * 60)
    pace_min_per_km = flat_pace_min_per_km * ratios
    speed_mps = np.where(pace_min_per_km > 0, 1000.0 / (pace_min_per_km * 60.0), np.nan)
    segment_time = np.where(speed_mps > 0, distances / speed_mps, 0.0)
    total_time_sec = np.nansum(segment_time)
    return float(total_time_sec)


# ---- Helper to build a route profile from user stream ----

def build_route_profile_from_stream(df: pd.DataFrame, step_m: float = 50.0) -> pd.DataFrame:
    """
    Downsample a stream to a simple route profile with distance and grade.

    This is useful for testing predictions using a known activity as the route.
    """
    if "distance" not in df.columns or "grade_smooth" not in df.columns:
        raise ValueError("Stream must contain distance and grade_smooth.")
    distances = df["distance"].to_numpy()
    grades = df["grade_smooth"].to_numpy()
    target_d = np.arange(0, distances.max() + step_m, step_m)
    interp_grade = np.interp(target_d, distances, grades)
    return pd.DataFrame({"distance_m": target_d, "grade_percent": interp_grade})


# ---- Example wiring (not executed automatically) ----

def example_usage(processed_root: Path, user_stream_path: Path, route_profile: pd.DataFrame):
    """
    Example flow:
    1) global_curve = build_global_curve(processed_root)
    2) user_df = prepare_stream(load_streams(user_stream_path))
    3) flat_pace = compute_flat_pace(user_df)
    4) anchors = compute_anchor_ratios(user_df, flat_pace)
    5) personalized = personalize_curve(global_curve, anchors)
    6) total_time_sec = predict_time_seconds(route_profile, flat_pace, personalized)
    """
    global_curve = build_global_curve(processed_root)
    user_df = prepare_stream(load_streams(user_stream_path))
    flat_pace = compute_flat_pace(user_df)
    anchors = compute_anchor_ratios(user_df, flat_pace)
    personalized = personalize_curve(global_curve, anchors)
    return predict_time_seconds(route_profile, flat_pace, personalized)
