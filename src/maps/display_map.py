import plotly.graph_objects as go

def generate_fig_map(latitudes, longitudes):
    # Create the map figure using OpenStreetMap
    fig_map = go.Figure(go.Scattermapbox(
        lat=latitudes,
        lon=longitudes,
        mode='lines',
        line=dict(width=2, color='blue'),
        showlegend=False,
    ))
    return fig_map

def display_map(latitudes, longitudes, fig_map = None):
    if fig_map is None:
        fig_map = generate_fig_map(latitudes, longitudes)

    # Update the layout without specifying an access token
    fig_map.update_layout(
        mapbox=dict(
            style='open-street-map',
            center=dict(lat=sum(latitudes)/len(latitudes), lon=sum(longitudes)/len(longitudes)),
            zoom=11,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
    )
    return fig_map


