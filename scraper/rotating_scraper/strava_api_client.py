#!/usr/bin/env python3
"""Strava API client using OAuth tokens.

Uses Strava's official API with access tokens instead of web scraping.
Designed to work with TokenRotator for rate limit management.
"""

import requests
import json
import time
from pathlib import Path
from typing import Optional, Dict, List


class StravaAPIClient:
    """Strava API client with token-based authentication."""

    def __init__(self, access_token: str):
        """Initialize API client.

        Args:
            access_token: Strava OAuth access token
        """
        self.access_token = access_token
        self.base_url = "https://www.strava.com/api/v3"

    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """Make authenticated API request.

        Args:
            endpoint: API endpoint (e.g., '/athlete/activities')
            params: Query parameters

        Returns:
            JSON response or None if failed
        """
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limited
                return {'error': 'rate_limited', 'status': 429}
            elif response.status_code == 401:
                # Unauthorized
                return {'error': 'unauthorized', 'status': 401}
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Request error: {e}")
            return None

    def get_activity(self, activity_id: int) -> Optional[Dict]:
        """Get activity details.

        Args:
            activity_id: Strava activity ID

        Returns:
            Activity dict or None
        """
        return self._make_request(f'/activities/{activity_id}')

    def get_activity_streams(self, activity_id: int, stream_types: List[str] = None) -> Optional[Dict]:
        """Get activity streams.

        Args:
            activity_id: Strava activity ID
            stream_types: List of stream types to fetch

        Returns:
            Dict with stream data or None
        """
        if stream_types is None:
            stream_types = ['time', 'latlng', 'distance', 'altitude', 'velocity_smooth',
                          'heartrate', 'cadence', 'watts', 'temp', 'moving', 'grade_smooth']

        keys = ','.join(stream_types)
        endpoint = f'/activities/{activity_id}/streams'

        response = self._make_request(endpoint, {'keys': keys, 'key_by_type': 'true'})

        if response and 'error' not in response:
            # Convert from list format to dict format
            if isinstance(response, list):
                streams_dict = {}
                for stream in response:
                    if isinstance(stream, dict):
                        stream_type = stream.get('type')
                        data = stream.get('data', [])
                        if stream_type:
                            streams_dict[stream_type] = data
                return streams_dict
            else:
                return response

        return None

    def get_athlete_activities(self, after: int = None, before: int = None,
                              page: int = 1, per_page: int = 30) -> Optional[List[Dict]]:
        """Get athlete's activities.

        Args:
            after: Timestamp to filter activities after
            before: Timestamp to filter activities before
            page: Page number
            per_page: Activities per page (max 200)

        Returns:
            List of activity dicts or None
        """
        params = {'page': page, 'per_page': per_page}

        if after:
            params['after'] = after
        if before:
            params['before'] = before

        return self._make_request('/athlete/activities', params)

    def scrape_activity(self, activity_id: int, output_dir: str = "data/strava/",
                       min_elevation: int = 0) -> bool:
        """Scrape complete activity data using API.

        Args:
            activity_id: Strava activity ID
            output_dir: Directory to save files
            min_elevation: Minimum elevation gain in meters

        Returns:
            True if successful
        """
        print(f"\n=== Scraping Activity {activity_id} ===\n")

        # Get metadata
        metadata = self.get_activity(activity_id)

        if not metadata:
            print(f"  ✗ Failed to fetch activity metadata")
            return False

        if 'error' in metadata:
            if metadata['error'] == 'rate_limited':
                print(f"  ⚠ Rate limited")
                return False
            elif metadata['error'] == 'unauthorized':
                print(f"  ✗ Unauthorized (token expired or invalid)")
                return False

        # Check elevation threshold
        elevation_gain = metadata.get('total_elevation_gain', 0)
        if elevation_gain < min_elevation:
            print(f"  ⊘ Skipped: Elevation {elevation_gain:.0f}m < {min_elevation}m threshold")
            return False

        print(f"  ✓ {metadata.get('name', 'Unnamed')}")
        print(f"    Sport: {metadata.get('type', 'Unknown')}")
        print(f"    Distance: {metadata.get('distance', 0)/1000:.2f} km")
        print(f"    Elevation: {elevation_gain:.0f} m")

        # Get streams
        print(f"  Fetching streams from API...")
        streams = self.get_activity_streams(activity_id)

        if not streams:
            print(f"  ✗ No streams available")
            return False

        if 'error' in streams:
            if streams['error'] == 'rate_limited':
                print(f"  ⚠ Rate limited on streams")
                return False

        # Validate required streams
        if 'latlng' not in streams:
            print(f"  ✗ Missing latlng stream")
            return False

        if 'altitude' not in streams:
            print(f"  ✗ Missing altitude stream")
            return False

        print(f"  ✓ Extracted streams: {list(streams.keys())}")

        # Save to files
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save metadata
        metadata_file = output_path / f"{activity_id}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"  → Saved metadata: {metadata_file}")

        # Save streams
        streams_file = output_path / f"{activity_id}_streams.json"
        with open(streams_file, 'w') as f:
            json.dump(streams, f, indent=2)
        print(f"  → Saved streams: {streams_file}")

        return True
