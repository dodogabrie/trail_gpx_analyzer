"""Analyze relationship between velocity and gradient for athlete activities.

This script aggregates velocity and gradient data from all activities
of a single athlete and creates scatter plots to visualize the relationship.
"""

import json
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def load_activity_streams(activity_id: str, athlete_dir: Path) -> pd.DataFrame:
    """Load streams data for a single activity.

    Args:
        activity_id: Activity ID
        athlete_dir: Directory containing athlete data

    Returns:
        DataFrame with time, velocity_smooth, grade_smooth
    """
    streams_path = athlete_dir / f"{activity_id}_streams.json"

    if not streams_path.exists():
        return None

    try:
        with open(streams_path) as f:
            streams = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Skipping {streams_path} due to JSON error: {exc}")
        return None

    # Check if required fields exist
    if 'velocity_smooth' not in streams or 'grade_smooth' not in streams:
        return None

    df = pd.DataFrame({
        'time': streams.get('time', []),
        'velocity_smooth': streams['velocity_smooth'],
        'grade_smooth': streams['grade_smooth'],
        'distance': streams.get('distance', [])
    })

    return df


def aggregate_athlete_data(athlete_id: str, data_dir: Path) -> pd.DataFrame:
    """Aggregate all activities for a single athlete.

    Args:
        athlete_id: Athlete ID
        data_dir: Base data directory

    Returns:
        Combined DataFrame with all activities
    """
    athlete_dir = data_dir / athlete_id

    # Load activities list
    activities_path = athlete_dir / "activities.json"
    if not activities_path.exists():
        print(f"No activities.json found for athlete {athlete_id}")
        return None

    with open(activities_path) as f:
        activities_data = json.load(f)

    all_data = []

    for activity_id in activities_data['activity_ids']:
        df = load_activity_streams(str(activity_id), athlete_dir)
        if df is not None:
            df['activity_id'] = activity_id
            all_data.append(df)

    if not all_data:
        print(f"No valid activity data found for athlete {athlete_id}")
        return None

    combined = pd.concat(all_data, ignore_index=True)

    print(f"Loaded {len(all_data)} activities with {len(combined)} data points")

    return combined


