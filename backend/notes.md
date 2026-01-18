# Notes: UTMB Prediction Model Analysis

## Previous Analysis Summary
See `task_plan.md` for root causes:
1. 42km fatigue normalization cap
2. Saturating exponential fatigue model
3. 50km max training data cap

---

# NEW: Annotation-Based Prediction Strategy

## Current State (from code analysis)

### Frontend (`PredictionResults.vue`, `AnnotationModal.vue`, `prediction.js`)
- Annotations stored in Pinia store (session-based) - **ALREADY WORKS**
- Types: `aid_station`, `generic` - **location markers only**
- Can save to backend via `/prediction/{id}/annotations` - **optional persistence**
- `calculateTimeToDistance()` interpolates arrival time - **read-only**
- **NO mechanism to add stop duration to total time**

### What's Missing
1. Annotation `duration_minutes` field
2. Frontend recalculation of total time including stops
3. Auto-import of GPX waypoints

---

## Strategy: Session-Based Time Annotations

### User Decisions
1. **Session-only** - annotations live in Pinia store, not persisted to backend
2. **Fatigue PAUSES** during stops (no reset, no accumulation)
3. **Auto-import waypoints** - frontend should detect and suggest

---

## Critical Insight: Fatigue is Distance-Based

### Current Fatigue Model (pipeline.py)
```python
# Fatigue accumulates based on DISTANCE, not TIME
load_gain = calculate_fatigue_contribution(grade, segment_len)
accumulated_load += load_gain
```

**Fatigue = f(distance_run, grade)** - NOT f(time_elapsed)

### Implication for Stops
Whether you run km 0-50 in 4h or 6h (with stops), the fatigue at km 50 is **IDENTICAL**.
Stops don't change how much downhill you've run.

**Therefore: backend doesn't need to know about stops for fatigue!**
The distance-based model already "pauses" fatigue during stops implicitly.

### Summary
| What | Where | Why |
|------|-------|-----|
| Fatigue calculation | Backend | Distance-based, unaffected by stops |
| Stop durations | Frontend only | Just adds time, no model re-run needed |
| Total time display | Frontend | base_time + sum(stop_durations) |

---

## Annotation Types (Simplified)

### 1. Time Stop (primary use case)
```javascript
{
  id: uuid,
  type: 'aid_station',          // or 'rest_stop', 'crew_stop'
  distance_km: 45.2,
  label: 'Courmayeur',
  duration_minutes: 10,         // NEW FIELD
  effort_scaling: true          // optional: scale duration by effort
}
```

### 2. Pace Modifier (future)
```javascript
{
  type: 'pace_modifier',
  start_km: 120,
  end_km: 140,
  factor: 1.2,                  // 20% slower
  reason: 'Night section'
}
```

**Fatigue reset REMOVED** - user prefers fatigue to just pause, not reset

---

## Implementation Strategy: Frontend-First

Since annotations are session-based, **ALL time recalculation happens in frontend**.
Backend prediction returns base time; frontend adds stop durations.

### Architecture

```
[Backend]                          [Frontend]

/hybrid/predict                    Pinia Store
    |                                  |
    v                                  v
base_prediction ─────────────────> prediction.value
    - total_time_seconds               |
    - segments[]                       + annotations[]
    - confidence_interval              |
                                       v
                              computedTotalTime (getter)
                                  = base_time + sum(stop_durations)
```

### Why Frontend-Only?
1. Session-based = no backend persistence needed
2. Instant feedback as user adds/edits stops
3. Backend prediction is expensive (ML model) - don't re-run for stop changes
4. Annotations are presentation layer, not model layer

---

## Frontend Changes Required

### 1. AnnotationModal.vue - Add Duration Field
```vue
<!-- NEW: Duration input for aid stations -->
<div v-if="annotationType === 'aid_station'" class="mb-3">
  <label>Stop Duration (minutes)</label>
  <input v-model.number="durationMinutes" type="number" min="1" max="120" />
</div>
```

