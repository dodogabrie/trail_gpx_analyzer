#!/usr/bin/env python3
"""
Scrape activities from athlete profile using modular components.

Usage:
    # Last 4 weeks, all sports
    python scrape_athlete.py 5452411

    # Last 8 weeks, runs only
    python scrape_athlete.py 5452411 --weeks 8 --sport Run

    # Use homepage feed instead of intervals
    python scrape_athlete.py 5452411 --use-homepage

    # Multiple athletes
    python scrape_athlete.py 5452411 13538059 --weeks 4 --sport Run
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.selenium_scraper import StravaSeleniumScraper
from src.athlete_scraper import AthleteScraper


def main():
    parser = argparse.ArgumentParser(
        description="Scrape activities from athlete profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single athlete - last 4 weeks
  python scrape_athlete.py 5452411

  # Multiple athletes - last 8 weeks, runs only
  python scrape_athlete.py 5452411 13538059 --weeks 8 --sport Run

  # Use homepage feed (faster, fewer activities)
  python scrape_athlete.py 5452411 --use-homepage
        """
    )

    parser.add_argument('athlete_ids', nargs='+', type=int, help='Athlete ID(s)')
    parser.add_argument('--weeks', type=int, default=4, help='Weeks to look back (default: 4)')
    parser.add_argument('--sport', help='Filter by sport (e.g., Run, Ride)')
    parser.add_argument('--use-homepage', action='store_true',
                       help='Use homepage feed instead of weekly intervals')
    parser.add_argument('--chrome-profile', help='Chrome user data directory')
    parser.add_argument('--profile-directory', default='Default', help='Chrome profile name')
    parser.add_argument('--show-browser', action='store_true', help='Show browser')
    parser.add_argument('--output-dir', default='data/strava/athletes/', help='Output directory')

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

        # Initialize athlete scraper
        athlete_scraper = AthleteScraper(scraper)

        # Scrape all athletes
        print(f"\n{'='*70}")
        print(f"SCRAPING {len(args.athlete_ids)} ATHLETE(S)")
        print(f"{'='*70}\n")

        for i, athlete_id in enumerate(args.athlete_ids, 1):
            print(f"\n[{i}/{len(args.athlete_ids)}] Athlete {athlete_id}")
            print("-" * 70)

            athlete_scraper.scrape_athlete(
                athlete_id=athlete_id,
                output_dir=args.output_dir,
                weeks_back=args.weeks,
                sport_filter=args.sport,
                use_intervals=not args.use_homepage
            )

        print(f"\n{'='*70}")
        print(f"COMPLETED: Scraped {len(args.athlete_ids)} athlete(s)")
        print(f"{'='*70}\n")

    finally:
        scraper.close()


if __name__ == '__main__':
    main()
