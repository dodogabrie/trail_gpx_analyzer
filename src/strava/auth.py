import requests
from dotenv import load_dotenv, set_key
import os
import time
from flask import request, redirect, session

# Load environment variables from .env file
load_dotenv()

CLIENT_ID = '138943'
CLIENT_SECRET = '2a19fb2e110bc07f82b97104060ed3cedd6f84e3'
REDIRECT_URI = 'http://localhost:5000/callback'

def get_auth_url():
    """Generate the Strava authorization URL."""
    return (
        f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code"
        f"&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
    )

def handle_callback():
    """Handle the OAuth callback from Strava and store the auth code."""
    auth_code = request.args.get('code')
    if not auth_code:
        return "Authorization failed. No code returned."
    session['auth_code'] = auth_code
    return redirect(f'/dash?auth_code={auth_code}')

def is_token_valid():
    """Check if the current access token is valid."""
    expires_at = os.getenv('EXPIRES_AT')
    current_time = time.time()
    if expires_at:
        try:
            expires_at = int(expires_at)
        except ValueError:
            print("Error: EXPIRES_AT is not a valid integer.")
            return False
        if expires_at > int(current_time):
            return True
    return False

def get_stored_access_token():
    """Get the stored access token if it's valid."""
    if is_token_valid():
        return os.getenv('ACCESS_TOKEN')
    return None

def get_access_token(auth_code=None):
    """Check for a valid token in the .env file or exchange the auth_code for a new access token."""
    access_token = get_stored_access_token()

    if access_token:
        print("Using stored access token.")
        return access_token, os.getenv('REFRESH_TOKEN')

    if auth_code is None:
        raise ValueError("Authorization code is required for exchanging a new access token.")

    # Exchange the auth_code for a new access token
    print("Exchanging authorization code for a new access token.")
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI
        }
    )
    response.raise_for_status()
    token_data = response.json()

    # Store access and refresh tokens in .env file
    set_key('.env', 'ACCESS_TOKEN', token_data['access_token'])
    set_key('.env', 'REFRESH_TOKEN', token_data['refresh_token'])
    set_key('.env', 'EXPIRES_AT', str(token_data['expires_at']))

    return token_data['access_token'], token_data['refresh_token']


def refresh_access_token():
    """Refresh the access token using the refresh token."""
    refresh_token = os.getenv('REFRESH_TOKEN')

    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
    )
    response.raise_for_status()
    token_data = response.json()

    # Update tokens in .env file
    set_key('.env', 'ACCESS_TOKEN', token_data['access_token'])
    set_key('.env', 'REFRESH_TOKEN', token_data['refresh_token'])
    set_key('.env', 'EXPIRES_AT', str(token_data['expires_at']))

    return token_data['access_token']
