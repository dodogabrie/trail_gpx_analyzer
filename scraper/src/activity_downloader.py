#!/usr/bin/env python3
"""Module for downloading activity data from Strava.

This module handles downloading both metadata and stream data for activities,
with validation for required data fields (latlng, altitude). Supports batch
downloading with skip-existing and validation logic.
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, Optional, List
from selenium.webdriver.remote.webdriver import WebDriver


class ActivityDownloader:
    """Download activity metadata and stream data.

    Handles downloading activities from Strava with validation for required
    stream data. Can skip existing downloads and re-download invalid ones.

    Attributes:
        scraper: StravaSeleniumScraper instance used for downloading
    """

    def __init__(self, scraper):
        """Initialize downloader.

        Args:
            scraper: StravaSeleniumScraper instance with active driver
        """
        self.scraper = scraper

    def _parse_elevation_str(self, elevation_str: Optional[str]) -> int:
        """Parse elevation string (e.g., "1,600 m") into an integer in meters."""
        if not elevation_str:
            return 0
        try:
            # Remove commas and extract number
            numeric_part = re.search(r'([\d,\.]+)', elevation_str)
            if numeric_part:
                value = float(numeric_part.group(1).replace(',', ''))
                # Assume default unit is meters if not specified or "m"
                if 'ft' in elevation_str.lower():
                    return int(value * 0.3048) # Convert feet to meters
                return int(value)
        except ValueError:
            pass
        return 0

    def activity_exists(self, activity_id: int, output_dir: Path) -> bool:
        """Check if activity files already exist.

        Args:
            activity_id: Strava activity ID
            output_dir: Directory where files would be saved

        Returns:
            True if both metadata and streams files exist
        """
        metadata_file = output_dir / f"{activity_id}_metadata.json"
        streams_file = output_dir / f"{activity_id}_streams.json"
        return metadata_file.exists() and streams_file.exists()

    def validate_streams(self, activity_id: int, output_dir: Path,
                        require_latlng: bool = True,
                        require_altitude: bool = True) -> bool:
        """Validate that activity has required stream data.

        Args:
            activity_id: Strava activity ID
            output_dir: Directory where streams file is saved
            require_latlng: Require latlng stream
            require_altitude: Require altitude stream

        Returns:
            True if streams meet requirements, False otherwise
        """
        streams_file = output_dir / f"{activity_id}_streams.json"

        if not streams_file.exists():
            return False

        try:
            with open(streams_file) as f:
                streams = json.load(f)

            if require_latlng and 'latlng' not in streams:
                return False

            if require_altitude and 'altitude' not in streams:
                return False

            return True

        except Exception:
            return False

    def download_activity(self, activity: Dict, output_dir: Path,
                         skip_existing: bool = True,
                         require_latlng: bool = True,
                         require_altitude: bool = True,
                         min_elevation: int = 0) -> bool:
        """Download single activity data.

        Args:
            activity: Dictionary containing activity ID and pre-extracted metadata
            output_dir: Directory to save files
            skip_existing: Skip if files already exist
            require_latlng: Require latlng stream
            require_altitude: Require altitude stream
            min_elevation: Minimum elevation gain in meters

        Returns:
            True if successful, False otherwise
        """
        activity_id = activity['id']
        pre_extracted_elevation_str = activity.get('elevation')
        pre_extracted_elevation = self._parse_elevation_str(pre_extracted_elevation_str)

        try:
            # Pre-filter by elevation if possible
            if pre_extracted_elevation < min_elevation:
                print(f"  ⊘ Skipped (pre-filter): Elevation {pre_extracted_elevation}m < {min_elevation}m threshold")
                return False

            # Check if already exists
            if skip_existing and self.activity_exists(activity_id, output_dir):
                # Validate streams
                if self.validate_streams(activity_id, output_dir, require_latlng, require_altitude):
                    print(f"  ⊘ Already exists (skipped)")
                    return True
                else:
                    print(f"  ⚠ Exists but missing required streams, re-downloading...")

            # Download
            # Pass min_elevation again to scraper.scrape_activity for its internal checks if any
            # Pass pre_extracted_elevation as known_elevation fallback
            success = self.scraper.scrape_activity(
                activity_id, 
                str(output_dir), 
                min_elevation=min_elevation,
                known_elevation=pre_extracted_elevation
            )

            if success:
                # Validate streams after download
                if not self.validate_streams(activity_id, output_dir, require_latlng, require_altitude):
                    print(f"  ⚠ Missing required streams (latlng: {require_latlng}, altitude: {require_altitude})")

                    # Remove invalid files
                    metadata_file = output_dir / f"{activity_id}_metadata.json"
                    streams_file = output_dir / f"{activity_id}_streams.json"
                    if metadata_file.exists():
                        metadata_file.unlink()
                    if streams_file.exists():
                        streams_file.unlink()

                    return False

            return success

        except Exception as e:
            print(f"  Error downloading {activity_id}: {e}")
            return False

    def download_activities(self, activities: List[Dict], output_dir: Path,
                          delay: float = 5.0,
                          skip_existing: bool = True,
                          require_latlng: bool = True,
                          require_altitude: bool = True,
                          min_elevation: int = 0) -> Dict:
        """Download multiple activities.

        Args:
            activities: List of activity dictionaries with pre-extracted metadata
            output_dir: Directory to save files
            delay: Delay between requests in seconds
            skip_existing: Skip activities that already exist
            require_latlng: Require latlng stream
            require_altitude: Require altitude stream
            min_elevation: Minimum elevation gain in meters

        Returns:
            Dict with download statistics
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        successful = 0
        failed = 0
        skipped = 0
        pre_filtered = 0 # New counter for pre-filtered activities

        print(f"\nDownloading {len(activities)} activities...")
        if skip_existing:
            print("Skipping existing activities")
        if require_latlng or require_altitude:
            filters = []
            if require_latlng:
                filters.append("latlng")
            if require_altitude:
                filters.append("altitude")
            print(f"Requiring streams: {', '.join(filters)}")

        for i, activity in enumerate(activities, 1):
            activity_id = activity['id']
            print(f"\n[{i}/{len(activities)}] Activity {activity_id} ({activity.get('name', 'Unnamed')})")

            # Check pre-extracted elevation for early skipping
            pre_extracted_elevation = self._parse_elevation_str(activity.get('elevation'))
            if pre_extracted_elevation < min_elevation:
                print(f"  ⊘ Skipped (pre-filter): Elevation {pre_extracted_elevation}m < {min_elevation}m threshold")
                pre_filtered += 1
                continue # Skip to next activity without attempting download

            # Check if skipped (existing files)
            was_skipped_existing = skip_existing and self.activity_exists(activity_id, output_dir)

            if self.download_activity(activity, output_dir, skip_existing, # Pass activity dict
                                    require_latlng, require_altitude, min_elevation):
                if was_skipped_existing:
                    skipped += 1
                successful += 1
            else:
                failed += 1

            # Delay between requests
            if i < len(activities):
                time.sleep(delay)

        return {
            'total': len(activities),
            'successful': successful,
            'failed': failed,
            'skipped': skipped,
            'pre_filtered': pre_filtered # Include pre-filtered count in summary
        }

