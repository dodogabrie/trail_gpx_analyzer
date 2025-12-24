# User Embedding for Fatigue Personalization

## Problem
Global ML model cannot adapt to individual fatigue patterns - same features yield same prediction regardless of user physiology.

## Solution: User Fatigue Fingerprint

### Phase 1: Extract User Metrics (per athlete, from 3+ activities)

From each athlete's historical activities, compute:

```python
user_endurance_score = median(pace_ratio_at_km_20) / median(pace_ratio_at_km_5)
# <1.0 = good endurance, >1.2 = poor endurance

user_recovery_rate = correlation(grade, pace_ratio_deviation)
# measures how well user handles grade changes vs average

user_base_fitness = 1.0 / flat_pace_median
# normalized speed baseline
```

Require 3+ activities per athlete covering 15km+ to compute reliably.

### Phase 2: Augment Training Data

For each segment in `build_training_dataset()`:
- Add 3 user-level features: `[user_endurance_score, user_recovery_rate, user_base_fitness]`
- Total features: 10 (current) + 3 (user) = 13

### Phase 3: Prediction with New User

**Calibration phase:**
- User provides 3+ activities (15km+ each)
- Extract their fingerprint: `[endurance_score, recovery_rate, base_fitness]`

**Prediction:**
- Compute segment features as normal
- Append user's fingerprint to each segment
- Model adapts residuals based on user type

### Phase 4: Cold Start (new user, <3 activities)

Fallback to curve-based predictor only. Require minimum data for ML predictions.

## Data Requirements
- Training: 21 athletes with 10+ activities each (marginal, current: ~12 avg)
- Per-user: 3-5 varied activities (15km+, mixed grades) for fingerprint

## Expected Improvement
Model learns: "users with endurance_score=0.95 maintain pace better at distance" vs "users with 1.15 degrade faster"

## Limitations
- Still requires multiple activities per user
- Won't capture day-to-day variation (nutrition, sleep, training state)
- Better than global, worse than per-user models (if enough data)
