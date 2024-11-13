import gpxpy
import os
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2

def parse_csv_files_in_directory(directory):
    all_data = []

    for file in os.listdir(directory):
        if file.endswith('.csv'):
            file_path = os.path.join(directory, file)
            df = pd.read_csv(file_path)
            all_data.append(df)

    # Concatenate all dataframes into a single dataframe
    combined_df = pd.concat(all_data, ignore_index=True)

    # Export the combined DataFrame to a CSV file
    combined_df.to_csv('combined_data.csv', index=False)

    return combined_df

def parse_gpx_files_in_directory(directory):
    data = []

    points_with_time = 0
    for file in os.listdir(directory):
        if file.endswith('.gpx'):
            with open(os.path.join(directory, file), 'r') as gpx_file:
                gpx = gpxpy.parse(gpx_file)
                for track in gpx.tracks:
                    for segment in track.segments:
                        for i in range(1, len(segment.points)):
                            point1 = segment.points[i - 1]
                            point2 = segment.points[i]

                            # Check for valid time data
                            if point1.time is None or point2.time is None:
                                continue  # Skip this segment if time data is missing
                            else:
                                points_with_time += 1

                            # Calculate distance between points
                            distance = haversine(point1.latitude, point1.longitude, point2.latitude, point2.longitude)
                            elevation_gain = point2.elevation - point1.elevation
                            slope = (elevation_gain / distance) * 100 if distance > 0 else 0
                            time_diff = (point2.time - point1.time).total_seconds() / 60  # time in minutes
                            pace = (time_diff / (distance / 1000)) if distance > 0 else None  # pace in min/km

                            if pace is None:
                                continue
                            if pace > 10 or np.abs(slope) > 75 or distance < 0.1:
                                continue

                            if pace:
                                data.append({
                                    'distance': distance,
                                    'slope': slope,
                                    'pace': pace,
                                })
                print(f'found {points_with_time} timestamp')

    df = pd.DataFrame(data)

    # Export the DataFrame to a CSV file
    df.to_csv('data.csv', index=False)

    return df


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a)) * 1000  # Distance in meters


def group_pace_by_slope(df, slope_intervals):
    grouped_data = {}

    for interval in slope_intervals:
        min_slope, max_slope = interval
        group = df[(df['grade_smooth'] >= min_slope) & (df['grade_smooth'] < max_slope)]

        if not group.empty:
            # Convert m/s to min/km: (1000m/speed)/(60s) = min/km
            mean_velocity = group['velocity_smooth'].mean()
            if mean_velocity > 0:
                avg_pace = (1000/mean_velocity)/60
            else:
                avg_pace = 30 

            # Calculate uncertainty, avoiding division by zero
            velocities = group['velocity_smooth']
            velocities = velocities[velocities > 0]  # Filter out zero velocities
            uncertainty = (1000/velocities).std()/60 if len(velocities) > 0 else 0

            grouped_data[(min_slope, max_slope)] = {
                'average_pace': avg_pace,
                'uncertainty': uncertainty
            }
    return grouped_data

def predict_time_for_gpx(input_gpx_path, slope_pace_data):
    with open(input_gpx_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    total_time = 0

    for track in gpx.tracks:
        for segment in track.segments:
            for i in range(1, len(segment.points)):
                point1 = segment.points[i - 1]
                point2 = segment.points[i]

                distance = haversine(point1.latitude, point1.longitude, point2.latitude, point2.longitude)
                elevation_gain = point2.elevation - point1.elevation
                slope = (elevation_gain / distance) * 100 if distance > 0 else 0

                for interval, pace_info in slope_pace_data.items():
                    if interval[0] <= slope < interval[1]:
                        segment_time = (distance / 1000) * pace_info['average_pace']  # Time in minutes
                        total_time += segment_time
                        break

    return total_time  # Total time in minutes


def create_slope_intervals(min_slope=-30, max_slope=30, step=2):
    """Create slope intervals from min_slope to max_slope with a given step."""
    intervals = [(i, i + step) for i in range(min_slope, max_slope, step)]
    return intervals


# if __name__ == '__main__':
#     slope_intervals = create_slope_intervals(min_slope=-50, max_slope=50, step=1)

#     df = parse_gpx_files_in_directory('data/strava/')
#     slope_pace_data = group_pace_by_slope(df, slope_intervals)
#     predicted_time = predict_time_for_gpx('data/cinghiale24.gpx', slope_pace_data)
#     print(f"Predicted time to complete the route: {predicted_time:.2f} minutes")


if __name__ == '__main__':
    # Example usage:
    # Load data from CSV files and process it
    combined_df = parse_csv_files_in_directory('data/strava/')
    slope_intervals = create_slope_intervals(min_slope=-50, max_slope=50, step=1)
    slope_pace_data = group_pace_by_slope(combined_df, slope_intervals)
    predicted_time = predict_time_for_gpx('data/cinghiale24.gpx', slope_pace_data)
    print(f"Predicted time to complete the route: {predicted_time:.2f} minutes")