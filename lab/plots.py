import matplotlib.pyplot as plt
import pandas as pd

# Define heart rate zones as constants
HEART_RATE_ZONES = {
    'Zone 1': (0, 137),
    'Zone 2': (137, 147),
    'Zone 3': (147, 160),
    'Zone 4': (160, float('inf'))
}

def load_and_filter_data(filepath, outlier_flag=1):
    """
    Load data from a CSV file, filter outliers.
    """
    df = pd.read_csv(filepath)
    df = df[df['outlier'] == outlier_flag]
    return df

def convert_velocity(df):
    """
    Convert velocity from m/s to min/km and back to m/s after filtering.
    """
    df['velocity_smooth'] = (1000 / df['velocity_smooth']) / 60
    df = df[df['velocity_smooth'] < 50]  # Exclude outliers
    df['velocity_smooth'] = 1000 / (df['velocity_smooth'] * 60)
    return df

def calculate_avg_speed(df):
    """
    Group by 'grade_smooth' and calculate the mean and standard deviation of 'velocity_smooth'.
    """
    avg_speed = df.groupby('grade_smooth')['velocity_smooth'].agg(['mean', 'std']).reset_index()
    return avg_speed

def plot_avg_speed(avg_speed, original_x, original_y, title):
    """
    Plot average speed per grade with error bars.
    """
    x = avg_speed['grade_smooth']
    y = avg_speed['mean']
    yerr = avg_speed['std']

    # plt.errorbar(x, y, yerr=yerr, fmt='o', markersize=5, alpha=0.5, ecolor='red', capsize=3)
    plt.plot(x, y, 'o', markersize=5, alpha=0.5, label=title)
    # plt.scatter(original_x, original_y, s=2, alpha=0.1)
    plt.xlabel('Grade Smooth (%)')
    plt.ylabel('Average Speed (m/s)')
    # plt.title(title)
    # plt.show()

def analyze_heart_zone(df, hr_min, hr_max, title):
    """
    Analyze and plot data for a specific heart rate zone.
    """
    df_zone = df[(df['heartrate'] >= hr_min) & (df['heartrate'] < hr_max)]
    df_zone = convert_velocity(df_zone)
    avg_speed = calculate_avg_speed(df_zone)
    plot_avg_speed(avg_speed, df_zone['grade_smooth'], df_zone['velocity_smooth'], title)

def calculate_mean_delta_time(df):
    """
    Calculate the mean delta time between consecutive measurements.
    """
    df['time'] = pd.to_datetime(df['time'], unit='s')  # Assuming 'time' is in seconds
    df = df.sort_values('time')  # Ensure data is sorted by time
    df['delta_time'] = df['time'].diff().dt.total_seconds().fillna(0)
    mean_delta_time = df['delta_time'].mean()
    return mean_delta_time

def compute_time_in_heart_zones(df, mean_delta_time):
    """
    Compute the total time spent in each heart rate zone.
    """
    time_in_zones = {}

    for zone, (hr_min, hr_max) in HEART_RATE_ZONES.items():
        zone_df = df[(df['heartrate'] >= hr_min) & (df['heartrate'] < hr_max)]
        time_in_zone = len(zone_df) * mean_delta_time
        time_in_zones[zone] = time_in_zone

    return time_in_zones

def heart_rate_distribution(df):
    """
    Calculate and print the percentage of time spent in each heart rate zone.
    """
    mean_delta_time = calculate_mean_delta_time(df)
    time_in_zones = compute_time_in_heart_zones(df, mean_delta_time)

    total_time = sum(time_in_zones.values())

    for zone, time in time_in_zones.items():
        percentage = (time / total_time) * 100
        print(f"{zone}: {percentage:.2f}%")

def main():
    filepath = 'combined_data_with_trend_outliers.csv'
    df = load_and_filter_data(filepath)

    # Calculate and print heart rate distribution
    heart_rate_distribution(df)

    # Analyze and plot for each heart zone
    for zone, (hr_min, hr_max) in HEART_RATE_ZONES.items():
        analyze_heart_zone(df, hr_min, hr_max, f'{zone}: Heart Rate {hr_min}-{hr_max if hr_max != float("inf") else "∞"}')
    plt.legend()
    plt.show()

if __name__ == '__main__':
    main()