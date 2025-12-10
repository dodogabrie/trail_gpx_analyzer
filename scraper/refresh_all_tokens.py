#!/usr/bin/env python3
"""Refresh all enabled tokens in config.json and update expires_at.

This script reads config.json, attempts to refresh all enabled tokens,
and updates the config file with new tokens and proper expires_at values.

Usage:
    python refresh_all_tokens.py
    python refresh_all_tokens.py --config api/config.json
"""

import argparse
import json
import requests
from pathlib import Path
from datetime import datetime


def refresh_token(client_id: str, client_secret: str, refresh_token: str, token_name: str) -> dict:
    """Refresh a single token.

    Args:
        client_id: Strava app client ID
        client_secret: Strava app client secret
        refresh_token: Current refresh token
        token_name: Name identifier for logging

    Returns:
        Dict with new token data or None if failed
    """
    print(f"\n[{token_name}]")
    print(f"  Refreshing token...")

    try:
        response = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            },
            timeout=10
        )

        print(f"  Response status: {response.status_code}")

        if response.status_code != 200:
            print(f"  ✗ Refresh failed: {response.text}")
            return None

        token_data = response.json()

        expires_dt = datetime.fromtimestamp(token_data['expires_at'])
        print(f"  ✓ Success!")
        print(f"    New access_token: {token_data['access_token'][:20]}...")
        print(f"    New refresh_token: {token_data['refresh_token'][:20]}...")
        print(f"    Expires at: {token_data['expires_at']} ({expires_dt.strftime('%Y-%m-%d %H:%M:%S')})")

        return {
            'access_token': token_data['access_token'],
            'refresh_token': token_data['refresh_token'],
            'expires_at': token_data['expires_at']
        }

    except requests.exceptions.Timeout:
        print(f"  ✗ Request timeout")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def refresh_all_tokens(config_file: str, dry_run: bool = False):
    """Refresh all enabled tokens in config file.

    Args:
        config_file: Path to config.json
        dry_run: If True, don't save changes
    """
    config_path = Path(config_file)

    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return

    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)

    print("="*70)
    print("REFRESHING ALL ENABLED TOKENS")
    print("="*70)
    print(f"Config file: {config_path}")
    print(f"Dry run: {dry_run}")

    updated_count = 0
    failed_count = 0
    skipped_count = 0

    # Process each token
    for i, token_config in enumerate(config['tokens']):
        if not token_config.get('enabled', True):
            print(f"\n[{token_config['name']}]")
            print(f"  ⊘ Disabled, skipping")
            skipped_count += 1
            continue

        # Each token has its own client_id and client_secret
        client_id = token_config.get('client_id')
        client_secret = token_config.get('client_secret')
        refresh_tok = token_config.get('refresh_token')

        if not client_id or not client_secret:
            print(f"\n[{token_config['name']}]")
            print(f"  ✗ Missing client_id or client_secret")
            failed_count += 1
            continue

        if not refresh_tok:
            print(f"\n[{token_config['name']}]")
            print(f"  ✗ No refresh_token available")
            failed_count += 1
            continue

        # Refresh token
        new_token_data = refresh_token(
            client_id,
            client_secret,
            refresh_tok,
            token_config['name']
        )

        if new_token_data:
            # Update config data
            config['tokens'][i]['access_token'] = new_token_data['access_token']
            config['tokens'][i]['refresh_token'] = new_token_data['refresh_token']
            config['tokens'][i]['expires_at'] = new_token_data['expires_at']
            updated_count += 1
        else:
            failed_count += 1

    # Save config
    if not dry_run and updated_count > 0:
        print(f"\n{'='*70}")
        print("SAVING UPDATED CONFIG")
        print(f"{'='*70}")

        # Create backup
        backup_path = config_path.with_suffix('.json.backup')
        with open(backup_path, 'w') as f:
            with open(config_path, 'r') as orig:
                f.write(orig.read())
        print(f"Backup saved: {backup_path}")

        # Save updated config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Config updated: {config_path}")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Updated: {updated_count} tokens")
    print(f"Failed: {failed_count} tokens")
    print(f"Skipped: {skipped_count} tokens (disabled)")

    if dry_run and updated_count > 0:
        print(f"\nDry run mode - no changes saved")
        print(f"Run without --dry-run to save changes")

    print(f"{'='*70}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Refresh all enabled tokens in config.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Refresh all tokens and update config
  python refresh_all_tokens.py

  # Dry run (test without saving)
  python refresh_all_tokens.py --dry-run

  # Custom config file
  python refresh_all_tokens.py --config api/config.json

Notes:
  - Only refreshes tokens where enabled=true
  - Creates backup before updating config
  - Requires valid refresh_token for each enabled token
        """
    )

    parser.add_argument('--config', default='api/config.json',
                       help='Path to config file (default: api/config.json)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Test without saving changes')

    args = parser.parse_args()

    # Convert to absolute path
    config_file = Path(__file__).parent / args.config

    refresh_all_tokens(str(config_file), args.dry_run)


if __name__ == '__main__':
    main()
