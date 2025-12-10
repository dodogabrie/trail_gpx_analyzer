#!/usr/bin/env python3
"""Module for scraping all activities from an athlete profile.

This module orchestrates the complete workflow for scraping an athlete's activities:
collecting activity IDs from either homepage feed or weekly intervals, then
downloading metadata and stream data for each activity.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

from .athlete_page import AthletePage
from .interval_navigator import IntervalNavigator
from .activity_extractor import ActivityExtractor
from .activity_downloader import ActivityDownloader


class AthleteScraper:
    """Scrape activities from athlete profiles.

    High-level orchestrator that combines navigation, activity extraction,
    and downloading. Provides two modes: homepage feed (recent 10-20 activities)
    or weekly intervals (configurable weeks back).

    Attributes:
        scraper: StravaSeleniumScraper instance
        athlete_page: AthletePage for navigation
        interval_nav: IntervalNavigator for weekly interval navigation
        activity_extractor: ActivityExtractor for parsing feed entries
        activity_downloader: ActivityDownloader for downloading data
    """

    def __init__(self, scraper):
        """Initialize athlete scraper.

        Args:
            scraper: StravaSeleniumScraper instance with active driver
        """
        self.scraper = scraper
        self.athlete_page = AthletePage(scraper.driver)
        self.interval_nav = IntervalNavigator(scraper.driver)
        self.activity_extractor = ActivityExtractor(scraper.driver)
        self.activity_downloader = ActivityDownloader(scraper)

    def get_activity_ids_from_homepage(self, athlete_id: int,
                                       sport_filter: Optional[str] = None) -> List[Dict]:
        """Get activity IDs from athlete homepage feed (10-20 recent activities).

        Args:
            athlete_id: Strava athlete ID
            sport_filter: Optional sport type filter

        Returns:
            List of activity dicts with pre-extracted metadata
        """
        print(f"Fetching from homepage...")

        if not self.athlete_page.navigate_to_athlete(athlete_id):
            print("Profile not found")
            return []

        athlete_name = self.athlete_page.get_athlete_name()
        if athlete_name:
            print(f"Athlete: {athlete_name}")

        self.athlete_page.scroll_to_load_feed()

        activities = self.activity_extractor.extract_all_activities(sport_filter)
        # Filter out activities that don't have an ID (shouldn't happen with strict extraction)
        # Return full activity dicts, not just IDs
        return [a for a in activities if a.get('id')]

    def get_activity_ids_from_intervals(self, athlete_id: int, weeks_back: int = 4,
                                        sport_filter: Optional[str] = None,
                                        top_weeks_mode: bool = False) -> List[Dict]:
        """Get activity IDs by clicking through weekly intervals.

        Args:
            athlete_id: Strava athlete ID
            weeks_back: Number of weeks to go back (or limit for top mode)
            sport_filter: Optional sport type filter
            top_weeks_mode: If True, select weeks with highest volume instead of recent ones

        Returns:
            List of activity dicts with pre-extracted metadata
        """
        print(f"Fetching from weekly intervals...")

        if not self.athlete_page.navigate_to_athlete(athlete_id):
            print("Profile not found")
            return []

        athlete_name = self.athlete_page.get_athlete_name()
        if athlete_name:
            print(f"Athlete: {athlete_name}")

        if top_weeks_mode:
            print(f"Selecting top {weeks_back} weeks by volume...")
            intervals = self.interval_nav.get_top_intervals(weeks_back)
        else:
            intervals = self.interval_nav.get_recent_intervals(weeks_back)

        if not intervals:
            print("No interval bars found")
            return []

        print(f"Checking {len(intervals)} weeks")

        # Change to store full activity dicts
        all_activities_from_feed = []
        seen_ids = set()

        for i, interval_bar in enumerate(intervals, 1):
            interval_id = self.interval_nav.get_interval_id(interval_bar)
            print(f"\n[{i}/{len(intervals)}] {interval_id}")

            if not self.interval_nav.click_interval(interval_bar):
                print("  Could not click")
                continue

            activities_in_interval = self.activity_extractor.extract_all_activities(sport_filter)

            new_count = 0
            for activity in activities_in_interval:
                if activity.get('id') and activity['id'] not in seen_ids:
                    seen_ids.add(activity['id'])
                    all_activities_from_feed.append(activity) # Store the dict
                    # Print more detailed info
                    print(f"  {activity.get('name', 'Unnamed')} (Distance: {activity.get('distance', 'N/A')}, Elev: {activity.get('elevation', 'N/A')})")
                    new_count += 1

            if new_count == 0:
                print("  No new activities")

        print(f"\nFound {len(all_activities_from_feed)} total activities")
        return all_activities_from_feed

    def scrape_athlete(self, athlete_id: int, output_dir: str = "data/strava/athletes/",
                      weeks_back: int = 4, sport_filter: Optional[str] = None,
                      use_intervals: bool = True, skip_existing: bool = True,
                      require_latlng: bool = True, require_altitude: bool = True,
                      min_elevation: int = 0, top_weeks_mode: bool = False) -> Dict:
        """Scrape all activities from athlete profile.

        Args:
            athlete_id: Strava athlete ID
            output_dir: Output directory
            weeks_back: Number of weeks to look back (intervals mode)
            sport_filter: Optional sport type filter
            use_intervals: Use weekly intervals (True) or homepage feed (False)
            skip_existing: Skip activities that already exist
            require_latlng: Require latlng stream data
            require_altitude: Require altitude stream data
            min_elevation: Minimum elevation gain in meters
            top_weeks_mode: If True, select weeks with highest volume instead of recent ones

        Returns:
            Summary dict with statistics
        """
        print(f"\n=== Scraping Athlete {athlete_id} ===")

        # Get activities (now full activity dicts with pre-extracted metadata)
        if use_intervals:
            mode_str = "Top volume" if top_weeks_mode else "Recent"
            print(f"Mode: Weekly intervals ({mode_str} {weeks_back} weeks)")
            activities_to_download = self.get_activity_ids_from_intervals(
                athlete_id, weeks_back, sport_filter, top_weeks_mode
            )
        else:
            print("Mode: Homepage feed")
            activities_to_download = self.get_activity_ids_from_homepage(athlete_id, sport_filter)

        if not activities_to_download:
            print("No activities found")
            return {'total': 0, 'successful': 0, 'failed': 0}

        # Create athlete directory
        athlete_dir = Path(output_dir) / str(athlete_id)
        athlete_dir.mkdir(parents=True, exist_ok=True)

        # Save activity list (store full dicts)
        activities_file = athlete_dir / "activities.json"
        with open(activities_file, 'w') as f:
            json.dump({
                'athlete_id': athlete_id,
                'activities': activities_to_download, # Store list of dicts
                'count': len(activities_to_download),
                'weeks_back': weeks_back,
                'sport_filter': sport_filter
            }, f, indent=2)
        print(f"\nSaved activity list: {activities_file}")

        # Download activities (pass full dicts)
        stats = self.activity_downloader.download_activities(
            activities_to_download, athlete_dir, # Pass list of dicts
            skip_existing=skip_existing,
            require_latlng=require_latlng,
            require_altitude=require_altitude,
            min_elevation=min_elevation
        )

        # Summary
        summary = {
            'athlete_id': athlete_id,
            **stats,
            'weeks_back': weeks_back,
            'sport_filter': sport_filter,
            'output_dir': str(athlete_dir)
        }

        print(f"\n=== Summary ===")
        print(f"Total: {summary['total']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        if 'skipped' in summary:
            print(f"Skipped: {summary['skipped']}")
        print(f"Output: {summary['output_dir']}")

        # Save summary
        summary_file = athlete_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        return summary
