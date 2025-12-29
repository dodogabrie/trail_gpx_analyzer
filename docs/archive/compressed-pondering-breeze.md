# Interactive Calibration Editor - Implementation Plan

## Overview

Add interactive calibration editing step to allow users to review and manually adjust their pace curve before predictions.

**User Flow:**
Select Activity → Calibrating → **Review/Edit Calibration** (NEW) → Predicting → Results

**Key Features:**
1. Visual curve editor with 7 draggable anchor points (grades: -30, -20, -10, 0, 10, 20, 30)
2. Flat pace manual adjustment input
3. Dual visualization: user curve vs global baseline
4. Map showing calibration activity route with pace overlay
5. Anchor quality diagnostics (sample counts)
6. Save to user profile for future predictions

---

## Implementation Phases

### Phase 1: Backend Foundation

#### 1.1 Database Migration
**Add to User model:**
```python
# /home/edoardo/Documents/RnD/gpx_analyzer/backend/models/user.py
saved_flat_pace = db.Column(db.Float, nullable=True)
saved_anchor_ratios = db.Column(db.JSON, nullable=True)
calibration_updated_at = db.Column(db.DateTime, nullable=True)
calibration_activity_id = db.Column(db.Integer, nullable=True)
```

**Migration script:**
```python
# /home/edoardo/Documents/RnD/gpx_analyzer/backend/migrate_user_calibration.py
ALTER TABLE users ADD COLUMN saved_flat_pace FLOAT;
ALTER TABLE users ADD COLUMN saved_anchor_ratios JSON;
ALTER TABLE users ADD COLUMN calibration_updated_at TIMESTAMP;
ALTER TABLE users ADD COLUMN calibration_activity_id INTEGER;
```

#### 1.2 Enhance PredictionService
**File:** `/home/edoardo/Documents/RnD/gpx_analyzer/backend/services/prediction_service.py`

**Add 3 new methods:**
1. `get_global_curve_for_frontend()` - Export global curve as list of dicts
2. `compute_anchor_quality(streams, anchor_ratios)` - Return sample counts per anchor
3. `prepare_calibration_activity_viz(streams)` - Downsample activity data for map (max 500 points)

**Modify existing:**
- `calibrate_from_activity()` - Return anchor_ratios in diagnostics dict

#### 1.3 API Endpoints
**File:** `/home/edoardo/Documents/RnD/gpx_analyzer/backend/api/prediction.py`

**Enhance `/api/prediction/calibrate` response:**
```json
{
  "flat_pace_min_per_km": 5.2,
  "anchor_ratios": {"-30": 0.45, "-20": 0.62, ...},
  "diagnostics": {
    "anchor_sample_counts": {"-30": 125, "-20": 340, ...}
  },
  "global_curve": [{grade: -40, median: 0.35, ...}, ...],
  "calibration_activity_streams": {
    "latlng": [[lat, lon], ...],
    "distance": [0, 50, ...],
    "pace_smooth": [4.8, 5.2, ...],
    "grade_smooth": [-2, 0, ...]
  }
}
```

**Create `/api/prediction/save-calibration` endpoint:**
```python
POST /api/prediction/save-calibration
{
  "flat_pace_min_per_km": 5.3,
  "anchor_ratios": {"-30": 0.47, ...},
  "calibration_activity_id": 12345678
}

# Validates ranges:
# - flat_pace: 0-20 min/km
# - ratios: 0.3-3.0
# - min 3 anchor ratios

# Saves to user.saved_flat_pace, user.saved_anchor_ratios, user.calibration_updated_at
```

**Modify `/api/prediction/predict`:**
- Accept anchor_ratios in request body
- Pass to prediction_service.predict_route_time()

---

### Phase 2: Frontend State

**File:** `/home/edoardo/Documents/RnD/gpx_analyzer/frontend/src/stores/prediction.js`

**Add state properties:**
```javascript
globalCurve: [],
calibrationActivityStreams: {},
editedFlatPace: null,
editedAnchorRatios: null
```

**Modify `calibrateFromActivity()` action:**
- Store global_curve, calibration_activity_streams from response
- Initialize editedFlatPace = flatPace
- Initialize editedAnchorRatios = anchor_ratios from response
- Set currentStep = 'edit-calibration' (instead of auto-predicting)

**Add `saveCalibration(editedData)` action:**
- POST to /save-calibration
- Update editedFlatPace, editedAnchorRatios in state

**Modify `predictRouteTime()` action:**
- Use editedFlatPace || flatPace
- Pass editedAnchorRatios in request body

---

### Phase 3: Calibration Editor Component

**File:** `/home/edoardo/Documents/RnD/gpx_analyzer/frontend/src/components/CalibrationEditor.vue` (NEW)

**Component Sections:**

1. **Header with User Warning**
   - "You are editing YOUR personal pace profile"
   - Clear messaging about impact

2. **Flat Pace Editor**
   - Number input: min=2.5, max=20, step=0.1
   - Real-time validation
   - "Reset" button to revert to original

3. **Interactive Curve Chart (ECharts)**
   - X-axis: Grade (-35 to +35%)
   - Y-axis: Pace (min/km), inverted (faster at top)
   - Series 1: Global baseline (gray dashed line)
   - Series 2: User curve (blue solid line with draggable anchor points)
   - 7 anchor points as circles
   - Drag implementation:
     - Track mousedown on anchor point
     - Update anchor ratio on mousemove
     - Clamp ratio to [0.3, 3.0]
   - Legend showing both curves

