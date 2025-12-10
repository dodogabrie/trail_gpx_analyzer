"""
Visualize how pace at a specific grade changes over distance (fatigue effect).

Shows how the ML model predicts pace evolution at constant grade as cumulative
distance increases, demonstrating the fatigue/distance effect in the model.
"""

import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add predictor to path
project_root = Path(__file__).resolve().parents[2]
predictor_path = project_root / "data_analysis" / "predictor"
sys.path.insert(0, str(predictor_path))

from predictor import build_global_curve


def predict_pace_at_grade_over_distance(
    model,
    global_curve: pd.DataFrame,
    grade: float,
    flat_pace: float,
    max_distance_km: float = 40.0,
    segment_len_m: float = 200.0,
):
    """
    Predict pace at constant grade over increasing distance.

    Args:
        model: Trained ML model
        global_curve: Global pace-grade curve
        grade: Target grade (%)
        flat_pace: User's flat pace (min/km)
        max_distance_km: Maximum distance to simulate
        segment_len_m: Segment length for predictions

    Returns:
        DataFrame with distance_km, predicted_pace, baseline_pace
    """
    # Get baseline ratio from global curve
    baseline_ratio = np.interp(grade, global_curve["grade"], global_curve["median"])
    baseline_pace = flat_pace * baseline_ratio

    # Simulate segments over distance
    distances_km = np.arange(0, max_distance_km, segment_len_m / 1000.0)
    results = []

    # Track state across segments
    prev_pace_ratio = 1.0
    cum_elevation_gain = 0.0

    for dist_km in distances_km:
        # Create features for this segment
        grade_mean = grade
        grade_std = 0.0  # constant grade
        abs_grade = abs(grade)
        cum_distance_km = dist_km

        # Temporal features
        prev_pace_ratio_feat = prev_pace_ratio
        grade_change = 0.0  # constant grade

        # Elevation features
        if grade > 0:
            cum_elevation_gain += (segment_len_m * grade / 100.0)
        elevation_gain_rate = cum_elevation_gain / max(dist_km, 0.1)

        # Context features
        rolling_avg_grade_500m = grade  # constant
        distance_remaining_km = max_distance_km - dist_km

        # Create feature vector (match training feature names exactly)
        features = pd.DataFrame([{
            "grade_mean": grade_mean,
            "grade_std": grade_std,
            "abs_grade": abs_grade,
            "cum_distance_km": cum_distance_km,  # Note: cum_distance_km, not cumulative_distance_km
            "prev_pace_ratio": prev_pace_ratio_feat,
            "grade_change": grade_change,
            "cum_elevation_gain_m": cum_elevation_gain,
            "elevation_gain_rate": elevation_gain_rate,
            "rolling_avg_grade_500m": rolling_avg_grade_500m,
            "distance_remaining_km": distance_remaining_km,
        }])

        # Predict residual multiplier
        try:
            residual_mult = model.predict(features)[0]
        except Exception:
            residual_mult = 1.0

        # Calculate actual predicted pace
        predicted_ratio = baseline_ratio * residual_mult
        predicted_pace = flat_pace * predicted_ratio

        results.append({
            "distance_km": dist_km,
            "predicted_pace": predicted_pace,
            "baseline_pace": baseline_pace,
            "residual_multiplier": residual_mult,
            "cum_elevation_gain_m": cum_elevation_gain,
        })

        # Update state - use baseline_ratio to avoid feedback loop
        # (model should predict deviation from baseline, not compound predictions)
        prev_pace_ratio = baseline_ratio

    return pd.DataFrame(results)