def plot_velocity_vs_gradient(df: pd.DataFrame, athlete_id: str, output_dir: Path):
    """Create scatter plot of velocity vs gradient.

    Args:
        df: DataFrame with velocity_smooth and grade_smooth
        athlete_id: Athlete ID for plot title
        output_dir: Directory to save plots
    """
    # Remove any NaN or infinite values
    df_clean = df[(df['velocity_smooth'].notna()) &
                  (df['grade_smooth'].notna()) &
                  (np.isfinite(df['velocity_smooth'])) &
                  (np.isfinite(df['grade_smooth']))].copy()

    # Smooth values with a centered rolling mean (point + 4 nearest neighbors)
    smoothed = df_clean[['velocity_smooth', 'grade_smooth']].rolling(
        window=5, center=True, min_periods=1
    ).mean()
    df_clean['velocity_smooth'] = smoothed['velocity_smooth']
    df_clean['grade_smooth'] = smoothed['grade_smooth']

    # Convert velocity to km/h for readability
    df_clean['velocity_kmh'] = df_clean['velocity_smooth'] * 3.6

    # Create figure with multiple plots
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle(f'Velocity vs Gradient Analysis - Athlete {athlete_id}', fontsize=16)

    # 1. Scatter plot - all points
    ax1 = axes[0, 0]
    ax1.scatter(df_clean['grade_smooth'], df_clean['velocity_kmh'],
                alpha=0.1, s=1, c='blue')
    ax1.set_xlabel('Gradient (%)')
    ax1.set_ylabel('Velocity (km/h)')
    ax1.set_title('All Data Points')
    ax1.grid(True, alpha=0.3)

    # 2. Hexbin plot - density visualization
    ax2 = axes[0, 1]
    hexbin = ax2.hexbin(df_clean['grade_smooth'], df_clean['velocity_kmh'],
                        gridsize=50, cmap='YlOrRd', mincnt=1)
    ax2.set_xlabel('Gradient (%)')
    ax2.set_ylabel('Velocity (km/h)')
    ax2.set_title('Density Plot')
    plt.colorbar(hexbin, ax=ax2, label='Count')

    # 3. Binned average - relationship trend
    ax3 = axes[1, 0]
    gradient_bins = np.arange(-20, 21, 1)
    df_clean['gradient_bin'] = pd.cut(df_clean['grade_smooth'], bins=gradient_bins)
    binned_stats = df_clean.groupby('gradient_bin', observed=False)['velocity_kmh'].agg(['mean', 'std', 'count'])
    binned_stats = binned_stats[binned_stats['count'] >= 10]  # Filter bins with few points

    bin_centers = [(interval.left + interval.right) / 2 for interval in binned_stats.index]
    ax3.errorbar(bin_centers, binned_stats['mean'], yerr=binned_stats['std'],
                 fmt='o-', capsize=3, alpha=0.7)
    ax3.set_xlabel('Gradient (%)')
    ax3.set_ylabel('Mean Velocity (km/h)')
    ax3.set_title('Average Velocity by Gradient (±1 std)')
    ax3.grid(True, alpha=0.3)

    # 4. Distribution plots
    ax4 = axes[1, 1]
    ax4_twin = ax4.twinx()
    ax4.hist(df_clean['grade_smooth'], bins=100, alpha=0.5, color='blue', label='Gradient')
    ax4_twin.hist(df_clean['velocity_kmh'], bins=100, alpha=0.5, color='red', label='Velocity')
    ax4.set_xlabel('Gradient (%) / Velocity (km/h)')
    ax4.set_ylabel('Gradient Frequency', color='blue')
    ax4_twin.set_ylabel('Velocity Frequency', color='red')
    ax4.set_title('Distributions')
    ax4.legend(loc='upper left')
    ax4_twin.legend(loc='upper right')

    plt.tight_layout()

    # Save plot
    output_path = output_dir / f'athlete_{athlete_id}_velocity_vs_gradient.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Plot saved to {output_path}")

    plt.show()

    # Print statistics
    print("\n=== Statistics ===")
    print(f"Total data points: {len(df_clean)}")
    print(f"\nGradient range: {df_clean['grade_smooth'].min():.1f}% to {df_clean['grade_smooth'].max():.1f}%")
    print(f"Mean gradient: {df_clean['grade_smooth'].mean():.1f}%")
    print(f"\nVelocity range: {df_clean['velocity_kmh'].min():.1f} to {df_clean['velocity_kmh'].max():.1f} km/h")
    print(f"Mean velocity: {df_clean['velocity_kmh'].mean():.1f} km/h")

    # Correlation
    correlation = df_clean['grade_smooth'].corr(df_clean['velocity_kmh'])
    print(f"\nCorrelation coefficient: {correlation:.3f}")


def main():
    """Main execution."""
    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data_analysis" / "data" / "processed"
    output_dir = project_root / "data_analysis" / "plot_scripts" / "velocity_vs_gradient"
    output_dir.mkdir(exist_ok=True, parents=True)

    # Get athlete ID from command line or use default
    if len(sys.argv) > 1:
        athlete_id = sys.argv[1]
        
        # Load and aggregate data
        df = aggregate_athlete_data(athlete_id, data_dir)
    
        if df is None:
            return
    
        # Create plots
        plot_velocity_vs_gradient(df, athlete_id, output_dir)
    else:
        # List available athletes
        athletes = [d.name for d in data_dir.iterdir() if d.is_dir()]
        if not athletes:
            print("No processed athlete data found")
            return

        print(f"Available athletes: {athletes}")
        print("Using all athletes")

        for athlete_id in athletes:
            # Load and aggregate data
            df = aggregate_athlete_data(athlete_id, data_dir)
        
            if df is None:
                return
        
            # Create plots
            plot_velocity_vs_gradient(df, athlete_id, output_dir)


if __name__ == "__main__":
    main()