4. **Anchor Diagnostics Grid**
   - 7 columns (one per anchor)
   - Each shows: grade, sample count, quality label
   - Color coding:
     - Green (>500): Excellent
     - Yellow (200-500): Good
     - Orange (50-200): Fair
     - Red (<50): Low

5. **Calibration Activity Map (Optional for MVP)**
   - Reuse MapView component
   - Show route with pace overlay
   - Or skip for initial version

6. **Action Buttons**
   - "Save & Continue" → emit('save', editedData)
   - "Reset to Original" → revert all edits
   - "Skip" → emit('skip')

**Props:**
- flatPace, anchorRatios, globalCurve, diagnostics, calibrationActivityStreams

**Emits:**
- save(editedData)
- skip()

**State:**
- editableFlatPace (ref)
- editableAnchors (ref)
- isDragging, dragAnchorGrade (for chart interaction)

**Dependencies:**
- vue-echarts for interactive charting
- Tailwind CSS for styling

---

### Phase 4: Workflow Integration

**File:** `/home/edoardo/Documents/RnD/gpx_analyzer/frontend/src/views/Prediction.vue`

**Update steps array:**
```javascript
const steps = [
  { key: 'select-activity', label: '1. Select Activity' },
  { key: 'calibrating', label: '2. Calibrate' },
  { key: 'edit-calibration', label: '3. Review & Edit' },  // NEW
  { key: 'predicting', label: '4. Predict' },
  { key: 'results', label: '5. Results' }
]
```

**Add step content:**
```vue
<div v-else-if="predictionStore.currentStep === 'edit-calibration'">
  <CalibrationEditor
    :flat-pace="predictionStore.flatPace"
    :anchor-ratios="predictionStore.editedAnchorRatios"
    :global-curve="predictionStore.globalCurve"
    :diagnostics="predictionStore.calibrationDiagnostics"
    :calibration-activity-streams="predictionStore.calibrationActivityStreams"
    @save="onCalibrationSaved"
    @skip="onCalibrationSkipped"
  />
</div>
```

**Event handlers:**
```javascript
const onCalibrationSaved = async (editedData) => {
  await predictionStore.saveCalibration(editedData)
  predictionStore.currentStep = 'predicting'
  await predictionStore.predictRouteTime(gpxId.value)
}

const onCalibrationSkipped = async () => {
  predictionStore.currentStep = 'predicting'
  await predictionStore.predictRouteTime(gpxId.value)
}
```

---

### Phase 5: Polish & Edge Cases

**Validation:**
- Flat pace: 2.5-20 min/km
- Anchor ratios: 0.3-3.0
- Enforce monotonicity (optional): pace increases with grade

**Edge Cases:**
1. **Missing anchors:** Show only available, use global for missing
2. **Extreme edits:** Warn if >50% deviation from global
3. **Large activities:** Downsample to 500 points for map

**UI Polish:**
- Loading states during save
- Smooth transitions between steps
- Mobile responsive layout
- Accessibility (keyboard navigation, labels)

---

## Implementation Order

**Recommended sequence:**

1. **Backend Foundation** (2-3h)
   - Database migration
   - PredictionService enhancements
   - API endpoint modifications

2. **Frontend State** (1h)
   - Update prediction.js store

3. **Calibration Editor Component** (4-6h)
   - Layout and props setup
   - Flat pace editor
   - Interactive curve chart
   - Anchor diagnostics grid
   - Skip map for MVP

4. **Workflow Integration** (1-2h)
   - Update Prediction.vue
   - Add event handlers
   - Test end-to-end flow

5. **Polish** (2-3h)
   - Validation and error handling
   - UI refinements

**Total estimate: 10-15 hours**

---

## Critical Files

### Backend
1. `/home/edoardo/Documents/RnD/gpx_analyzer/backend/models/user.py` - Add calibration columns
2. `/home/edoardo/Documents/RnD/gpx_analyzer/backend/services/prediction_service.py` - Add 3 methods
3. `/home/edoardo/Documents/RnD/gpx_analyzer/backend/api/prediction.py` - Enhance endpoints

### Frontend
4. `/home/edoardo/Documents/RnD/gpx_analyzer/frontend/src/components/CalibrationEditor.vue` - NEW component
5. `/home/edoardo/Documents/RnD/gpx_analyzer/frontend/src/stores/prediction.js` - State management
6. `/home/edoardo/Documents/RnD/gpx_analyzer/frontend/src/views/Prediction.vue` - Workflow integration

### Predictor (minimal changes)
7. `/home/edoardo/Documents/RnD/gpx_analyzer/data_analysis/predictor/predictor.py` - Already has needed functions

---

## User Experience

**Step-by-step journey:**

1. User selects Strava activity
2. System calibrates (2-5s): computes flat pace, anchor ratios, fetches global curve
3. **NEW: Review & Edit screen appears**
   - Shows flat pace input
   - Interactive curve with 7 draggable points
   - Anchor quality diagnostics
   - Optional: calibration activity map
4. User can:
   - Adjust flat pace via input
   - Drag anchor points to modify curve
   - See real-time updates to curve
   - Review data quality
   - Click "Save & Continue" or "Skip"
5. System saves to profile (if user clicked Save)
6. Prediction runs with personalized curve
7. Results displayed

**Key UX principle:** User is aware they're editing their own capabilities, not the model's baseline.
