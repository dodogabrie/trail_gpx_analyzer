# Data Analysis

Analysis and visualization of Strava athlete data.

## Directory Structure

```
data_analysis/
├── data/
│   └── processed/          # Preprocessed data in SI units
├── preprocessing/
│   └── convert_to_si.py   # SI unit conversion script
├── scripts/                # Analysis scripts
└── plot_scripts/          # Visualization scripts
```

## Data Structure

Raw data is collected in `scraper/data/strava/athletes/` with the following structure:

```
athletes/
└── {athlete_id}/
    ├── activities.json           # List of activity IDs
    ├── summary.json             # Collection summary
    ├── {activity_id}_metadata.json  # Activity metadata
    └── {activity_id}_streams.json   # Activity time series data
```

### Stream Data Fields

- `time`: seconds (s)
- `distance`: meters (m)
- `altitude`: meters (m)
- `velocity_smooth`: meters per second (m/s)
- `heartrate`: beats per minute (bpm)
- `cadence`: revolutions per minute (rpm)
- `watts`: power (W)
- `temp`: temperature (Celsius)
- `moving`: boolean
- `grade_smooth`: percentage (%)

## Preprocessing

### Converting to SI Units

Run the preprocessing script to convert all data to SI units:

```bash
python data_analysis/preprocessing/convert_to_si.py
```

This script:
1. Reads raw data from `scraper/data/strava/athletes/`
2. Detects units (F vs C for temperature, ft vs m for altitude)
3. Converts to SI units
4. Saves processed data to `data_analysis/data/processed/`

### Unit Conversions

- Temperature: Fahrenheit → Celsius
- Altitude: Feet → Meters (if detected)
- Distance: Already in meters (Strava API)
- Speed: Already in m/s (Strava API)

### Detection Heuristics

- Temperature: If average > 50, assumes Fahrenheit
- Altitude: If max > 3000, assumes feet

## Next Steps

1. Run preprocessing: `python data_analysis/preprocessing/convert_to_si.py`
2. Create analysis scripts in `scripts/`
3. Create visualization scripts in `plot_scripts/`
