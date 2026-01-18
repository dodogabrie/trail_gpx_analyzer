# Task Plan: Investigate UTMB Prediction Model Issues

## Goal
Identify why the prediction model gives unrealistic times for ultra-distance races (19h UTMB prediction) and determine how fatigue/training are modeled.

## Phases
- [x] Phase 1: Explore prediction service and model architecture
- [x] Phase 2: Analyze fatigue modeling implementation
- [x] Phase 3: Check training/calibration factors
- [x] Phase 4: Document findings and recommendations

## Key Questions (ANSWERED)
1. How does the model calculate pace predictions?
   -> Physics model with Minetti cost function + terrain/fatigue factors
2. Is fatigue modeled as distance/time increases?
   -> YES but CAPPED at 42km normalization, and uses SATURATING exponential
3. How is user calibration/training level incorporated?
   -> Through v_flat, k_up, k_tech from activity calibration + ML residuals
4. What features does the GBM model use?
   -> Grade, cumulative distance, elevation gain rate, grade change, etc.

## ROOT CAUSES IDENTIFIED

1. **42km Normalization Cap** (pipeline.py:79)
   - Fatigue normalized by min(distance, 42km)
   - For 170km UTMB, this severely underestimates fatigue

2. **Saturating Exponential Model** (performance_tracker.py)
   - Fatigue model: y(d) = 1 + a*(1-exp(-d/tau))
   - Plateaus after ~50km regardless of actual distance

3. **50km Fatigue Data Cap** (performance_tracker.py:44)
   - Fatigue curves only calculated up to 50km
   - No training data for ultra-distance fatigue

## Status
**COMPLETE** - Findings documented in notes.md

---

# NEW DIRECTION: Annotation-Based Predictions

## Strategy Focus
User wants to add annotations (aid stops, pace modifiers) that affect time accumulation.

Key insight: **Think in TIME, not distance** - altitude makes distance meaningless.

## User Decisions (Confirmed)
- **Session-only** annotations (Pinia store, no backend persistence)
- **Fatigue PAUSES** during stops (no reset, no accumulation)
- **Auto-import waypoints** - detect from GPX <wpt> elements

## Architecture Decision
**Frontend-first approach**:
- Backend returns BASE prediction (expensive ML call)
- Frontend adds stop durations (instant, no re-prediction)
- `totalTimeWithStops` computed getter in Pinia

## Key Insight: Fatigue is Distance-Based
Current model: `fatigue = f(distance, grade)` NOT `f(time)`

**Stops don't affect fatigue calculation!**
- Running km 0-50 in 4h or 6h = same fatigue at km 50
- Backend doesn't need stop info for fatigue
- Frontend-only approach works perfectly

## Implementation Phases

### Phase 1: Core (MVP)
- [ ] Add `duration_minutes` field to AnnotationModal
- [ ] Add `totalTimeWithStops` getter to prediction store
- [ ] Update PredictionResults to show base + stops breakdown
- [ ] Update timeline calculation with stop offsets

### Phase 2: Timeline UX
- [ ] Show arrival/departure times at each stop
- [ ] Cumulative time table view
- [ ] Stop markers on elevation profile

### Phase 3: Auto-Import
- [ ] Parse GPX <wpt> waypoints
- [ ] "Import waypoints as aid stations" UI
- [ ] Distance-matching for waypoint locations

See `notes.md` for detailed implementation strategy.
