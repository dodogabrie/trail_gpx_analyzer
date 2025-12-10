#!/usr/bin/env python3
"""Remove athlete directories with no downloaded activities."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    data_dir = Path(__file__).parent.parent / "data/strava/athletes"

    if not data_dir.exists():
        print(f"Directory not found: {data_dir}")
        return

    removed = 0

    for athlete_dir in sorted(data_dir.iterdir()):
        if not athlete_dir.is_dir():
            continue

        try:
            athlete_id = int(athlete_dir.name)
        except ValueError:
            continue

        # Check for any metadata or streams files
        has_data = any(athlete_dir.glob("*_metadata.json")) or \
                   any(athlete_dir.glob("*_streams.json"))

        if not has_data:
            print(f"Removing {athlete_id}: no downloaded activities")
            import shutil
            shutil.rmtree(athlete_dir)
            removed += 1

    print(f"\nRemoved {removed} empty athlete directories")


if __name__ == '__main__':
    main()
