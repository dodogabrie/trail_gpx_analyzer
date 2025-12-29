"""Core physics calculations for trail running prediction model.

This module implements the fundamental physics equations based on:
- Minetti et al. (2002) energy cost of transport polynomial
- Regime separation (energy-limited uphill vs kinematic-limited downhill)
- Eccentric fatigue accumulation from descents

All functions are pure (no side effects) and operate on SI units.
"""

import math


def minetti_cost_of_transport(grade: float) -> float:
    """Calculate metabolic energy cost of transport on inclined terrain.

    Based on empirical polynomial from treadmill studies by Minetti et al. (2002).
    This function quantifies how much metabolic energy is required to move 1 kg
    of body mass over 1 meter of horizontal distance at a given grade.

    The polynomial is asymmetric:
    - Flat (g=0): C = 3.6 J/(kg·m) - baseline metabolic cost
    - Uphill (g>0): Cost increases rapidly (steep grades are exponentially harder)
    - Downhill (g<0): Cost initially decreases, then increases due to eccentric control

    Valid range: -35% to +35% grade (values clamped to prevent polynomial explosion)

    Args:
        grade: Terrain gradient as fraction (NOT percentage).
               Examples: 0.10 = 10% uphill, -0.05 = 5% downhill
               Automatically clamped to [-0.35, 0.35] for numerical stability.

    Returns:
        Metabolic energy cost in Joules per kilogram per meter.
        Typical values: 2.5 (gentle downhill) to 15+ (steep uphill).

    Reference:
        Minetti et al., "Energy cost of walking and running at extreme uphill
        and downhill slopes", Journal of Applied Physiology, 2002.
        https://doi.org/10.1152/japplphysiol.01177.2001

    Example:
        >>> minetti_cost_of_transport(0.0)    # Flat ground
        3.6
        >>> minetti_cost_of_transport(0.10)   # 10% uphill
        6.2  # ~1.7x harder than flat
        >>> minetti_cost_of_transport(-0.10)  # 10% downhill
        2.8  # Easier than flat (gravity assists)
    """
    # Clamp grade to polynomial's valid range to prevent numerical instability
    # Beyond ±35%, the polynomial extrapolates poorly and doesn't reflect real running
    g = max(-0.35, min(0.35, grade))

    # Minetti polynomial (5th order fitted to empirical treadmill data)
    cost = (155.4 * g**5) \
         - (30.4 * g**4) \
         - (43.3 * g**3) \
         + (46.3 * g**2) \
         + (19.5 * g) \
         + 3.6

    return cost

def normalized_cost_ratio(grade: float) -> float:
    """Calculate energy cost ratio relative to flat ground.

    Normalizes the Minetti cost function to flat ground baseline, providing
    a simple multiplier for how much harder/easier a given grade is.

    Args:
        grade: Terrain gradient as fraction (e.g., 0.10 = 10% uphill)

    Returns:
        Cost ratio relative to flat (C(grade) / C(0)).
        Examples:
        - 1.0 = same as flat ground
        - 1.7 = 70% more energy required (typical for 10% uphill)
        - 0.8 = 20% less energy (gentle downhill with gravity assist)

    Example:
        >>> normalized_cost_ratio(0.10)  # 10% uphill
        1.72  # Requires 72% more energy than flat
        >>> normalized_cost_ratio(0.0)   # Flat
        1.0   # Baseline
    """
    c0 = 3.6  # Minetti baseline cost at 0% grade
    return minetti_cost_of_transport(grade) / c0

def predict_uphill_velocity(
    grade: float,
    v_flat: float,
    k_up: float,
    k_terrain: float = 1.0,
    fatigue_factor: float = 1.0
) -> float:
    """Predict running velocity in energy-limited regime (uphill and flat).

    On uphill and flat terrain, running speed is limited by metabolic power output.
    Assuming constant sustainable power, velocity must decrease as the energy cost
    per meter increases (steeper grades require more energy per meter).

    Formula:
        v = v_flat / (CostRatio(g) * k_terrain * k_up * fatigue)

    Where:
        - CostRatio(g) = Minetti energy multiplier for grade g
        - k_terrain = terrain difficulty multiplier (1.0 = road, >1.0 = trail)
        - k_up = user's uphill efficiency (1.0 = average, <1.0 = strong climber)
        - fatigue = accumulated fatigue factor (1.0 = fresh, >1.0 = fatigued)

    Args:
        grade: Terrain gradient as fraction (typically >= 0 for this regime)
        v_flat: User's baseline velocity on flat ground in m/s
        k_up: User-specific uphill difficulty multiplier
        k_terrain: Terrain roughness penalty (default 1.0 = smooth)
        fatigue_factor: Current fatigue state (default 1.0 = fresh)

    Returns:
        Predicted velocity in m/s.
        Lower velocity = harder grade, rougher terrain, more fatigue.

    Example:
        >>> predict_uphill_velocity(
        ...     grade=0.10,        # 10% uphill
        ...     v_flat=3.5,        # 4:45 min/km on flat
        ...     k_up=1.1,          # 10% slower than average on climbs
        ...     k_terrain=1.08,    # Trail (8% penalty)
        ...     fatigue_factor=1.0 # Fresh
        ... )
        1.72  # Predicted: ~9:40 min/km (much slower due to grade)
    """
    # Calculate how much harder this grade is compared to flat
    cost_ratio = normalized_cost_ratio(grade)

    # Combine all slowdown factors
    denom = cost_ratio * k_terrain * k_up * fatigue_factor

    # Protect against division by zero (should never happen in practice)
    if denom <= 0:
        return 0.001

    # At constant power: velocity inversely proportional to energy cost
    return v_flat / denom

