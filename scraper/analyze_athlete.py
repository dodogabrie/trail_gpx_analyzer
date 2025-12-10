#!/usr/bin/env python3
"""
Analyze Athlete Activities

Load scraped athlete activities and create gradient/pace plots.

Usage:
    python analyze_athlete.py --athlete-id 5452411
    python analyze_athlete.py --athlete-dir data/strava/athletes/5452411
"""

import sys
import argparse
import json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import RANSACRegressor
from sklearn.preprocessing import PolynomialFeatures
from scipy.interpolate import UnivariateSpline

sys.path.insert(0, str(Path(__file__).parent.parent))


def is_flat_activity(df: pd.DataFrame, flat_threshold: float = 1.0, flat_ratio: float = 0.90) -> bool:
    """Determine if an activity is mostly flat terrain.

    Args:
        df: DataFrame with grade_smooth column
        flat_threshold: Grade percentage threshold for considering flat (default 1.0%)
        flat_ratio: Minimum ratio of flat points to consider activity flat (default 0.90)

    Returns:
        True if activity is mostly flat, False otherwise
    """
    if 'grade_smooth' not in df.columns or len(df) == 0:
        return True

    # Count points with grade between -threshold and +threshold
    flat_points = ((df['grade_smooth'] >= -flat_threshold) &
                   (df['grade_smooth'] <= flat_threshold)).sum()

    ratio = flat_points / len(df)
    return ratio >= flat_ratio


def load_athlete_streams(athlete_dir: Path) -> pd.DataFrame:
    """Load all stream data from athlete directory.

    Args:
        athlete_dir: Path to athlete data directory

    Returns:
        Combined DataFrame with all activities
    """
    streams_files = list(athlete_dir.glob("*_streams.json"))

    if not streams_files:
        print(f"No stream files found in {athlete_dir}")
        return pd.DataFrame()

    print(f"Loading {len(streams_files)} activities...")

    all_data = []
    flat_activities = 0

    for stream_file in streams_files:
        activity_id = stream_file.stem.replace("_streams", "")

        try:
            with open(stream_file) as f:
                streams = json.load(f)

            # Convert to DataFrame
            df = pd.DataFrame()

            # Add available streams
            for key in ['time', 'distance', 'altitude', 'grade_smooth',
                       'velocity_smooth', 'heartrate', 'cadence', 'moving']:
                if key in streams:
                    df[key] = streams[key]

            # Add latlng if available
            if 'latlng' in streams and streams['latlng']:
                latlng = streams['latlng']
                if latlng and len(latlng) > 0:
                    df['lat'] = [coord[0] for coord in latlng]
                    df['lon'] = [coord[1] for coord in latlng]

            df['activity_id'] = activity_id

            # Skip flat activities
            if is_flat_activity(df):
                flat_activities += 1
                continue

            all_data.append(df)

        except Exception as e:
            print(f"Error loading {stream_file}: {e}")
            continue

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    print(f"Loaded {len(combined_df)} data points from {len(all_data)} activities")
    if flat_activities > 0:
        print(f"Skipped {flat_activities} flat terrain activities")

    return combined_df


