# Model Explainability

Visualization tools to understand how the ML prediction model works.

## Overview

This folder contains scripts to visualize and explain the route time prediction model's behavior:

1. **Pace Evolution at Constant Grade** - Shows fatigue/distance effects
2. **Athlete Calibration Curves** - Shows personalization from global to athlete-specific curves

## Prerequisites

```bash
# Ensure model is trained
cd data_analysis
source venv/bin/activate
python predictor/train.py

# Ensure data is preprocessed
python preprocessing/convert_to_si.py
```

## Scripts

### 1. Pace Evolution at Grade

**File:** `pace_evolution_at_grade.py`

**Purpose:** Visualize how pace changes over distance at constant grade.

Shows the fatigue/cumulative distance effect embedded in the ML model by predicting pace at a fixed grade (e.g., 10%) as distance increases from 0 to 40km.

**Usage:**
```bash
cd tests/explainability
python pace_evolution_at_grade.py
```

**Output:**
- `plots/pace_evolution_grade_0pct.png` - Flat terrain (0%)
- `plots/pace_evolution_grade_+5pct.png` - Moderate uphill (5%)
- `plots/pace_evolution_grade_+10pct.png` - Steep uphill (10%)
- `plots/pace_evolution_grade_+15pct.png` - Very steep uphill (15%)

**What It Shows:**
- **Baseline pace** (dashed gray): Pure global curve without fatigue
- **ML-corrected pace** (blue): Model prediction including distance/fatigue effects
- **Residual multiplier** (bottom plot): Correction factor applied by ML model

**Interpretation:**
- Multiplier > 1.0: Model predicts slower than baseline (fatigue effect)
- Multiplier < 1.0: Model predicts faster than baseline
- Pace increase over distance: Quantifies fatigue at specific grade

**Example Output:**
```
Processing grade +10%...
  Initial pace: 6.50 min/km
  Final pace: 6.82 min/km
  Increase: +0.32 min/km
```

This shows that at 10% grade, the model predicts a 0.32 min/km pace increase from 0km to 40km due to fatigue.

### 2. Athlete Calibration Comparison

**File:** `athlete_curve_comparison.py`

**Purpose:** Visualize how the global curve is personalized for individual athletes.

Shows:
- Global curve (median across all athletes)
- Individual athlete's raw data points
- Personalized curve fitted to athlete's anchor points
- Anchor points used for calibration

**Usage:**
```bash
cd tests/explainability
python athlete_curve_comparison.py
```

**Output:**
- `plots/athlete_calibration_{id}.png` - Detailed calibration for one athlete
- `plots/athletes_comparison.png` - Comparison of multiple athletes

**What It Shows:**
- **Gray dashed line:** Global average pace-grade curve
- **Gray shaded area:** Inter-quartile range (25-75%) across athletes
- **Blue line:** Personalized curve for specific athlete
- **Light blue dots:** Athlete's actual pace measurements (sampled 5%)
- **Red stars:** Anchor points used for calibration

**Interpretation:**
- Closer to global curve = athlete performs similar to average
- Steeper personalized curve = more affected by grade changes
- Flatter personalized curve = better at handling hills
- Anchor points show where calibration occurred

**Example Output:**
```
Processing athlete 12345678...
Found 7 anchor points: [-30, -20, -10, 0, 10, 20, 30]
Flat Pace: 5.20 min/km
```

## Understanding the Model

### Global Curve

The **global curve** represents the average pace-grade relationship across all athletes:
- Built from 239 activities from 21 athletes
- Normalized by each athlete's flat pace
- Binned by grade (1% bins) and aggregated (median + IQR)
- Smoothed with 3-bin rolling median

**Formula:**
```
pace_ratio = pace / flat_pace
global_curve(grade) = median(pace_ratio across all athletes)
```

### Personalization

**Anchor-based calibration:**
1. User selects a calibration activity
2. System extracts pace at anchor grades: [-30, -20, -10, 0, 10, 20, 30]%
3. Computes user's pace ratios at anchors (using ±2% window)
4. Warps global curve to match user's anchors via interpolation

**Formula:**
```
multiplier(grade) = user_ratio(anchor) / global_ratio(anchor)
personalized_ratio(grade) = global_ratio(grade) * multiplier(grade)
```

### ML Residual Correction

**Gradient Boosting Model** learns corrections to the curve-based prediction:

