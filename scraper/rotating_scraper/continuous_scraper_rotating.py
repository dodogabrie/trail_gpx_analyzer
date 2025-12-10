#!/usr/bin/env python3
"""Continuous recursive scraper with token rotation.

Uses token rotation to bypass rate limits. Can scrape 5-10x more than single token.
Reuses existing scripts/src infrastructure but swaps Selenium for API client.
"""

import sys
import time
import json
import signal
import argparse
from pathlib import Path
from datetime import datetime
from typing import Set, List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import token rotation
from rotating_scraper.token_rotator import TokenRotator
from rotating_scraper.strava_api_client import StravaAPIClient

# Import existing modules (using Selenium-based ones for profile navigation)
from src.selenium_scraper import StravaSeleniumScraper
from src.following_extractor import FollowingExtractor
from src.athlete_filter import AthleteFilter
from src.athlete_page import AthletePage
from src.interval_navigator import IntervalNavigator
from src.activity_extractor import ActivityExtractor


class ScraperState:
    """Manage scraping state with persistence."""

    def __init__(self, state_file: str = "scraper_state.json"):
        """Initialize state manager."""
        self.state_file = Path(__file__).parent.parent / state_file
        self.seed_athlete_id: Optional[int] = None
        self.weeks_to_scrape: int = 5
        self.days_for_active_filter: int = 7
        self.visited_athletes: Set[int] = set()
        self.queue: List[int] = []
        self.total_activities_scraped: int = 0
        self.start_time: Optional[str] = None
        self.last_update: Optional[str] = None

    def load(self) -> bool:
        """Load state from file."""
        if not self.state_file.exists():
            return False

        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)

            self.seed_athlete_id = data.get('seed_athlete_id')
            self.weeks_to_scrape = data.get('weeks_to_scrape', 5)
            self.days_for_active_filter = data.get('days_for_active_filter', 7)
            self.visited_athletes = set(data.get('visited_athletes', []))
            self.queue = data.get('queue', [])
            self.total_activities_scraped = data.get('total_activities_scraped', 0)
            self.start_time = data.get('start_time')
            self.last_update = data.get('last_update')

            print(f"\nLoaded state from {self.state_file}")
            print(f"  Visited: {len(self.visited_athletes)} athletes")
            print(f"  Queue: {len(self.queue)} athletes")
            print(f"  Activities: {self.total_activities_scraped}\n")

            return True

        except Exception as e:
            print(f"Error loading state: {e}")
            return False

    def save(self):
        """Save current state to file."""
        self.last_update = datetime.now().isoformat()

        data = {
            'seed_athlete_id': self.seed_athlete_id,
            'weeks_to_scrape': self.weeks_to_scrape,
            'days_for_active_filter': self.days_for_active_filter,
            'visited_athletes': list(self.visited_athletes),
            'queue': self.queue,
            'total_activities_scraped': self.total_activities_scraped,
            'start_time': self.start_time,
            'last_update': self.last_update
        }

        try:
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")

    def add_to_queue(self, athlete_ids: List[int]):
        """Add athletes to queue if not visited."""
        added = 0
        for athlete_id in athlete_ids:
            if athlete_id not in self.visited_athletes and athlete_id not in self.queue:
                self.queue.append(athlete_id)
                added += 1

        if added > 0:
            print(f"  Added {added} new athletes to queue")

    def mark_visited(self, athlete_id: int):
        """Mark athlete as visited."""
        self.visited_athletes.add(athlete_id)

    def initialize(self, seed_athlete_id: int, weeks: int, days_filter: int):
        """Initialize fresh state."""
        self.seed_athlete_id = seed_athlete_id
        self.weeks_to_scrape = weeks
        self.days_for_active_filter = days_filter
        self.queue = [seed_athlete_id]
        self.start_time = datetime.now().isoformat()


