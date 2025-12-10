#!/usr/bin/env python3
"""Get fresh Strava tokens via OAuth flow.

This script helps you get proper access_token, refresh_token, and expires_at
for each of your Strava apps.

Usage:
    python get_fresh_token.py --client-id YOUR_CLIENT_ID --client-secret YOUR_SECRET
"""

import argparse
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

# Global to capture authorization code
auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""

    def do_GET(self):
        global auth_code

        # Parse query parameters
        query = urlparse(self.path).query
        params = parse_qs(query)

        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body>
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
            """)
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>Authorization Failed</h1>")

    def log_message(self, format, *args):
        # Suppress log messages
        pass


def get_tokens(client_id: str, client_secret: str):
    """Get fresh tokens via OAuth flow.

    Args:
        client_id: Strava app client ID
        client_secret: Strava app client secret
    """
    redirect_uri = "http://localhost:8000/callback"

    # Step 1: Generate authorization URL
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=activity:read_all"
    )

    print("\n" + "="*70)
    print("STEP 1: Authorize the application")
    print("="*70)
    print("\nOpening browser for authorization...")
    print(f"If browser doesn't open, visit:\n{auth_url}\n")

    webbrowser.open(auth_url)

    # Step 2: Start local server to capture callback
    print("Waiting for authorization callback on http://localhost:8000...")
    server = HTTPServer(('localhost', 8000), CallbackHandler)

    # Wait for one request
    server.handle_request()

    if not auth_code:
        print("\n✗ Failed to get authorization code")
        return

    print(f"\n✓ Received authorization code: {auth_code[:20]}...\n")

    # Step 3: Exchange code for tokens
    print("="*70)
    print("STEP 2: Exchanging code for tokens")
    print("="*70)

    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            'client_id': client_id,
            'client_secret': client_secret,
            'code': auth_code,
            'grant_type': 'authorization_code'
        }
    )

    if response.status_code != 200:
        print(f"\n✗ Token exchange failed: {response.text}")
        return

    token_data = response.json()

    print("\n✓ Successfully obtained tokens!\n")
    print("="*70)
    print("TOKEN DATA - Add this to your config.json:")
    print("="*70)

    token_config = {
        "name": "Your App Name Here",
        "access_token": token_data['access_token'],
        "refresh_token": token_data['refresh_token'],
        "expires_at": token_data['expires_at'],
        "enabled": True
    }

    print(json.dumps(token_config, indent=2))

    print("\n" + "="*70)
    print("ATHLETE INFO:")
    print("="*70)
    athlete = token_data.get('athlete', {})
    print(f"Name: {athlete.get('firstname')} {athlete.get('lastname')}")
    print(f"ID: {athlete.get('id')}")
    print(f"Username: {athlete.get('username')}")

    print("\n" + "="*70)
    print("EXPIRES AT:")
    print("="*70)
    from datetime import datetime
    expires_dt = datetime.fromtimestamp(token_data['expires_at'])
    print(f"Timestamp: {token_data['expires_at']}")
    print(f"Date: {expires_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Get fresh Strava tokens via OAuth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get tokens for your app
  python get_fresh_token.py --client-id 138943 --client-secret YOUR_SECRET

  # For each of your 3 apps, run this script separately
  python get_fresh_token.py --client-id APP1_ID --client-secret APP1_SECRET
  python get_fresh_token.py --client-id APP2_ID --client-secret APP2_SECRET
  python get_fresh_token.py --client-id APP3_ID --client-secret APP3_SECRET

Then copy the JSON output to your config.json file.
        """
    )

    parser.add_argument('--client-id', required=True,
                       help='Strava app client ID')
    parser.add_argument('--client-secret', required=True,
                       help='Strava app client secret')

    args = parser.parse_args()

    get_tokens(args.client_id, args.client_secret)


if __name__ == '__main__':
    main()
