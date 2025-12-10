"""
Visualize how the global curve is personalized for a specific athlete.

Shows:
1. Global curve (median pace ratio across all athletes)
2. Athlete's actual data points
3. Personalized curve after calibration with anchor points
4. Anchor points used for calibration
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add predictor to path
project_root = Path(__file__).resolve().parents[2]
predictor_path = project_root / "data_analysis" / "predictor"
sys.path.insert(0, str(predictor_path))

from predictor import (
    build_global_curve,
    compute_anchor_ratios,
    compute_flat_pace,
    iter_athlete_streams,
    personalize_curve,
    ANCHOR_GRADES,
    ANCHOR_WINDOW,
)


def collect_athlete_data_points(athlete_dir: Path, sample_fraction: float = 0.1):
    """
    Collect all grade-pace pairs for an athlete.

    Args:
        athlete_dir: Path to athlete's data directory
        sample_fraction: Fraction of points to sample for plotting (to reduce clutter)

    Returns:
        DataFrame with grade, pace, pace_ratio columns
    """
    all_points = []

    for df in iter_athlete_streams(athlete_dir):
        all_points.append(df[["grade_smooth", "pace_min_per_km"]])

    if not all_points:
        return None

    df_all = pd.concat(all_points, ignore_index=True)

    # Compute flat pace
    flat_mask = df_all["grade_smooth"].between(-1, 1, inclusive="both")
    if not flat_mask.any():
        return None

    flat_pace = df_all.loc[flat_mask, "pace_min_per_km"].median()
    if not np.isfinite(flat_pace) or flat_pace <= 0:
        return None

    # Add pace ratio
    df_all["pace_ratio"] = df_all["pace_min_per_km"] / flat_pace
    df_all["flat_pace"] = flat_pace

    # Sample points to reduce plotting clutter
    if sample_fraction < 1.0:
        df_all = df_all.sample(frac=sample_fraction, random_state=42)

    return df_all


def plot_athlete_calibration(
    athlete_dir: Path,
    global_curve: pd.DataFrame,
    save_path: Path = None,
):
    """
    Plot global curve vs athlete's personalized curve.

    Args:
        athlete_dir: Path to athlete's data directory
        global_curve: Global pace-grade curve
        save_path: Optional path to save plot
    """
    athlete_id = athlete_dir.name

    # Collect athlete data
    print(f"Collecting data for athlete {athlete_id}...")
    athlete_data = collect_athlete_data_points(athlete_dir, sample_fraction=0.05)

    if athlete_data is None:
        print(f"No data found for athlete {athlete_id}")
        return

    flat_pace = athlete_data["flat_pace"].iloc[0]

    # Get one activity for calibration
    print("Computing anchor ratios...")
    activity_stream = None
    for df in iter_athlete_streams(athlete_dir):
        activity_stream = df
        break

    if activity_stream is None:
        print("No activity stream found")
        return

    anchor_ratios = compute_anchor_ratios(activity_stream, flat_pace)
    if not anchor_ratios:
        print("No anchor ratios found")
        return

    print(f"Found {len(anchor_ratios)} anchor points: {list(anchor_ratios.keys())}")

    # Personalize curve
    print("Personalizing curve...")
    personalized = personalize_curve(global_curve, anchor_ratios)

    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))

    # Plot athlete's raw data points (scatter)
    ax.scatter(
        athlete_data["grade_smooth"],
        athlete_data["pace_ratio"],
        alpha=0.15,
        s=5,
        color="lightblue",
        label="Athlete data points",
        zorder=1,
    )

    # Plot global curve (median)
    ax.plot(
        global_curve["grade"],
        global_curve["median"],
        linewidth=3,
        color="gray",
        linestyle="--",
        label="Global curve (all athletes)",
        zorder=3,
    )

    # Plot global curve IQR (shaded area)
    ax.fill_between(
        global_curve["grade"],
        global_curve["p25"],
        global_curve["p75"],
        alpha=0.2,
        color="gray",
        label="Global IQR (25-75%)",
        zorder=2,
    )

    # Plot personalized curve
    ax.plot(
        personalized["grade"],
        personalized["personalized_ratio"],
        linewidth=3.5,
        color="darkblue",
        label=f"Personalized curve (athlete {athlete_id})",
        zorder=4,
    )

    # Plot anchor points
    anchor_grades = list(anchor_ratios.keys())
    anchor_ratios_vals = list(anchor_ratios.values())
    ax.scatter(
        anchor_grades,
        anchor_ratios_vals,
        s=150,
        color="red",
        marker="*",
        edgecolors="black",
        linewidths=1.5,
        label=f"Anchor points (n={len(anchor_ratios)})",
        zorder=5,
    )

    # Add vertical lines at anchor grades
    for grade in anchor_grades:
        ax.axvline(x=grade, linestyle=":", color="red", alpha=0.3, linewidth=1)

    # Formatting
    ax.set_xlabel("Grade (%)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Pace Ratio (pace / flat_pace)", fontsize=13, fontweight="bold")
    ax.set_title(
        f"Athlete {athlete_id} Calibration\n"
        f"Flat Pace: {flat_pace:.2f} min/km | "
        f"Anchor Points: {len(anchor_ratios)}",
        fontsize=14,
        fontweight="bold",
    )
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(fontsize=11, loc="upper left")

    # Set reasonable y-axis limits
    ax.set_ylim(0.5, 3.0)

    # Add interpretation box
    interpretation = (
        "Interpretation:\n"
        "• Gray line: Average pace curve across all athletes\n"
        "• Blue line: Personalized curve fitted to athlete's anchor points\n"
        "• Red stars: Calibration anchor points (from athlete's activity)\n"
        "• Light blue dots: All athlete's actual pace measurements\n"
        f"• Anchor window: ±{ANCHOR_WINDOW}% around each anchor grade"
    )

    ax.text(
        0.02, 0.02,
        interpretation,
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Saved plot to {save_path}")
    else:
        plt.show()


def plot_multiple_athletes_comparison(
    processed_root: Path,
    global_curve: pd.DataFrame,
    num_athletes: int = 4,
    save_path: Path = None,
):
    """
    Plot comparison of multiple athletes' personalized curves.

    Args:
        processed_root: Path to processed data root
        global_curve: Global pace-grade curve
        num_athletes: Number of athletes to compare
        save_path: Optional path to save plot
    """
    athlete_dirs = [
        p for p in processed_root.iterdir()
        if p.is_dir() and p.name.isdigit()
    ][:num_athletes]

    if not athlete_dirs:
        print("No athlete directories found")
        return

    fig, ax = plt.subplots(figsize=(14, 8))

    # Plot global curve
    ax.plot(
        global_curve["grade"],
        global_curve["median"],
        linewidth=4,
        color="black",
        linestyle="--",
        label="Global curve",
        zorder=10,
    )

    # Plot each athlete's personalized curve
    colors = plt.cm.tab10(np.linspace(0, 1, num_athletes))

    for i, athlete_dir in enumerate(athlete_dirs):
        athlete_id = athlete_dir.name
        print(f"Processing athlete {athlete_id}...")

        # Get activity for calibration
        activity_stream = None
        for df in iter_athlete_streams(athlete_dir):
            activity_stream = df
            break

        if activity_stream is None:
            continue

        try:
            flat_pace = compute_flat_pace(activity_stream)
            anchor_ratios = compute_anchor_ratios(activity_stream, flat_pace)

            if anchor_ratios:
                personalized = personalize_curve(global_curve, anchor_ratios)
                ax.plot(
                    personalized["grade"],
                    personalized["personalized_ratio"],
                    linewidth=2.5,
                    color=colors[i],
                    label=f"Athlete {athlete_id} (flat: {flat_pace:.2f})",
                    alpha=0.8,
                )
        except Exception as e:
            print(f"  Skipped athlete {athlete_id}: {e}")

    # Formatting
    ax.set_xlabel("Grade (%)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Pace Ratio (pace / flat_pace)", fontsize=13, fontweight="bold")
    ax.set_title(
        "Comparison of Athlete-Specific Calibrations",
        fontsize=14,
        fontweight="bold",
    )
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(fontsize=10, loc="upper left")
    ax.set_ylim(0.5, 3.0)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Saved plot to {save_path}")
    else:
        plt.show()


def main():
    """Generate athlete calibration plots."""
    project_root = Path(__file__).resolve().parents[2]
    processed_root = project_root / "data_analysis" / "data" / "processed"
    output_dir = Path(__file__).parent / "plots"
    output_dir.mkdir(exist_ok=True)

    print(f"Building global curve from {processed_root}...")
    global_curve = build_global_curve(processed_root)

    # Find athlete directories
    athlete_dirs = [
        p for p in processed_root.iterdir()
        if p.is_dir() and p.name.isdigit()
    ]

    if not athlete_dirs:
        print(f"No athlete directories found in {processed_root}")
        return

    print(f"Found {len(athlete_dirs)} athletes")

    # Plot first athlete in detail
    print("\n=== Detailed Calibration Plot (First Athlete) ===")
    first_athlete = athlete_dirs[0]
    save_path = output_dir / f"athlete_calibration_{first_athlete.name}.png"
    plot_athlete_calibration(first_athlete, global_curve, save_path)

    # Plot comparison of multiple athletes
    print("\n=== Multi-Athlete Comparison ===")
    save_path = output_dir / "athletes_comparison.png"
    plot_multiple_athletes_comparison(
        processed_root,
        global_curve,
        num_athletes=min(6, len(athlete_dirs)),
        save_path=save_path,
    )

    print(f"\nAll plots saved to {output_dir}/")
    print("\nInterpretation:")
    print("- Global curve: Average pace-grade relationship across all athletes")
    print("- Personalized curves: Fitted to individual athlete's anchor points")
    print("- Variance shows different athlete capabilities at different grades")
    print("- Steeper curves = more affected by grade changes")


if __name__ == "__main__":
    main()
