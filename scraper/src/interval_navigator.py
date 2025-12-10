#!/usr/bin/env python3
"""Module for navigating weekly interval bars on Strava athlete profiles.

This module provides utilities to find, select, and interact with the weekly
interval bars displayed on Strava athlete profile pages. Used to access activities
from specific weeks.
"""

import time
from typing import List
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver


class IntervalNavigator:
    """Navigate and interact with weekly interval bars on athlete profiles.

    Finds and clicks on weekly interval bars to load activities from specific
    time periods. Supports selecting recent N weeks.

    Attributes:
        driver: Selenium WebDriver instance
    """

    def __init__(self, driver: WebDriver):
        """Initialize navigator.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver

    def find_interval_bars(self) -> List:
        """Find all weekly interval bars on current page.

        Returns:
            List of interval bar elements
        """
        try:
            interval_container = self.driver.find_element(By.CSS_SELECTOR, "ul.intervals")
            interval_bars = interval_container.find_elements(By.CSS_SELECTOR, "li.interval.selectable")
            return interval_bars
        except:
            return []

    def get_recent_intervals(self, weeks_back: int = 4) -> List:
        """Get the most recent N weeks of interval bars.

        Args:
            weeks_back: Number of recent weeks to retrieve

        Returns:
            List of interval bar elements
        """
        all_bars = self.find_interval_bars()
        if not all_bars:
            return []

        return all_bars[-weeks_back:] if len(all_bars) >= weeks_back else all_bars

    def get_top_intervals(self, limit: int = 4) -> List:
        """Get the N weeks with the highest activity volume (bar height).

        Args:
            limit: Number of top weeks to retrieve

        Returns:
            List of interval bar elements sorted by height (descending)
        """
        all_bars = self.find_interval_bars()
        if not all_bars:
            return []

        # Extract height and sort
        bar_heights = []
        for bar in all_bars:
            try:
                fill_div = bar.find_element(By.CSS_SELECTOR, ".fill")
                style = fill_div.get_attribute("style")
                # Parse "height: 33px;"
                import re
                match = re.search(r'height:\s*([\d\.]+)px', style)
                height = float(match.group(1)) if match else 0
                bar_heights.append((height, bar))
            except:
                bar_heights.append((0, bar))
        
        # Sort by height descending
        bar_heights.sort(key=lambda x: x[0], reverse=True)
        
        # Return top N bars
        return [b[1] for b in bar_heights[:limit]]

    def click_interval(self, interval_bar) -> bool:
        """Click an interval bar to load its activities.

        Args:
            interval_bar: Interval bar element to click

        Returns:
            True if clicked successfully, False otherwise
        """
        try:
            link = interval_bar.find_element(By.CSS_SELECTOR, "a.bar")
            self.driver.execute_script("arguments[0].click();", link)
            time.sleep(2)

            # Scroll to load activities
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

            return True
        except:
            return False

    def get_interval_id(self, interval_bar) -> str:
        """Get the ID attribute of an interval bar.

        Args:
            interval_bar: Interval bar element

        Returns:
            Interval ID string or empty string
        """
        try:
            return interval_bar.get_attribute("id") or ""
        except:
            return ""

    def get_interval_elevation(self, interval_bar) -> int:
        """Extract elevation gain for a week by clicking the interval and reading totals.

        Args:
            interval_bar: Interval bar element

        Returns:
            Elevation gain in meters, or 0 if not found
        """
        try:
            # Click the interval to load its data
            if not self.click_interval(interval_bar):
                return 0

            # Wait for totals to update
            time.sleep(1)

            # Find the totals section (outside the interval bars)
            totals_ul = self.driver.find_element(By.ID, "totals")
            stats_items = totals_ul.find_elements(By.TAG_NAME, "li")

            # Look for the elevation stat (has abbr with title="meters")
            for item in stats_items:
                try:
                    abbr = item.find_element(By.CSS_SELECTOR, "abbr.unit[title='meters']")
                    if abbr:
                        strong = item.find_element(By.TAG_NAME, "strong")
                        elevation_text = strong.text.strip().replace(',', '')
                        # Parse "2,176 m" -> 2176
                        return int(elevation_text.split()[0])
                except:
                    continue

        except Exception as e:
            print(f"Error extracting elevation: {e}")

        return 0

    def get_total_elevation_for_weeks(self, weeks_back: int = 4) -> int:
        """Calculate total elevation gain for recent N weeks.

        Args:
            weeks_back: Number of recent weeks to sum

        Returns:
            Total elevation gain in meters
        """
        intervals = self.get_recent_intervals(weeks_back)
        total_elevation = 0

        for interval in intervals:
            elevation = self.get_interval_elevation(interval)
            total_elevation += elevation

        return total_elevation
