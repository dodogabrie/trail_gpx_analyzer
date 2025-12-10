#!/usr/bin/env python3
"""Test token refresh and API access."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from api.stream_downloader import StravaStreamDownloader

def test_tokens():
    """Test token refresh and basic API call."""
    print("Testing token configuration...\n")

    downloader = StravaStreamDownloader("api/config.json")

    # Test raw request first
    print("\n" + "="*70)
    print("RAW API TEST (bypassing downloader)")
    print("="*70)

    token = downloader.token_managers[0].access_token
    test_url = "https://www.strava.com/api/v3/athlete"

    print(f"\nTesting direct request to {test_url}")
    print(f"Token: {token[:20]}...")

    import requests
    try:
        response = requests.get(
            test_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print(f"✓ Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Authenticated as: {data['firstname']} {data['lastname']}")
            print(f"✓ Athlete ID: {data['id']}")
        else:
            print(f"✗ Response: {response.text}")
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()

    print("\nChecking token status:")
    for i, manager in enumerate(downloader.token_managers):
        print(f"\n[{manager.name}]")
        print(f"  Token: {manager.access_token[:20]}...")
        print(f"  Expires at: {manager.expires_at}")
        print(f"  Is valid: {manager.is_token_valid()}")

        if not manager.is_token_valid():
            print(f"  Token expired, attempting refresh...")
            if manager.refresh_access_token():
                print(f"  ✓ Refresh successful")
                print(f"  New expires at: {manager.expires_at}")
            else:
                print(f"  ✗ Refresh failed")

    print("\n" + "="*70)
    print("Testing API call with first token...")
    print("="*70)

    # Test with athlete endpoint first (should always work with valid token)
    print("\nTesting /athlete endpoint (should always work)...")
    import requests
    token = downloader.token_managers[0].access_token

    try:
        resp = requests.get(
            "https://www.strava.com/api/v3/athlete",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            athlete = resp.json()
            print(f"  ✓ Authenticated as: {athlete['firstname']} {athlete['lastname']} (ID: {athlete['id']})")
            your_athlete_id = athlete['id']
        else:
            print(f"  Response: {resp.text[:200]}")
            your_athlete_id = None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        your_athlete_id = None

    # Test with a known public activity or your own
    test_activity_id = 16647691934

    print(f"\nTrying to fetch activity {test_activity_id}...")
    metadata = downloader.get_activity_metadata(test_activity_id)

    if metadata:
        print(f"\n✓ Success!")
        print(f"  Name: {metadata.get('name')}")
        print(f"  Sport: {metadata.get('sport_type')}")
    else:
        print(f"\n✗ Failed to fetch activity")
        if your_athlete_id:
            print(f"\nTip: Activity {test_activity_id} might be private.")
            print(f"     Try testing with one of YOUR activities (athlete ID: {your_athlete_id})")

    print("\nFinal token status:")
    downloader.print_all_status()

if __name__ == '__main__':
    test_tokens()
