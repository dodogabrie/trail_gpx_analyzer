## Route-Time Prediction: Curve + ML Residual (How It Works)

This document explains the predictor implemented in `predictor.py` and `ml_residual.py`. It combines a physics-ish baseline (pace vs. gradient) with an optional ML correction trained on your existing streams.

### Key Concepts
- **Pace ratio**: pace_at_grade / flat_pace. Ratio > 1 means slower than flat; < 1 means faster than flat.
- **Baseline curve**: A “typical” ratio vs. gradient built from all athletes, each normalized by their own flat pace.
- **Residual multiplier**: A learned correction on top of the baseline curve that accounts for factors like grade variability and distance into the activity.

### Baseline Curve (predictor.py)
1) For each athlete, compute flat pace as the median pace on near-flat grades (−1% to +1%).
2) For each activity, smooth velocity and grade; keep moving-only samples.
3) Bin by gradient (default 1% bins, capped to ±40%). For each bin, compute median pace, then divide by flat pace → pace ratio.
4) Aggregate across athletes: take the median ratio per grade bin (drop bins with very few athletes). Lightly smooth the curve.

Result: `global_curve` DataFrame with columns:
- `grade` (percent)
- `median` (baseline ratio at that grade)
- `p25`, `p75` (IQR, not used in prediction)

### User Calibration (predictor.py)
To personalize the curve without full ML:
1) From a user activity, compute their flat pace.
2) Choose a few anchor grades (default −30, −20, −10, 0, 10, 20, 30). For each anchor, take the median pace in a small window (±2%) and divide by flat pace → user anchor ratio.
3) Compute multipliers = (user anchor ratio) / (global baseline at that anchor). Interpolate these multipliers across all grades and warp the global curve.

Result: `personalized_curve` with columns:
- `grade`
- `personalized_ratio` (baseline ratio × interpolated multiplier)
- `multiplier` (the interpolated adjustment)

### Optional ML Residual Model (ml_residual.py)
Adds a learned correction on top of the baseline curve.

Training data build:
- Segment activities into fixed-length chunks (default 200 m).
- For each segment:
  - Features: `grade_mean`, `grade_std`, `abs_grade`, `cum_distance_km`.
  - Actual ratio = (segment pace) / (flat pace for that activity).
  - Baseline ratio = lookup from `global_curve` at `grade_mean`.
  - Target (residual_mult) = actual_ratio / baseline_ratio.
- Keep segments with enough samples (default ≥5 points per segment).

Model:
- GradientBoostingRegressor on the features above to predict `residual_mult`.

### Predicting a Route Time
Inputs:
- `route_profile`: columns `distance_m` (monotonic) and `grade_percent`.
- `flat_pace_min_per_km`: user flat pace (from a calibration activity).
- `global_curve`: baseline ratios.
- (Optional) `personalized_curve`: if using anchor-based personalization.
- (Optional) `residual_model`: ML model for residuals.

Steps per segment:
1) Baseline ratio = interpolate `global_curve` at segment grade (or `personalized_ratio` if available).
2) If residual model is used: predict `residual_mult` from features (grade mean/std, abs grade, cumulative distance); final ratio = baseline_ratio × residual_mult.
3) Pace at segment = flat_pace × final_ratio; speed = 1000 / (pace_min_per_km × 60).
4) Segment time = segment_distance / speed. Sum over all segments → total time (seconds).

### Example Wiring (pseudocode)
```python
from pathlib import Path
import pandas as pd
from predictor import build_global_curve, load_streams, prepare_stream, compute_flat_pace, personalize_curve
from ml_residual import build_training_dataset, train_residual_model, predict_time_with_model

processed_root = Path("data_analysis/data/processed")
# 1) Build baseline
global_curve = build_global_curve(processed_root)

# 2) Train residual model (optional, one-time)
train_df = build_training_dataset(processed_root, global_curve, segment_len_m=200)
res_model = train_residual_model(train_df)

# 3) Calibrate user (one activity)
user_stream = prepare_stream(load_streams(Path("..._streams.json")))
flat_pace = compute_flat_pace(user_stream)
anchors = {}  # or compute_anchor_ratios(user_stream, flat_pace) if you want anchor-based warp
personalized_curve = personalize_curve(global_curve, anchors) if anchors else None

# 4) Build route profile (distance_m, grade_percent) from GPX or a downsampled activity
route_profile = pd.DataFrame({"distance_m": [...], "grade_percent": [...]})

# 5) Predict time
if personalized_curve is not None:
    # If you want to bypass ML and just use personalization:
    total_sec = predict_time_seconds(route_profile, flat_pace, personalized_curve)
else:
    # Use baseline + ML residual
    total_sec = predict_time_with_model(route_profile, flat_pace, global_curve, res_model)
print(total_sec, "seconds")
```

### Notes and Tunables
- Grade cap: default ±40% to avoid noisy tails.
- Flat band: default ±1% for baseline; widen if you lack flat samples.
- Anchors: change `ANCHOR_GRADES` and `ANCHOR_WINDOW` in `predictor.py`.
- Segment length: `segment_len_m` in `ml_residual.py` (200 m default).
- Model: GBDT is a simple, strong baseline for tabular residuals; you can swap for other regressors if desired.

### Why this setup?
- The baseline curve captures the dominant physics/behavior (grade drives pace), normalized per athlete.
- Anchors let you quickly personalize with just a few grade samples.
- The residual model learns small corrections for grade variability and distance/fatigue effects without overcomplicating the pipeline.
