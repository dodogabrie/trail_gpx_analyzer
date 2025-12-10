#!/usr/bin/env python3
"""Token rotation manager for multiple Strava apps.

Manages a pool of Strava OAuth tokens from multiple applications,
automatically rotating between them to avoid rate limits.
"""

import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime


class TokenRotator:
    """Manage and rotate between multiple Strava app tokens."""

    def __init__(self, config_file: str = "apps_config.json"):
        """Initialize token rotator.

        Args:
            config_file: Path to apps configuration file
        """
        self.config_file = Path(__file__).parent / config_file
        self.apps = []
        self.current_index = 0
        self.load_config()

    def load_config(self):
        """Load app configurations from file."""
        if not self.config_file.exists():
            raise FileNotFoundError(
                f"Config file not found: {self.config_file}\n"
                f"Copy apps_config.example.json to apps_config.json and add your credentials"
            )

        with open(self.config_file, 'r') as f:
            data = json.load(f)

        self.apps = data.get('apps', [])

        if not self.apps:
            raise ValueError("No apps configured in apps_config.json")

        # Initialize tracking fields if missing
        for app in self.apps:
            if 'requests_15min' not in app:
                app['requests_15min'] = 0
            if 'requests_daily' not in app:
                app['requests_daily'] = 0
            if 'window_start' not in app:
                app['window_start'] = time.time()

    def save_config(self):
        """Save current app configurations to file."""
        with open(self.config_file, 'w') as f:
            json.dump({'apps': self.apps}, f, indent=2)

    def get_current_app(self) -> Dict:
        """Get currently active app.

        Returns:
            Current app configuration dict
        """
        return self.apps[self.current_index]

    def get_access_token(self) -> Optional[str]:
        """Get current access token, refreshing if needed.

        Returns:
            Access token or None if all tokens exhausted
        """
        app = self.get_current_app()

        # Check if token expired
        if app['expires_at'] < time.time():
            print(f"[{app['name']}] Token expired, refreshing...")
            if not self.refresh_token(app):
                print(f"[{app['name']}] Failed to refresh token")
                return None

        return app['access_token']

    def refresh_token(self, app: Dict) -> bool:
        """Refresh access token for an app.

        Args:
            app: App configuration dict

        Returns:
            True if successful
        """
        if not app['refresh_token']:
            return False

        try:
            response = requests.post(
                'https://www.strava.com/oauth/token',
                data={
                    'client_id': app['client_id'],
                    'client_secret': app['client_secret'],
                    'grant_type': 'refresh_token',
                    'refresh_token': app['refresh_token']
                }
            )

            if response.status_code == 200:
                data = response.json()
                app['access_token'] = data['access_token']
                app['refresh_token'] = data['refresh_token']
                app['expires_at'] = data['expires_at']
                self.save_config()
                print(f"[{app['name']}] Token refreshed successfully")
                return True
            else:
                print(f"[{app['name']}] Refresh failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"[{app['name']}] Refresh error: {e}")
            return False

    def record_request(self):
        """Record a request for rate limit tracking."""
        app = self.get_current_app()
        current_time = time.time()

        # Reset 15-minute window if needed
        if current_time - app['window_start'] > 900:  # 15 minutes
            app['requests_15min'] = 0
            app['window_start'] = current_time

        app['requests_15min'] += 1
        app['requests_daily'] += 1

        self.save_config()

    def is_rate_limited(self, app: Dict = None) -> bool:
        """Check if an app is rate limited.

        Args:
            app: App to check (defaults to current)

        Returns:
            True if rate limited
        """
        if app is None:
            app = self.get_current_app()

        current_time = time.time()

        # Reset counters if windows passed
        if current_time - app['window_start'] > 900:
            app['requests_15min'] = 0
            app['window_start'] = current_time

        # Check limits (conservative: 190 instead of 200)
        if app['requests_15min'] >= 190:
            return True

        if app['requests_daily'] >= 1900:  # Conservative: 1900 instead of 2000
            return True

        return False

    def rotate_to_next(self) -> bool:
        """Rotate to next available app.

        Returns:
            True if found available app, False if all rate limited
        """
        apps_checked = 0
        original_index = self.current_index

        while apps_checked < len(self.apps):
            self.current_index = (self.current_index + 1) % len(self.apps)
            apps_checked += 1

            app = self.get_current_app()

            if not self.is_rate_limited(app):
                if self.current_index != original_index:
                    print(f"[Rotating] Switched from {self.apps[original_index]['name']} to {app['name']}")
                return True

        # All apps rate limited
        return False

    def get_best_app(self) -> Optional[Dict]:
        """Get the app with most available requests.

        Returns:
            Best app or None if all exhausted
        """
        best_app = None
        best_remaining = -1

        for app in self.apps:
            if self.is_rate_limited(app):
                continue

            remaining = min(
                190 - app['requests_15min'],
                1900 - app['requests_daily']
            )

            if remaining > best_remaining:
                best_remaining = remaining
                best_app = app

        return best_app

    def wait_for_available(self, timeout: int = 900):
        """Wait until an app becomes available.

        Args:
            timeout: Maximum wait time in seconds (default: 15 minutes)
        """
        print(f"\n[Rate Limit] All apps exhausted. Waiting for window to reset...")

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if any app has available requests
            for i, app in enumerate(self.apps):
                if not self.is_rate_limited(app):
                    self.current_index = i
                    print(f"[Available] {app['name']} is ready")
                    return True

            # Wait 30 seconds before checking again
            time.sleep(30)

        print(f"[Timeout] No apps available after {timeout}s")
        return False

    def get_status(self) -> str:
        """Get status summary of all apps.

        Returns:
            Formatted status string
        """
        lines = ["\n=== Token Rotator Status ==="]

        for i, app in enumerate(self.apps):
            current = " (CURRENT)" if i == self.current_index else ""
            limited = " [RATE LIMITED]" if self.is_rate_limited(app) else ""

            lines.append(f"\n{app['name']}{current}{limited}")
            lines.append(f"  15-min: {app['requests_15min']}/200")
            lines.append(f"  Daily: {app['requests_daily']}/2000")

            if app['access_token']:
                lines.append(f"  Token: ...{app['access_token'][-8:]}")
            else:
                lines.append(f"  Token: NOT AUTHORIZED")

        lines.append("\n" + "="*30)

        return "\n".join(lines)
