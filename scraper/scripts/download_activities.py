#!/usr/bin/env python3
"""Recover missing activities using Strava API (not Selenium).

This script scans athlete directories, finds activities that were listed but
not downloaded (missing _metadata.json and _streams.json files), and attempts
to download them via API with token rotation and rate limit tracking.

Usage:
    # Recover all missing activities
    python recover_activities_api.py

    # Dry run (show what would be downloaded)
    python recover_activities_api.py --dry-run

    # Specific athlete
    python recover_activities_api.py --athlete-id 11943431

    # Custom data directory
    python recover_activities_api.py --data-dir data/strava/athletes/

    # Custom config file
    python recover_activities_api.py --config ../api/config.json
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.stream_downloader import StravaStreamDownloader
from api.activity_downloader import ActivityDownloader


def find_missing_activities(athlete_dir: Path) -> List[int]:
    """Find activity IDs that are listed but not downloaded.

    Args:
        athlete_dir: Path to athlete directory

    Returns:
        List of missing activity IDs
    """
    activities_file = athlete_dir / "activities.json"
    if not activities_file.exists():
        return []

    # Load activity list
    with open(activities_file) as f:
        data = json.load(f)

    activity_ids = data.get('activity_ids', [])
    missing = []

    # Check which ones are missing files
    for activity_id in activity_ids:
        metadata_file = athlete_dir / f"{activity_id}_metadata.json"
        streams_file = athlete_dir / f"{activity_id}_streams.json"

        if not (metadata_file.exists() and streams_file.exists()):
            missing.append(activity_id)

    return missing


def scan_athletes(data_dir: Path, athlete_id: int = None) -> Dict[int, List[int]]:
    """Scan athlete directories for missing activities.

    Args:
        data_dir: Root data directory
        athlete_id: Optional specific athlete ID to scan

    Returns:
        Dict mapping athlete_id -> list of missing activity IDs
    """
    missing_by_athlete = {}

    if athlete_id:
        # Scan specific athlete
        athlete_dir = data_dir / str(athlete_id)
        if athlete_dir.exists():
            missing = find_missing_activities(athlete_dir)
            if missing:
                missing_by_athlete[athlete_id] = missing
    else:
        # Scan all athletes
        for athlete_dir in data_dir.iterdir():
            if not athlete_dir.is_dir():
                continue

            try:
                athlete_id = int(athlete_dir.name)
            except ValueError:
                continue

            missing = find_missing_activities(athlete_dir)
            if missing:
                missing_by_athlete[athlete_id] = missing

    return missing_by_athlete


def recover_activities(missing_by_athlete: Dict[int, List[int]],
                      data_dir: Path, config_file: str, dry_run: bool = False):
    """Recover missing activities via API.

    Args:
        missing_by_athlete: Dict mapping athlete_id -> missing activity IDs
        data_dir: Root data directory
        config_file: Path to API config file
        dry_run: If True, only show what would be downloaded
    """
    total_missing = sum(len(ids) for ids in missing_by_athlete.values())

    print(f"\n{'='*70}")
    print(f"RECOVERY SCAN RESULTS")
    print(f"{'='*70}")
    print(f"Athletes with missing activities: {len(missing_by_athlete)}")
    print(f"Total missing activities: {total_missing}")
    print(f"{'='*70}\n")

    if dry_run:
        print("DRY RUN - Showing what would be downloaded:\n")
        for athlete_id, activity_ids in missing_by_athlete.items():
            print(f"Athlete {athlete_id}: {len(activity_ids)} missing activities")
            for activity_id in activity_ids[:5]:  # Show first 5
                print(f"  - {activity_id}")
            if len(activity_ids) > 5:
                print(f"  ... and {len(activity_ids) - 5} more")
        print(f"\nTotal: {total_missing} activities would be downloaded")
        return

    # Initialize API downloader
    print("Initializing API downloader...")
    stream_downloader = StravaStreamDownloader(config_file)
    downloader = ActivityDownloader(stream_downloader)

    # Show initial rate limit status
    stream_downloader.print_all_status()

    # Process each athlete
    total_recovered = 0
    total_failed = 0

    for i, (athlete_id, activity_ids) in enumerate(missing_by_athlete.items(), 1):
        athlete_dir = data_dir / str(athlete_id)

        print(f"\n[{i}/{len(missing_by_athlete)}] Athlete {athlete_id}")
        print(f"Missing: {len(activity_ids)} activities")
        print("-" * 70)

        # Download missing activities
        result = downloader.download_activities(
            activity_ids,
            athlete_dir,
            delay=0.5,  # API handles rate limiting, just a small courtesy delay
            skip_existing=True,
            require_latlng=True,
            require_altitude=True,
            min_elevation=200
        )

        recovered = result['successful'] - result['skipped']
        total_recovered += recovered
        total_failed += result['failed']

        print(f"\nRecovered: {recovered} activities")
        print(f"Failed: {result['failed']} activities")

        # Update summary file
        summary_file = athlete_dir / "summary.json"
        if summary_file.exists():
            with open(summary_file, 'r') as f:
                summary = json.load(f)

            summary['successful'] = summary.get('successful', 0) + recovered
            summary['failed'] = max(0, summary.get('failed', 0) - recovered)

            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)

    # Final statistics
    print(f"\n{'='*70}")
    print(f"RECOVERY COMPLETE")
    print(f"{'='*70}")
    print(f"Total recovered: {total_recovered} activities")
    print(f"Total failed: {total_failed} activities")
    print(f"{'='*70}\n")

    # Final rate limit status
    print("Final API usage:")
    stream_downloader.print_all_status()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Recover missing activities using Strava API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan and recover all missing activities
  python recover_activities_api.py

  # Dry run (show what would be downloaded)
  python recover_activities_api.py --dry-run

  # Specific athlete
  python recover_activities_api.py --athlete-id 11943431

  # Custom data directory
  python recover_activities_api.py --data-dir data/strava/athletes/

  # Custom config file
  python recover_activities_api.py --config ../api/config.json
        """
    )

    parser.add_argument('--athlete-id', type=int,
                       help='Specific athlete ID to recover (optional)')
    parser.add_argument('--data-dir', default='data/strava/athletes/',
                       help='Data directory path (default: data/strava/athletes/)')
    parser.add_argument('--config', default='api/config.json',
                       help='API config file (default: api/config.json)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be downloaded without actually downloading')

    args = parser.parse_args()

    # Convert to absolute paths
    data_dir = Path(__file__).parent.parent / args.data_dir
    config_file = Path(__file__).parent.parent / args.config

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        return

    if not config_file.exists():
        print(f"Error: Config file not found: {config_file}")
        return

    # Scan for missing activities
    print("Scanning athlete directories for missing activities...")
    missing_by_athlete = scan_athletes(data_dir, args.athlete_id)

    if not missing_by_athlete:
        print("No missing activities found!")
        return

    # Recover activities
    recover_activities(missing_by_athlete, data_dir, str(config_file), args.dry_run)


if __name__ == '__main__':
    main()
