# Frontend - Vue 3 Web Application

Vue 3 + Vite application for GPX analysis, Strava integration, and route time prediction.

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Application runs on `http://localhost:5173`

## Tech Stack

- **Vue 3** - Progressive JavaScript framework
- **Vite** - Build tool and dev server
- **Vue Router** - Client-side routing
- **Pinia** - State management
- **Tailwind CSS** - Utility-first CSS
- **Leaflet** - Interactive maps (via vue-leaflet)
- **ECharts** - Data visualization (elevation profiles)
- **Axios** - HTTP client

## Features

### GPX Analysis
- Upload and parse GPX files
- Interactive route map (Leaflet)
- Elevation profile with distance markers
- Coordinated hover/selection between map and chart
- Segment statistics (distance, D+, D-)

### Strava Integration
- OAuth 2.0 authorization flow
- Activity browsing and filtering
- Download similar activities
- Compare routes and performance

### Route Time Prediction
- ML-based time predictions
- Activity-based calibration (flat pace extraction)
- Segment-by-segment breakdown
- Confidence intervals
- Similar activity recommendations
- Export results to .txt

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ActivitySelector.vue      # Strava activity picker
│   │   ├── PredictionResults.vue     # Prediction display
│   │   └── ...
│   ├── views/
│   │   ├── Home.vue                  # GPX upload and list
│   │   ├── Analysis.vue              # GPX visualization
│   │   ├── Prediction.vue            # Prediction workflow
│   │   └── StravaAuth.vue            # OAuth callback
│   ├── stores/
│   │   ├── gpx.js                    # GPX state
│   │   ├── strava.js                 # Strava auth state
│   │   └── prediction.js             # Prediction state
│   ├── router/
│   │   └── index.js                  # Route configuration
│   ├── services/
│   │   └── api.js                    # Axios HTTP client
│   ├── App.vue                       # Root component
│   └── main.js                       # App entry point
├── public/                            # Static assets
├── index.html                         # HTML template
├── vite.config.js                     # Vite configuration
├── tailwind.config.js                 # Tailwind configuration
└── package.json                       # Dependencies
```

## User Workflows

### 1. Upload and Analyze GPX

1. **Home** (`/`) - Upload GPX file
2. **Analysis** (`/analysis/:id`) - View map and elevation
3. Interact:
   - Hover on elevation chart → highlight point on map
   - Select range on elevation chart → show segment stats

### 2. Connect Strava

1. Click "Connect Strava" in navbar
2. Authorize on Strava OAuth page
3. Redirect to `/strava-auth` callback
4. Token stored in Pinia store

### 3. Predict Route Time

1. **Analysis view** - Click "Predict Time" (green button)
2. **Prediction view** (`/prediction/:gpxId`) - Select calibration activity
3. Recommended activities shown first (similar distance)
4. Click "Select" on any Run activity
5. Wait for calibration (~2-5s)
6. Wait for prediction (~2-5s)
7. View results:
   - Total time with confidence interval
   - 1km segment breakdown with grades
   - Similar past activities
8. Export or recalibrate

## State Management (Pinia)

### `stores/gpx.js`

**State:**
- `gpxFiles` - Uploaded GPX files
- `currentGpx` - Currently displayed GPX

**Actions:**
- `uploadGpx(file)` - Upload and parse GPX
- `fetchGpxList()` - Load all GPX files
- `fetchGpxData(id)` - Get specific GPX data
- `deleteGpx(id)` - Remove GPX file

### `stores/strava.js`

**State:**
- `isConnected` - Strava authorization status
- `accessToken` - OAuth token
- `user` - Athlete profile

**Actions:**
- `getAuthUrl()` - Get OAuth URL
- `handleAuthCallback(code)` - Exchange code for token
- `checkConnection()` - Verify token validity
- `disconnect()` - Clear tokens

### `stores/prediction.js`

**State:**
- `calibrationActivities` - List of activities for calibration
- `selectedActivity` - Chosen calibration activity
- `flatPace` - Calibrated flat pace (min/km)
- `prediction` - Prediction results
- `isCalibrating`, `isPredicting` - Loading states

**Actions:**
- `fetchCalibrationActivities(gpxId)` - Load activities
- `calibrate(activityId)` - Compute flat pace
- `predict(gpxId)` - Generate prediction
- `reset()` - Clear state

## Key Components

### `ActivitySelector.vue`

Activity picker with recommendations:
- Shows Run activities only
- Marks similar activities as "Recommended"
- Displays distance, date, stream availability
- Search and filter capabilities

**Props:**
- `activities` - Array of activities
- `loading` - Loading state

**Events:**
- `@select` - Activity selected

### `PredictionResults.vue`

Prediction display:
- Total time with formatted HH:MM:SS
- Confidence interval (±10%)
- Segment table (1km chunks)
  - Color-coded grades (red=steep, green=down, gray=flat)
  - Time per segment
- Similar activities list
- Calibration info
- Export to .txt button
- Recalibrate button

**Props:**
- `prediction` - Prediction object
- `activity` - Calibration activity
- `flatPace` - Flat pace value

**Events:**
- `@recalibrate` - User wants to recalibrate
- `@export` - Export results

## Routing

```javascript
{
  path: '/',
  name: 'Home',
  component: Home
},
{
  path: '/analysis/:id',
  name: 'Analysis',
  component: Analysis
},
{
  path: '/prediction/:gpxId',
  name: 'Prediction',
  component: Prediction
},
{
  path: '/strava-auth',
  name: 'StravaAuth',
  component: StravaAuth
}
```

## API Integration

### Base URL
Configured in `src/services/api.js`:
```javascript
const api = axios.create({
  baseURL: 'http://localhost:5000/api'
})
```

### Endpoints Used

**GPX:**
- `POST /gpx/upload` - Upload GPX file
- `GET /gpx/list` - List all GPX files
- `GET /gpx/:id` - Get GPX data
- `DELETE /gpx/:id` - Delete GPX file

**Strava:**
- `GET /strava/auth-url` - Get authorization URL
- `GET /strava/auth-callback?code=X` - OAuth callback
- `GET /strava/activities` - List activities
- `GET /strava/activity/:id/streams` - Download streams

**Prediction:**
- `GET /prediction/calibration-activities?gpx_id=X` - List activities
- `POST /prediction/calibrate` - Calibrate flat pace
- `POST /prediction/predict` - Generate prediction

## Development

### Install Dependencies
```bash
npm install
```

### Run Dev Server
```bash
npm run dev
```

Hot reload enabled at `http://localhost:5173`

