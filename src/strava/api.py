import os
import requests as r
import time
import json
import gpxpy.gpx
import pandas as pd
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2


def fetch_activities(access_token, after_timestamp):
    """Fetch activities from Strava after a certain timestamp."""
    headers = {'Authorization': f'Bearer {access_token}'}
    activities = []

    # Initial request to get the first page of activities
    page = 1
    while True:
        response = r.get(
            f"https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            params={'per_page': 100, 'page': page, 'after': after_timestamp}
        )
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        activities.extend(data)
        page += 1

    return activities


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a)) * 1000  # Distance in meters


def download_and_enhance_gpx(activity_id, access_token, start_time, output_directory='data/strava/'):
    """Download the GPX from Strava and enhance it with time data from the streams API."""
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # Step 1: Download the original GPX file from Strava
    gpx_url = f"https://www.strava.com/activities/{activity_id}/export_gpx"
    headers = {'Authorization': f'Bearer {access_token}'}
    response = r.get(gpx_url, headers=headers)

    if response.status_code == 200:
        gpx_path = os.path.join(output_directory, f"activity_{activity_id}.gpx")
        with open(gpx_path, 'wb') as gpx_file:
            gpx_file.write(response.content)
        print(f"Downloaded GPX file for activity {activity_id} to {gpx_path}")
    else:
        print(f"Failed to download GPX file for activity {activity_id}. Status code: {response.status_code}")
        return None

    # Step 2: Get the distance and time data from the Strava Streams API
    stream_url = f"https://www.strava.com/api/v3/activities/{activity_id}/streams"
    required_params = ['time', 'altitude', 'grade_smooth', 'velocity_smooth', 'heartrate']
    data = {key: [] for key in required_params}

    for param in required_params:
        params = {'keys': [param], 'key_by_type': 'true'}
        response = r.get(stream_url, headers=headers, params=params)

        if response.status_code != 200:
            print(f"Failed to fetch streams. Status code: {response.status_code}")
            return None

        streams = response.json()

        data[param] = streams.get(param, {}).get('data', [])
        print(param, len(data[param]))
        if param == 'time':
            data['distance'] = streams.get('distance', {}).get('data', [])


    if not all(len(data[key]) for key in data):
        print("Error: Missing or incomplete data in activity streams.")
        return None


    # Create a DataFrame from the streams data
    df = pd.DataFrame(data)

    # Save the DataFrame to CSV in the same directory as the GPX file
    csv_path = os.path.join(output_directory, f"activity_{activity_id}_streams.csv")
    df.to_csv(csv_path, index=False)
    print(f"Saved streams data to {csv_path}")

    # Step 3: Parse the GPX file and insert the time data based on the distance
    with open(gpx_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    time_index = 0
    cumulative_distance = 0

    # Convert start_time to a datetime object if it's a string
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")

    for track in gpx.tracks:
        for segment in track.segments:
            for i in range(1, len(segment.points)):
                point1 = segment.points[i - 1]
                point2 = segment.points[i]

                # Calculate distance between the current point and the previous point
                distance = haversine(point1.latitude, point1.longitude, point2.latitude, point2.longitude)
                cumulative_distance += distance

                # Find the closest distance in the stream data
                while time_index < len(data['distance']) - 1 and data['distance'][time_index] < cumulative_distance:
                    time_index += 1

                if time_index < len(data['time']):
                    # Set the time for the current point
                    point2.time = start_time + timedelta(seconds=data['time'][time_index])

    # Step 4: Save the enhanced GPX file
    with open(gpx_path, 'w') as enhanced_gpx_file:
        enhanced_gpx_file.write(gpx.to_xml())

    print(f"Replaced the original GPX file with enhanced time data for activity {activity_id} at {gpx_path}")
    return gpx_path