def filter_moving_data(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to only moving data points.

    Args:
        df: Input DataFrame

    Returns:
        Filtered DataFrame
    """
    if 'moving' in df.columns:
        df = df[df['moving'] == True].copy()
        print(f"After filtering moving data: {len(df)} points")

    # Remove invalid velocity values
    if 'velocity_smooth' in df.columns:
        df = df[df['velocity_smooth'] > 0].copy()
        df = df[df['velocity_smooth'] < 10].copy()  # < 10 m/s = < 36 km/h

    # Remove extreme grades
    if 'grade_smooth' in df.columns:
        df = df[(df['grade_smooth'] > -50) & (df['grade_smooth'] < 50)].copy()

    return df


def remove_outliers_ransac(df: pd.DataFrame, degree: int = 3) -> pd.DataFrame:
    """Remove outliers using RANSAC regression.

    Args:
        df: DataFrame with grade_smooth and velocity_smooth
        degree: Polynomial degree for fitting

    Returns:
        DataFrame with outliers removed and inlier_mask column
    """
    df_clean = df.dropna(subset=['grade_smooth', 'velocity_smooth']).copy()

    X = df_clean[['grade_smooth']].values
    y = df_clean['velocity_smooth'].values

    # Create polynomial features
    poly = PolynomialFeatures(degree=degree)
    X_poly = poly.fit_transform(X)

    # Fit RANSAC
    ransac = RANSACRegressor(
        min_samples=0.7,
        residual_threshold=0.5,
        random_state=42
    )
    ransac.fit(X_poly, y)

    # Mark inliers
    df_clean['inlier'] = ransac.inlier_mask_

    outliers_removed = (~ransac.inlier_mask_).sum()
    print(f"Removed {outliers_removed} outliers ({outliers_removed/len(df_clean)*100:.1f}%)")

    return df_clean


def fit_smooth_curve(grades: np.ndarray, speeds: np.ndarray, smoothing: float = None):
    """Fit smooth curve through data using binned averages and spline.

    Args:
        grades: Grade values
        speeds: Speed values
        smoothing: Smoothing factor (auto if None)

    Returns:
        Tuple of (grade_curve, speed_curve)
    """
    # Bin the data by grade for smoother curve
    df_temp = pd.DataFrame({'grade': grades, 'speed': speeds})

    # Remove any NaN values
    df_temp = df_temp.dropna()

    # Round grades to nearest 1% for binning (was 0.5%, too granular)
    df_temp['grade_bin'] = df_temp['grade'].round()

    # Calculate average speed per bin
    binned = df_temp.groupby('grade_bin')['speed'].agg(['mean', 'count']).reset_index()

    # Filter bins with enough data (at least 10 points)
    binned = binned[binned['count'] >= 10].copy()

    # Sort by grade
    binned = binned.sort_values('grade_bin')

    grades_binned = binned['grade_bin'].values
    speeds_binned = binned['mean'].values

    print(f"Using {len(grades_binned)} bins from {len(df_temp)} points")
    print(f"Grade bins range: [{grades_binned.min()}, {grades_binned.max()}]")
    print(f"Speed range: [{speeds_binned.min():.2f}, {speeds_binned.max():.2f}] m/s")

    # Create smooth curve
    grade_curve = np.linspace(grades_binned.min(), grades_binned.max(), 200)

    # Try multiple methods
    speed_curve = None

    # Method 1: Spline
    try:
        if smoothing is None:
            smoothing = len(grades_binned) * 2.0  # Increased smoothing

        spline = UnivariateSpline(grades_binned, speeds_binned, s=smoothing, k=min(3, len(grades_binned)-1))
        speed_curve = spline(grade_curve)

        if np.any(np.isnan(speed_curve)):
            raise ValueError("Spline produced NaN values")

        print(f"✓ Fitted spline successfully")
    except Exception as e:
        print(f"Spline failed: {e}")

    # Method 2: Polynomial fallback
    if speed_curve is None or np.any(np.isnan(speed_curve)):
        try:
            degree = min(4, len(grades_binned)-1)
            poly_coef = np.polyfit(grades_binned, speeds_binned, degree)
            speed_curve = np.polyval(poly_coef, grade_curve)
            print(f"✓ Using polynomial (degree {degree})")
        except Exception as e:
            print(f"Polynomial failed: {e}")

    # Method 3: Linear interpolation as last resort
    if speed_curve is None or np.any(np.isnan(speed_curve)):
        print("Using linear interpolation as fallback")
        speed_curve = np.interp(grade_curve, grades_binned, speeds_binned)

    return grade_curve, speed_curve


def plot_grade_vs_speed(df: pd.DataFrame, output_file: str = None):
    """Create gradient vs pace plot with outlier removal and smooth curve.

    Args:
        df: DataFrame with grade_smooth and velocity_smooth
        output_file: Optional output file path
    """
    if 'grade_smooth' not in df.columns or 'velocity_smooth' not in df.columns:
        print("Missing required columns for plotting")
        return

    # Remove outliers
    print("\nRemoving outliers using RANSAC...")
    df_clean = remove_outliers_ransac(df)
    df_inliers = df_clean[df_clean['inlier']].copy()
    df_outliers = df_clean[~df_clean['inlier']].copy()

    # Fit smooth curve
    print(f"\nFitting curve with {len(df_inliers)} inlier points...")
    grade_curve, speed_curve = fit_smooth_curve(
        df_inliers['grade_smooth'].values,
        df_inliers['velocity_smooth'].values
    )
    print(f"Curve fitted: grade range [{grade_curve.min():.1f}, {grade_curve.max():.1f}]")
    print(f"Curve speed range: [{speed_curve.min():.2f}, {speed_curve.max():.2f}] m/s")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # Downsample data for plotting (show only fraction of points)
    sample_size = min(5000, len(df_inliers))
    df_inliers_sample = df_inliers.sample(n=sample_size, random_state=42) if len(df_inliers) > sample_size else df_inliers

    sample_size_outliers = min(1000, len(df_outliers))
    df_outliers_sample = df_outliers.sample(n=sample_size_outliers, random_state=42) if len(df_outliers) > sample_size_outliers else df_outliers

    # Plot 1: Speed vs Grade
    # Outliers in red
    if len(df_outliers_sample) > 0:
        ax1.scatter(df_outliers_sample['grade_smooth'], df_outliers_sample['velocity_smooth'],
                   s=2, alpha=0.15, color='red', label=f'Outliers ({len(df_outliers)} total)', rasterized=True)

    # Inliers in blue
    ax1.scatter(df_inliers_sample['grade_smooth'], df_inliers_sample['velocity_smooth'],
               s=2, alpha=0.08, color='lightblue', label=f'Data points ({len(df_inliers)} total)', rasterized=True)

    # Smooth curve - MAKE IT STAND OUT
    ax1.plot(grade_curve, speed_curve, 'g-', linewidth=5,
            label='Athlete curve', zorder=100, alpha=0.9)
    # Add shadow for better visibility
    ax1.plot(grade_curve, speed_curve, 'darkgreen', linewidth=7,
            zorder=99, alpha=0.3)

    ax1.set_xlabel('Grade (%)', fontsize=12)
    ax1.set_ylabel('Speed (m/s)', fontsize=12)
    ax1.set_title('Speed vs Gradient (Athlete Performance Curve)', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best')

    # Plot 2: Pace vs Grade
    # Convert to pace
    df_pace = df_inliers.copy()
    df_pace['pace_min_km'] = 1000 / (df_pace['velocity_smooth'] * 60)
    df_pace = df_pace[df_pace['pace_min_km'] < 15]

    # Sample for plotting
    sample_size_pace = min(5000, len(df_pace))
    df_pace_sample = df_pace.sample(n=sample_size_pace, random_state=42) if len(df_pace) > sample_size_pace else df_pace

    pace_curve = 1000 / (speed_curve * 60)
    pace_curve = np.clip(pace_curve, 0, 15)  # Limit extreme values

    df_outliers_pace = df_outliers_sample.copy()
    df_outliers_pace['pace_min_km'] = 1000 / (df_outliers_pace['velocity_smooth'] * 60)
    df_outliers_pace = df_outliers_pace[df_outliers_pace['pace_min_km'] < 15]

    # Outliers
    if len(df_outliers_pace) > 0:
        ax2.scatter(df_outliers_pace['grade_smooth'], df_outliers_pace['pace_min_km'],
                   s=2, alpha=0.15, color='red', label='Outliers', rasterized=True)

    # Inliers
    ax2.scatter(df_pace_sample['grade_smooth'], df_pace_sample['pace_min_km'],
               s=2, alpha=0.08, color='lightblue', label='Data points', rasterized=True)

    # Smooth curve - MAKE IT STAND OUT
    ax2.plot(grade_curve, pace_curve, 'g-', linewidth=5,
            label='Athlete curve', zorder=100, alpha=0.9)
    # Add shadow
    ax2.plot(grade_curve, pace_curve, 'darkgreen', linewidth=7,
            zorder=99, alpha=0.3)

    ax2.set_xlabel('Grade (%)', fontsize=12)
    ax2.set_ylabel('Pace (min/km)', fontsize=12)
    ax2.set_title('Pace vs Gradient (Athlete Performance Curve)', fontsize=14, fontweight='bold')
    ax2.invert_yaxis()
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best')

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Saved plot to {output_file}")

    plt.show()


def plot_heart_rate_zones(df: pd.DataFrame, zones: dict, output_file: str = None):
    """Plot speed vs gradient colored by heart rate zones.

    Args:
        df: DataFrame with heartrate, grade_smooth, velocity_smooth
        zones: Dictionary of heart rate zones
        output_file: Optional output file path
    """
    if 'heartrate' not in df.columns:
        print("No heart rate data available")
        return

    fig, ax = plt.subplots(figsize=(12, 8))

    colors = ['green', 'yellow', 'orange', 'red']

    for (zone_name, (hr_min, hr_max)), color in zip(zones.items(), colors):
        zone_df = df[(df['heartrate'] >= hr_min) & (df['heartrate'] < hr_max)]

        if len(zone_df) == 0:
            continue

        avg_speed = zone_df.groupby('grade_smooth')['velocity_smooth'].agg(['mean', 'std']).reset_index()

        ax.errorbar(avg_speed['grade_smooth'], avg_speed['mean'],
                   yerr=avg_speed['std'], fmt='o-', color=color,
                   markersize=3, alpha=0.7, capsize=2, label=zone_name)

    ax.set_xlabel('Grade (%)')
    ax.set_ylabel('Speed (m/s)')
    ax.set_title('Speed vs Gradient by Heart Rate Zone')
    ax.grid(True, alpha=0.3)
    ax.legend()

    if output_file:
        plt.savefig(output_file, dpi=150)
        print(f"Saved plot to {output_file}")

    plt.show()


def analyze_statistics(df: pd.DataFrame):
    """Print summary statistics.

    Args:
        df: DataFrame with activity data
    """
    print("\n" + "="*60)
    print("ATHLETE STATISTICS")
    print("="*60)

    print(f"\nTotal data points: {len(df)}")
    print(f"Number of activities: {df['activity_id'].nunique()}")

    if 'distance' in df.columns:
        total_km = df.groupby('activity_id')['distance'].max().sum() / 1000
        print(f"Total distance: {total_km:.1f} km")

    if 'velocity_smooth' in df.columns:
        avg_speed = df['velocity_smooth'].mean()
        avg_pace = 1000 / (avg_speed * 60)
        print(f"\nAverage speed: {avg_speed:.2f} m/s ({avg_pace:.2f} min/km)")

    if 'grade_smooth' in df.columns:
        print(f"\nGrade range: {df['grade_smooth'].min():.1f}% to {df['grade_smooth'].max():.1f}%")
        print(f"Average grade: {df['grade_smooth'].mean():.2f}%")

    if 'heartrate' in df.columns:
        print(f"\nHeart rate range: {df['heartrate'].min():.0f} to {df['heartrate'].max():.0f} bpm")
        print(f"Average heart rate: {df['heartrate'].mean():.1f} bpm")

    if 'altitude' in df.columns:
        print(f"\nAltitude range: {df['altitude'].min():.0f} to {df['altitude'].max():.0f} m")


def main():
    parser = argparse.ArgumentParser(description="Analyze scraped athlete activities")

    parser.add_argument('--athlete-id', type=int, help='Athlete ID')
    parser.add_argument('--athlete-dir', help='Direct path to athlete directory')
    parser.add_argument('--output', help='Output file for plots (without extension)')
    parser.add_argument('--hr-zones', action='store_true', help='Plot heart rate zones')

    args = parser.parse_args()

    # Find athlete directory
    if args.athlete_dir:
        athlete_dir = Path(args.athlete_dir)
    elif args.athlete_id:
        athlete_dir = Path(f"data/strava/athletes/{args.athlete_id}")
    else:
        print("ERROR: Provide --athlete-id or --athlete-dir")
        return

    if not athlete_dir.exists():
        print(f"ERROR: Directory not found: {athlete_dir}")
        return

    print(f"Analyzing athlete data from: {athlete_dir}\n")

    # Load data
    df = load_athlete_streams(athlete_dir)

    if df.empty:
        print("No data loaded")
        return

    # Filter data
    df = filter_moving_data(df)

    # Statistics
    analyze_statistics(df)

    # Plot gradient vs speed
    output_file = f"{args.output}_grade_speed.png" if args.output else None
    plot_grade_vs_speed(df, output_file)

    # Plot heart rate zones if requested
    if args.hr_zones and 'heartrate' in df.columns:
        zones = {
            'Zone 1 (Easy)': (0, 137),
            'Zone 2 (Moderate)': (137, 147),
            'Zone 3 (Hard)': (147, 160),
            'Zone 4 (Max)': (160, 250)
        }
        output_file = f"{args.output}_hr_zones.png" if args.output else None
        plot_heart_rate_zones(df, zones, output_file)


if __name__ == '__main__':
    main()
