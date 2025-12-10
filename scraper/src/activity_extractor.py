#!/usr/bin/env python3
"""Module for extracting activity data from Strava feed entries.

This module provides utilities to parse Strava's web feed entries and extract
activity information including ID, type, date, name, and distance. Works with
the current Strava web interface DOM structure.
"""

from typing import List, Dict, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver


class ActivityExtractor:
    """Extract activity information from Strava feed entries.

    Parses DOM elements from Strava's web feed to extract activity metadata.
    Uses CSS selectors and test IDs to locate and extract data.

    Attributes:
        driver: Selenium WebDriver instance for DOM access
    """

    def __init__(self, driver: WebDriver):
        """Initialize extractor.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver

    def get_feed_entries(self) -> List:
        """Find all feed entry elements on current page.

        Returns:
            List of feed entry elements
        """
        return self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='web-feed-entry']")

    def extract_activity_id(self, entry) -> Optional[int]:
        """Extract activity ID from feed entry.

        Args:
            entry: Feed entry element

        Returns:
            Activity ID as int, or None if not found
        """
        try:
            container = entry.find_element(By.CSS_SELECTOR, "[data-testid='activity_entry_container']")
            activity_link = container.find_element(By.CSS_SELECTOR, "a[href*='/activities/']")
            href = activity_link.get_attribute("href")

            if "/activities/" in href:
                activity_id = int(href.split("/activities/")[1].split("/")[0].split("?")[0])
                return activity_id
        except:
            pass

        return None

    def extract_activity_type(self, entry) -> Optional[str]:
        """Extract activity type from feed entry icon.

        Args:
            entry: Feed entry element

        Returns:
            Activity type string (e.g., "Run", "Ride"), or None if not found
        """
        try:
            icon_svg = entry.find_element(By.CSS_SELECTOR, "[data-testid='activity-icon']")
            title_elem = icon_svg.find_element(By.TAG_NAME, "title")
            return title_elem.text
        except:
            return None

    def extract_activity_date(self, entry) -> Optional[str]:
        """Extract activity date from feed entry.

        Args:
            entry: Feed entry element

        Returns:
            Date string, or None if not found
        """
        try:
            time_elem = entry.find_element(By.CSS_SELECTOR, "time")
            return time_elem.get_attribute("datetime") or time_elem.text
        except:
            pass

        try:
            date_elem = entry.find_element(By.CSS_SELECTOR, "[class*='timestamp'], [class*='date']")
            return date_elem.text
        except:
            pass

        return None

    def extract_activity_name(self, entry) -> Optional[str]:
        """Extract activity name from feed entry.

        Args:
            entry: Feed entry element

        Returns:
            Activity name string, or None if not found
        """
        try:
            container = entry.find_element(By.CSS_SELECTOR, "[data-testid='activity_entry_container']")
            activity_link = container.find_element(By.CSS_SELECTOR, "a[href*='/activities/']")
            return activity_link.text
        except:
            return None

    def _extract_stat(self, entry, stat_label: str) -> Optional[str]:
        """Helper to extract a specific stat from feed entry.

        Args:
            entry: Feed entry element
            stat_label: The label of the stat to extract (e.g., "Distance", "Elev Gain", "Time")

        Returns:
            Stat value string, or None if not found
        """
        try:
            container = entry.find_element(By.CSS_SELECTOR, "[data-testid='activity_entry_container']")
            stats = container.find_elements(By.CSS_SELECTOR, ".mGV12")

            for stat in stats:
                # Check for the span containing the label
                label_span = stat.find_element(By.CSS_SELECTOR, ".U5UN2.rzwyM")
                if label_span and stat_label.lower() in label_span.text.lower():
                    value_div = stat.find_element(By.CSS_SELECTOR, ".vNsSU")
                    return value_div.text
        except:
            pass
        return None

    def extract_activity_distance(self, entry) -> Optional[str]:
        """Extract activity distance from feed entry.

        Args:
            entry: Feed entry element

        Returns:
            Distance string (e.g., "5.2 km"), or None if not found
        """
        return self._extract_stat(entry, "Distance")

    def extract_activity_elevation(self, entry) -> Optional[str]:
        """Extract activity elevation from feed entry.

        Args:
            entry: Feed entry element

        Returns:
            Elevation string (e.g., "1,600 m"), or None if not found
        """
        # Try "Elev" to match "Elevation", "Elev Gain", etc.
        return self._extract_stat(entry, "Elev")

    def extract_activity_time(self, entry) -> Optional[str]:
        """Extract activity time from feed entry.

        Args:
            entry: Feed entry element

        Returns:
            Time string (e.g., "3h 59m"), or None if not found
        """
        return self._extract_stat(entry, "Time")

    def extract_full_activity(self, entry) -> Dict:
        """Extract all available activity data from feed entry.

        Args:
            entry: Feed entry element

        Returns:
            Dict with activity data (id, type, date, name, distance, elevation, time)
        """
        return {
            'id': self.extract_activity_id(entry),
            'type': self.extract_activity_type(entry),
            'date': self.extract_activity_date(entry),
            'name': self.extract_activity_name(entry),
            'distance': self.extract_activity_distance(entry),
            'elevation': self.extract_activity_elevation(entry),
            'time': self.extract_activity_time(entry)
        }

    def extract_all_activities(self, sport_filter: Optional[str] = None) -> List[Dict]:
        """Extract all activities from current page feed.

        Args:
            sport_filter: Optional sport type filter (e.g., "Run")

        Returns:
            List of activity dicts
        """
        activities = []
        feed_entries = self.get_feed_entries()

        for entry in feed_entries:
            activity_type = self.extract_activity_type(entry)

            # Apply sport filter if specified
            if sport_filter:
                # Strict filtering: if type is unknown or doesn't match, skip it
                if not activity_type:
                    continue
                
                if sport_filter.lower() not in activity_type.lower():
                    continue

            activity = self.extract_full_activity(entry)
            if activity['id']:
                # Ensure type is set in the result
                if activity_type and not activity['type']:
                    activity['type'] = activity_type
                activities.append(activity)

        return activities

    def has_run_over_distance(self, min_distance_km: float = 30.0) -> bool:
        """Check if any visible run activity exceeds minimum distance.

        Args:
            min_distance_km: Minimum distance in kilometers

        Returns:
            True if at least one run meets distance threshold
        """
        feed_entries = self.get_feed_entries()

        for entry in feed_entries:
            activity_type = self.extract_activity_type(entry)

            if activity_type and "run" in activity_type.lower():
                distance_str = self.extract_activity_distance(entry)
                if distance_str:
                    try:
                        # Parse distance: "30.5 km" or "30.5km"
                        distance_match = distance_str.replace(',', '').split()
                        if distance_match:
                            distance_value = float(distance_match[0])
                            # Check if km or convert from miles (m)
                            if 'km' in distance_str.lower():
                                if distance_value >= min_distance_km:
                                    return True
                            elif 'mi' in distance_str.lower():
                                # Convert miles to km
                                distance_km = distance_value * 1.60934
                                if distance_km >= min_distance_km:
                                    return True
                    except:
                        pass

        return False
