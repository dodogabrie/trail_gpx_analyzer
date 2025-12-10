# GPX Analyzer

Web application for GPX route analysis with ML-based time prediction and Strava integration.

## Overview

GPX Analyzer helps runners predict completion times for new routes using machine learning. The system:
- Analyzes GPX files with interactive maps and elevation profiles
- Integrates with Strava to calibrate predictions from past activities
- Uses gradient boosting ML model to predict segment-by-segment times
- Provides confidence intervals and similar activity recommendations

## Quick Start

### 1. Setup Backend
```bash
cd backend
source venv/bin/activate
python app.py
```

### 2. Setup Frontend
```bash
cd frontend
npm install
npm run dev
```

### 3. Train ML Model (if needed)
```bash
cd data_analysis
source venv/bin/activate
python predictor/train.py
```

### 4. Cache Global Curve (recommended)
```bash
cd backend
python scripts/cache_global_curve.py
```

Application runs on `http://localhost:5173` (frontend) with backend on `http://localhost:5000`

## Architecture

### Components

**[Backend](backend/)** - Flask REST API
- GPX file management
- Strava OAuth integration
- ML-based time prediction service
- Activity stream downloads
- See [backend/README.md](backend/README.md)

**[Frontend](frontend/)** - Vue 3 SPA
- GPX upload and visualization
- Interactive maps (Leaflet) and elevation profiles (ECharts)
- Strava activity selection
- Prediction workflow and results display
- See [frontend/README.md](frontend/README.md)

**[Scraper](scraper/)** - Data Collection
- Multi-user Strava data scraping
- Optimized API usage (85% reduction)
- Rate limiting (200 req/15min, 2000 req/day)
- Database storage with performance metrics
- See [scraper/README.md](scraper/README.md)

**[Data Analysis](data_analysis/)** - ML Training
- SI unit preprocessing
- Gradient boosting model training
- Global pace-grade curve generation
- Visualization and validation
- See [data_analysis/README.md](data_analysis/README.md)

### Data Flow

```
GPX Upload → Frontend → Backend API → Parse GPX
                ↓
        Strava OAuth → Token Storage
                ↓
Activity Selection → Calibration → Flat Pace Extraction
                ↓
   Route + Flat Pace → ML Model → Segment Predictions
                ↓
        Results Display ← Confidence Intervals
```

## Features

### GPX Analysis
- Upload and parse GPX files
- Interactive route visualization
- Elevation profile with distance markers
- Coordinated hover/selection between map and chart
- Segment statistics (distance, elevation gain/loss)

### Strava Integration
- OAuth 2.0 authorization
- Activity browsing and filtering
- Download activity streams (GPS, altitude, heart rate, etc.)
- Compare similar routes

### ML Time Prediction
- Activity-based calibration (extracts flat pace)
- Segment-by-segment prediction (50m segments)
- Confidence intervals (±10%)
- 1km segment breakdown with color-coded grades
- Similar activity recommendations
- Export results to .txt

### Data Collection
- Optimized Strava API usage (1 req/activity vs 7)
- Multi-user database with SQLite
- Performance metrics (VAM, pace, speed)
- Rate limiting and quota management
- Interactive monitoring dashboard

## Project Structure

```
gpx_analyzer/
├── backend/              # Flask REST API
│   ├── api/              # Endpoint blueprints
│   ├── services/         # Business logic (prediction, Strava)
│   ├── scripts/          # Utilities (cache generation)
│   └── README.md         # Backend documentation
│
├── frontend/             # Vue 3 web app
│   ├── src/
│   │   ├── components/   # Reusable Vue components
│   │   ├── views/        # Page components
│   │   ├── stores/       # Pinia state management
│   │   └── router/       # Vue Router config
│   └── README.md         # Frontend documentation
│
├── scraper/              # Strava data collection
│   ├── scraper.py        # CLI scraping tool
│   ├── monitor.py        # Monitoring dashboard
│   └── README.md         # Scraper documentation
│
├── data_analysis/        # ML model training
│   ├── preprocessing/    # Data cleaning
│   ├── predictor/        # Model training and prediction
│   ├── plot_scripts/     # Visualization
│   └── README.md         # Analysis documentation
│
├── src/                  # Legacy Dash app (deprecated)
├── lab/                  # Experimental code
└── data/                 # GPX files and databases
```

## Tech Stack

### Backend
- Python 3.12
- Flask + Flask-CORS
- SQLite
- scikit-learn (ML)
- pandas, numpy
- gpxpy (GPX parsing)

### Frontend
- Vue 3 + Vite
- Pinia (state)
- Vue Router
- Tailwind CSS
- Leaflet (maps)
- ECharts (charts)
- Axios (HTTP)

### ML/Analysis
- scikit-learn (Gradient Boosting)
- pandas, numpy
- matplotlib (plots)
- joblib (serialization)

## User Workflow

### 1. Upload GPX
1. Navigate to home page
2. Upload .gpx file
3. View in analysis page with map and elevation profile

### 2. Connect Strava
1. Click "Connect Strava" in navbar
2. Authorize on Strava OAuth page
3. Token stored for future use

