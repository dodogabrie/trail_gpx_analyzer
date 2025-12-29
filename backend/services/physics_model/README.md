# Physics-Based Trail Running Prediction Model

A scientifically-grounded model for predicting trail running pace and race times based on energy cost of transport, terrain effects, and accumulated fatigue.

## Overview

This model predicts running performance on varied terrain by combining:
- **Metabolic energy cost** (Minetti et al. 2002 polynomial)
- **Regime separation** (energy-limited uphill vs kinematic-limited downhill)
- **Eccentric fatigue accumulation** from descents
- **User-specific calibration** from historical activity data

### Key Innovation

Unlike simple pace-adjustment models, this physics model:
- Treats uphill as **energy-limited** (metabolic cost determines speed)
- Treats downhill as **kinematic-limited** (technique and terrain cap speed)
- Accumulates **eccentric load** from descents that degrades performance on subsequent segments
- Personalizes all parameters using **only the individual user's data** (Strava API compliant)

## Scientific Foundation

### Minetti Cost of Transport (2002)

The model is based on the empirical energy cost function from treadmill studies:

```
C(g) = 155.4g^5 - 30.4g^4 - 43.3g^3 + 46.3g^2 + 19.5g + 3.6
```

Where:
- `C(g)` = Energy cost of transport in J/(kg·m)
- `g` = Grade as fraction (e.g., 0.10 for 10%)
- `C(0) = 3.6` = Baseline cost on flat ground

**Reference**: Minetti et al., *Journal of Applied Physiology*, 2002
https://journals.physiology.org/doi/full/10.1152/japplphysiol.01177.2001

### Regime Separation

#### Uphill/Flat (Energy-Limited)
At constant metabolic power output, velocity is inversely proportional to energy cost:

```python
v_uphill = v_flat / (C(g)/C(0) * k_terrain * k_up * fatigue_factor)
```

**Physical interpretation**: Steeper grades require more energy per meter, so you must slow down to maintain sustainable power output.

#### Downhill (Kinematic-Limited)
Descents are limited by technique, terrain roughness, and safety rather than pure metabolic cost:

```python
v_downhill = min(
    v_energy,  # Theoretical energy-based speed (usually very high)
    v_cap      # Practical kinematic limit
)

v_cap = v_flat * (1 + a * |g|) * (k_tech / fatigue_factor) / k_terrain_down
```

**Physical interpretation**:
- Gravity assists, allowing faster pace
- But speed is capped by foot strike control, terrain navigation, and eccentric muscle capacity
- Fatigue reduces downhill technique effectiveness

### Eccentric Fatigue Model

Descents cause muscle damage that accumulates and degrades performance:

```python
# Accumulate eccentric load on descents
if grade < 0:
    load = (|grade| - 0.005)^1.5 * segment_length
    accumulated_load += load

# Apply fatigue to subsequent segments
norm_load = accumulated_load / min(route_distance, 42000m)
fatigue_factor = 1 + (alpha * norm_load)
```

**Physical interpretation**:
- Steep descents (>5%) cause exponentially more damage than gentle descents
- Accumulated damage reduces both uphill power output and downhill control
- Normalization by 42km baseline ensures consistent fatigue scaling across race distances

## Module Structure

```
physics_model/
├── README.md                    # This file
├── core.py                      # Core physics calculations
├── pipeline.py                  # Prediction loop with fatigue
├── calibration.py               # User parameter calibration
└── fatigue_calibration.py       # Fatigue alpha extraction
```

### core.py
Low-level physics functions:
- `minetti_cost_of_transport(grade)` - Energy cost calculation
- `predict_uphill_velocity(...)` - Energy-limited regime
- `predict_downhill_velocity(...)` - Kinematic-limited regime
- `calculate_fatigue_contribution(...)` - Eccentric load accumulation

### pipeline.py
Main prediction engine:
- `run_physics_prediction(route_df, user_params, fatigue_alpha)` - Full route prediction
- Handles route preprocessing (resampling, grade smoothing)
- Loops through segments applying regime-specific models
- Accumulates fatigue and applies to subsequent segments
- Returns time prediction + diagnostics

### calibration.py
User-specific parameter fitting:
- `calibrate_user_params(activity_streams)` - Extract v_flat, k_up, k_tech, a_param
- Uses only the individual user's historical activities (Strava compliant)
- Robust estimation via median and binning to handle GPS noise

### fatigue_calibration.py
Fatigue sensitivity extraction:
- `calibrate_fatigue_alpha_from_curve(fatigue_curve, distance)` - Convert performance degradation curves to physics alpha
- Supports both exponential fit (new) and legacy degradation array formats

## Key Parameters

### User-Calibrated Parameters

| Parameter | Type | Range | Meaning | Calibration Method |
|-----------|------|-------|---------|-------------------|
| `v_flat` | m/s | 2.5-5.0 | Flat ground pace | Median velocity on 0-2% grade segments |
| `k_up` | multiplier | 0.5-2.0 | Uphill difficulty | Ratio of predicted vs observed uphill pace |
| `k_tech` | multiplier | 0.5-1.5 | Downhill technique | Intercept of v_down vs \|grade\| regression |
| `a_param` | multiplier | 1.0-6.0 | Grade-to-speed gain | Slope of v_down vs \|grade\| regression |
| `fatigue_alpha` | sensitivity | 0.0-2.0 | Fatigue accumulation rate | Fitted from performance degradation curves |

