# Data Analysis - ML Model Training & Prediction

Analysis, preprocessing, and ML model training for route time prediction.

## Quick Start

```bash
cd data_analysis
source venv/bin/activate

# Preprocess athlete data
python preprocessing/convert_to_si.py

# Train ML model
python predictor/train.py
```

## Features

- **Data Preprocessing:** SI unit conversion, outlier detection
- **ML Model Training:** Gradient Boosting Regressor for pace prediction
- **Route Time Prediction:** Segment-based time estimation
- **Global Curve Generation:** Pace-grade relationship from athlete data
- **Visualization:** Plot scripts for analysis and validation

## Directory Structure

```
data_analysis/
├── data/
│   ├── processed/              # SI-converted athlete data
│   └── raw/                    # Raw data (if any)
├── preprocessing/
│   └── convert_to_si.py       # SI unit conversion
├── predictor/
│   ├── train.py               # Train ML model
│   ├── predictor.py           # Core prediction logic
│   ├── residual_model.joblib  # Trained model (generated)
│   └── global_curve.json      # Cached curve (generated)
├── plot_scripts/               # Visualization utilities
├── scripts/                    # Analysis scripts
└── requirements.txt            # Python dependencies
```

## Data Pipeline

### 1. Data Collection

Raw data collected by scraper in `scraper/data/strava/athletes/`:

```
athletes/
└── {athlete_id}/
    ├── activities.json              # Activity IDs
    ├── summary.json                 # Collection summary
    ├── {activity_id}_metadata.json  # Activity metadata
    └── {activity_id}_streams.json   # Time-series data
```

### 2. Preprocessing

Convert to SI units and validate:

```bash
python preprocessing/convert_to_si.py
```

**Input:** `scraper/data/strava/athletes/`
**Output:** `data_analysis/data/processed/`

**Conversions:**
- Temperature: Fahrenheit → Celsius (if avg > 50)
- Altitude: Feet → Meters (if max > 3000)
- Distance: Already meters (Strava API)
- Speed: Already m/s (Strava API)

### 3. Model Training

Train Gradient Boosting model:

```bash
python predictor/train.py
```

**Output:** `predictor/residual_model.joblib` (~270KB)

**Training Data:**
- 239 activities from 21 athletes
- Features: Grade mean/std, cumulative distance (fatigue)
- Target: Pace residual from global curve

**Model:** GradientBoostingRegressor with cross-validation

### 4. Global Curve Caching

Pre-compute for faster predictions:

```bash
cd ../backend
python scripts/cache_global_curve.py
```

**Output:** `predictor/global_curve.json`

**Impact:**
- Backend startup: 30-60s → <5s
- Prediction time: 30-60s → 2-5s

## Stream Data Fields

**Metadata:**
- `time`: seconds (s)
- `distance`: meters (m)
- `altitude`: meters (m)
- `velocity_smooth`: meters/second (m/s)
- `heartrate`: bpm
- `cadence`: rpm
- `watts`: power (W)
- `temp`: temperature (C)
- `moving`: boolean
- `grade_smooth`: percentage (%)

## ML Model Details

### Algorithm
Gradient Boosting Regressor (scikit-learn)

### Features
Per 50m segment:
- `grade_mean`: Average grade (%)
- `grade_std`: Grade variability
- `cumulative_distance_km`: Distance so far (fatigue proxy)

### Target
Pace residual: `actual_pace - global_curve_pace`

### Training Process

1. **Load athlete data** from `data/processed/`
2. **Compute global curve** - Average pace-grade relationship across all athletes
3. **Extract segments** - 50m chunks with grade and pace
4. **Calculate residuals** - Difference from global curve
5. **Train model** - Predict residuals from features
6. **Validate** - Cross-validation, feature importance
7. **Save model** - `residual_model.joblib`

### Performance

**Metrics (from training):**
- MAE: ~0.3 min/km
- R²: ~0.65
- Confidence Interval: ±10% (conservative)

**Best for:**
- Routes 5-50km
- Varied elevation
- Running activities

## Prediction Pipeline

### User Calibration

1. **Select Strava activity** - Recent run similar to target route
2. **Download streams** - GPS, altitude, time, distance
3. **Extract flat pace** - Pace on flat terrain (±2% grade)
4. **Store calibration** - Used for all predictions

### Route Prediction

1. **Parse GPX** - Extract lat/lon, altitude
2. **Create segments** - 50m chunks
3. **Calculate grades** - Slope for each segment
4. **Compute features** - Grade mean/std, distance
5. **Predict residuals** - ML model output
6. **Apply corrections** - Global curve + residuals
7. **Sum segment times** - Total prediction

### Output

- **Total time** (HH:MM:SS)
- **Confidence interval** (±10%)
- **Segment breakdown** (1km chunks for display)
- **Statistics** (distance, D+, avg grade)
- **Similar activities** (within 15% distance)

## Scripts

### `preprocessing/convert_to_si.py`

