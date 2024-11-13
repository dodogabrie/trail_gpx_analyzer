from dash import html, Input, Output, State
from strava.auth import get_access_token
from strava.api import fetch_activities, download_and_enhance_gpx
from strava.activity_filter import filter_activities_by_length, get_timestamp_for_last_year

output_directory = 'data/strava/'

def register_strava_callbacks(app, df):
    @app.callback(
        Output('strava-output', 'children'),
        [Input('auth-button', 'n_clicks')],
        [State('auth-code-store', 'data')]
    )
    def fetch_strava_activities(n_clicks, auth_code):
        if n_clicks == 0 or not auth_code:
            return "Click 'Authorize Strava' to begin."

        access_token, _ = get_access_token(auth_code)
        after_timestamp = get_timestamp_for_last_year()
        activities = fetch_activities(access_token, after_timestamp)
        route_length = df['Distance'].iloc[-1]
        matching_activities = filter_activities_by_length(activities, route_length)

        if not matching_activities:
            return "No matching activities found in the last year."

        for activity in matching_activities:
            activity_id = activity['id']
            start_time = activity.get('start_date')  # Use 'start_date_local' if you prefer local time
            download_and_enhance_gpx(activity_id, access_token, start_time, output_directory)

        activity_names = [activity['name'] for activity in matching_activities]
        return html.Ul([html.Li(f"Downloaded: {name}") for name in activity_names])
