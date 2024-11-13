from flask import Flask, request, redirect, session
from strava.auth import get_auth_url

# Flask app for handling authentication
server = Flask(__name__)
server.secret_key = 'supersecretkey'  # Set a strong secret key for session management

@server.route('/')
def home():
    """Redirects to Strava's authorization page."""
    return redirect(get_auth_url())

@server.route('/callback')
def callback():
    """Handles the OAuth callback from Strava."""
    auth_code = request.args.get('code')
    if not auth_code:
        return "Authorization failed. No code returned."
    session['auth_code'] = auth_code
    return redirect('/dash?auth_code=' + auth_code)

@server.route('/print-session')
def print_session():
    """Prints the current session data."""
    print("Session Data:", dict(session))
    return "Session data printed to the console."
