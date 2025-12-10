#!/usr/bin/env python3
"""Module for navigating and interacting with athlete profile pages.

This module provides basic navigation to athlete profile pages and utilities
for loading activity feeds through scrolling. Handles basic profile information
extraction.
"""

import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver


class AthletePage:
    """Handle navigation and basic info extraction from athlete pages.

    Provides utilities to navigate to athlete profiles, extract basic information
    like athlete name, and load the activity feed through scrolling.

    Attributes:
        driver: Selenium WebDriver instance
    """

    def __init__(self, driver: WebDriver):
        """Initialize athlete page handler.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver

    def navigate_to_athlete(self, athlete_id: int) -> bool:
        """Navigate to athlete profile page.

        Args:
            athlete_id: Strava athlete ID

        Returns:
            True if page loaded successfully, False if not found
        """
        url = f"https://www.strava.com/athletes/{athlete_id}"
        self.driver.get(url)
        time.sleep(3)

        if "Page Not Found" in self.driver.page_source or "404" in self.driver.title:
            return False

        return True

    def get_athlete_name(self) -> Optional[str]:
        """Extract athlete name from current page.

        Returns:
            Athlete name string, or None if not found
        """
        try:
            name_elem = self.driver.find_element(By.CSS_SELECTOR, ".athlete-name, h1, [class*='AthleteHeader']")
            return name_elem.text
        except:
            return None

    def scroll_to_load_feed(self, scroll_count: int = 3):
        """Scroll page to load activity feed.

        Args:
            scroll_count: Number of times to scroll to bottom
        """
        for _ in range(scroll_count):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
