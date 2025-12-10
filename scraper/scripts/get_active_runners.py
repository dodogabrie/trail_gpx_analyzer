#!/usr/bin/env python3
"""
Extract athlete IDs from following list that have recent running activities.

Usage:
    # Get all following athletes with runs in last 7 days
    python get_active_runners.py 9474525

    # Look back 14 days
    python get_active_runners.py 9474525 --days 14

    # Save to file
    python get_active_runners.py 9474525 --output active_runners.txt
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.selenium_scraper import StravaSeleniumScraper
from src.following_extractor import FollowingExtractor
from src.athlete_filter import AthleteFilter


def main():
    parser = argparse.ArgumentParser(
        description="Get athlete IDs from following list with recent runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get athletes with runs in last 7 days
  python get_active_runners.py 9474525

  # Look back 14 days
  python get_active_runners.py 9474525 --days 14

  # With 60 second timeout
  python get_active_runners.py 9474525 --timeout 60

  # Save to file
  python get_active_runners.py 9474525 --output active_runners.txt
        """
    )

    parser.add_argument('athlete_id', type=int, help='Source athlete ID')
    parser.add_argument('--days', type=int, default=7,
                       help='Days to look back for recent runs (default: 7)')
    parser.add_argument('--timeout', type=int,
                       help='Timeout in seconds for scanning athletes')
    parser.add_argument('--max-scrolls', type=int, default=10,
                       help='Max scrolls to load following list (default: 10)')
    parser.add_argument('--output', help='Output file to save athlete IDs')
    parser.add_argument('--chrome-profile', help='Chrome user data directory')
    parser.add_argument('--profile-directory', default='Default',
                       help='Chrome profile directory name (default: Default)')
    parser.add_argument('--show-browser', action='store_true', help='Show browser')

    args = parser.parse_args()

    # Initialize scraper
    scraper = StravaSeleniumScraper(
        headless=not args.show_browser,
        chrome_profile=args.chrome_profile,
        profile_directory=args.profile_directory
    )

    try:
        scraper.setup_driver()

        # Login
        if args.chrome_profile:
            scraper.driver.get("https://www.strava.com/dashboard")
            time.sleep(3)
            if "login" in scraper.driver.current_url:
                print("Please login...")
                input("Press ENTER when logged in: ")
                scraper.save_session()
        elif not scraper.load_session():
            print("No session. Use --chrome-profile to login")
            return

        # Initialize modules
        following_extractor = FollowingExtractor(scraper.driver)
        athlete_filter = AthleteFilter(scraper.driver)

        # Get following list
        print(f"\n=== Getting Following List ===")
        following_ids = following_extractor.get_all_following(args.athlete_id, args.max_scrolls)

        if not following_ids:
            print("No athletes found in following list")
            return

        # Filter for active runners
        print(f"\n=== Filtering for Active Runners ===")
        active_runner_ids = athlete_filter.filter_athletes_with_recent_runs(
            following_ids,
            days_back=args.days,
            timeout_seconds=args.timeout
        )

        # Display results
        print(f"\n=== Results ===")
        print(f"Total following: {len(following_ids)}")
        print(f"Active runners: {len(active_runner_ids)}")
        print(f"\nActive runner IDs:")
        for athlete_id in active_runner_ids:
            print(f"  {athlete_id}")

        # Save to file if requested
        if args.output:
            output_file = Path(args.output)
            with open(output_file, 'w') as f:
                for athlete_id in active_runner_ids:
                    f.write(f"{athlete_id}\n")
            print(f"\nSaved to: {output_file}")

    finally:
        scraper.close()


if __name__ == '__main__':
    main()
