"""Fatigue parameter calibration for physics model.

Converts user's historical fatigue curves (from performance snapshots)
into physics model fatigue parameters.
"""
import numpy as np
from typing import Dict, Optional, List


def calibrate_fatigue_alpha_from_curve(
    fatigue_curve: Dict,
    expected_distance_km: float = 20.0
) -> float:
    """Calibrate fatigue_alpha from user's historical fatigue curve.

    Args:
        fatigue_curve: Fatigue curve dict from PerformanceSnapshot
                      Contains 'overall' with fitted params {a, tau_km} (new format)
                      OR 'grades' with degradation arrays (legacy format)
        expected_distance_km: Typical race distance for calibration

    Returns:
        Calibrated fatigue_alpha parameter for physics model
    """
    if not fatigue_curve:
        return 0.3  # Default

    # Try new format first
    overall = fatigue_curve.get('overall', {})
    fit_params = overall.get('fit', {}).get('params', {})

    if fit_params and fit_params.get('a') is not None:
        # New format with fitted exponential parameters
        a = fit_params.get('a', 0.0)
        tau_km = fit_params.get('tau_km', 10.0)

        expected_degradation = 1.0 + a * (1.0 - np.exp(-expected_distance_km / tau_km))

        estimated_load_per_km = 0.15
        total_load = estimated_load_per_km * expected_distance_km
        norm_load = total_load / max(1000.0, expected_distance_km * 1000)

        if norm_load > 0:
            fatigue_alpha = (expected_degradation - 1.0) / norm_load
        else:
            fatigue_alpha = 0.3

        return max(0.0, min(2.0, fatigue_alpha))

    # Fallback: Legacy format with 'grades'
    grades = fatigue_curve.get('grades', {})
    sample_distances = fatigue_curve.get('sample_distances', [])

    if not grades or not sample_distances:
        return 0.3

    # Try to get degradation from flat grade (0)
    grade_data = grades.get('0') or grades.get(0)
    if not grade_data:
        # Try any available grade
        for key in ['10', '-10', '20', '-20']:
            grade_data = grades.get(key) or grades.get(int(key)) if key.lstrip('-').isdigit() else None
            if grade_data:
                break

    if not grade_data:
        return 0.3

    degradation = grade_data.get('degradation', [])
    if not degradation or len(degradation) < 2:
        return 0.3

    # Find degradation at expected distance
    distances = [float(d) for d in sample_distances if d is not None]
    degradations = [float(v) for v in degradation if v is not None]

    if not distances or not degradations or len(distances) != len(degradations):
        return 0.3

    # Interpolate degradation at expected distance
    if expected_distance_km <= distances[0]:
        expected_degradation = degradations[0]
    elif expected_distance_km >= distances[-1]:
        expected_degradation = degradations[-1]
    else:
        expected_degradation = float(np.interp(expected_distance_km, distances, degradations))

    # Calculate fatigue_alpha from degradation
    estimated_load_per_km = 0.15
    total_load = estimated_load_per_km * expected_distance_km
    norm_load = total_load / max(1000.0, expected_distance_km * 1000)

    if norm_load > 0 and expected_degradation > 1.0:
        fatigue_alpha = (expected_degradation - 1.0) / norm_load
    else:
        # Use degradation directly as a rough estimate
        # degradation of 1.2 (20% slower) → alpha ~0.5
        fatigue_alpha = (expected_degradation - 1.0) * 2.5

    return max(0.0, min(2.0, fatigue_alpha))


def get_band_specific_alpha(
    fatigue_curve: Dict,
    grade_band: str = 'overall',
    expected_distance_km: float = 20.0
) -> float:
    """Get fatigue alpha for specific grade band.

    Args:
        fatigue_curve: Fatigue curve dict from PerformanceSnapshot
        grade_band: 'overall', 'downhill', 'uphill', 'flat', etc.
        expected_distance_km: Typical race distance

    Returns:
        Calibrated fatigue_alpha for the grade band
    """
    if not fatigue_curve:
        return 0.3

    if grade_band == 'overall':
        return calibrate_fatigue_alpha_from_curve(fatigue_curve, expected_distance_km)

    bands = fatigue_curve.get('bands', {})
    band_data = bands.get(grade_band, {})

    if not band_data:
        return calibrate_fatigue_alpha_from_curve(fatigue_curve, expected_distance_km)

    fit_params = band_data.get('fit', {}).get('params', {})
    if not fit_params:
        return calibrate_fatigue_alpha_from_curve(fatigue_curve, expected_distance_km)

    a = fit_params.get('a', 0.0)
    tau_km = fit_params.get('tau_km', 10.0)

    expected_degradation = 1.0 + a * (1.0 - np.exp(-expected_distance_km / tau_km))

    # Adjust load estimate based on grade band
    if 'downhill' in grade_band.lower():
        estimated_load_per_km = 0.25  # More eccentric load on descents
    elif 'uphill' in grade_band.lower():
        estimated_load_per_km = 0.05  # Less eccentric, more muscular fatigue
    else:
        estimated_load_per_km = 0.10

    total_load = estimated_load_per_km * expected_distance_km
    norm_load = total_load / max(1000.0, expected_distance_km * 1000)

    if norm_load > 0:
        fatigue_alpha = (expected_degradation - 1.0) / norm_load
    else:
        fatigue_alpha = 0.3

    return max(0.0, min(2.0, fatigue_alpha))


def estimate_route_fatigue_alpha(
    fatigue_curve: Dict,
    route_profile: Dict
) -> float:
    """Estimate fatigue_alpha based on route terrain profile.

    Args:
        fatigue_curve: User's fatigue curve from performance snapshot
        route_profile: Dict with terrain breakdown:
                      {'downhill_pct': 0.3, 'uphill_pct': 0.4, 'flat_pct': 0.3}

    Returns:
        Weighted fatigue_alpha based on route composition
    """
    if not fatigue_curve or not route_profile:
        return 0.3

    downhill_pct = route_profile.get('downhill_pct', 0.3)
    uphill_pct = route_profile.get('uphill_pct', 0.4)
    flat_pct = route_profile.get('flat_pct', 0.3)

    # Get band-specific alphas
    alpha_downhill = get_band_specific_alpha(fatigue_curve, 'downhill')
    alpha_uphill = get_band_specific_alpha(fatigue_curve, 'uphill')
    alpha_flat = get_band_specific_alpha(fatigue_curve, 'flat')

    # Weighted average based on route composition
    weighted_alpha = (
        downhill_pct * alpha_downhill +
        uphill_pct * alpha_uphill +
        flat_pct * alpha_flat
    )

    return weighted_alpha
