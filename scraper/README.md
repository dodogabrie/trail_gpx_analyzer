# Scraper - Multi-User Strava Data Collection

Isolated environment for collecting Strava activity data with optimized API usage and rate limiting.

## Quick Start

```bash
cd scraper
source venv/bin/activate

# Scrape running activities from last 30 days
python scraper.py scrape --sport Run --days 30 --download-streams

# Check progress
python scraper.py status
```

## Features

- **Optimized API Usage:** 1 request per activity (was 7) - 85% reduction
- **Rate Limiting:** Automatic tracking of 15-min (200 req) and daily (2000 req) quotas
- **Isolated Environment:** Separate venv with minimal dependencies
- **Multi-User Support:** Database schema for multiple athletes
- **Stream Downloads:** GPS, altitude, heart rate, cadence, power data
- **Monitoring Dashboard:** Interactive progress tracking

## Setup

### 1. Create Virtual Environment
```bash
./setup.sh
source venv/bin/activate
```

### 2. Authorize Strava (One-Time)

Run main app to authorize:
```bash
cd ..
python src/app.py
# Visit http://localhost:5000 and authorize via Strava
```

Tokens stored in project root `.env`

## Usage

### Scraping Data

```bash
# All activities
python scraper.py scrape

# Running activities only
python scraper.py scrape --sport Run

# Last 30 days with streams
python scraper.py scrape --sport Run --days 30 --download-streams

# Date range
python scraper.py scrape --after 2024-01-01 --before 2024-12-31
```

### Monitoring

```bash
# Interactive menu
python monitor.py

# Quick summary
python monitor.py --once
```

**Dashboard Views:**
1. API Quota Status - Visual bars for rate limits
2. Database Overview - Users, activities, storage stats
3. Recent Activities - Last 10 activities
4. Sport Type Breakdown - Count and totals by sport
5. User Statistics - Per-user aggregates

### Status Check

```bash
python scraper.py status
```

Shows:
- Total activities collected
- Activities with streams
- Sport type breakdown
- API quota usage

## API Optimization

### Before vs After

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Requests per activity | 7 | 1 | 85% reduction |
| Daily capacity | ~285 activities | ~1900 activities | 6.6x increase |
| Stream download | 6 separate calls | 1 combined call | - |

### How It Works

**Old Method:**
- 1 request for activity metadata
- 6 separate requests for streams (lat, lon, altitude, time, distance, grade)

**New Method:**
- 1 request for activity metadata
- 1 request for all streams combined

Implemented in `src/strava/api.py:download_activity_streams()`

## Rate Limiting

### Strava API Limits
- **15-minute window:** 200 requests
- **Daily window:** 2000 requests

### Auto-Management

The `RateLimiter` class (`src/strava/rate_limiter.py`):
- Tracks usage from response headers
- Auto-waits when approaching limits
- Handles quota exhaustion gracefully
- Logs quota status after each request

**Example Log:**
```
Rate limit: 15-min [45/200], Daily [1250/2000]
Approaching 15-min limit, waiting 120 seconds...
```

## Database Schema

SQLite database at `data/gpx_analyzer.db`

### Tables

**users**
- `id`: Primary key
- `strava_id`: Strava athlete ID (unique)
- `username`: Display name
- `first_name`, `last_name`
- `created_at`: Timestamp

**activities**
- `id`: Primary key
- `user_id`: Foreign key to users
- `strava_id`: Strava activity ID (unique)
- `name`: Activity name
- `sport_type`: Run, Ride, Swim, etc.
- `distance`: meters
- `moving_time`: seconds
- `elapsed_time`: seconds
- `total_elevation_gain`: meters
- `start_date`: ISO timestamp
- `start_lat`, `start_lng`: GPS coordinates

**streams**
- `id`: Primary key
- `activity_id`: Foreign key to activities
- `stream_type`: time, distance, altitude, latlng, etc.
- `data`: JSON array of values

**user_clusters** (for future clustering)
- `user_id`: Foreign key
- `cluster_id`: Cluster assignment
- `vam_avg`, `pace_avg`: Performance metrics

**segments** (for future NN training)
- `id`: Primary key
- `activity_id`: Foreign key
- `start_idx`, `end_idx`: Segment boundaries
- `grade_mean`, `grade_std`: Grade statistics
- `pace_mean`: Pace in segment

### Indexes

