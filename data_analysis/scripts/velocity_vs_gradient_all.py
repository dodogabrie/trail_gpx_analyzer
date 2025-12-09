"""Aggregate velocity vs gradient across all athletes with normalization.

Build a general curve by:
1) Smoothing velocity/grade per activity and keeping moving samples.
2) Computing pace (min/km) and binning by gradient (1% bins).
3) For each athlete, normalizing pace by their flat baseline (median pace in -1% to +1%).
4) Aggregating normalized pace ratios across athletes (median + IQR per grade bin).
Outputs a single plot in plot_scripts/velocity_vs_gradient/all_athletes_velocity_vs_gradient.png.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


GRADE_BIN_WIDTH = 1  # percent
SMOOTH_WINDOW = 5
FLAT_BASE_RANGE = (-1.0, 1.0)  # percent
MIN_POINTS_PER_BIN = 10
MIN_ATHLETES_PER_BIN = 5
MAX_GRADE_ABS = 40  # focus range [-40, 40] %
SMOOTH_POINTS = 3  # rolling window for aggregated curve


def load_activity_streams(activity_id: str, athlete_dir: Path) -> Optional[pd.DataFrame]:
    """Load and return streams as DataFrame."""
    streams_path = athlete_dir / f"{activity_id}_streams.json"
    if not streams_path.exists():
        return None
    try:
        with open(streams_path) as f:
            streams = json.load(f)
    except json.JSONDecodeError:
        return None

    required = {"velocity_smooth", "grade_smooth", "moving"}
    if not required.issubset(streams):
        return None

    df = pd.DataFrame(
        {
            "velocity_smooth": streams["velocity_smooth"],
            "grade_smooth": streams["grade_smooth"],
            "moving": streams["moving"],
        }
    )
    return df if not df.empty else None


def prepare_activity(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Smooth streams and compute pace/min/km."""
    if df is None or df.empty:
        return None

    # Keep moving samples
    if "moving" in df.columns and df["moving"].notna().any():
        df = df[df["moving"] == True]  # noqa: E712
    if df.empty:
        return None

    df = df.copy()
    df["velocity_smooth"] = (
        df["velocity_smooth"]
        .rolling(window=SMOOTH_WINDOW, center=True, min_periods=1)
        .mean()
    )
    df["grade_smooth"] = (
        df["grade_smooth"]
        .rolling(window=SMOOTH_WINDOW, center=True, min_periods=1)
        .mean()
    )
    df["velocity_kmh"] = df["velocity_smooth"] * 3.6
    df["pace_min_per_km"] = np.where(
        df["velocity_kmh"] > 0, 60.0 / df["velocity_kmh"], np.nan
    )
    df = df[np.isfinite(df["pace_min_per_km"]) & np.isfinite(df["grade_smooth"])]
    return df if not df.empty else None


def athlete_curve(athlete_id: str, data_dir: Path) -> Optional[pd.DataFrame]:
    """Compute normalized pace ratio per grade bin for one athlete."""
    athlete_dir = data_dir / athlete_id
    activities_path = athlete_dir / "activities.json"
    if not activities_path.exists():
        return None
    try:
        with open(activities_path) as f:
            activities_data = json.load(f)
    except json.JSONDecodeError:
        return None

    all_points = []
    for activity_id in activities_data.get("activity_ids", []):
        df = load_activity_streams(str(activity_id), athlete_dir)
        df = prepare_activity(df)
        if df is not None:
            all_points.append(df[["grade_smooth", "pace_min_per_km"]])
    if not all_points:
        return None

    df_all = pd.concat(all_points, ignore_index=True)
    if df_all.empty:
        return None

    # Limit to desired grade range
    df_all = df_all[
        df_all["grade_smooth"].between(-MAX_GRADE_ABS, MAX_GRADE_ABS, inclusive="both")
    ]
    if df_all.empty:
        return None

    # Athlete baseline: median pace on flat band
    flat_mask = df_all["grade_smooth"].between(*FLAT_BASE_RANGE, inclusive="both")
    if not flat_mask.any():
        return None
    flat_baseline = df_all.loc[flat_mask, "pace_min_per_km"].median()
    if not np.isfinite(flat_baseline) or flat_baseline <= 0:
        return None

    # Bin by grade
    grade_bins = np.arange(-MAX_GRADE_ABS, MAX_GRADE_ABS + GRADE_BIN_WIDTH, GRADE_BIN_WIDTH)
    df_all["grade_bin"] = pd.cut(
        df_all["grade_smooth"], bins=grade_bins, include_lowest=True
    )

    binned = (
        df_all.groupby("grade_bin", observed=False)["pace_min_per_km"]
        .agg(["median", "count"])
        .reset_index()
    )
    binned = binned[binned["count"] >= MIN_POINTS_PER_BIN]
    if binned.empty:
        return None

    binned["grade"] = binned["grade_bin"].apply(
        lambda interval: (interval.left + interval.right) / 2
    )
    binned["pace_ratio"] = binned["median"] / flat_baseline
    binned["athlete_id"] = athlete_id
    return binned[["athlete_id", "grade", "pace_ratio", "count"]]


