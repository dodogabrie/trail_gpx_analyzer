# Strava Data Caching System

## Overview

The application implements a comprehensive caching system to minimize Strava API calls and improve performance. Data is cached in both the database and filesystem.

## What Gets Cached

### 1. Activity Lists
- **Storage**: Database only (`strava_activity_cache` table)
- **Cache Duration**: 24 hours
- **Content**: List of user's activities from Strava
- **Purpose**: Avoid repeated API calls when selecting calibration activities

### 2. Activity Streams
- **Storage**: Database (`strava_activities` table) + Filesystem (`data/strava_cache/streams/{user_id}/{activity_id}.json`)
- **Cache Duration**: Permanent (until manually cleared)
- **Content**: Detailed activity data (distance, time, velocity, grade, etc.)
- **Purpose**: Avoid re-downloading activity streams for calibration and analysis

## Architecture

### Database Models

**StravaActivity**
- Stores activity metadata and streams
- Fields: user_id, strava_id, name, distance, start_date, streams (JSON)
- One-to-many relationship with User

**StravaActivityCache**
- Stores activity list snapshots
- Fields: user_id, activities (JSON), fetched_at, activity_count
- Auto-expires after 24 hours

### Cache Service (`services/cache_service.py`)

**Key Methods:**
- `get_cached_activities(user_id, max_age_hours=24)` - Get cached activity list
- `cache_activities(user_id, activities)` - Store activity list
- `get_cached_streams(user_id, activity_id)` - Get cached streams (checks DB then filesystem)
- `cache_streams(user_id, activity_id, ...)` - Store streams in DB + filesystem
- `clear_stale_caches(max_age_hours=168)` - Clean up old caches

### Filesystem Structure

```
data/strava_cache/
└── streams/
    └── {user_id}/
        ├── {activity_id_1}.json
        ├── {activity_id_2}.json
        └── ...
```

## Cache Flow

### Fetching Calibration Activities

1. Check `strava_activity_cache` table for user
2. If exists and not stale (< 24h) → Use cached data
3. If missing or stale → Fetch from Strava API
4. Store in `strava_activity_cache` table

### Downloading Activity Streams

1. Check `strava_activities` table for user + activity_id
2. If exists with streams → Return from DB
3. Check filesystem: `data/strava_cache/streams/{user_id}/{activity_id}.json`
4. If exists → Load from file, optionally sync to DB
5. If missing → Download from Strava API
6. Store in both DB and filesystem

## API Endpoints

### GET `/api/prediction/cache/status`
Get cache status for current user

**Response:**
```json
{
  "activity_list_cache": {
    "exists": true,
    "fetched_at": "2025-01-20T10:30:00",
    "activity_count": 142,
    "is_stale": false
  },
  "cached_streams": [
    {
      "activity_id": 123456,
      "activity_name": "Morning Run",
      "downloaded_at": "2025-01-20T08:00:00",
      "has_db_cache": true,
      "has_filesystem_cache": true
    }
  ],
  "total_cached_streams": 15
}
```

### POST `/api/prediction/cache/clear`
Clear caches for current user

**Request:**
```json
{
  "clear_activity_list": true,  // Clear activity list cache
  "clear_streams": false         // Clear activity streams cache
}
```

**Response:**
```json
{
  "cleared_activity_list": true,
  "cleared_streams_count": 0
}
```

## Migration

### For Existing Databases

Run the migration script to add the new cache table:

```bash
cd backend
python migrate_cache_table.py
```

This creates the `strava_activity_cache` table without affecting existing data.

## Benefits

1. **Reduced API Calls**: Activity lists cached for 24h, streams cached permanently
2. **Faster Response**: DB/filesystem reads are much faster than API calls
3. **Offline Capability**: Can work with cached data when Strava is unavailable
4. **Cost Savings**: Avoids hitting Strava API rate limits
5. **Reliability**: Less dependent on Strava API availability

## Cache Invalidation

### Automatic
- Activity list cache expires after 24 hours
- Stale caches can be cleaned with `clear_stale_caches()`

### Manual
- Use `/api/prediction/cache/clear` endpoint
- Delete cache files from `data/strava_cache/`
- Delete records from database tables

## Best Practices

1. **Don't clear stream caches unnecessarily** - They're expensive to rebuild
2. **Monitor cache size** - Large filesystems may need periodic cleanup
3. **Backup cache directory** - Avoid re-downloading all streams
4. **Check cache status** - Use status endpoint to monitor cache health

## Logging

Cache operations are logged with symbols:
- `✓` Cache hit (data found in cache)
- `✗` Cache miss (data not in cache)
- `⚠️` Cache stale or warning

Example logs:
```
✓ Using cached activities for user 123
✓ Found streams in DB for activity 456789
⚠️ No cache, fetching from Strava for user 123
✓ Saved streams to filesystem: data/strava_cache/streams/123/456789.json
```
