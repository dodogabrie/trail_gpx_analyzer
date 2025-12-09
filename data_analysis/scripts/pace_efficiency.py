"""Pace efficiency curves across athletes on specific gradients.

For each athlete, we keep only samples within a target grade range, compute
pace over absolute activity distance (km), and plot median pace with
interquartile range. Activities only contribute where they have the target
grade, but the x-axis is the activity distance (e.g., km 2, km 30).
"""

import json
import sys
from pathlib import Path
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BIN_SIZE_KM = 1.0
GRADE_MIN = 5.0
GRADE_MAX = 10.0


def load_activity_streams(activity_id: str, athlete_dir: Path) -> Optional[pd.DataFrame]:
    """Load stream data for a single activity."""
    streams_path = athlete_dir / f"{activity_id}_streams.json"
    if not streams_path.exists():
        return None

    try:
        with open(streams_path) as f:
            streams = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Skipping {streams_path} due to JSON error: {exc}")
        return None

    required = {"distance", "velocity_smooth", "time", "grade_smooth"}
    if not required.issubset(streams):
        return None

    df = pd.DataFrame(
        {
            "time": streams["time"],
            "distance": streams["distance"],
            "velocity_smooth": streams["velocity_smooth"],
            "moving": streams.get("moving"),
            "grade_smooth": streams["grade_smooth"],
        }
    )
    return df if not df.empty else None


def prepare_activity_df(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Filter to target gradient range and keep absolute distance (km)."""
    if df is None or df.empty or df["distance"].max() <= 0:
        return None

    # Keep only moving samples if available
    if "moving" in df.columns and df["moving"].notna().any():
        df = df[df["moving"] == True]  # noqa: E712

    if df.empty:
        return None

    df = df.copy()
    df["velocity_smooth"] = (
        df["velocity_smooth"]
        .rolling(window=5, center=True, min_periods=1)
        .mean()
    )
    df["grade_smooth"] = (
        df["grade_smooth"]
        .rolling(window=5, center=True, min_periods=1)
        .mean()
    )
    condition = df["grade_smooth"].between(GRADE_MIN, GRADE_MAX, inclusive="both")
    if not condition.any():
        return None

    df["distance_km"] = df["distance"] / 1000.0
    df["velocity_kmh"] = df["velocity_smooth"] * 3.6
    df["pace_min_per_km"] = np.where(
        df["velocity_kmh"] > 0, 60.0 / df["velocity_kmh"], np.nan
    )

    df = df[condition].copy()
    if df.empty:
        return None

    return df[["distance_km", "pace_min_per_km", "velocity_kmh"]]


def aggregate_athlete_profiles(athlete_id: str, data_dir: Path) -> Optional[pd.DataFrame]:
    """Compute aggregated pace profile for an athlete."""
    athlete_dir = data_dir / athlete_id
    activities_path = athlete_dir / "activities.json"
    if not activities_path.exists():
        print(f"Skipping athlete {athlete_id}: no activities.json")
        return None

    with open(activities_path) as f:
        activities_data = json.load(f)

    prepared: List[tuple[str, pd.DataFrame]] = []
    max_distance_km = 0.0
    for activity_id in activities_data.get("activity_ids", []):
        df = load_activity_streams(str(activity_id), athlete_dir)
        if df is None:
            continue
        max_distance_km = max(max_distance_km, df["distance"].max() / 1000.0)
        filtered = prepare_activity_df(df)
        if filtered is None:
            continue
        prepared.append((str(activity_id), filtered))

    if not prepared or max_distance_km <= 0:
        print(f"No valid profiles for athlete {athlete_id}")
        return None

    distance_bins = np.arange(0, max_distance_km + BIN_SIZE_KM, BIN_SIZE_KM)
    if len(distance_bins) < 2:
        distance_bins = np.array([0, max_distance_km])

    profiles: List[pd.DataFrame] = []
    for activity_id, df in prepared:
        df = df.copy()
        df["distance_bin"] = pd.cut(
            df["distance_km"], bins=distance_bins, include_lowest=True
        )
        binned = (
            df.groupby("distance_bin", observed=False)[
                ["pace_min_per_km", "velocity_kmh"]
            ]
            .mean()
            .dropna(how="all")
            .reset_index()
        )
        if binned.empty:
            continue
        binned["distance_km"] = binned["distance_bin"].apply(
            lambda interval: (interval.left + interval.right) / 2
        )
        binned["activity_id"] = activity_id
        profiles.append(
            binned[["activity_id", "distance_km", "pace_min_per_km", "velocity_kmh"]]
        )

    if not profiles:
        print(f"No valid profiles for athlete {athlete_id}")
        return None

    combined = pd.concat(profiles, ignore_index=True)
    summary = combined.groupby("distance_km", observed=False)["pace_min_per_km"].agg(
        median="median",
        p25=lambda x: x.quantile(0.25),
        p75=lambda x: x.quantile(0.75),
        count="count",
    )
    summary = summary.reset_index().dropna(subset=["median"]).sort_values("distance_km")
    return summary


def plot_pace_efficiency(summary: pd.DataFrame, athlete_id: str, output_dir: Path):
    """Plot median pace vs distance with IQR shading."""
    fig, ax = plt.subplots(figsize=(15, 6))
    fig.suptitle(
        f"Pace vs distance at {GRADE_MIN:g}-{GRADE_MAX:g}% - Athlete {athlete_id}",
        fontsize=16,
    )
    ax.plot(
        summary["distance_km"],
        summary["median"],
        label="Median pace",
        color="blue",
        linewidth=1.5,
        marker="o",
        markersize=3,
        alpha=0.8,
    )
    ax.fill_between(
        summary["distance_km"],
        summary["p25"],
        summary["p75"],
        color="tab:blue",
        alpha=0.2,
        label="25th-75th percentile",
    )

    ax.set_xlabel("Distance in grade window (km)")
    ax.set_ylabel("Pace (min/km)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.set_title(f"Bin size {BIN_SIZE_KM:g} km", fontsize=12)

    output_dir.mkdir(exist_ok=True, parents=True)
    out_path = output_dir / f"athlete_{athlete_id}_pace_efficiency.png"
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_path} (activities used: {int(summary['count'].max())})")


def main():
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data_analysis" / "data" / "processed"
    output_dir = project_root / "data_analysis" / "plot_scripts" / "pace_efficiency"

    # Specific athletes passed as args, otherwise run all
    if len(sys.argv) > 1:
        athlete_ids = sys.argv[1:]
    else:
        athlete_ids = sorted(
            d.name for d in data_dir.iterdir() if d.is_dir() and d.name.isdigit()
        )

    if not athlete_ids:
        print("No athletes found.")
        return

    for athlete_id in athlete_ids:
        summary = aggregate_athlete_profiles(athlete_id, data_dir)
        if summary is None:
            continue
        plot_pace_efficiency(summary, athlete_id, output_dir)


if __name__ == "__main__":
    main()
