import pandas as pd
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS coordinates using Haversine formula."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    
    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

def create_dataframe(latitudes, longitudes, elevations, times):
    """Create a DataFrame from GPX data with calculated distances."""
    df = pd.DataFrame({
        'Latitude': latitudes,
        'Longitude': longitudes,
        'Elevation': elevations,
        'Time': times
    })
    
    distances = [0]
    for i in range(1, len(df)):
        dist = haversine(
            df.loc[i-1, 'Latitude'], df.loc[i-1, 'Longitude'],
            df.loc[i, 'Latitude'], df.loc[i, 'Longitude']
        )
        distances.append(distances[-1] + dist)
    
    df['Distance'] = distances
    return df

def process_gpx_data(parsed_data):
    """Process parsed GPX data into structured format for API response."""
    df = create_dataframe(
        parsed_data['latitudes'],
        parsed_data['longitudes'],
        parsed_data['elevations'],
        parsed_data['times']
    )
    
    points = []
    for idx, row in df.iterrows():
        points.append({
            'lat': row['Latitude'],
            'lon': row['Longitude'],
            'elevation': row['Elevation'],
            'distance': row['Distance'],
            'time': row['Time']
        })
    
    bounds = {
        'minLat': df['Latitude'].min(),
        'maxLat': df['Latitude'].max(),
        'minLon': df['Longitude'].min(),
        'maxLon': df['Longitude'].max()
    }
    
    return {
        'points': points,
        'bounds': bounds,
        'total_distance': df['Distance'].iloc[-1] if len(df) > 0 else 0
    }
