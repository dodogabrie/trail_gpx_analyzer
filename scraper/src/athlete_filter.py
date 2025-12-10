#!/usr/bin/env python3
"""Module for filtering athletes based on activity criteria.

This module provides functionality to filter athlete lists based on whether
they have recent activities of a specific type. Useful for identifying active
athletes matching certain criteria.
"""

from typing import List, Set
from datetime import datetime, timedelta
from .athlete_page import AthletePage
from .activity_extractor import ActivityExtractor
from .interval_navigator import IntervalNavigator


class AthleteFilter:
    """Filter athletes based on their recent activities.

    Navigates to athlete profiles, loads their activity feed, and checks
    for recent activities matching specific criteria (sport type, date range).

    Attributes:
        driver: Selenium WebDriver instance
        athlete_page: AthletePage instance for navigation
        activity_extractor: ActivityExtractor instance for parsing activities
    """

    def __init__(self, driver):
        """Initialize filter.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.athlete_page = AthletePage(driver)
        self.activity_extractor = ActivityExtractor(driver)
        self.interval_navigator = IntervalNavigator(driver)

    def has_recent_activity_of_type(self, athlete_id: int, sport_type: str,
                                   days_back: int = 7) -> bool:
        """Check if athlete has recent activity of specific type.

        Args:
            athlete_id: Strava athlete ID
            sport_type: Sport type to check (e.g., "Run", "Ride")
            days_back: Number of days to look back

        Returns:
            True if athlete has recent activity of specified type
        """
        # Navigate to athlete
        if not self.athlete_page.navigate_to_athlete(athlete_id):
            return False

        # Load feed
        self.athlete_page.scroll_to_load_feed(scroll_count=2)

        # Extract activities with sport filter
        activities = self.activity_extractor.extract_all_activities(sport_type)

        if not activities:
            return False

        # Check if any activity is within time range
        cutoff_date = datetime.now() - timedelta(days=days_back)

        for activity in activities:
            if activity['date']:
                try:
                    # Parse date - handle different formats
                    date_str = activity['date']

                    # Try ISO format first
                    if 'T' in date_str or 'Z' in date_str:
                        activity_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        # Try parsing "December 4, 2025 at 10:10 AM"
                        activity_date = datetime.strptime(date_str, "%B %d, %Y at %I:%M %p")

                    if activity_date >= cutoff_date:
                        return True

                except (ValueError, AttributeError):
                    # If can't parse date, assume it's recent (from homepage feed)
                    return True

        return False

    def has_sufficient_elevation(self, athlete_id: int, weeks_back: int = 4,
                                min_elevation_per_week: int = 800) -> tuple[bool, int]:
        """Check if athlete has sufficient elevation gain in recent weeks.

        Args:
            athlete_id: Strava athlete ID
            weeks_back: Number of weeks to check
            min_elevation_per_week: Minimum elevation per week in meters

        Returns:
            Tuple of (passes_filter, total_elevation)
        """
        if not self.athlete_page.navigate_to_athlete(athlete_id):
            return False, 0

        total_elevation = self.interval_navigator.get_total_elevation_for_weeks(weeks_back)
        min_required = weeks_back * min_elevation_per_week
        passes = total_elevation >= min_required

        return passes, total_elevation

    def has_long_run(self, athlete_id: int, weeks_back: int = 4,
                    min_distance_km: float = 30.0) -> bool:
        """Check if athlete has at least one run >= min_distance_km in recent weeks.

        Args:
            athlete_id: Strava athlete ID
            weeks_back: Number of weeks to check
            min_distance_km: Minimum run distance in kilometers

        Returns:
            True if athlete has at least one long run
        """
        if not self.athlete_page.navigate_to_athlete(athlete_id):
            return False

        # Click through recent weeks and check for long runs
        intervals = self.interval_navigator.get_recent_intervals(weeks_back)

        for interval in intervals:
            if not self.interval_navigator.click_interval(interval):
                continue

            # Check activities in this week
            if self.activity_extractor.has_run_over_distance(min_distance_km):
                return True

        return False

    def filter_athletes_with_recent_runs(self, athlete_ids: List[int],
                                        days_back: int = 7,
                                        weeks_back: int = 4,
                                        min_elevation_per_week: int = 800,
                                        min_long_run_km: float = 30.0,
                                        timeout_seconds: int = None,
                                        max_results: int = None) -> List[int]:
        """Filter athletes who have recent runs, sufficient elevation, and long runs.

        Args:
            athlete_ids: List of athlete IDs to check
            days_back: Number of days to look back for activity check
            weeks_back: Number of weeks to check for elevation and long runs
            min_elevation_per_week: Minimum elevation per week in meters
            min_long_run_km: Minimum distance for long run in kilometers
            timeout_seconds: Optional timeout in seconds (stops scanning after this time)
            max_results: Stop after finding this many active runners

        Returns:
            List of athlete IDs meeting all criteria
        """
        import time

        filtered_ids = []
        start_time = time.time()

        print(f"\nFiltering {len(athlete_ids)} athletes...")
        print(f"✓ Recent runs: last {days_back} days")
        print(f"✓ Elevation: {weeks_back} weeks * {min_elevation_per_week}m = {weeks_back * min_elevation_per_week}m min")
        print(f"✓ Long run: ≥ {min_long_run_km}km in last {weeks_back} weeks")
        if timeout_seconds:
            print(f"Timeout: {timeout_seconds} seconds")
        if max_results:
            print(f"Stopping after finding {max_results} athletes")
        print()

        for i, athlete_id in enumerate(athlete_ids, 1):
            # Check timeout
            if timeout_seconds:
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    print(f"\n⏱ Timeout reached ({timeout_seconds}s) after checking {i-1}/{len(athlete_ids)} athletes")
                    break

            # Check max results
            if max_results and len(filtered_ids) >= max_results:
                print(f"\n✓ Found {max_results} active runners, stopping early")
                break

            print(f"[{i}/{len(athlete_ids)}] Checking athlete {athlete_id}...", end=" ")

            # Check recent activity
            if not self.has_recent_activity_of_type(athlete_id, "Run", days_back):
                print("✗ No recent runs")
                continue

            # Check elevation (already on athlete page from previous check)
            passes_elevation, total_elevation = self.has_sufficient_elevation(
                athlete_id, weeks_back, min_elevation_per_week
            )

            if not passes_elevation:
                min_required = weeks_back * min_elevation_per_week
                print(f"✗ Low elevation ({total_elevation}m < {min_required}m)")
                continue

            # Check long run
            has_long = self.has_long_run(athlete_id, weeks_back, min_long_run_km)

            if has_long:
                print(f"✓ All checks passed ({total_elevation}m elev)")
                filtered_ids.append(athlete_id)
            else:
                print(f"✗ No run ≥ {min_long_run_km}km")

        print(f"\nFiltered: {len(filtered_ids)} athletes meeting all criteria")
        return filtered_ids