Optimized queries:
- `idx_activities_user` - Activities by user
- `idx_activities_sport` - Activities by sport type
- `idx_activities_date` - Activities by date
- `idx_streams_activity` - Streams by activity

## Data Storage

### Primary Storage
SQLite database (`data/gpx_analyzer.db`)

### CSV Backups (Legacy)
Also creates CSV files in `data/strava/`:
- Activity metadata
- Stream data

*May be removed in future versions*

## Performance Metrics

Module: `src/utils/performance_metrics.py`

**Available Calculations:**
- `calculate_vam()` - Vertical Ascent Meters per hour
- `calculate_pace()` - Minutes per km/mile
- `calculate_speed()` - km/h
- `calculate_segment_vam()` - VAM for segments
- `calculate_activity_stats()` - Comprehensive stats
- `calculate_user_features()` - User-level aggregates

Used for:
- User clustering (performance groups)
- Distance preference categorization
- ML feature extraction

## CLI Reference

### `scraper.py`

**Commands:**
- `scrape` - Collect activity data
- `status` - Show collection summary

**Options:**
- `--sport TYPE` - Filter by sport (Run, Ride, Swim, etc.)
- `--days N` - Last N days
- `--after DATE` - Activities after date (YYYY-MM-DD)
- `--before DATE` - Activities before date (YYYY-MM-DD)
- `--download-streams` - Include stream data
- `--limit N` - Max activities to fetch

**Examples:**
```bash
# Last 7 days, running only, with streams
python scraper.py scrape --sport Run --days 7 --download-streams

# All rides in 2024
python scraper.py scrape --sport Ride --after 2024-01-01 --before 2024-12-31

# Quick metadata only (no streams)
python scraper.py scrape --sport Run --days 30
```

### `monitor.py`

**Modes:**
- Interactive: `python monitor.py`
- One-time summary: `python monitor.py --once`

**Interactive Menu:**
1. View API quota
2. View database overview
3. View recent activities
4. View sport breakdown
5. View user stats
6. All views
0. Exit

## Testing

Run tests from project root:
```bash
pytest tests/test_rate_limiter.py    # 12 tests
pytest tests/test_strava_api.py      # 8 tests (mocked)
pytest tests/test_database.py        # 13 tests
```

## Known Limitations

1. **Single OAuth Token** - Uses one Strava account
   - Future: Support multiple API keys for increased quota

2. **CSV Backups** - Still creating CSV files
   - Future: Make optional or remove

3. **Manual Scraping** - No automation
   - Future: Cron job or scheduler

4. **Basic Error Handling** - Stops on first error
   - Future: Retry logic with backoff

5. **No Data Validation** - Assumes clean data
   - Future: Outlier detection and GPS smoothing

## Directory Structure

```
scraper/
├── venv/                   # Virtual environment
├── setup.sh                # Setup script
├── requirements.txt        # Minimal dependencies
├── scraper.py              # Main CLI tool
├── monitor.py              # Monitoring dashboard
├── data/                   # CSV backups (legacy)
│   └── strava/
│       └── athletes/
│           └── {id}/
│               ├── activities.json
│               ├── summary.json
│               ├── {id}_metadata.json
│               └── {id}_streams.json
└── rotating_scraper/       # Advanced scraper (separate project)
```

## Next Steps

**Phase 2: Data Collection**
- Multi-user collection strategy (public segments/clubs)
- Automated daily scraping schedule
- Data validation and cleaning pipeline
- GPS smoothing for elevation data

**Phase 3: Clustering**
- K-means implementation
- Cluster validation (silhouette score)
- New user assignment logic

**Phase 4: Segment Extraction**
- Auto-segmentation by slope change
- Segment feature extraction
- Training data preparation

## Dependencies

Minimal requirements:
- `requests` - Strava API client
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `python-dotenv` - Environment variables

Install:
```bash
pip install -r requirements.txt
```

## Troubleshooting

### "No Strava tokens found"
Authorize via main app first:
```bash
cd .. && python src/app.py
# Visit http://localhost:5000 and connect Strava
```

### Rate Limit Exhausted
Wait for quota reset:
- 15-min limit: Wait up to 15 minutes
- Daily limit: Wait until next day (UTC)

Monitor quota:
```bash
python monitor.py
# Select option [1] for API quota status
```

### Database Locked
Another process using database. Stop other scripts or restart.

### Missing Dependencies
Ensure scraper venv is active:
```bash
source venv/bin/activate
pip install -r requirements.txt
```
