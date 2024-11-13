
from flask_routes import server
import dash
from dash import dcc, html
import os
import plotly.graph_objects as go
from maps.parse_gpx import parse_gpx
from maps.display_map import display_map
from maps.display_elevation_profile import create_dataframe, display_elevation_profile
from callbacks.auth_callbacks import register_auth_callbacks
from callbacks.strava_callbacks import register_strava_callbacks
from callbacks.map_callbacks import register_map_callbacks
from callbacks.map_interactions_callbacks import register_hover_selection_callbacks


# Initialize Dash app
app = dash.Dash(__name__, server=server, routes_pathname_prefix='/dash/')

# Specify the path to your GPX file
filepath = os.path.join('data', 'cinghiale24.gpx')
# filepath = os.path.join('data', 'activity_10648019382.gpx')
latitudes, longitudes, elevations, times = parse_gpx(filepath)
df = create_dataframe(latitudes, longitudes, elevations, times)
fig_elev = display_elevation_profile(df)
fig_map = display_map(latitudes, longitudes)

# Define Dash layout
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='auth-code-store'),
    dcc.Store(id='map-zoom-store', data=fig_map.layout.mapbox.zoom),
    dcc.Store(id='map-center-store', data={
        'lat': fig_map.layout.mapbox.center.lat,
        'lon': fig_map.layout.mapbox.center.lon
    }),
    html.Div([
        html.Button('Authorize Strava', id='auth-button', n_clicks=0),
        html.Div(id='strava-output')
    ]),
    dcc.Graph(id='route-map', figure=fig_map, style={'height': '400px', 'width': '90%'}),
    html.Div(id='stats-output', style={'padding': '20px', 'fontSize': '20px'}),
    dcc.Graph(id='elevation-profile', figure=fig_elev, style={'height': '300px', 'width': '90%'})
], style={'display': 'flex', 'flex-direction': 'column', 'justify-content': 'center', 'align-items': 'center'})

# Register Dash callbacks
# register_callbacks(app, df, fig_map)
register_auth_callbacks(app)
register_strava_callbacks(app, df)
register_map_callbacks(app)
register_hover_selection_callbacks(app, df, fig_map)

if __name__ == '__main__':
    server.run(debug=True)