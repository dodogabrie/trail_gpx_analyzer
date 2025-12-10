#!/usr/bin/env python3
"""Continuous recursive Strava scraper.

This script implements a BFS-style recursive scraper that:
- Starts from a seed athlete ID
- Scrapes their activities (configurable weeks)
- Extracts following list for active runners
- Recursively scrapes each active runner
- Tracks visited athletes to avoid duplicates
- Saves state for resume capability
- Runs until manual stop or timeout

Usage:
    # Start fresh scraping
    python continuous_scraper.py 5452411 --weeks 5 --days-filter 7

    # Resume from previous run
    python continuous_scraper.py 5452411 --resume

    # Reset and start over
    python continuous_scraper.py 5452411 --weeks 5 --reset

    # Custom timeout (5 hours)
    python continuous_scraper.py 5452411 --weeks 3 --timeout 5
"""

import sys
import time
import json
import signal
import argparse
from pathlib import Path
from datetime import datetime
from typing import Set, List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.selenium_scraper import StravaSeleniumScraper
from src.athlete_scraper import AthleteScraper
from src.following_extractor import FollowingExtractor
from src.athlete_filter import AthleteFilter


class ScraperState:
    """Manage scraping state with persistence."""

    def __init__(self, state_file: str = "scraper_state.json"):
        """Initialize state manager.

        Args:
            state_file: Path to state file for persistence
        """
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
        """Load state from file if exists.

        Returns:
            True if state loaded, False if file doesn't exist
        """
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
        """Add athletes to queue if not already visited.

        Args:
            athlete_ids: List of athlete IDs to add
        """
        added = 0
        for athlete_id in athlete_ids:
            if athlete_id not in self.visited_athletes and athlete_id not in self.queue:
                self.queue.append(athlete_id)
                added += 1

        if added > 0:
            print(f"  Added {added} new athletes to queue")

    def mark_visited(self, athlete_id: int):
        """Mark athlete as visited.

        Args:
            athlete_id: Athlete ID to mark as visited
        """
        self.visited_athletes.add(athlete_id)

    def initialize(self, seed_athlete_id: int, weeks: int, days_filter: int):
        """Initialize fresh state.

        Args:
            seed_athlete_id: Starting athlete ID
            weeks: Weeks to scrape per athlete
            days_filter: Days for active runner filter
        """
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
        """Handle shutdown signal.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        print("\n\nShutdown signal received...")
        self.shutdown_requested = True


def print_progress(state: ScraperState, athlete_id: int, start_time: float):
    """Print live progress statistics.

    Args:
        state: Current scraper state
        athlete_id: Current athlete being processed
        start_time: Start time timestamp
    """
    elapsed_hours = (time.time() - start_time) / 3600
    activities_per_hour = state.total_activities_scraped / elapsed_hours if elapsed_hours > 0 else 0

    print(f"\n{'='*70}")
    print(f"Runtime: {elapsed_hours:.1f}h | Rate: {activities_per_hour:.1f} activities/hour")
    print(f"Current: Athlete {athlete_id}")
    print(f"Queue: {len(state.queue)} athletes | Visited: {len(state.visited_athletes)} athletes")
    print(f"Total activities: {state.total_activities_scraped} (with latlng+altitude)")
    print(f"{'='*70}\n")


def run_continuous_scraper(seed_athlete_id: int, weeks: int, days_filter: int,
                          timeout_hours: int, state_file: str, resume: bool,
                          top_weeks_mode: bool = False):
    """Run continuous recursive scraper.

    Args:
        seed_athlete_id: Starting athlete ID
        weeks: Weeks of activities to scrape per athlete
        days_filter: Days to look back for active runner filter
        timeout_hours: Maximum runtime in hours
        state_file: Path to state file
        resume: Whether to resume from existing state
        top_weeks_mode: If True, scrape weeks with highest volume
    """
    # Initialize state
    state = ScraperState(state_file)

    if resume:
        if not state.load():
            print("No state file found to resume from")
            return
    else:
        state.initialize(seed_athlete_id, weeks, days_filter)

    # Initialize graceful shutdown handler
    shutdown = GracefulShutdown()

    # Setup scraper
    print("Initializing browser...")
    scraper = StravaSeleniumScraper(headless=True)

    try:
        scraper.setup_driver()

        # Load session
        if not scraper.load_session():
            print("\nNo Strava session found.")
            print("Please use --chrome-profile to login first, or run scrape_athlete.py once to create session")
            return

        # Initialize modules
        athlete_scraper = AthleteScraper(scraper)
        following_extractor = FollowingExtractor(scraper.driver)
        athlete_filter = AthleteFilter(scraper.driver)

        start_time = time.time()

        print(f"\n{'='*70}")
        print(f"CONTINUOUS SCRAPER STARTED")
        print(f"{'='*70}")
        print(f"Seed athlete: {seed_athlete_id}")
        print(f"Weeks to scrape: {weeks} ({'Top Volume' if top_weeks_mode else 'Recent'})")
        print(f"Active filter: {days_filter} days")
        print(f"Timeout: {timeout_hours} hours")
        print(f"Queue size: {len(state.queue)}")
        print(f"{'='*70}\n")

        # Main scraping loop
        while state.queue and not shutdown.shutdown_requested:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_hours * 3600:
                print(f"\nTimeout reached ({timeout_hours}h)")
                break

            # Get next athlete
            athlete_id = state.queue.pop(0)

            # Skip if already visited
            if athlete_id in state.visited_athletes:
                continue

            # Print progress
            print_progress(state, athlete_id, start_time)

            # 1. Scrape athlete activities
            try:
                print(f"Scraping activities...")
                result = athlete_scraper.scrape_athlete(
                    athlete_id=athlete_id,
                    weeks_back=weeks,
                    sport_filter="Run",
                    use_intervals=True,
                    skip_existing=True,
                    require_latlng=True,
                    require_altitude=True,
                    min_elevation=200,
                    top_weeks_mode=top_weeks_mode
                )

                # Update activity count
                state.total_activities_scraped += result.get('successful', 0)
                print(f"\nScraped {result.get('successful', 0)} valid activities")

            except Exception as e:
                print(f"Error scraping athlete {athlete_id}: {e}")
                
                if "Rate Limit" in str(e):
                    print("\n[!!!] CRITICAL: Rate Limit Detected. Stopping scraper to protect account.")
                    # Do NOT mark as visited so we can retry later
                    state.save()
                    break

                # Mark as visited even if failed to avoid retry loop
                state.mark_visited(athlete_id)
                state.save()
                continue

            # Mark as visited
            state.mark_visited(athlete_id)

            # 2. Get following list
            try:
                print(f"\nFetching following list...")
                following_ids = following_extractor.get_all_following(athlete_id, max_scrolls=10)
                print(f"Found {len(following_ids)} following")

            except Exception as e:
                print(f"Error getting following list: {e}")
                following_ids = []

            # 3. Filter for active runners (stop after finding 5)
            if following_ids:
                try:
                    print(f"\nFiltering for active runners...")
                    active_runners = athlete_filter.filter_athletes_with_recent_runs(
                        following_ids,
                        days_back=days_filter,
                        weeks_back=weeks,
                        min_elevation_per_week=800,
                        min_long_run_km=30.0,
                        timeout_seconds=None,
                        max_results=5
                    )
                    print(f"Found {len(active_runners)} active runners")

                    # 4. Add to queue
                    state.add_to_queue(active_runners)

                except Exception as e:
                    print(f"Error filtering athletes: {e}")

            # 5. Save state
            state.save()

            # Small delay between athletes
            time.sleep(3)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user - saving state...")
        state.save()

    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        state.save()

    finally:
        scraper.close()

        # Final statistics
        elapsed_hours = (time.time() - start_time) / 3600

        print(f"\n{'='*70}")
        print(f"FINAL STATISTICS")
        print(f"{'='*70}")
        print(f"Runtime: {elapsed_hours:.1f} hours")
        print(f"Visited athletes: {len(state.visited_athletes)}")
        print(f"Total activities scraped: {state.total_activities_scraped}")
        print(f"Remaining in queue: {len(state.queue)}")
        if elapsed_hours > 0:
            print(f"Rate: {state.total_activities_scraped / elapsed_hours:.1f} activities/hour")
        print(f"State saved to: {state.state_file}")
        print(f"{'='*70}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Continuous recursive Strava scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start fresh scraping
  python continuous_scraper.py 5452411 --weeks 5 --days-filter 7

  # Scrape highest volume weeks instead of recent ones
  python continuous_scraper.py 5452411 --weeks 5 --top-weeks

  # Resume from previous run
  python continuous_scraper.py 5452411 --resume

  # Reset and start over
  python continuous_scraper.py 5452411 --weeks 5 --reset

  # Custom timeout (5 hours)
  python continuous_scraper.py 5452411 --weeks 3 --timeout 5

Stop gracefully:
  - Press Ctrl+C to save state and exit
  - Wait for timeout for automatic shutdown
        """
    )

    parser.add_argument('athlete_id', type=int,
                       help='Seed athlete ID to start from')
    parser.add_argument('--weeks', type=int, default=5,
                       help='Weeks of activities to scrape per athlete (default: 5)')
    parser.add_argument('--days-filter', type=int, default=7,
                       help='Days to look back for active runner filter (default: 7)')
    parser.add_argument('--timeout', type=int, default=10,
                       help='Timeout in hours (default: 10)')
    parser.add_argument('--state-file', default='scraper_state.json',
                       help='State file for resume capability (default: scraper_state.json)')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from existing state file')
    parser.add_argument('--reset', action='store_true',
                       help='Reset state and start fresh')
    parser.add_argument('--top-weeks', action='store_true',
                       help='Scrape weeks with highest volume instead of most recent')

    args = parser.parse_args()

    # Handle reset
    if args.reset:
        state_path = Path(__file__).parent.parent / args.state_file
        if state_path.exists():
            state_path.unlink()
            print(f"Deleted state file: {state_path}\n")

    # Run scraper
    run_continuous_scraper(
        seed_athlete_id=args.athlete_id,
        weeks=args.weeks,
        days_filter=args.days_filter,
        timeout_hours=args.timeout,
        state_file=args.state_file,
        resume=args.resume,
        top_weeks_mode=args.top_weeks
    )


if __name__ == '__main__':
    main()
