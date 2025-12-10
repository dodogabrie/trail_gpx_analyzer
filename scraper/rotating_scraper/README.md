# Rotating Token Scraper

Multi-app token rotation system for Strava scraping to bypass rate limits.

## Overview

This system uses multiple Strava API applications to rotate OAuth tokens, allowing you to scrape 5-10x more activities per day by distributing requests across multiple apps.

## Setup

### 1. Create Multiple Strava Apps

1. Go to https://www.strava.com/settings/api
2. Create 3-5 applications with different names (e.g., "MyApp1", "MyApp2", etc.)
3. For each app, note down:
   - Client ID
   - Client Secret

### 2. Configure Apps

Copy the example config and add your apps:

```bash
cp apps_config.example.json apps_config.json
```

Edit `apps_config.json`:

```json
{
  "apps": [
    {
      "name": "App1",
      "client_id": "123456",
      "client_secret": "abc123...",
      "access_token": "",
      "refresh_token": "",
      "expires_at": 0
    },
    {
      "name": "App2",
      "client_id": "789012",
      "client_secret": "def456...",
      "access_token": "",
      "refresh_token": "",
      "expires_at": 0
    }
  ]
}
```

### 3. Authorize Apps

Run the authorization script for each app:

```bash
python authorize_apps.py
```

This will:
- Open a browser for each app
- Guide you through OAuth flow
- Save tokens to `apps_config.json`

### 4. Run Continuous Scraper with Rotation

```bash
# Start continuous scraping with token rotation
python continuous_scraper_rotating.py 5452411 --weeks 3

# Resume from previous state
python continuous_scraper_rotating.py 5452411 --resume

# Dry run
python continuous_scraper_rotating.py 5452411 --dry-run
```

## How It Works

1. **Token Pool**: Maintains a pool of access tokens from multiple apps
2. **Automatic Rotation**: Switches to next token when rate limited
3. **Token Refresh**: Automatically refreshes expired tokens
4. **Fallback**: If all tokens rate limited, waits 15 minutes
5. **State Persistence**: Saves which token was used, resumes on restart

## Rate Limits

Each Strava app has:
- **200 requests per 15 minutes**
- **2,000 requests per day**

With 5 apps:
- **1,000 requests per 15 minutes** (rotating)
- **10,000 requests per day** (combined)

## Files

- `apps_config.json` - Your app credentials and tokens (gitignored)
- `apps_config.example.json` - Template for configuration
- `token_rotator.py` - Token rotation logic
- `authorize_apps.py` - OAuth authorization for apps
- `continuous_scraper_rotating.py` - Main scraper with rotation
- `strava_api_client.py` - API client using access tokens
- `README.md` - This file

## Security

**IMPORTANT**: `apps_config.json` contains sensitive credentials. It's automatically gitignored.

Never commit:
- Client secrets
- Access tokens
- Refresh tokens

## Monitoring

The scraper logs:
- Which app/token is being used
- Rate limit status for each app
- Token refresh events
- Rotation events

Example output:
```
[App1] Fetching activity 12345...
[App1] Rate limited (200/200 requests)
[Rotating] Switching to App2
[App2] Fetching activity 12346...
```
