Goal: Provide a reproducible route-time predictor that uses your existing streams. The predictor should (a) build a global grade→pace ratio curve, (b) personalize it with a few anchor points from a user activity, and (c) apply it to a route grade profile to estimate finish time.

What we’ll build now
- A small library (`predictor.py`) that:
  - Loads processed stream JSON files (same structure you already have).
  - Computes a global normalized pace curve vs. gradient.
  - Extracts user-specific anchor ratios at a few grades (e.g., −30, −20, −10, 0, 10, 20, 30) from one calibration activity.
  - Warps the global curve with those anchors to form a personalized curve.
  - Predicts route time given a grade profile (distance, grade) and the user’s flat pace.
- This code stays self-contained; it won’t modify existing scripts.

Assumptions / Inputs
- Processed data layout: `data_analysis/data/processed/<athlete_id>/<activity_id>_streams.json` with at least `grade_smooth`, `velocity_smooth`, `moving`. Activities are listed in `activities.json` per athlete.
- Grade range of interest: [-40%, 40%] with 1% bins by default.
- Flat pace band for normalization: ±1% grade.
- Anchor grades: configurable; default [-30, -20, -10, 0, 10, 20, 30].
- Route profile: a DataFrame-like table with columns `distance_m` (monotonic) and `grade_percent`; can be derived from GPX (e.g., via gpxpy) or any precomputed profile.

Workflow
1) Build global curve (once): median pace ratio vs. grade across all athletes, normalized by each athlete’s flat pace. (Similar to `velocity_vs_gradient_all` but packaged as a function.)
2) User calibration: from one user activity, compute flat pace and anchor ratios at selected grades.
3) Personalization: interpolate an adjustment multiplier so that the personalized curve matches the user’s anchors, then apply it to the global curve.
4) Prediction: for each route segment, look up the personalized ratio for its grade, compute segment pace = flat_pace × ratio, then sum segment times.

Future extensions (not done now)
- Add GPX parsing helper (requires gpxpy).
- Add a learned correction model (e.g., tree model on residuals) if you want to go beyond curve-based prediction.
- Add caching of global curve to avoid recomputation.***

ML residual model (added now as a separate module)
- `ml_residual.py` builds a segment-level dataset and trains a small Gradient Boosting model to predict a correction multiplier on top of the curve-based baseline.
- Features per segment (default 200 m): grade mean/std, abs grade, cumulative distance (km).
- Target: actual pace ratio vs flat, divided by the baseline ratio from the global curve (i.e., a residual multiplier).
- Usage flow: build global curve → build dataset from processed streams → train model → predict route time with baseline×ML multiplier.
