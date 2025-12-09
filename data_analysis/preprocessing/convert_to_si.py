"""Preprocess Strava athlete data and convert to SI units.

This script reads raw athlete data from scraper/data/strava/athletes/
and converts all measurements to SI units:
- Distance: meters (m)
- Temperature: Celsius (C)
- Speed: meters per second (m/s)
- Altitude: meters (m)
- Power: watts (W)
- Heart rate: bpm (no conversion needed)
- Cadence: rpm (no conversion needed)
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


def fahrenheit_to_celsius(temp_f: float) -> float:
    """Convert Fahrenheit to Celsius.

    Args:
        temp_f: Temperature in Fahrenheit

    Returns:
        Temperature in Celsius
    """
    return (temp_f - 32) * 5 / 9


def feet_to_meters(feet: float) -> float:
    """Convert feet to meters.

    Args:
        feet: Distance in feet

    Returns:
        Distance in meters
    """
    return feet * 0.3048


def miles_to_meters(miles: float) -> float:
    """Convert miles to meters.

    Args:
        miles: Distance in miles

    Returns:
        Distance in meters
    """
    return miles * 1609.34


def mph_to_mps(mph: float) -> float:
    """Convert miles per hour to meters per second.

    Args:
        mph: Speed in miles per hour

    Returns:
        Speed in meters per second
    """
    return mph * 0.44704


def parse_distance(distance_str: str) -> Optional[Tuple[float, str]]:
    """Parse distance string and extract value and unit.

    Args:
        distance_str: Distance string like "14.83 mi" or "10.5 km"

    Returns:
        Tuple of (value, unit) or None if parsing fails
    """
    match = re.match(r'([\d.,]+)\s*(mi|km|m|ft)', distance_str.strip())
    if match:
        value = float(match.group(1).replace(',', ''))
        unit = match.group(2)
        return value, unit
    return None


def parse_temperature(temp_str: str) -> Optional[Tuple[float, str]]:
    """Parse temperature string and extract value and unit.

    Args:
        temp_str: Temperature string like "44 °F" or "20 °C"

    Returns:
        Tuple of (value, unit) or None if parsing fails
    """
    match = re.match(r'([\d.,]+)\s*[°]?\s*([CFcf])', temp_str.strip())
    if match:
        value = float(match.group(1).replace(',', ''))
        unit = match.group(2).upper()
        return value, unit
    return None


def parse_speed(speed_str: str) -> Optional[Tuple[float, str]]:
    """Parse speed string and extract value and unit.

    Args:
        speed_str: Speed string like "3.8 mi/h" or "10 km/h"

    Returns:
        Tuple of (value, unit) or None if parsing fails
    """
    match = re.match(r'([\d.,]+)\s*(mi/h|km/h|m/s)', speed_str.strip())
    if match:
        value = float(match.group(1).replace(',', ''))
        unit = match.group(2)
        return value, unit
    return None


def convert_metadata_stats(stats: Dict[str, str]) -> Dict[str, Any]:
    """Convert metadata stats to SI units.

    Args:
        stats: Raw stats dictionary with imperial units

    Returns:
        Converted stats with SI units and structured data
    """
    converted = {}

    for key, label in stats.items():
        # Distance
        if label == "Distance":
            parsed = parse_distance(key)
            if parsed:
                value, unit = parsed
                if unit == "mi":
                    converted["distance_m"] = miles_to_meters(value)
                elif unit == "km":
                    converted["distance_m"] = value * 1000
                elif unit == "m":
                    converted["distance_m"] = value
                elif unit == "ft":
                    converted["distance_m"] = feet_to_meters(value)

        # Elevation
        elif label == "elevation" or key == "elevation":
            parsed = parse_distance(label)
            if parsed:
                value, unit = parsed
                if unit == "ft":
                    converted["elevation_m"] = feet_to_meters(value)
                elif unit == "m":
                    converted["elevation_m"] = value

        # Temperature
        elif label == "temperature" or key == "temperature":
            parsed = parse_temperature(label)
            if parsed:
                value, unit = parsed
                if unit == "F":
                    converted["temperature_c"] = fahrenheit_to_celsius(value)
                elif unit == "C":
                    converted["temperature_c"] = value

        # Feels like
        elif label == "feels like" or key == "feels like":
            parsed = parse_temperature(label)
            if parsed:
                value, unit = parsed
                if unit == "F":
                    converted["feels_like_c"] = fahrenheit_to_celsius(value)
                elif unit == "C":
                    converted["feels_like_c"] = value

        # Wind speed
        elif label == "wind speed" or key == "wind speed":
            parsed = parse_speed(label)
            if parsed:
                value, unit = parsed
                if unit == "mi/h":
                    converted["wind_speed_mps"] = mph_to_mps(value)
                elif unit == "km/h":
                    converted["wind_speed_mps"] = value / 3.6
                elif unit == "m/s":
                    converted["wind_speed_mps"] = value

        # Keep non-numeric data as-is
        elif label in ["Temperature", "wind direction", "Humidity"]:
            if key not in ["temperature", "feels like", "wind speed"]:
                converted[label.lower().replace(" ", "_")] = key

    return converted


def process_streams(streams: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
    """Process stream data (already in SI units from Strava API).

    Args:
        streams: Raw stream data with time series measurements

    Returns:
        Streams data as-is (already in SI units)
    """
    # Strava API already returns streams in SI units:
    # - distance: meters (m)
    # - altitude: meters (m)
    # - velocity_smooth: m/s
    # - temp: Celsius (C)
    # - watts: W
    # - heartrate: bpm
    # - cadence: rpm
    # - grade_smooth: %

    return streams


def process_athlete_data(athlete_id: str, input_dir: Path, output_dir: Path) -> Dict[str, Any]:
    """Process all activities for a single athlete.

    Args:
        athlete_id: Athlete ID
        input_dir: Input directory with raw data
        output_dir: Output directory for processed data

    Returns:
        Summary of processing results
    """
    athlete_input_dir = input_dir / athlete_id
    athlete_output_dir = output_dir / athlete_id
    athlete_output_dir.mkdir(parents=True, exist_ok=True)

    # Load activities list
    activities_path = athlete_input_dir / "activities.json"
    if not activities_path.exists():
        return {"athlete_id": athlete_id, "status": "no_activities"}

    with open(activities_path) as f:
        activities_data = json.load(f)

    # Support both formats: activity_ids array OR activities array with objects
    activity_ids = activities_data.get("activity_ids")
    if not activity_ids:
        # Try extracting from activities array
        activities_array = activities_data.get("activities", [])
        activity_ids = [act["id"] for act in activities_array if "id" in act]

    if not activity_ids:
        return {"athlete_id": athlete_id, "status": "no_activity_ids"}

    processed_count = 0
    failed_count = 0

    # Process each activity
    for activity_id in activity_ids:
        streams_path = athlete_input_dir / f"{activity_id}_streams.json"
        metadata_path = athlete_input_dir / f"{activity_id}_metadata.json"

        if not streams_path.exists():
            failed_count += 1
            continue

        try:
            # Load and convert streams
            with open(streams_path) as f:
                streams = json.load(f)
            processed_streams = process_streams(streams)

            # Save processed streams
            output_streams_path = athlete_output_dir / f"{activity_id}_streams.json"
            with open(output_streams_path, 'w') as f:
                json.dump(processed_streams, f, indent=2)

            # Load and convert metadata
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)

                # Convert stats to SI units
                if 'stats' in metadata:
                    metadata['stats_si'] = convert_metadata_stats(metadata['stats'])
                    # Keep original for reference
                    metadata['stats_original'] = metadata.pop('stats')

                output_metadata_path = athlete_output_dir / f"{activity_id}_metadata.json"
                with open(output_metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

            processed_count += 1

        except Exception as e:
            print(f"Failed to process {athlete_id}/{activity_id}: {e}")
            failed_count += 1

    # Copy activities and summary files
    with open(athlete_output_dir / "activities.json", 'w') as f:
        json.dump(activities_data, f, indent=2)

    summary_path = athlete_input_dir / "summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            summary = json.load(f)
        with open(athlete_output_dir / "summary.json", 'w') as f:
            json.dump(summary, f, indent=2)

    return {
        "athlete_id": athlete_id,
        "status": "success",
        "processed": processed_count,
        "failed": failed_count
    }


def main():
    """Main preprocessing pipeline."""
    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    input_dir = project_root / "scraper" / "data" / "strava" / "athletes"
    output_dir = project_root / "data_analysis" / "data" / "processed"

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get all athlete IDs
    athlete_ids = [d.name for d in input_dir.iterdir() if d.is_dir()]

    print(f"Processing {len(athlete_ids)} athletes...")

    results = []
    for athlete_id in athlete_ids:
        print(f"Processing athlete {athlete_id}...")
        result = process_athlete_data(athlete_id, input_dir, output_dir)
        results.append(result)
        print(f"  Status: {result['status']}")
        if result.get('processed'):
            print(f"  Processed: {result['processed']}, Failed: {result['failed']}")

    # Save processing summary
    summary = {
        "total_athletes": len(athlete_ids),
        "results": results
    }

    with open(output_dir / "processing_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nProcessing complete. Results saved to {output_dir}")
    print(f"Total athletes: {len(athlete_ids)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'success')}")


if __name__ == "__main__":
    main()
