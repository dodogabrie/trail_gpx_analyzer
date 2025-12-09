import requests
import time
from datetime import datetime, timedelta

class StravaService:
    """Service for interacting with Strava API."""
    
    BASE_URL = 'https://www.strava.com'
    API_URL = 'https://www.strava.com/api/v3'
    
    def __init__(self, client_id, client_secret, redirect_uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
    
    def get_auth_url(self, state=None):
        """Generate Strava authorization URL."""
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'approval_prompt': 'force',
            'scope': 'read,activity:read_all'
        }
        if state:
            params['state'] = state
        
        query = '&'.join([f'{k}={v}' for k, v in params.items()])
        return f'{self.BASE_URL}/oauth/authorize?{query}'
    
    def exchange_code(self, code):
        """Exchange authorization code for access token."""
        response = requests.post(
            f'{self.BASE_URL}/oauth/token',
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code'
            }
        )
        response.raise_for_status()
        return response.json()
    
    def refresh_token(self, refresh_token):
        """Refresh access token using refresh token."""
        response = requests.post(
            f'{self.BASE_URL}/oauth/token',
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }
        )
        response.raise_for_status()
        return response.json()
    
    def is_token_valid(self, expires_at):
        """Check if access token is still valid."""
        return expires_at > int(time.time())
    
    def get_valid_token(self, access_token, refresh_token, expires_at):
        """Get a valid access token, refreshing if necessary."""
        if self.is_token_valid(expires_at):
            return access_token, refresh_token, expires_at
        
        token_data = self.refresh_token(refresh_token)
        return (
            token_data['access_token'],
            token_data['refresh_token'],
            token_data['expires_at']
        )
    
    def fetch_activities(self, access_token, after_timestamp=None, per_page=100):
        """Fetch user activities from Strava."""
        headers = {'Authorization': f'Bearer {access_token}'}
        activities = []
        page = 1
        
        while True:
            params = {'per_page': per_page, 'page': page}
            if after_timestamp:
                params['after'] = after_timestamp
            
            response = requests.get(
                f'{self.API_URL}/athlete/activities',
                headers=headers,
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break
            
            activities.extend(data)
            page += 1
        
        return activities
    
    def download_streams(self, activity_id, access_token):
        """Download activity streams from Strava."""
        headers = {'Authorization': f'Bearer {access_token}'}
        stream_url = f'{self.API_URL}/activities/{activity_id}/streams'
        
        required_params = ['time', 'altitude', 'grade_smooth', 'velocity_smooth',
                          'heartrate', 'cadence', 'moving', 'distance']
        
        streams_data = {}
        
        for param in required_params:
            params = {'keys': param, 'key_by_type': 'true'}
            response = requests.get(stream_url, headers=headers, params=params)
            
            if response.status_code == 200:
                streams = response.json()
                streams_data[param] = streams.get(param, {}).get('data', [])
            else:
                streams_data[param] = []
        
        return streams_data
    
    def filter_activities_by_length(self, activities, target_distance, tolerance=0.1):
        """Filter activities by distance with tolerance."""
        min_distance = target_distance * (1 - tolerance)
        max_distance = target_distance * (1 + tolerance)
        
        return [
            activity for activity in activities
            if min_distance <= activity.get('distance', 0) <= max_distance
        ]
    
    def get_timestamp_for_last_year(self):
        """Get Unix timestamp for one year ago."""
        one_year_ago = datetime.now() - timedelta(days=365)
        return int(one_year_ago.timestamp())