def aggregate_curves(data_dir: Path) -> Optional[pd.DataFrame]:
    """Aggregate normalized curves across athletes."""
    athlete_ids = sorted(
        d.name for d in data_dir.iterdir() if d.is_dir() and d.name.isdigit()
    )
    curves: List[pd.DataFrame] = []
    for athlete_id in athlete_ids:
        curve = athlete_curve(athlete_id, data_dir)
        if curve is not None:
            curves.append(curve)

    if not curves:
        return None

    # First average within athlete per grade, then aggregate across athletes equally
    per_athlete = pd.concat(curves, ignore_index=True)
    summary = (
        per_athlete.groupby("grade", observed=False)["pace_ratio"]
        .agg(
            median="median",
            p25=lambda x: x.quantile(0.25),
            p75=lambda x: x.quantile(0.75),
            count="count",
        )
        .reset_index()
        .sort_values("grade")
    )
    summary = summary[summary["count"] >= MIN_ATHLETES_PER_BIN]
    if summary.empty:
        return None

    # Light smoothing to reduce bin-to-bin noise
    for col in ["median", "p25", "p75"]:
        summary[col] = (
            summary[col]
            .rolling(window=SMOOTH_POINTS, center=True, min_periods=1)
            .median()
        )
    return summary


def plot_curve(summary: pd.DataFrame, output_dir: Path):
    """Plot aggregated normalized pace ratio vs grade."""
    fig, ax = plt.subplots(2, 1, figsize=(12, 10))
    fig.suptitle(
        "Normalized pace vs gradient (median across athletes)", fontsize=16
    )

    # Pace ratio curve
    ax0 = ax[0]
    ax0.plot(
        summary["grade"],
        summary["median"],
        color="blue",
        marker="o",
        markersize=3,
        linewidth=1.5,
        label="Median pace ratio",
    )
    ax0.fill_between(
        summary["grade"],
        summary["p25"],
        summary["p75"],
        color="blue",
        alpha=0.2,
        label="25th-75th percentile",
    )
    ax0.axhline(1.0, color="gray", linestyle="--", linewidth=1, label="Flat baseline")
    ax0.set_xlabel("Gradient (%)")
    ax0.set_ylabel("Pace ratio (pace / flat pace)")
    ax0.grid(True, alpha=0.3)
    ax0.legend()
    ax0.set_xlim(-MAX_GRADE_ABS, MAX_GRADE_ABS)

    # Count of athlete contributions per bin
    ax1 = ax[1]
    ax1.bar(summary["grade"], summary["count"], width=0.8, color="gray", alpha=0.7)
    ax1.set_xlabel("Gradient (%)")
    ax1.set_ylabel("Athlete-bin count (≥1 activity)")
    ax1.set_title("Number of athlete contributions per grade bin")
    ax1.grid(True, axis="y", alpha=0.3)
    ax1.set_xlim(-MAX_GRADE_ABS, MAX_GRADE_ABS)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "all_athletes_velocity_vs_gradient.png"
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved aggregate plot to {out_path}")


def main():
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data_analysis" / "data" / "processed"
    output_dir = project_root / "data_analysis" / "plot_scripts" / "velocity_vs_gradient"

    summary = aggregate_curves(data_dir)
    if summary is None or summary.empty:
        print("No data to plot.")
        return
    plot_curve(summary, output_dir)


if __name__ == "__main__":
    main()