### Build for Production
```bash
npm run build
```

Output in `dist/`

### Preview Production Build
```bash
npm run preview
```

### Lint Code
```bash
npm run lint
```

## Environment Variables

Create `frontend/.env` (if needed):
```bash
VITE_API_URL=http://localhost:5000/api
```

Access in code:
```javascript
import.meta.env.VITE_API_URL
```

## Styling

### Tailwind CSS

Utility-first CSS framework:
```vue
<div class="bg-blue-500 text-white p-4 rounded-lg">
  Content
</div>
```

Configure in `tailwind.config.js`

### Custom Styles

Global styles in `src/assets/main.css`

Component-scoped styles:
```vue
<style scoped>
.custom-class {
  /* styles */
}
</style>
```

## Map Integration (Leaflet)

### Basic Usage
```vue
<template>
  <l-map :zoom="13" :center="[lat, lng]">
    <l-tile-layer :url="tileUrl" />
    <l-polyline :lat-lngs="routeCoords" :color="'blue'" />
    <l-marker :lat-lng="currentPoint" />
  </l-map>
</template>

<script setup>
import { LMap, LTileLayer, LPolyline, LMarker } from '@vue-leaflet/vue-leaflet'
</script>
```

Tile provider: OpenStreetMap

### Interactive Features
- Zoom and pan
- Hover highlighting
- Range selection overlay
- Auto-fit bounds to route

## Chart Integration (ECharts)

### Elevation Profile
```vue
<template>
  <v-chart :option="chartOption" @mousemove="handleHover" />
</template>

<script setup>
import VChart from 'vue-echarts'

const chartOption = {
  xAxis: { type: 'value', name: 'Distance (km)' },
  yAxis: { type: 'value', name: 'Elevation (m)' },
  series: [{
    type: 'line',
    data: elevationData,
    areaStyle: {}
  }]
}
</script>
```

Features:
- Area chart for elevation
- Distance on X-axis, elevation on Y-axis
- Hover tooltip
- Range selection (brush tool)

## Troubleshooting

### CORS Errors
Ensure backend CORS allows frontend origin:
```python
# backend/config.py
CORS(app, origins=['http://localhost:5173'])
```

### API Connection Failed
Check backend is running:
```bash
curl http://localhost:5000/api/health
```

### Strava Auth Fails
1. Check CLIENT_ID/SECRET in backend `.env`
2. Verify redirect URI matches Strava app settings
3. Check backend logs for errors

### Prediction Errors
1. Ensure ML model exists: `data_analysis/predictor/residual_model.joblib`
2. Check backend cache: `python backend/scripts/cache_global_curve.py`
3. Verify Strava token is valid (reconnect if needed)

### Map Not Displaying
1. Check Leaflet CSS is loaded
2. Verify GPX data has valid coordinates
3. Check browser console for errors

## Dependencies

Key packages in `package.json`:
- `vue@^3.x` - Vue framework
- `vue-router@^4.x` - Routing
- `pinia@^2.x` - State management
- `axios@^1.x` - HTTP client
- `@vue-leaflet/vue-leaflet` - Map components
- `vue-echarts` - Chart components
- `tailwindcss@^3.x` - CSS framework
- `vite@^6.x` - Build tool

## IDE Support

Recommended setup:
- **VS Code** + **Volar** extension
- Disable Vetur if installed
- Use `<script setup>` syntax

## Browser Support

Supports modern browsers:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

No IE11 support (Vite requirement)