### 3. Predict Route Time
1. From analysis page, click "Predict Time"
2. Select calibration activity (recommended activities shown)
3. Wait for calibration (~2-5s)
4. Wait for prediction (~2-5s with cache)
5. View results:
   - Total time with confidence interval
   - Segment breakdown (1km chunks)
   - Similar past activities
6. Export or recalibrate

## Performance

| Operation | With Cache | Without Cache |
|-----------|-----------|---------------|
| Backend startup | <5s | 30-60s |
| First prediction | 3-8s | 30-60s |
| Subsequent predictions | 2-5s | 30-60s |
| Calibration | 2-5s | 2-5s |

**Recommendation:** Run `backend/scripts/cache_global_curve.py` before first use.

## API Endpoints

### GPX Management
- `POST /api/gpx/upload` - Upload GPX file
- `GET /api/gpx/list` - List uploaded files
- `GET /api/gpx/:id` - Get GPX data
- `DELETE /api/gpx/:id` - Delete file

### Strava Integration
- `GET /api/strava/auth-url` - Get OAuth URL
- `GET /api/strava/auth-callback` - OAuth callback
- `GET /api/strava/activities` - List user activities
- `GET /api/strava/activity/:id/streams` - Download streams

### Prediction
- `GET /api/prediction/calibration-activities` - List activities for calibration
- `POST /api/prediction/calibrate` - Compute flat pace
- `POST /api/prediction/predict` - Generate prediction

## Environment Setup

### Backend `.env`
```bash
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

### Prerequisites
- Python 3.12+
- Node.js 18+
- npm/yarn
- Strava developer account (for OAuth)

## Development

### Backend Development
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### ML Model Training
```bash
cd data_analysis
source venv/bin/activate
pip install -r requirements.txt
python predictor/train.py
```

### Data Collection
```bash
cd scraper
source venv/bin/activate
python scraper.py scrape --sport Run --days 30 --download-streams
```

## Troubleshooting

### Slow Backend Startup
Generate global curve cache:
```bash
cd backend && python scripts/cache_global_curve.py
```

### ML Model Not Found
Train model:
```bash
cd data_analysis && python predictor/train.py
```

### Strava Auth Fails
1. Check `.env` has correct CLIENT_ID/SECRET
2. Verify redirect URI in Strava app settings
3. Check backend logs

### CORS Errors
Ensure `backend/config.py` allows frontend origin:
```python
CORS(app, origins=['http://localhost:5173'])
```

### API Connection Failed
Check backend is running:
```bash
curl http://localhost:5000/api/health
```

## Testing

### Backend Service Test
```bash
cd backend && python test_prediction_service.py
```

### Scraper Tests
```bash
pytest tests/test_rate_limiter.py
pytest tests/test_strava_api.py
pytest tests/test_database.py
```

## Documentation

Detailed documentation for each component:
- **[Backend Documentation](backend/README.md)** - API endpoints, services, database
- **[Frontend Documentation](frontend/README.md)** - Components, routing, state management
- **[Scraper Documentation](scraper/README.md)** - Data collection, rate limiting, monitoring
- **[Data Analysis Documentation](data_analysis/README.md)** - ML model, preprocessing, prediction

## ML Model Details

**Algorithm:** Gradient Boosting Regressor

**Features (per 50m segment):**
- Grade mean (%)
- Grade standard deviation
- Cumulative distance (fatigue proxy)

**Training Data:**
- 239 activities from 21 athletes
- Routes 5-50km with varied elevation

**Performance:**
- MAE: ~0.3 min/km
- Confidence interval: ±10%
- Best for running activities 5-50km

## Data Collection Stats

**API Optimization:**
- Before: 7 requests per activity
- After: 1 request per activity
- Reduction: 85%

**Daily Capacity:**
- Before: ~285 activities
- After: ~1900 activities
- Improvement: 6.6x

## Known Limitations

1. **Single OAuth Token** - Uses one Strava account
2. **Running Only** - Model trained on running data
3. **Conservative CI** - ±10% confidence interval (can be refined)
4. **No Real-Time Updates** - Manual data collection
5. **SQLite Database** - Not suitable for high concurrency

## Future Enhancements

**Phase 2: Data Collection**
- Multi-user data collection (public segments/clubs)
- Automated daily scraping
- GPS smoothing and validation

**Phase 3: Advanced ML**
- Fatigue modeling (time-based)
- Weather features (temperature, humidity)
- Terrain classification (trail vs road)
- User clustering by performance

**Phase 4: Deployment**
- PostgreSQL migration
- Redis caching
- Docker containers
- Production deployment

**Phase 5: Features**
- Race strategy planning
- Training plan integration
- Social features (share predictions)
- Mobile app

## Contributing

1. Fork repository
2. Create feature branch
3. Follow code style (Python: Google docstrings, JS: ESLint)
4. Add tests for new features
5. Submit pull request

## License

MIT License (add LICENSE file if needed)

## Authors

Developed as R&D project for GPX route analysis and time prediction.

## Support

For issues or questions:
- Check component-specific READMEs
- Review troubleshooting sections
- Check backend/frontend logs
