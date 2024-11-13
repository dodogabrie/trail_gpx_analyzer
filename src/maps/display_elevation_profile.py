import pandas as pd
import numpy as np

# Function to calculate distance between two lat/lon points
def haversine(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    a = sin(delta_phi/2)**2 + cos(phi1)*cos(phi2)*sin(delta_lambda/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

def create_dataframe(latitudes, longitudes, elevations, times):
    # Calculate cumulative distance
    distances = [0]
    for i in range(1, len(latitudes)):
        distance = haversine(latitudes[i-1], longitudes[i-1], latitudes[i], longitudes[i])
        distances.append(distances[-1] + distance)

    # Create a DataFrame
    df = pd.DataFrame({
        'Latitude': latitudes,
        'Longitude': longitudes,
        'Elevation': elevations,
        'Distance': distances,
        'Time': times
    })
    return df

def display_elevation_profile(df):
    import plotly.express as px

    fig_elev = px.line(df, x='Distance', y='Elevation', hover_data=['Latitude', 'Longitude'])
    fig_elev.update_layout(
        xaxis_title='Distance (m)',
        yaxis_title='Elevation (m)',
        hovermode='x unified',
        dragmode="select"  # Set drag mode to selection
    )
    return fig_elev
