#!/usr/bin/env python3
"""Test elevation extraction from athlete profiles.

Usage:
    python tests/test_elevation_extraction.py 15931965
    python tests/test_elevation_extraction.py 15931965 --weeks 8
    python tests/test_elevation_extraction.py 15931965 --weeks 4 --headless
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.selenium_scraper import StravaSeleniumScraper
from src.interval_navigator import IntervalNavigator


def test_elevation_extraction(athlete_id: int, weeks_back: int = 4, headless: bool = False):
    """Test elevation extraction for an athlete.

    Args:
        athlete_id: Strava athlete ID
        weeks_back: Number of weeks to test
        headless: Whether to run in headless mode
    """
    print(f"\n{'='*70}")
    print(f"TESTING ELEVATION EXTRACTION")
    print(f"{'='*70}")
    print(f"Athlete ID: {athlete_id}")
    print(f"Weeks to check: {weeks_back}")
    print(f"Headless: {headless}")
    print(f"{'='*70}\n")

    scraper = StravaSeleniumScraper(headless=headless)

    try:
        # Setup driver
        print("Initializing browser...")
        scraper.setup_driver()

        # Load session (like continuous_scraper does)
        if not scraper.load_session():
            print("\n❌ No Strava session found.")
            print("Please run scripts/scrape_athlete.py once to create a session,")
            print("or use continuous_scraper.py to login first")
            return

        print("✓ Session loaded\n")

        # Navigate to athlete
        url = f"https://www.strava.com/pros/{athlete_id}"
        print(f"Navigating to {url}...")
        scraper.driver.get(url)

        import time
        time.sleep(3)

        print("✓ Page loaded\n")

        # Initialize interval navigator
        navigator = IntervalNavigator(scraper.driver)

        # Get recent intervals
        print(f"Finding recent {weeks_back} weeks...")
        intervals = navigator.get_recent_intervals(weeks_back)

        if not intervals:
            print("❌ No interval bars found!")
            print("Make sure you're on an athlete profile page with activity data")
            return

        print(f"✓ Found {len(intervals)} interval bars\n")

        # Extract elevation for each week
        print(f"{'Week':<8} {'Interval ID':<20} {'Elevation (m)':<15}")
        print("-" * 45)

        week_elevations = []
        for i, interval in enumerate(intervals, 1):
            interval_id = navigator.get_interval_id(interval)
            elevation = navigator.get_interval_elevation(interval)

            week_elevations.append(elevation)
            print(f"{i:<8} {interval_id:<20} {elevation:<15}")

        # Calculate total
        total_elevation = sum(week_elevations)

        print("-" * 45)
        print(f"{'TOTAL':<8} {'':<20} {total_elevation:<15}")
        print()

        # Summary
        print(f"\n{'='*70}")
        print(f"SUMMARY")
        print(f"{'='*70}")
        print(f"Weeks analyzed: {len(week_elevations)}")
        print(f"Total elevation: {total_elevation}m")
        print(f"Average per week: {total_elevation // len(week_elevations) if week_elevations else 0}m")
        print(f"{'='*70}\n")

        # Compare with get_total_elevation_for_weeks
        print("Testing get_total_elevation_for_weeks() method...")

        # Need to navigate back to athlete page
        scraper.driver.get(url)
        time.sleep(3)

        navigator2 = IntervalNavigator(scraper.driver)
        total_from_method = navigator2.get_total_elevation_for_weeks(weeks_back)

        print(f"Result: {total_from_method}m")

        if total_from_method == total_elevation:
            print("✓ Method returns correct total!")
        else:
            print(f"⚠ Warning: Method returned {total_from_method}m but manual sum was {total_elevation}m")

        print("\n✓ Test completed successfully!")

        if not headless:
            print("\nBrowser will stay open for 30 seconds so you can verify visually...")
            time.sleep(30)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nClosing browser...")
        scraper.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test elevation extraction from athlete profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test athlete 15931965 for 4 weeks (default)
  python tests/test_elevation_extraction.py 15931965

  # Test for 8 weeks
  python tests/test_elevation_extraction.py 15931965 --weeks 8

  # Test in headless mode
  python tests/test_elevation_extraction.py 15931965 --weeks 4 --headless
        """
    )

    parser.add_argument('athlete_id', type=int,
                       help='Strava athlete ID to test')
    parser.add_argument('--weeks', type=int, default=4,
                       help='Number of weeks to check (default: 4)')
    parser.add_argument('--headless', action='store_true',
                       help='Run in headless mode (no visible browser)')

    args = parser.parse_args()

    test_elevation_extraction(
        athlete_id=args.athlete_id,
        weeks_back=args.weeks,
        headless=args.headless
    )


if __name__ == '__main__':
    main()