class GracefulShutdown:
    """Handle graceful shutdown on signals."""

    def __init__(self):
        """Initialize signal handlers."""
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signal."""
        print("\n\nShutdown signal received...")
        self.shutdown_requested = True


def get_activity_ids_from_profile(athlete_id: int, weeks: int, selenium_scraper) -> List[int]:
    """Get activity IDs from athlete profile using Selenium.

    Args:
        athlete_id: Athlete ID
        weeks: Weeks to look back
        selenium_scraper: Selenium scraper instance

    Returns:
        List of activity IDs
    """
    athlete_page = AthletePage(selenium_scraper.driver)
    interval_nav = IntervalNavigator(selenium_scraper.driver)
    activity_extractor = ActivityExtractor(selenium_scraper.driver)

    # Navigate
    if not athlete_page.navigate_to_athlete(athlete_id):
        return []

    # Get intervals
    intervals = interval_nav.get_recent_intervals(weeks)
    if not intervals:
        return []

    # Extract activities
    all_activity_ids = []
    seen_ids = set()

    for interval_bar in intervals:
        if not interval_nav.click_interval(interval_bar):
            continue

        activities = activity_extractor.extract_all_activities("Run")

        for activity in activities:
            if activity['id'] and activity['id'] not in seen_ids:
                seen_ids.add(activity['id'])
                all_activity_ids.append(activity['id'])

    return all_activity_ids


def download_activities_with_rotation(activity_ids: List[int], output_dir: Path,
                                      rotator: TokenRotator, min_elevation: int = 200) -> Dict:
    """Download activities using token rotation.

    Args:
        activity_ids: List of activity IDs
        output_dir: Output directory
        rotator: Token rotator instance
        min_elevation: Minimum elevation

    Returns:
        Stats dict
    """
    successful = 0
    failed = 0
    skipped = 0

    for i, activity_id in enumerate(activity_ids, 1):
        print(f"\n[{i}/{len(activity_ids)}] Activity {activity_id}")

        # Check if already exists
        metadata_file = output_dir / f"{activity_id}_metadata.json"
        streams_file = output_dir / f"{activity_id}_streams.json"

        if metadata_file.exists() and streams_file.exists():
            print(f"  ⊘ Already exists (skipped)")
            skipped += 1
            successful += 1
            continue

        # Get current token
        token = rotator.get_access_token()
        if not token:
            print(f"  ✗ No valid token available")
            failed += 1
            continue

        # Create API client
        client = StravaAPIClient(token)
        app = rotator.get_current_app()

        # Try to download
        success = client.scrape_activity(activity_id, str(output_dir), min_elevation)

        if success:
            rotator.record_request()
            successful += 1
            time.sleep(2)  # Delay between activities
        else:
            # Check if rate limited
            if rotator.is_rate_limited():
                print(f"[{app['name']}] Rate limit reached, rotating...")

                if not rotator.rotate_to_next():
                    print(f"[Rate Limit] All apps exhausted, waiting...")
                    if not rotator.wait_for_available(timeout=900):
                        print(f"Stopping - all apps rate limited")
                        break

            failed += 1

    return {
        'total': len(activity_ids),
        'successful': successful,
        'failed': failed,
        'skipped': skipped
    }


def run_continuous_scraper(seed_athlete_id: int, weeks: int, days_filter: int,
                          timeout_hours: int, state_file: str, resume: bool):
    """Run continuous scraper with token rotation."""
    # Initialize state
    state = ScraperState(state_file)

    if resume:
        if not state.load():
            print("No state file found to resume from")
            return
    else:
        state.initialize(seed_athlete_id, weeks, days_filter)

    # Initialize token rotator
    print("Initializing token rotator...")
    try:
        rotator = TokenRotator()
        print(rotator.get_status())
    except Exception as e:
        print(f"Failed to initialize token rotator: {e}")
        return

    # Initialize Selenium scraper (for profile navigation only)
    print("Initializing browser for profile navigation...")
    selenium_scraper = StravaSeleniumScraper(headless=True)

    try:
        selenium_scraper.setup_driver()

        if not selenium_scraper.load_session():
            print("\nNo Selenium session. Using token-only mode (limited features)")
            selenium_scraper = None
        else:
            # Initialize profile navigation modules
            following_extractor = FollowingExtractor(selenium_scraper.driver)
            athlete_filter = AthleteFilter(selenium_scraper.driver)

        shutdown = GracefulShutdown()
        start_time = time.time()

        print(f"\n{'='*70}")
        print(f"CONTINUOUS SCRAPER WITH TOKEN ROTATION STARTED")
        print(f"{'='*70}\n")

        # Main loop
        while state.queue and not shutdown.shutdown_requested:
            # Check timeout
            if time.time() - start_time > timeout_hours * 3600:
                print(f"\nTimeout reached ({timeout_hours}h)")
                break

            athlete_id = state.queue.pop(0)

            if athlete_id in state.visited_athletes:
                continue

            print(f"\n{'='*70}")
            print(f"Athlete {athlete_id}")
            print(f"Queue: {len(state.queue)} | Visited: {len(state.visited_athletes)}")
            print(f"Activities: {state.total_activities_scraped}")
            print(f"{'='*70}\n")

            # Create output directory
            athlete_dir = Path("../data/strava/athletes") / str(athlete_id)
            athlete_dir.mkdir(parents=True, exist_ok=True)

            # Get activity IDs
            if selenium_scraper:
                activity_ids = get_activity_ids_from_profile(athlete_id, weeks, selenium_scraper)
            else:
                # Fallback: use API to get recent activities
                token = rotator.get_access_token()
                if token:
                    client = StravaAPIClient(token)
                    activities = client.get_athlete_activities(per_page=200)
                    activity_ids = [a['id'] for a in activities] if activities else []
                else:
                    activity_ids = []

            if not activity_ids:
                state.mark_visited(athlete_id)
                state.save()
                continue

            print(f"Found {len(activity_ids)} activities")

            # Download activities
            result = download_activities_with_rotation(activity_ids, athlete_dir, rotator, min_elevation=200)

            state.total_activities_scraped += result['successful']
            state.mark_visited(athlete_id)

            # Get following and filter
            if selenium_scraper:
                following_ids = following_extractor.get_all_following(athlete_id)

                if following_ids:
                    active_runners = athlete_filter.filter_athletes_with_recent_runs(
                        following_ids,
                        days_back=days_filter,
                        max_results=5
                    )
                    state.add_to_queue(active_runners)

            state.save()

        # Final stats
        print(f"\n{'='*70}")
        print(f"FINAL STATISTICS")
        print(f"{'='*70}")
        print(f"Visited: {len(state.visited_athletes)} athletes")
        print(f"Activities: {state.total_activities_scraped}")
        print(rotator.get_status())

    finally:
        if selenium_scraper:
            selenium_scraper.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Continuous scraper with token rotation")

    parser.add_argument('athlete_id', type=int, help='Seed athlete ID')
    parser.add_argument('--weeks', type=int, default=5, help='Weeks to scrape')
    parser.add_argument('--days-filter', type=int, default=7, help='Days for active filter')
    parser.add_argument('--timeout', type=int, default=10, help='Timeout in hours')
    parser.add_argument('--state-file', default='scraper_state.json', help='State file')
    parser.add_argument('--resume', action='store_true', help='Resume from state')
    parser.add_argument('--reset', action='store_true', help='Reset state')

    args = parser.parse_args()

    if args.reset:
        state_path = Path(__file__).parent.parent / args.state_file
        if state_path.exists():
            state_path.unlink()
            print(f"Deleted state file: {state_path}\n")

    run_continuous_scraper(
        seed_athlete_id=args.athlete_id,
        weeks=args.weeks,
        days_filter=args.days_filter,
        timeout_hours=args.timeout,
        state_file=args.state_file,
        resume=args.resume
    )


if __name__ == '__main__':
    main()