### 2. prediction.js Store - Add Computed Total
```javascript
getters: {
  // NEW: Total time including all stop durations
  totalTimeWithStops: (state) => {
    if (!state.prediction) return null

    const baseSeconds = state.prediction.total_time_seconds
    const stopSeconds = state.annotations
      .filter(a => a.duration_minutes)
      .reduce((sum, a) => sum + a.duration_minutes * 60, 0)

    return baseSeconds + stopSeconds
  },

  // NEW: Format total time
  totalTimeWithStopsFormatted: (state) => {
    const total = state.totalTimeWithStops
    if (!total) return null
    const h = Math.floor(total / 3600)
    const m = Math.floor((total % 3600) / 60)
    const s = Math.floor(total % 60)
    return `${h}:${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`
  }
}
```

### 3. PredictionResults.vue - Show Adjusted Time
```vue
<!-- Show BOTH base prediction and adjusted total -->
<div class="text-5xl font-bold">
  {{ predictionStore.totalTimeWithStopsFormatted || prediction.total_time_formatted }}
</div>

<!-- Breakdown if stops exist -->
<div v-if="totalStopMinutes > 0" class="text-sm text-slate-500">
  Base: {{ prediction.total_time_formatted }}
  + {{ totalStopMinutes }} min stops
</div>
```

### 4. PredictionResults.vue - Annotation-Aware Timeline

The `calculateTimeToDistance()` function needs to account for previous stops.
This is used by the modal to show "Predicted arrival time".

```javascript
// CURRENT (broken - ignores stops)
const calculateTimeToDistance = (targetKm) => {
  return interpolateFromSegments(targetKm)  // base running time only
}

// FIXED (includes prior stops)
const calculateTimeToDistance = (targetKm) => {
  // 1. Base running time from segment interpolation
  const baseTimeSeconds = interpolateFromSegmentsSeconds(targetKm)

  // 2. Sum ALL stop durations BEFORE this point
  const priorStopSeconds = predictionStore.annotations
    .filter(a => a.distance_km < targetKm && a.duration_minutes)
    .reduce((sum, a) => sum + a.duration_minutes * 60, 0)

  return formatSecondsToHms(baseTimeSeconds + priorStopSeconds)
}
```

### Flow Example
```
User clicks km 45 on elevation profile
    |
    v
calculateTimeToDistance(45)
    |
    +-- interpolateFromSegments(45) = 12,600s (3:30:00 base running)
    |
    +-- sum stops before km 45:
        - km 15: +10 min (600s)
        - km 30: +8 min (480s)
        = 1,080s
    |
    v
Total: 13,680s -> Modal shows "Predicted arrival: 3:48:00"
```

### Why This Works
- `predictionStore.annotations` is reactive (Pinia)
- Adding a stop at km 15 automatically updates arrival times for all points > km 15
- No backend call needed - instant recalculation

---

## Auto-Import GPX Waypoints

### Detection Logic
```javascript
// In gpx.js store or prediction.js
const detectWaypoints = (gpxData) => {
  // GPX files can contain <wpt> elements (waypoints)
  // Parse and convert to annotation suggestions

  return gpxData.waypoints?.map(wpt => ({
    type: 'aid_station',
    distance_km: findNearestDistance(wpt.lat, wpt.lon),
    label: wpt.name || 'Waypoint',
    duration_minutes: null,  // User must fill in
    suggested: true          // Mark as auto-detected
  }))
}
```

### UI Flow
1. GPX loaded -> check for waypoints
2. If found, show banner: "Found 7 waypoints. Import as aid stations?"
3. User clicks "Import" -> annotations added with `suggested: true`
4. User can edit/delete/add duration to each

---

## Time Display Strategy

### Main Display
```
PREDICTED FINISH TIME
      24:35:00           <- includes stops

Base running time: 22:55:00
Aid station stops: 1:40:00 (7 stops)
```

### Timeline View (cumulative with stops)
| Point | Distance | Running | +Stop | Cumulative |
|-------|----------|---------|-------|------------|
| Start | 0 km | 0:00 | - | 0:00 |
| Aid 1 | 15 km | 2:15 | +10m | 2:25 |
| Aid 2 | 42 km | 5:30 | +15m | 5:45 |
| ... | | | | |
| Finish | 170 km | 22:55 | - | 24:35 |

---

## Implementation Priority (Revised)

### Phase 1: Core Functionality
1. Add `duration_minutes` to AnnotationModal
2. Add `totalTimeWithStops` getter to store
3. Update PredictionResults to show adjusted time
4. Update `calculateTimeToDistance` with stop offsets

### Phase 2: Timeline Improvements
5. Show stop markers on elevation profile
6. Display arrival/departure times at each stop
7. Cumulative time table view

### Phase 3: Auto-Import
8. Parse GPX waypoints in gpx store
9. "Import waypoints" UI flow
10. Waypoint-to-distance matching algorithm

### Phase 4: Future Enhancements
11. Effort-based stop scaling
12. Pace modifier sections
13. Export to Garmin/watch with stops
