"""User fingerprint extraction for personalized fatigue modeling.

Computes three user-level features from multiple activities:
- user_endurance_score: endurance over distance (pace degradation)
- user_recovery_rate: how well user handles grade changes vs baseline
- user_base_fitness: normalized speed baseline

Requires: 3-5 activities with 15km+ each for reliable fingerprint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from predictor import prepare_stream, compute_flat_pace, FLAT_BASE_RANGE


MIN_ACTIVITIES = 3
IDEAL_ACTIVITIES = 5
MIN_DISTANCE_KM = 15.0
ENDURANCE_EARLY_KM = 5.0
ENDURANCE_LATE_KM = 20.0


def extract_fingerprint_from_activities(
    activities_streams: List[pd.DataFrame],
    global_curve: pd.DataFrame
) -> Optional[Dict[str, float]]:
    """Extract user fingerprint from multiple activity streams.

    Args:
        activities_streams: List of prepared DataFrames (from prepare_stream)
        global_curve: Global pace ratio curve for baseline comparison

    Returns:
        Dict with keys: user_endurance_score, user_recovery_rate, user_base_fitness
        Returns None if insufficient data

    Raises:
        ValueError: If activities_streams is empty or invalid
    """
    if not activities_streams or len(activities_streams) < MIN_ACTIVITIES:
        raise ValueError(f"Need at least {MIN_ACTIVITIES} activities for fingerprint extraction")

    # Filter activities by minimum distance
    valid_activities = []
    for df in activities_streams:
        if 'distance' not in df.columns:
            continue
        max_dist_km = df['distance'].max() / 1000.0
        if max_dist_km >= MIN_DISTANCE_KM:
            valid_activities.append(df)

    if len(valid_activities) < MIN_ACTIVITIES:
        raise ValueError(
            f"Only {len(valid_activities)} activities meet {MIN_DISTANCE_KM}km requirement. Need {MIN_ACTIVITIES}+"
        )

    # Compute flat pace for each activity
    flat_paces = []
    for df in valid_activities:
        try:
            flat_pace = compute_flat_pace(df)
            if flat_pace and np.isfinite(flat_pace) and flat_pace > 0:
                flat_paces.append(flat_pace)
        except ValueError:
            continue

    if len(flat_paces) < MIN_ACTIVITIES:
        raise ValueError(f"Could not compute flat pace for {MIN_ACTIVITIES}+ activities")

    # Feature 1: user_base_fitness = 1.0 / median(flat_pace)
    median_flat_pace = float(np.median(flat_paces))
    user_base_fitness = 1.0 / median_flat_pace

    # Feature 2: user_endurance_score
    endurance_score = _compute_endurance_score(valid_activities, flat_paces)

    # Feature 3: user_recovery_rate
    recovery_rate = _compute_recovery_rate(valid_activities, flat_paces, global_curve)

    return {
        'user_endurance_score': float(endurance_score),
        'user_recovery_rate': float(recovery_rate),
        'user_base_fitness': float(user_base_fitness)
    }


def _compute_endurance_score(
    activities: List[pd.DataFrame],
    flat_paces: List[float]
) -> float:
    """Compute endurance score: pace degradation over distance.

    Compares pace at early distance (5km) vs late distance (20km).
    Score < 1.0 = good endurance, > 1.2 = poor endurance.

    Args:
        activities: List of activity DataFrames
        flat_paces: Corresponding flat paces for each activity

    Returns:
        Endurance score (median ratio of late/early pace ratios)
    """
    endurance_ratios = []

    for df, flat_pace in zip(activities, flat_paces):
        if 'distance' not in df.columns:
            continue

        max_dist = df['distance'].max() / 1000.0
        if max_dist < ENDURANCE_LATE_KM:
            # Activity too short for endurance calculation, use partial
            continue

        # Early pace (around 5km)
        early_mask = df['distance'].between(
            (ENDURANCE_EARLY_KM - 0.5) * 1000,
            (ENDURANCE_EARLY_KM + 0.5) * 1000,
            inclusive='both'
        )
        if not early_mask.any():
            continue
        early_pace = df.loc[early_mask, 'pace_min_per_km'].median()
        if not np.isfinite(early_pace) or early_pace <= 0:
            continue
        early_ratio = early_pace / flat_pace

        # Late pace (around 20km)
        late_mask = df['distance'].between(
            (ENDURANCE_LATE_KM - 0.5) * 1000,
            (ENDURANCE_LATE_KM + 0.5) * 1000,
            inclusive='both'
        )
        if not late_mask.any():
            continue
        late_pace = df.loc[late_mask, 'pace_min_per_km'].median()
        if not np.isfinite(late_pace) or late_pace <= 0:
            continue
        late_ratio = late_pace / flat_pace

        # Endurance degradation
        if early_ratio > 0:
            endurance_ratios.append(late_ratio / early_ratio)

    if not endurance_ratios:
        # Fallback: neutral endurance
        return 1.0

    return float(np.median(endurance_ratios))


def _compute_recovery_rate(
    activities: List[pd.DataFrame],
    flat_paces: List[float],
    global_curve: pd.DataFrame
) -> float:
    """Compute recovery rate: correlation between grade and pace deviation from baseline.

    Measures how well user handles grade changes compared to global curve.
    Positive = slower than baseline on climbs, negative = faster.

    Args:
        activities: List of activity DataFrames
        flat_paces: Corresponding flat paces for each activity
        global_curve: Global curve for baseline comparison

    Returns:
        Correlation coefficient between grade and pace_ratio deviation
    """
    all_grades = []
    all_deviations = []

    for df, flat_pace in zip(activities, flat_paces):
        if 'grade_smooth' not in df.columns or 'pace_min_per_km' not in df.columns:
            continue

        grades = df['grade_smooth'].to_numpy()
        paces = df['pace_min_per_km'].to_numpy()

        # Compute actual pace ratios
        pace_ratios = paces / flat_pace

        # Compute baseline ratios from global curve
        baseline_ratios = np.interp(
            grades,
            global_curve['grade'],
            global_curve['median'],
            left=global_curve['median'].iloc[0],
            right=global_curve['median'].iloc[-1]
        )

        # Deviation = actual - baseline
        deviations = pace_ratios - baseline_ratios

        # Filter finite values
        mask = np.isfinite(grades) & np.isfinite(deviations)
        all_grades.extend(grades[mask])
        all_deviations.extend(deviations[mask])

    if len(all_grades) < 100:
        # Insufficient data for correlation, return neutral
        return 0.0

    # Compute correlation
    corr = np.corrcoef(all_grades, all_deviations)[0, 1]

    if not np.isfinite(corr):
        return 0.0

    return float(corr)


def compute_global_median_fingerprint(processed_root: Path, global_curve: pd.DataFrame) -> Dict[str, float]:
    """Compute global median fingerprint from all athletes for cold-start users.

    Args:
        processed_root: Path to processed athlete data
        global_curve: Pre-built global curve

    Returns:
        Dict with median fingerprint values
    """
    from predictor import iter_athlete_streams

    athlete_dirs = [
        p for p in processed_root.iterdir() if p.is_dir() and p.name.isdigit()
    ]

    all_fingerprints = []

    for athlete_dir in athlete_dirs:
        streams = list(iter_athlete_streams(athlete_dir))
        if len(streams) < MIN_ACTIVITIES:
            continue

        try:
            fingerprint = extract_fingerprint_from_activities(streams[:IDEAL_ACTIVITIES], global_curve)
            if fingerprint:
                all_fingerprints.append(fingerprint)
        except ValueError:
            continue

    if not all_fingerprints:
        # Fallback: neutral/unfit user
        return {
            'user_endurance_score': 1.15,  # Slightly poor endurance
            'user_recovery_rate': 0.0,  # Neutral recovery
            'user_base_fitness': 0.15  # Slow baseline (~6:40 min/km)
        }

    # Compute medians across all athletes
    return {
        'user_endurance_score': float(np.median([fp['user_endurance_score'] for fp in all_fingerprints])),
        'user_recovery_rate': float(np.median([fp['user_recovery_rate'] for fp in all_fingerprints])),
        'user_base_fitness': float(np.median([fp['user_base_fitness'] for fp in all_fingerprints]))
    }
