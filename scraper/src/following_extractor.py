#!/usr/bin/env python3
"""Module for extracting following/followers from athlete profiles.

This module provides functionality to extract athlete IDs from following/followers
lists. Handles scrolling to load all athletes and parsing the DOM structure.
"""

import time
from typing import List, Set
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver


class FollowingExtractor:
    """Extract athletes from following/followers lists.

    Navigates to athlete following pages, loads all entries through scrolling,
    and extracts athlete IDs from the list elements.

    Attributes:
        driver: Selenium WebDriver instance
    """

    def __init__(self, driver: WebDriver):
        """Initialize extractor.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver

    def get_following_count(self, athlete_id: int) -> int:
        """Get the count of athletes this athlete is following.

        Args:
            athlete_id: Strava athlete ID

        Returns:
            Number of athletes being followed, or 0 if not accessible
        """
        try:
            # Navigate to profile first
            self.driver.get(f"https://www.strava.com/athletes/{athlete_id}")
            time.sleep(2)

            # Find the following count in social stats
            following_link = self.driver.find_element(
                By.CSS_SELECTOR,
                "a[href*='/follows?type=following']"
            )
            count_text = following_link.text
            return int(count_text.replace(',', ''))
        except:
            return 0

    def navigate_to_following(self, athlete_id: int) -> bool:
        """Navigate to athlete's following page.

        Args:
            athlete_id: Strava athlete ID

        Returns:
            True if page loaded, False otherwise
        """
        url = f"https://www.strava.com/athletes/{athlete_id}/follows?type=following"
        self.driver.get(url)
        time.sleep(3)

        if "Page Not Found" in self.driver.page_source or "404" in self.driver.title:
            return False

        return True

    def scroll_to_load_all(self, max_scrolls: int = 10):
        """Scroll to load all following entries.

        Args:
            max_scrolls: Maximum number of scrolls
        """
        for _ in range(max_scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

    def extract_athlete_ids(self) -> List[int]:
        """Extract all athlete IDs from current following/followers page.

        Returns:
            List of athlete IDs
        """
        athlete_ids = []

        try:
            # Find all list items with data-athlete-id
            athlete_items = self.driver.find_elements(By.CSS_SELECTOR, "li[data-athlete-id]")

            for item in athlete_items:
                try:
                    athlete_id = int(item.get_attribute("data-athlete-id"))
                    athlete_ids.append(athlete_id)
                except (ValueError, TypeError):
                    continue

        except Exception as e:
            print(f"Error extracting athlete IDs: {e}")

        return athlete_ids

    def get_all_following(self, athlete_id: int, max_scrolls: int = 10) -> List[int]:
        """Get all athlete IDs from following list.

        Args:
            athlete_id: Strava athlete ID
            max_scrolls: Maximum scrolls to load more athletes

        Returns:
            List of athlete IDs
        """
        print(f"Fetching following list for athlete {athlete_id}...")

        # Get following count first
        following_count = self.get_following_count(athlete_id)
        if following_count > 0:
            print(f"Athlete is following {following_count} athletes")

        if not self.navigate_to_following(athlete_id):
            print("Following page not accessible")
            return []

        # Scroll to load all
        self.scroll_to_load_all(max_scrolls)

        # Extract IDs
        athlete_ids = self.extract_athlete_ids()

        print(f"Found {len(athlete_ids)} athletes in following list")
        if following_count > 0 and len(athlete_ids) < following_count:
            print(f"Note: Only loaded {len(athlete_ids)}/{following_count}. Try increasing --max-scrolls")

        return athlete_ids
