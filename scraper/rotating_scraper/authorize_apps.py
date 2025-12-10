#!/usr/bin/env python3
"""Authorize Strava apps and save tokens.

Run this script to authorize each app configured in apps_config.json.
Opens browser for OAuth flow and saves tokens.
"""

import json
import webbrowser
import requests
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from Strava."""

    def do_GET(self):
        """Handle GET request with authorization code."""
        # Parse query parameters
        query = urlparse(self.path).query
        params = parse_qs(query)

        if 'code' in params:
            self.server.auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>')
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authorization failed</h1></body></html>')

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


def authorize_app(app: dict, callback_port: int = 8000) -> bool:
    """Authorize a single app via OAuth.

    Args:
        app: App configuration dict
        callback_port: Port for OAuth callback

    Returns:
        True if successful
    """
    print(f"\n{'='*70}")
    print(f"Authorizing: {app['name']}")
    print(f"{'='*70}")

    # Build authorization URL
    redirect_uri = f"http://localhost:{callback_port}/callback"
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={app['client_id']}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=read,activity:read_all"
    )

    print(f"\nOpening browser for authorization...")
    print(f"If browser doesn't open, visit:")
    print(f"{auth_url}\n")

    webbrowser.open(auth_url)

    # Start local server to receive callback
    print(f"Waiting for authorization callback on port {callback_port}...")

    server = HTTPServer(('localhost', callback_port), OAuthCallbackHandler)
    server.auth_code = None

    # Handle one request
    server.handle_request()

    if not server.auth_code:
        print("Failed to receive authorization code")
        return False

    print(f"Received authorization code")

    # Exchange code for tokens
    print("Exchanging code for access token...")

    try:
        response = requests.post(
            'https://www.strava.com/oauth/token',
            data={
                'client_id': app['client_id'],
                'client_secret': app['client_secret'],
                'code': server.auth_code,
                'grant_type': 'authorization_code'
            }
        )

        if response.status_code == 200:
            data = response.json()

            app['access_token'] = data['access_token']
            app['refresh_token'] = data['refresh_token']
            app['expires_at'] = data['expires_at']

            print(f"✓ Successfully authorized {app['name']}")
            print(f"  Access Token: ...{app['access_token'][-8:]}")
            print(f"  Athlete: {data.get('athlete', {}).get('username', 'Unknown')}")

            return True
        else:
            print(f"✗ Failed to exchange code: {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Main entry point."""
    config_file = Path(__file__).parent / "apps_config.json"

    if not config_file.exists():
        print("Error: apps_config.json not found")
        print("Copy apps_config.example.json to apps_config.json and add your credentials")
        return

    # Load config
    with open(config_file, 'r') as f:
        data = json.load(f)

    apps = data.get('apps', [])

    if not apps:
        print("Error: No apps configured in apps_config.json")
        return

    print("="*70)
    print("STRAVA APP AUTHORIZATION")
    print("="*70)
    print(f"\nFound {len(apps)} app(s) to authorize\n")

    # Show apps
    for i, app in enumerate(apps, 1):
        has_token = "✓" if app.get('access_token') else "✗"
        print(f"{i}. {app['name']} {has_token}")

    print("\nAuthorization will:")
    print("  1. Open browser for each app")
    print("  2. You'll need to click 'Authorize'")
    print("  3. Tokens will be saved to apps_config.json")

    input("\nPress ENTER to start authorization...")

    # Authorize each app
    success_count = 0

    for app in apps:
        # Skip if already authorized
        if app.get('access_token'):
            print(f"\n{app['name']}: Already authorized (skipping)")
            success_count += 1
            continue

        if authorize_app(app):
            success_count += 1

        # Save after each app
        with open(config_file, 'w') as f:
            json.dump(data, f, indent=2)

    # Summary
    print(f"\n{'='*70}")
    print(f"AUTHORIZATION COMPLETE")
    print(f"{'='*70}")
    print(f"Successful: {success_count}/{len(apps)}")
    print(f"Config saved to: {config_file}")
    print(f"\nYou can now run the continuous scraper with token rotation!")


if __name__ == '__main__':
    main()
