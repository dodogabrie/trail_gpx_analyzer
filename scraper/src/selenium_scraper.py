#!/usr/bin/env python3
"""
Selenium-based Strava Activity Scraper

Scrapes activity data and streams directly from Strava web pages.
Works with activities that are visible when logged in but not accessible via API.

Usage:
    python selenium_scraper.py --activity-id 16320173559
    python selenium_scraper.py --input activity_ids.txt
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import argparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class StravaSeleniumScraper:
    """Scraper for Strava activities using Selenium."""

    def __init__(self, headless: bool = True, session_file: str = "strava_session.json",
                 chrome_profile: str = None, profile_directory: str = "Default"):
        """Initialize the scraper.

        Args:
            headless: Run browser in headless mode
            session_file: Path to save/load session cookies
            chrome_profile: Path to Chrome user data directory (uses existing login)
            profile_directory: Chrome profile directory name (e.g., 'Default', 'Profile 1', 'Profile 2')
        """
        self.session_file = Path(__file__).parent.parent / session_file
        self.driver = None
        self.headless = headless
        self.chrome_profile = chrome_profile
        self.profile_directory = profile_directory

    def setup_driver(self):
        """Setup Chrome WebDriver with options."""
        chrome_options = Options()

        # Use existing Chrome profile if provided
        if self.chrome_profile:
            # Copy profile to temp location to avoid locking issues
            import shutil
            import tempfile

            source_profile = Path(self.chrome_profile) / self.profile_directory
            temp_dir = Path(tempfile.gettempdir()) / "selenium_chrome_profile"

            # Clean up old temp profile if exists
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

            # Copy profile - only copy essential files for cookies/login
            print(f"Copying Chrome profile (cookies and login data)...")
            temp_profile = temp_dir / self.profile_directory
            temp_profile.mkdir(parents=True, exist_ok=True)

            # Copy essential files for login session
            essential_files = ['Cookies', 'Cookies-journal', 'Login Data', 'Login Data-journal',
                             'Preferences', 'Local Storage', 'Session Storage', 'Web Data']

            for file_name in essential_files:
                source_file = source_profile / file_name
                if source_file.exists():
                    try:
                        if source_file.is_file():
                            shutil.copy2(source_file, temp_profile / file_name)
                        else:
                            shutil.copytree(source_file, temp_profile / file_name,
                                          ignore=shutil.ignore_patterns('*Lock*'))
                    except Exception as e:
                        print(f"Warning: Could not copy {file_name}: {e}")

            chrome_options.add_argument(f"user-data-dir={temp_dir}")
            chrome_options.add_argument(f"profile-directory={self.profile_directory}")
            print(f"Using Chrome profile: {temp_dir}/{self.profile_directory}")
        else:
            if self.headless:
                chrome_options.add_argument("--headless")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

        # Hide automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        self.driver = webdriver.Chrome(options=chrome_options)

        # Remove webdriver property
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
        })
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def login(self, email: str, password: str):
        """Login to Strava.

        Args:
            email: Strava account email
            password: Strava account password
        """
        print("Logging in to Strava...")

        self.driver.get("https://www.strava.com/login")

        # Wait for login form
        email_input = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        password_input = self.driver.find_element(By.ID, "password")

        # Enter credentials
        email_input.send_keys(email)
        password_input.send_keys(password)

        # Submit
        login_button = self.driver.find_element(By.ID, "login-button")
        login_button.click()

        # Wait for redirect
        WebDriverWait(self.driver, 10).until(
            EC.url_contains("dashboard")
        )

        print("Login successful!")

        # Save session
        self.save_session()

    def save_session(self):
        """Save browser cookies to file."""
        cookies = self.driver.get_cookies()
        with open(self.session_file, 'w') as f:
            json.dump(cookies, f)
        print(f"Session saved to {self.session_file}")

    def load_session(self) -> bool:
        """Load browser cookies from file.

        Returns:
            True if session loaded successfully
        """
        if not self.session_file.exists():
            return False

        try:
            with open(self.session_file, 'r') as f:
                cookies = json.load(f)

            # Navigate to Strava first
            self.driver.get("https://www.strava.com")

            # Add cookies
            for cookie in cookies:
                self.driver.add_cookie(cookie)

            # Verify session is valid
            self.driver.get("https://www.strava.com/dashboard")
            time.sleep(2)

            # Check if we're logged in
            if "login" in self.driver.current_url:
                return False

            print("Session loaded successfully!")
            return True

        except Exception as e:
            print(f"Failed to load session: {e}")
            return False

    def check_for_rate_limit(self) -> bool:
        """Check if current page indicates rate limiting.

        Returns:
            True if rate limited, False otherwise
        """
        try:
            # Check title
            if "Too Many Requests" in self.driver.title or "429" in self.driver.title:
                print("\n[!!!] RATE LIMIT DETECTED (Title check) [!!!]")
                return True
            
            # Check body text (careful not to read huge pages unnecessarily)
            # Usually rate limit pages are small
            if len(self.driver.page_source) < 5000:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                if "Too Many Requests" in body_text:
                    print("\n[!!!] RATE LIMIT DETECTED (Body check) [!!!]")
                    return True
        except:
            pass
        return False

    def get_activity_metadata(self, activity_id: int) -> Optional[Dict]:
        """Scrape activity metadata from activity page.

        Args:
            activity_id: Strava activity ID

        Returns:
            Dictionary with activity metadata or None if failed
        """
        url = f"https://www.strava.com/activities/{activity_id}"
        print(f"Fetching activity: {url}")

        self.driver.get(url)
        
        # Check for rate limit immediately
        if self.check_for_rate_limit():
            raise Exception("Strava Rate Limit Detected (429)")

        time.sleep(2)

        metadata = {'id': activity_id}

        try:
            # Extract from page source - more reliable than selectors
            page_source = self.driver.page_source

            # Check if activity exists
            if "Page Not Found" in page_source or "This activity is private" in page_source:
                print(f"  Activity {activity_id} not accessible")
                return None

            # Try to extract from embedded JSON data
            import re

            # Look for pageView data in script tags
            json_pattern = r'pageView\.activity\(\)\s*=\s*({.*?});'
            match = re.search(json_pattern, page_source, re.DOTALL)

            if match:
                try:
                    activity_data = json.loads(match.group(1))

                    metadata['name'] = activity_data.get('name', '')
                    metadata['sport_type'] = activity_data.get('type', 'Unknown')
                    metadata['distance'] = activity_data.get('distance', 0)
                    metadata['moving_time'] = activity_data.get('moving_time', 0)
                    metadata['elapsed_time'] = activity_data.get('elapsed_time', 0)
                    metadata['elevation_gain'] = activity_data.get('elevation_gain', 0)
                    metadata['start_date'] = activity_data.get('start_date_local', '')

                    print(f"  ✓ {metadata['name']}")
                    print(f"    Sport: {metadata['sport_type']}")
                    print(f"    Distance: {metadata.get('distance', 0)/1000:.2f} km")
                    print(f"    Elevation: {metadata.get('elevation_gain', 0):.0f} m")

                    return metadata

                except json.JSONDecodeError:
                    pass

            # Simple fallback: detect sport from Pace vs Speed in page
            if 'sport_type' not in metadata or metadata.get('sport_type') == 'Unknown':
                # Check for "Pace" label (indicates running/walking)
                if 'data-type="pace"' in page_source or '>Pace</div>' in page_source or '>Pace</' in page_source:
                    metadata['sport_type'] = 'Run'
                # Check for "Speed" label (indicates biking/other)
                elif 'data-type="speed"' in page_source or '>Speed</text>' in page_source or '>Speed</' in page_source:
                    metadata['sport_type'] = 'Ride'
                else:
                    metadata['sport_type'] = 'Unknown'

            # Fallback: Try CSS selectors (may not work if Strava changed layout)
            # Activity name - try multiple selectors
            name_selectors = [
                (By.CSS_SELECTOR, "h1.activity-name"),
                (By.CSS_SELECTOR, ".activity-summary-name"),
                (By.TAG_NAME, "h1"),
                (By.CSS_SELECTOR, "[data-testid='activity-name']")
            ]

            for by, selector in name_selectors:
                try:
                    name_elem = self.driver.find_element(by, selector)
                    metadata['name'] = name_elem.text.strip()
                    if metadata['name']:
                        break
                except:
                    continue

            # Sport type
            sport_selectors = [
                (By.CSS_SELECTOR, ".activity-type"),
                (By.CSS_SELECTOR, "[data-testid='activity-type']"),
                (By.CSS_SELECTOR, ".sport-icon")
            ]

            for by, selector in sport_selectors:
                try:
                    sport_elem = self.driver.find_element(by, selector)
                    metadata['sport_type'] = sport_elem.text.strip() or sport_elem.get_attribute("title")
                    if metadata['sport_type']:
                        break
                except:
                    continue

            if 'sport_type' not in metadata or not metadata['sport_type']:
                metadata['sport_type'] = 'Unknown'

            # Stats
            stats = {}
            stat_selectors = [
                ".stat",
                "[class*='stat']",
                ".inline-stats"
            ]

            for selector in stat_selectors:
                try:
                    stat_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for stat in stat_elements:
                        try:
                            text = stat.text.strip()
                            if text:
                                # Parse stat text (usually "label\nvalue" format)
                                lines = text.split('\n')
                                if len(lines) >= 2:
                                    stats[lines[0].lower()] = lines[1]
                        except:
                            continue
                    if stats:
                        break
                except:
                    continue

            metadata['stats'] = stats

            # Parse elevation from stats if not already set
            if 'elevation_gain' not in metadata or metadata['elevation_gain'] == 0:
                if 'elevation' in stats:
                    # Parse "344 m" or "1,123 ft" etc
                    import re
                    elev_text = stats['elevation']
                    elev_match = re.search(r'([\d,]+)\s*m', elev_text)
                    if elev_match:
                        elevation_str = elev_match.group(1).replace(',', '')
                        metadata['elevation_gain'] = float(elevation_str)

            print(f"  ✓ {metadata.get('name', 'Unnamed Activity')}")
            print(f"    Sport: {metadata.get('sport_type', 'Unknown')}")
            if stats:
                print(f"    Stats: {stats}")
            if 'elevation_gain' in metadata:
                print(f"    Elevation gain: {metadata['elevation_gain']:.0f} m")

            return metadata

        except Exception as e:
            print(f"  ✗ Error extracting metadata: {e}")
            import traceback
            traceback.print_exc()
            return metadata  # Return partial metadata

    def get_activity_streams(self, activity_id: int) -> Optional[Dict]:
        """Fetch activity stream data directly from Strava streams API.

        Args:
            activity_id: Strava activity ID

        Returns:
            Dictionary with stream arrays or None if failed
        """
        # Use Strava's streams endpoint directly
        stream_types = ['time', 'latlng', 'distance', 'altitude', 'velocity_smooth',
                       'heartrate', 'cadence', 'watts', 'temp', 'moving', 'grade_smooth']

        streams_url = f"https://www.strava.com/activities/{activity_id}/streams"
        params = '&'.join([f'stream_types[]={st}' for st in stream_types])
        url = f"{streams_url}?{params}"

        print(f"  Fetching streams from API endpoint...")
        print(f"  URL: {url}")

        try:
            self.driver.get(url)
            
            if self.check_for_rate_limit():
                raise Exception("Strava Rate Limit Detected (429)")

            time.sleep(3)  # Increased delay to avoid rate limiting

            # Get the JSON response from the page
            page_text = self.driver.find_element(By.TAG_NAME, "body").text

            # Check if empty or error page
            if not page_text or page_text.strip() == "":
                print(f"  ✗ Empty response from streams API")
                return None

            # Parse JSON first (if it's valid JSON, it's the data we want)
            try:
                streams_data = json.loads(page_text)
            except json.JSONDecodeError as e:
                # Not JSON - check for error pages
                if "Page Not Found" in page_text:
                    print(f"  ✗ Activity streams not found (404)")
                    return None

                if "You are not authorized" in page_text or "private" in page_text.lower():
                    print(f"  ✗ Activity is private or not accessible")
                    return None

                if "Too Many Requests" in page_text:
                    print(f"  ⚠ Rate limited! Waiting 60 seconds...")
                    time.sleep(60)
                    # Retry once
                    self.driver.get(url)
                    time.sleep(5)
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    try:
                        streams_data = json.loads(page_text)
                    except json.JSONDecodeError:
                        print(f"  ✗ Still rate limited or invalid response after retry")
                        return None
                else:
                    print(f"  ✗ Invalid JSON response. First 200 chars: {page_text[:200]}")
                    return None

            # The response is already a dictionary with stream types as keys
            if isinstance(streams_data, dict):
                print(f"  ✓ Extracted streams: {list(streams_data.keys())}")
                return streams_data
            # Or it might be an array of objects with 'type' and 'data'
            elif isinstance(streams_data, list):
                streams_dict = {}
                for stream in streams_data:
                    if isinstance(stream, dict):
                        stream_type = stream.get('type')
                        data = stream.get('data', [])
                        if stream_type:
                            streams_dict[stream_type] = data
                print(f"  ✓ Extracted streams: {list(streams_dict.keys())}")
                return streams_dict
            else:
                print(f"  ✗ Unexpected streams format: {type(streams_data)}")
                return None

        except Exception as e:
            print(f"  ✗ Error fetching streams: {e}")
            import traceback
            traceback.print_exc()
            return None

    def scrape_activity(self, activity_id: int, output_dir: str = "data/strava/",
                       min_elevation: int = 0, known_elevation: int = 0) -> bool:
        """Scrape complete activity data and save to files.

        Args:
            activity_id: Strava activity ID
            output_dir: Directory to save scraped data
            min_elevation: Minimum elevation gain in meters (skip if below)
            known_elevation: Elevation known from feed (used as fallback)

        Returns:
            True if successful
        """
        print(f"\n=== Scraping Activity {activity_id} ===\n")

        # Get metadata
        metadata = self.get_activity_metadata(activity_id)
        if not metadata:
            return False

        # Fallback to known elevation if page scrape failed to find it
        if metadata.get('elevation_gain', 0) == 0 and known_elevation > 0:
            print(f"    Using known elevation from feed: {known_elevation}m")
            metadata['elevation_gain'] = known_elevation

        # Check elevation threshold
        elevation_gain = metadata.get('elevation_gain', 0)
        if elevation_gain < min_elevation:
            print(f"  ⊘ Skipped: Elevation {elevation_gain:.0f}m < {min_elevation}m threshold")
            return False

        # Get streams
        streams = self.get_activity_streams(activity_id)
        if not streams:
            print("Warning: No stream data found")

        # Save to files
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save metadata
        metadata_file = output_path / f"{activity_id}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"  → Saved metadata: {metadata_file}")

        # Save streams
        if streams:
            streams_file = output_path / f"{activity_id}_streams.json"
            with open(streams_file, 'w') as f:
                json.dump(streams, f, indent=2)
            print(f"  → Saved streams: {streams_file}")

        return True

    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Strava activities using Selenium",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First time - will prompt for login
  python selenium_scraper.py --activity-id 16320173559

  # Subsequent runs use saved session
  python selenium_scraper.py --activity-id 16320173559

  # Multiple activities
  python selenium_scraper.py --input activity_ids.txt

  # Show browser window (non-headless)
  python selenium_scraper.py --activity-id 16320173559 --show-browser
        """
    )

    parser.add_argument('--activity-id', type=int, help='Single activity ID to scrape')
    parser.add_argument('--input', help='File with activity IDs (one per line)')
    parser.add_argument('--email', help='Strava email (will prompt if not provided)')
    parser.add_argument('--password', help='Strava password (will prompt if not provided)')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window')
    parser.add_argument('--chrome-profile', help='Path to Chrome user data directory (e.g., ~/.config/google-chrome)')
    parser.add_argument('--profile-directory', default='Default', help='Chrome profile directory name (e.g., "Default", "Profile 1")')
    parser.add_argument('--output-dir', default='data/strava/', help='Output directory')

    args = parser.parse_args()

    if not args.activity_id and not args.input:
        parser.print_help()
        return

    # Initialize scraper
    scraper = StravaSeleniumScraper(
        headless=not args.show_browser,
        chrome_profile=args.chrome_profile,
        profile_directory=args.profile_directory
    )

    try:
        scraper.setup_driver()

        # If using Chrome profile, skip login
        if args.chrome_profile:
            print("Using existing Chrome profile - skipping login")
            # Test navigation to Strava
            print("Navigating to Strava dashboard...")
            scraper.driver.get("https://www.strava.com/dashboard")
            time.sleep(3)
            print(f"Current URL: {scraper.driver.current_url}")

            # Check if we need manual login
            if "login" in scraper.driver.current_url or "verify" in scraper.driver.current_url.lower():
                print("\n" + "="*60)
                print("MANUAL LOGIN REQUIRED")
                print("="*60)
                print("Please login manually in the browser window.")
                print("Complete any 2FA/verification steps.")
                print("Once you see the Strava dashboard, press ENTER here...")
                print("="*60 + "\n")
                input("Press ENTER when logged in: ")

                # Save the session after manual login
                scraper.save_session()
                print("Session saved for future use!")
        # Try to load existing session
        elif not scraper.load_session():
            # Need to login
            email = args.email
            password = args.password

            if not email:
                email = input("Strava email: ")
            if not password:
                import getpass
                password = getpass.getpass("Strava password: ")

            scraper.login(email, password)

        # Scrape activities
        if args.activity_id:
            # Single activity
            success = scraper.scrape_activity(args.activity_id, args.output_dir)
            print("\n✓ Successfully scraped" if success else "\n✗ Failed to scrape")

        elif args.input:
            # Multiple activities from file
            if not os.path.exists(args.input):
                print(f"ERROR: File not found: {args.input}")
                return

            activity_ids = []
            with open(args.input, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            activity_ids.append(int(line))
                        except ValueError:
                            print(f"WARNING: Invalid activity ID: {line}")

            print(f"\nScraping {len(activity_ids)} activities...\n")

            successful = 0
            failed = 0

            for i, activity_id in enumerate(activity_ids, 1):
                print(f"\n[{i}/{len(activity_ids)}]")
                if scraper.scrape_activity(activity_id, args.output_dir):
                    successful += 1
                else:
                    failed += 1

                # Brief pause between requests
                if i < len(activity_ids):
                    time.sleep(2)

            print(f"\n=== Summary ===")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            print(f"Total: {successful + failed}")

    finally:
        scraper.close()


if __name__ == '__main__':
    main()