**Features (10 total):**
- `grade_mean`: Average grade in segment
- `grade_std`: Grade variability
- `abs_grade`: Absolute grade value
- `cumulative_distance_km`: Distance so far (fatigue proxy)
- `prev_pace_ratio`: Previous segment's pace ratio (momentum)
- `grade_change`: Change in grade from previous segment
- `cum_elevation_gain_m`: Total elevation climbed
- `elevation_gain_rate`: Elevation gain per km
- `rolling_avg_grade_500m`: Recent grade context
- `distance_remaining_km`: Distance left (pacing strategy)

**Target:**
```
residual_multiplier = actual_pace_ratio / baseline_pace_ratio
```

**Prediction:**
```
final_pace = flat_pace * personalized_ratio(grade) * residual_multiplier
```

## Key Insights from Visualizations

### 1. Fatigue Effect (from pace_evolution_at_grade.py)

**Findings:**
- At 0% (flat): Minimal pace increase (~1-2%)
- At 5% (moderate): ~3-5% pace increase over 40km
- At 10% (steep): ~5-8% pace increase over 40km
- At 15% (very steep): ~8-12% pace increase over 40km

**Implication:** Model accounts for cumulative fatigue, especially on hills.

### 2. Athlete Variance (from athlete_curve_comparison.py)

**Findings:**
- Wide variance at steep grades (±30%)
- Narrow variance at flat grades (±10%)
- Some athletes excel at downhills (ratio < 1.0)
- Some struggle more on uphills (steeper curve)

**Implication:** Personalization is crucial for accurate predictions.

### 3. Model Corrections (from residual multiplier plots)

**Typical patterns:**
- Early distance: multiplier ~0.95-1.00 (fresh, slightly faster)
- Mid distance: multiplier ~1.00-1.05 (settling in)
- Late distance: multiplier ~1.05-1.15 (fatigue setting in)

**Implication:** ML model captures non-linear fatigue that curves alone miss.

## Use Cases

### Model Validation

Check if model behavior makes physiological sense:
- Pace should increase with distance (fatigue)
- Steeper grades should have higher pace
- Personalization should reduce variance

### Feature Engineering

Identify which features drive predictions:
- High correlation between distance and residual multiplier
- Grade change affects pace transitions
- Elevation gain rate impacts fatigue

### User Communication

Explain predictions to users:
- "Your pace will slow by X min/km due to fatigue"
- "You handle hills Y% better/worse than average"
- "This route will feel harder after Z km"

## Extending Explainability

### Additional Visualizations

**Suggested:**
1. Feature importance plot (from model.feature_importances_)
2. Partial dependence plots (scikit-learn PDPbox)
3. SHAP values (for individual predictions)
4. Prediction error analysis by grade/distance

**Example:**
```python
from sklearn.inspection import PartialDependenceDisplay

PartialDependenceDisplay.from_estimator(
    model,
    X_train,
    ['cumulative_distance_km', 'grade_mean']
)
```

### Interactive Dashboards

Use Streamlit/Dash to create interactive explainability:
- Adjust flat pace → see curve shift
- Adjust distance → see fatigue effect
- Compare multiple athletes side-by-side

## Troubleshooting

### No plots generated

Check:
```bash
# Model exists
ls data_analysis/predictor/residual_model.joblib

# Data exists
ls data_analysis/data/processed/
```

### Empty plots

Ensure:
- At least 50 activities in processed data
- Activities have stream data (not just metadata)
- Athletes have varied grade profiles

### Import errors

Add predictor to path:
```python
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
predictor_path = project_root / "data_analysis" / "predictor"
sys.path.insert(0, str(predictor_path))
```

## Dependencies

All scripts use standard data analysis stack:
- `matplotlib` - Plotting
- `numpy` - Numerical operations
- `pandas` - Data manipulation
- `joblib` - Model loading
- `scikit-learn` - ML model

Installed in `data_analysis/venv/`:
```bash
cd data_analysis
source venv/bin/activate
pip install -r requirements.txt
```

## Output Directory

All plots saved to `tests/explainability/plots/`:
```
plots/
├── pace_evolution_grade_0pct.png
├── pace_evolution_grade_+5pct.png
├── pace_evolution_grade_+10pct.png
├── pace_evolution_grade_+15pct.png
├── athlete_calibration_12345678.png
└── athletes_comparison.png
```

## Next Steps

**Phase 1: Current**
- ✅ Pace evolution at constant grade
- ✅ Athlete calibration visualization

**Phase 2: Advanced**
- Feature importance plots
- Partial dependence plots
- SHAP value analysis
- Error analysis by segment type

**Phase 3: Interactive**
- Streamlit dashboard for live exploration
- User-specific prediction breakdown
- Segment-by-segment contribution analysis