Convert raw Strava data to SI units.

**Usage:**
```bash
python preprocessing/convert_to_si.py
```

**Options:**
- Automatically detects units
- Saves processed data
- Logs conversion summary

### `predictor/train.py`

Train ML model from athlete data.

**Usage:**
```bash
python predictor/train.py
```

**Requirements:**
- Processed data in `data/processed/`
- At least 50 activities recommended

**Output:**
- `predictor/residual_model.joblib` - Trained model
- Training metrics logged to console

### `plot_scripts/`

Visualization utilities (examples):
- Pace-grade curves
- Residual distributions
- Feature importance
- Model validation plots

## API Integration

### PredictionService

Located in `backend/services/prediction_service.py`

**Methods:**
- `load_model()` - Load trained model
- `compute_global_curve()` - Calculate or load cached curve
- `calibrate_from_activity(activity_id)` - Extract flat pace
- `predict_time(gpx_id, flat_pace)` - Generate prediction

### Endpoints

- `POST /api/prediction/calibrate` - Calibrate user
- `POST /api/prediction/predict` - Generate prediction

## Testing

Test prediction service:
```bash
cd ../backend
python test_prediction_service.py
```

Validates:
- Model loading
- Global curve computation
- Calibration logic
- Prediction generation

## Troubleshooting

### "No processed data found"

Run preprocessing:
```bash
python preprocessing/convert_to_si.py
```

Ensure scraper collected data first.

### "Model file not found"

Train model:
```bash
python predictor/train.py
```

### "Insufficient data for training"

Collect more activities:
```bash
cd ../scraper
python scraper.py scrape --sport Run --days 90 --download-streams
```

Need at least 50 activities for reliable model.

### Slow predictions

Generate global curve cache:
```bash
cd ../backend
python scripts/cache_global_curve.py
```

### Poor prediction accuracy

1. **Calibration activity** - Choose similar route/conditions
2. **More training data** - Collect diverse activities
3. **Model retraining** - Run `train.py` with updated data

## Dependencies

Key packages in `requirements.txt`:
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `scikit-learn` - ML model
- `joblib` - Model serialization
- `matplotlib` - Plotting
- `scipy` - Scientific computing

Install:
```bash
pip install -r requirements.txt
```

## Data Quality

### Preprocessing Checks

- Temperature range: -20 to 50°C
- Altitude range: -100 to 9000m
- Speed range: 0 to 15 m/s (running)
- Grade range: -50 to 50%

### Outlier Detection

Future enhancement:
- GPS smoothing for elevation noise
- Anomaly detection for bad data
- Activity validation rules

## Model Improvements

**Future Enhancements:**

1. **Fatigue Modeling** - Time-based fatigue features
2. **Weather Features** - Temperature, humidity effects
3. **Terrain Features** - Surface type, technicality
4. **User Clustering** - Performance-based grouping
5. **Ensemble Models** - Combine multiple algorithms
6. **Cross-Validation** - Better confidence intervals

## File Formats

### Processed Data

JSON format per activity:
```json
{
  "metadata": {
    "activity_id": 123456,
    "distance": 10000,
    "moving_time": 3600,
    "total_elevation_gain": 200
  },
  "streams": {
    "time": [0, 1, 2, ...],
    "distance": [0, 2.5, 5.0, ...],
    "altitude": [100, 101, 102, ...],
    "velocity_smooth": [3.0, 3.1, 3.0, ...],
    "grade_smooth": [0, 1, 2, ...]
  }
}
```

### Model File

Joblib serialized scikit-learn model:
- `residual_model.joblib` - GradientBoostingRegressor
- Can be loaded with `joblib.load()`

### Global Curve Cache

JSON array of pace-grade pairs:
```json
{
  "grades": [-30, -20, -10, 0, 10, 20, 30],
  "paces": [4.0, 4.5, 5.0, 5.5, 6.5, 8.0, 10.0]
}
```

## Performance Metrics

### Training Performance

| Metric | Value |
|--------|-------|
| Training time | ~30s (239 activities) |
| Model size | ~270KB |
| Cross-validation folds | 5 |
| Feature count | 3 |

### Prediction Performance

| Metric | With Cache | Without Cache |
|--------|-----------|---------------|
| Model loading | <0.1s | <0.1s |
| Global curve | <0.1s | 30-60s |
| Calibration | 2-5s | 2-5s |
| Prediction (10km route) | 0.5-1s | 0.5-1s |

**Total:** 2-6s with cache, 33-66s without

## Next Steps

**Phase 2: Data Collection**
- Collect 500+ activities for better model
- Include diverse athletes and routes
- Validate data quality

**Phase 3: Advanced Features**
- Implement fatigue modeling
- Add weather data
- Terrain classification

**Phase 4: Model Optimization**
- Hyperparameter tuning
- Feature engineering
- Ensemble methods

**Phase 5: Deployment**
- Model versioning
- A/B testing
- Performance monitoring