def plot_pace_evolution(
    results: pd.DataFrame,
    grade: float,
    flat_pace: float,
    save_path: Path = None,
):
    """
    Plot pace evolution at constant grade.

    Args:
        results: DataFrame from predict_pace_at_grade_over_distance
        grade: Grade used (%)
        flat_pace: Flat pace used (min/km)
        save_path: Optional path to save plot
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # Plot 1: Pace vs Distance
    ax1.plot(
        results["distance_km"],
        results["baseline_pace"],
        label="Baseline (global curve)",
        linestyle="--",
        linewidth=2,
        color="gray",
        alpha=0.7,
    )
    ax1.plot(
        results["distance_km"],
        results["predicted_pace"],
        label="ML-corrected pace",
        linewidth=2.5,
        color="darkblue",
    )

    ax1.set_xlabel("Cumulative Distance (km)", fontsize=12)
    ax1.set_ylabel("Pace (min/km)", fontsize=12)
    ax1.set_title(
        f"Pace Evolution at {grade:+.1f}% Grade\n"
        f"Flat Pace: {flat_pace:.2f} min/km",
        fontsize=14,
        fontweight="bold",
    )
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=11)

    # Add annotation showing pace change
    initial_pace = results["predicted_pace"].iloc[0]
    final_pace = results["predicted_pace"].iloc[-1]
    pace_increase = final_pace - initial_pace
    pace_increase_pct = (pace_increase / initial_pace) * 100

    ax1.text(
        0.02, 0.98,
        f"Fatigue effect:\n"
        f"+{pace_increase:.2f} min/km (+{pace_increase_pct:.1f}%)\n"
        f"over {results['distance_km'].iloc[-1]:.1f} km",
        transform=ax1.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    # Plot 2: Residual Multiplier vs Distance
    ax2.plot(
        results["distance_km"],
        results["residual_multiplier"],
        linewidth=2.5,
        color="darkred",
    )
    ax2.axhline(y=1.0, linestyle="--", color="gray", alpha=0.7, label="No correction")

    ax2.set_xlabel("Cumulative Distance (km)", fontsize=12)
    ax2.set_ylabel("Residual Multiplier", fontsize=12)
    ax2.set_title("ML Model Correction Factor Over Distance", fontsize=13, fontweight="bold")
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=11)

    # Add annotation
    avg_mult = results["residual_multiplier"].mean()
    ax2.text(
        0.02, 0.98,
        f"Average multiplier: {avg_mult:.3f}\n"
        f"(>1 = slower than baseline)",
        transform=ax2.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.5),
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Saved plot to {save_path}")
    else:
        plt.show()


def main():
    """Generate pace evolution plots for multiple grades."""
    # Load model
    project_root = Path(__file__).resolve().parents[2]
    model_path = project_root / "data_analysis" / "predictor" / "residual_model.joblib"
    processed_root = project_root / "data_analysis" / "data" / "processed"
    output_dir = Path(__file__).parent / "plots"
    output_dir.mkdir(exist_ok=True)

    if not model_path.exists():
        print(f"Error: Model not found at {model_path}")
        print("Run: cd data_analysis && python predictor/train.py")
        return

    print(f"Loading model from {model_path}...")
    model = joblib.load(model_path)

    print(f"Building global curve from {processed_root}...")
    global_curve = build_global_curve(processed_root)

    # Test parameters
    flat_pace = 5.0  # 5 min/km flat pace
    max_distance_km = 40.0
    grades = [0, 5, 10, 15]  # Different grades to test

    print(f"\nGenerating pace evolution plots...")
    print(f"Flat pace: {flat_pace:.2f} min/km")
    print(f"Max distance: {max_distance_km:.1f} km")
    print(f"Grades: {grades}")

    for grade in grades:
        print(f"\nProcessing grade {grade:+.1f}%...")

        # Generate predictions
        results = predict_pace_at_grade_over_distance(
            model,
            global_curve,
            grade,
            flat_pace,
            max_distance_km,
        )

        # Print summary
        initial_pace = results["predicted_pace"].iloc[0]
        final_pace = results["predicted_pace"].iloc[-1]
        pace_increase = final_pace - initial_pace

        print(f"  Initial pace: {initial_pace:.2f} min/km")
        print(f"  Final pace: {final_pace:.2f} min/km")
        print(f"  Increase: +{pace_increase:.2f} min/km")

        # Plot
        save_path = output_dir / f"pace_evolution_grade_{grade:+.0f}pct.png"
        plot_pace_evolution(results, grade, flat_pace, save_path)

    print(f"\nAll plots saved to {output_dir}/")
    print("\nInterpretation:")
    print("- Baseline (dashed): Pure global curve without fatigue")
    print("- ML-corrected: Model prediction including distance/fatigue effects")
    print("- Residual multiplier >1: Model predicts slower than baseline (fatigue)")
    print("- Residual multiplier <1: Model predicts faster than baseline")


if __name__ == "__main__":
    main()
