## Route-Time Prediction: How to Train and Use the Residual Model

This walks you through training and using the predictor with the existing code.

### 1) Prereqs
- Activate the venv: `source data_analysis/venv/bin/activate`
- Install deps (if needed): `pip install scikit-learn joblib`

### 2) Train the residual model
This builds the global baseline curve, constructs a segment-level dataset, trains a Gradient Boosting model, and saves it.
```bash
python data_analysis/predictor/train.py
# Output: data_analysis/predictor/residual_model.joblib
```

### 3) Calibrate a user (get flat pace)
Use one of the user’s activities (streams JSON) to compute flat pace. Optional: build a route profile from that activity for testing.
```python
from pathlib import Path
from predictor import load_streams, prepare_stream, compute_flat_pace, build_route_profile_from_stream

user_stream = prepare_stream(load_streams(Path("path/to/user_streams.json")))
flat_pace = compute_flat_pace(user_stream)  # min/km

# For testing using this activity as the route:
route_profile = build_route_profile_from_stream(user_stream, step_m=50)  # distance_m, grade_percent
```

### 4) Load global curve + model, predict time (with ML residual)
```python
import joblib
from pathlib import Path
from predictor import build_global_curve
from ml_residual import predict_time_with_model

processed_root = Path("data_analysis/data/processed")
global_curve = build_global_curve(processed_root)
model = joblib.load("data_analysis/predictor/residual_model.joblib")

# route_profile: DataFrame with distance_m (monotonic) and grade_percent
total_sec = predict_time_with_model(route_profile, flat_pace, global_curve, model)
print("Predicted time (min):", total_sec / 60)
```

### 5) (Alternative) Anchor-based personalization instead of ML residual
If you prefer using user anchor grades to warp the baseline curve (no ML residual):
```python
from predictor import compute_anchor_ratios, personalize_curve, predict_time_seconds

anchors = compute_anchor_ratios(user_stream, flat_pace)  # default grades [-30..30] with a small window
personalized_curve = personalize_curve(global_curve, anchors)
total_sec = predict_time_seconds(route_profile, flat_pace, personalized_curve)
print("Predicted time (min):", total_sec / 60)
```

### Inputs recap
- Processed data: `data_analysis/data/processed/<athlete_id>/<activity_id>_streams.json` plus `activities.json`.
- User calibration: one activity with `grade_smooth`, `velocity_smooth`, `moving` to derive flat pace and anchors (optional).
- Route profile: `distance_m`, `grade_percent` (from GPX or downsampled activity).

### Tunables
- Segment length for ML: set `segment_len_m` (default 200 m) in `train.py` / `build_training_dataset`.
- Grade range: capped at ±40% in the baseline curve.
- Flat band: ±1% by default; widen if you lack flat samples.
- Anchors: change `ANCHOR_GRADES` and `ANCHOR_WINDOW` in `predictor.py`.

### Notes
- The ML residual model already considers cumulative distance (fatigue signal). You can add more features in `build_training_dataset` (e.g., elapsed time, rolling speed/grade) and retrain.
- For GPX routes, you’ll need to compute `distance_m` and `grade_percent` externally (e.g., gpxpy) before calling the predictor.