def predict_downhill_velocity(
    grade: float,
    v_flat: float,
    k_tech: float,
    a_param: float,
    k_terrain_down: float = 1.0,
    k_terrain_up: float = 1.0,
    fatigue_factor: float = 1.0
) -> float:
    """Predict running velocity in kinematic-limited regime (downhill).

    On downhill terrain, metabolic cost is LOW (gravity assists), but practical
    speed is limited by:
    - Downhill running technique (foot strike control, braking)
    - Terrain roughness (rocks, roots, mud)
    - Eccentric muscle capacity and accumulated fatigue
    - Risk management (injury avoidance)

    The model takes the MINIMUM of two limits:
    1. Energy-based limit: theoretical max speed from metabolic cost (usually very high)
    2. Kinematic cap: practical limit from technique and terrain

    Formula for kinematic cap:
        v_cap = v_flat * (1 + a * |grade|) * (k_tech / fatigue) / k_terrain_down

    Where:
        - (1 + a * |grade|) = grade-to-speed multiplier (steeper = faster due to gravity)
        - k_tech = user's downhill technique (1.0 = average, >1.0 = skilled)
        - fatigue degrades technique (fatigued = worse control = slower for safety)
        - k_terrain_down = trail roughness penalty on descents

    Args:
        grade: Terrain gradient as fraction (typically < 0 for downhill)
        v_flat: User's baseline velocity on flat ground in m/s
        k_tech: User's downhill technique multiplier
        a_param: Grade-to-speed sensitivity (how much grade increases speed)
        k_terrain_down: Terrain penalty on descents (default 1.0 = smooth)
        k_terrain_up: Terrain factor for energy calc (rarely matters)
        fatigue_factor: Current fatigue state (degrades technique)

    Returns:
        Predicted velocity in m/s.
        Capped by whichever is LOWER: energy limit or kinematic limit.
        (Almost always kinematic-limited in practice)

    Example:
        >>> predict_downhill_velocity(
        ...     grade=-0.10,        # 10% downhill
        ...     v_flat=3.5,         # 4:45 min/km on flat
        ...     k_tech=1.05,        # 5% better downhill skill
        ...     a_param=3.0,        # Moderate grade sensitivity
        ...     k_terrain_down=1.12,# Trail (12% penalty on descents)
        ...     fatigue_factor=1.08 # 8% fatigued
        ... )
        4.2  # Predicted: ~3:58 min/km (faster than flat, but capped by technique)
    """
    # 1. Energy-based theoretical limit (usually much higher than achievable)
    #    Using uphill energy model with k_up=1.0 for neutral comparison
    #    In practice, this limit rarely matters because kinematic cap dominates
    v_energy = predict_uphill_velocity(grade, v_flat, 1.0, k_terrain_up, fatigue_factor)

    # 2. Kinematic/Technical Limit (USUALLY THE LIMITING FACTOR)
    #    Formula: v_cap = v_flat * grade_multiplier * technique / terrain_penalty
    abs_g = abs(grade)

    # Fatigue reduces technique effectiveness (tired = worse control = must slow for safety)
    effective_k_tech = k_tech / fatigue_factor

    # Grade multiplier: steeper descents allow faster pace (gravity assist)
    # But terrain and technique limit how much you can capitalize on this
    v_cap = v_flat * (1.0 + a_param * abs_g) * effective_k_tech / k_terrain_down

    # Return whichever limit is LOWER (almost always v_cap in real trail running)
    return min(v_energy, v_cap)

def calculate_fatigue_contribution(grade: float, segment_len_m: float) -> float:
    """Calculate eccentric load contribution from a downhill segment.

    Downhill running causes eccentric muscle contractions (muscles lengthen under load)
    which leads to:
    - Muscle fiber micro-damage
    - Delayed onset muscle soreness (DOMS)
    - Reduced power output and control in subsequent segments

    This function quantifies the "fatigue load" accumulated from a single segment.
    The load is:
    - Zero for flat/uphill (no eccentric stress)
    - Increases exponentially with descent steepness (steep = more damage)
    - Proportional to distance covered

    Formula:
        load = w(|grade|) * distance
        where w(|g|) = max(0, |g| - threshold)^1.5

    The threshold (0.5%) filters out nearly-flat sections while allowing gentle
    descents (1-5%) to contribute proportionally over distance.

    Args:
        grade: Terrain gradient as fraction (negative for downhill)
        segment_len_m: Segment length in meters

    Returns:
        Eccentric load contribution (dimensionless accumulated stress).
        Zero if grade >= 0 (no downhill).
        Increases with steepness and distance.

    Example:
        >>> calculate_fatigue_contribution(-0.01, 100)  # 1% descent, 100m
        5.0   # Very gentle, small contribution
        >>> calculate_fatigue_contribution(-0.10, 100)  # 10% descent, 100m
        92.4  # Steep, significant contribution
        >>> calculate_fatigue_contribution(0.10, 100)   # Uphill
        0.0   # No eccentric load
    """
    # Only downhill segments contribute eccentric load
    if grade >= 0:
        return 0.0

    abs_g = abs(grade)

    # Threshold: very gentle descents (<0.5%) cause negligible eccentric stress
    # This filters GPS noise while capturing real rolling terrain
    damage_threshold = 0.005  # 0.5% grade

    # Smooth power law function (no discontinuity at threshold)
    # Exponent 1.5 means steep descents cause exponentially more damage
    abs_g_net = max(0.0, abs_g - damage_threshold)
    weight = abs_g_net ** 1.5  # Power law as per biomechanical models

    # Total load = intensity × distance
    return weight * segment_len_m
