# Backend - Flask API Server

Flask-based REST API for GPX analysis and route time prediction with Strava integration.

## Quick Start

```bash
cd backend
source venv/bin/activate
python app.py
```

Server runs on `http://localhost:5000`

## Prerequisites

### 1. Environment Variables

Create `backend/.env`:
```bash
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

### 2. ML Model (Required for Predictions)

Train or ensure model exists:
```bash
cd ../data_analysis
source venv/bin/activate
python predictor/train.py
```

Creates `data_analysis/predictor/residual_model.joblib`

### 3. Global Curve Cache (Optional, Recommended)

Pre-compute for faster startup (saves ~30s):
```bash
python scripts/cache_global_curve.py
```

Creates `data_analysis/predictor/global_curve.json`

## Architecture

### Flask Server
- **Entry Point:** `app.py`
- **Config:** `config.py` - CORS, Strava credentials, paths
- **Database:** `database.py` - SQLite for GPX files and user sessions

### API Modules

#### `/api/strava`
Strava OAuth and activity fetching
- `GET /api/strava/auth-url` - Get authorization URL
- `GET /api/strava/auth-callback` - OAuth callback handler
- `GET /api/strava/activities` - List user activities
- `GET /api/strava/activity/:id/streams` - Download activity streams

#### `/api/gpx`
GPX file management
- `POST /api/gpx/upload` - Upload GPX file
- `GET /api/gpx/list` - List uploaded files
- `GET /api/gpx/:id` - Get GPX data
- `DELETE /api/gpx/:id` - Delete GPX file

#### `/api/prediction`
Route time prediction (see [Prediction API](#prediction-api))
- `GET /api/prediction/calibration-activities` - List activities for calibration
- `POST /api/prediction/calibrate` - Compute flat pace from activity
- `POST /api/prediction/predict` - Generate route time prediction

## Services

### PredictionService (`services/prediction_service.py`)

Core ML prediction service:
- Loads GradientBoosting model
- Computes global pace-grade curve
- Calibrates user flat pace from Strava activities
- Generates segment-by-segment predictions

**Key Methods:**
- `calibrate_from_activity(activity_id)` - Extract flat pace
- `predict_time(gpx_id, flat_pace)` - Generate prediction
- `get_calibration_activities(gpx_id, limit)` - List suitable activities

### StravaService (`services/strava_service.py`)

Strava API integration:
- OAuth token management
- Activity fetching and filtering
- Stream downloads (lat/lon, altitude, time, distance, grade)
- Rate limiting (200 req/15min, 2000 req/day)

## Prediction API

### Workflow

1. **List Calibration Activities**
   ```http
   GET /api/prediction/calibration-activities?gpx_id=5&limit=50
   ```

   Response: Activities similar to GPX route, marked as "recommended"

2. **Calibrate Flat Pace**
   ```http
   POST /api/prediction/calibrate
   Content-Type: application/json

   {"activity_id": 123456}
   ```

   Response: `{"flat_pace_min_per_km": 5.2, ...}`

3. **Generate Prediction**
   ```http
   POST /api/prediction/predict
   Content-Type: application/json

   {"gpx_id": 5, "flat_pace_min_per_km": 5.2}
   ```

   Response: Time prediction with segments, confidence interval, similar activities

### Response Structure

```json
{
  "prediction": {
    "total_time_seconds": 3720,
    "total_time_formatted": "01:02:00",
    "confidence_interval": {
      "lower_seconds": 3348,
      "upper_seconds": 4092,
      "lower_formatted": "00:55:48",
      "upper_formatted": "01:08:12"
    },
    "segments": [
      {
        "segment_km": 1,
        "distance_m": 1000,
        "avg_grade_percent": 2.5,
        "time_seconds": 360,
        "time_formatted": "00:06:00"
      }
    ],
    "statistics": {
      "total_distance_km": 10.5,
      "total_elevation_gain_m": 450,
      "avg_grade_percent": 1.8,
      "flat_pace_min_per_km": 5.2
    }
  },
  "similar_activities": [...]
}
```

## Database Schema

SQLite database (`instance/gpx_analyzer.db`):

### Tables

**gpx_files**
- `id`: Primary key
- `filename`: Original filename
- `upload_date`: Timestamp
- `file_data`: GPX XML content

**user_sessions**
- `id`: Primary key
- `strava_user_id`: Strava athlete ID
- `access_token`: OAuth token
- `refresh_token`: OAuth refresh token
- `expires_at`: Token expiration
- `created_at`: Session creation

## Scripts

### `scripts/cache_global_curve.py`

Pre-computes the global pace-grade curve from athlete data.

**Usage:**
```bash
python scripts/cache_global_curve.py
```

**Output:** `data_analysis/predictor/global_curve.json`

**Impact:**
- Startup time: 30-60s → <5s
- First prediction: 30-60s → 2-5s

## Testing

### Service Test
```bash
python test_prediction_service.py
```

Tests prediction service with sample data.

### Health Check
```bash
curl http://localhost:5000/api/health
```

## Troubleshooting

### Slow Startup (~30s)
Run cache script:
```bash
python scripts/cache_global_curve.py
```

### "ML model not found"
Train model:
```bash
cd ../data_analysis && python predictor/train.py
```

### "No global curve data available"
Either:
1. Run cache script (recommended)
2. Ensure `data_analysis/data/processed/` contains athlete data

### "STRAVA_CLIENT_ID not found"
Create `backend/.env` with credentials (see Prerequisites)

### CORS Errors
Check `config.py` CORS settings match frontend URL

## Directory Structure

```
backend/
├── api/
│   ├── gpx.py              # GPX endpoints
│   ├── strava.py           # Strava endpoints
│   └── prediction.py       # Prediction endpoints
├── services/
│   ├── prediction_service.py  # ML prediction logic
│   └── strava_service.py      # Strava API client
├── scripts/
│   └── cache_global_curve.py  # Cache generation
├── instance/
│   └── gpx_analyzer.db     # SQLite database
├── app.py                  # Flask entry point
├── config.py               # Configuration
├── database.py             # Database setup
└── requirements.txt        # Python dependencies
```

## Dependencies

Key packages:
- `flask` - Web framework
- `flask-cors` - CORS support
- `gpxpy` - GPX parsing
- `pandas` - Data manipulation
- `scikit-learn` - ML model (joblib)
- `requests` - Strava API client

Install:
```bash
pip install -r requirements.txt
```

## Performance

| Operation | With Cache | Without Cache |
|-----------|-----------|---------------|
| Server startup | <5s | 30-60s |
| First prediction | 3-8s | 30-60s |
| Subsequent predictions | 2-5s | 30-60s |
| Calibration | 2-5s | 2-5s |

**Recommendation:** Always run cache script before production use.
