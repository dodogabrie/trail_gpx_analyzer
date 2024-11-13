import datetime

def filter_activities_by_length(activities, route_length, length_threshold=0.5):
    """Filter activities that match at least half the length of the route."""
    threshold_length = route_length * length_threshold
    return [activity for activity in activities if activity['distance'] >= threshold_length]

def get_timestamp_for_last_year():
    """Get the timestamp for one year ago."""
    one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)
    return int(one_year_ago.timestamp())