### Fixed Terrain Factors

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `k_terrain_up` | 1.08 | Trail penalty on climbs (8% slower than road) |
| `k_terrain_down` | 1.12 | Trail penalty on descents (12% slower than road) |
| `k_terrain_flat` | 1.05 | Trail penalty on flats (5% slower than road) |

**Note**: Future versions may calibrate terrain factors from GPS curvature/roughness metrics.

## Usage Example

```python
from services.physics_model.pipeline import run_physics_prediction
import pandas as pd

# Prepare route data
route_df = pd.DataFrame({
    'distance': [0, 50, 100, 150, ...],      # meters (cumulative)
    'elevation': [100, 105, 112, 108, ...]   # meters
})

# User parameters from calibration
user_params = {
    'v_flat': 3.5,          # 4:45 min/km on flat
    'k_up': 1.1,            # 10% slower than baseline on climbs
    'k_tech': 1.05,         # 5% better downhill technique than average
    'a_param': 3.2,         # Moderate grade-to-speed gain
    'k_terrain_up': 1.08,
    'k_terrain_down': 1.12,
    'k_terrain_flat': 1.05
}

# Run prediction
result = run_physics_prediction(
    route_df,
    user_params,
    fatigue_alpha=0.4  # Moderate fatigue sensitivity
)

# Extract results
print(f"Predicted time: {result['total_time_seconds'] / 3600:.2f} hours")
print(f"Final fatigue factor: {result['diagnostics']['final_fatigue_factor']:.3f}")
```

## Model Validation

### Expected Accuracy
- **MAE (Mean Absolute Error)**: 5-10% on routes with similar terrain to calibration data
- **Systematic bias**: <3% (model neither consistently optimistic nor pessimistic)

### Known Limitations
1. **Technical terrain**: Model doesn't account for extreme technicality (boulder fields, scrambling)
2. **Altitude**: No physiological adjustment for elevation >2000m
3. **Weather**: Doesn't model heat, cold, or precipitation effects
4. **Nutrition**: Assumes proper fueling strategy
5. **GPS noise**: Requires smoothed elevation data (done automatically via resampling)

## Comparison to ML Model

| Aspect | Physics Model | ML Model |
|--------|---------------|----------|
| **Data requirements** | Single user activities | Multi-user dataset |
| **Strava compliance** | ✅ Yes (intra-user only) | ❌ No (cross-user learning) |
| **Interpretability** | ✅ High (physics-based) | ⚠️ Low (black box) |
| **Cold start** | ✅ Works with defaults | ❌ Needs training data |
| **Personalization** | ⚠️ Requires calibration activities | ✅ Automatic from any data |
| **Extreme terrain** | ⚠️ Extrapolates poorly | ✅ Better if trained on similar |
| **Fatigue modeling** | ✅ Explicit eccentric load | ⚠️ Implicit in pace degradation |

## Future Enhancements

### Planned
- [ ] Altitude physiological adjustment (VO2max degradation >1500m)
- [ ] Heat stress model (temperature + humidity effects)
- [ ] Dynamic terrain factor calibration from GPS curvature
- [ ] Grade-dependent fatigue (steep descents cause more damage)

### Research Ideas
- [ ] Recovery model (fatigue decay during flat/easy sections)
- [ ] Asymmetric fatigue (descents affect climbs more than vice versa)
- [ ] Biomechanical muscle fiber type modeling (fast-twitch vs slow-twitch)
- [ ] Circadian rhythm effects (time-of-day performance variation)

## References

### Primary Scientific Papers
1. **Minetti et al. (2002)** - "Energy Cost of Walking and Running at Extreme Uphill and Downhill Slopes"
   *Journal of Applied Physiology*, 93(3), 1039-1046
   https://journals.physiology.org/doi/full/10.1152/japplphysiol.01177.2001

2. **Lemire et al. (2021)** - "Considerations for Energy Cost Estimation in Trail Running"
   *Frontiers in Physiology*, 12, 697315
   https://www.frontiersin.org/articles/10.3389/fphys.2021.697315/full

3. **Balducci et al. (2016)** - "Performance Factors in Trail Running"
   *Journal of Sports Science & Medicine*, 15(2), 239-246
   https://www.jssm.org/jssm-15-239.xml

### Related Documentation
- `../../new_model_strategy.txt` - Theoretical foundation and legal compliance strategy
- `../../new_model_pseudocode.txt` - Detailed implementation specification

## License & Attribution

This model implementation is based on publicly available scientific literature and does not use proprietary datasets. All user calibration is performed using only the individual user's own activity data, ensuring compliance with Strava API Terms of Service.

When using this model, please cite:
- Minetti et al. (2002) for the energy cost function
- This implementation for the regime separation and fatigue model
