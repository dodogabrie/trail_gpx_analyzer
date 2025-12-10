#!/usr/bin/env python3
"""
Manual login helper for Strava (supports 2FA/CAPTCHA).
Opens a browser window for you to log in manually, then saves the session.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.selenium_scraper import StravaSeleniumScraper

def main():
    print("="*60)
    print("STRAVA MANUAL LOGIN TOOL")
    print("="*60)
    print("This script will open a browser window.")
    print("1. Enter your email and password manually.")
    print("2. Handle any 2FA codes or CAPTCHAs.")
    print("3. Wait until you see your Strava Dashboard.")
    print("4. Return to this terminal and press ENTER.")
    print("="*60)
    
    input("\nPress ENTER to launch browser...")

    # Initialize scraper in visible mode (not headless)
    scraper = StravaSeleniumScraper(headless=False)
    
    try:
        scraper.setup_driver()
        
        print("\nNavigating to login page...")
        scraper.driver.get("https://www.strava.com/login")
        
        # Wait for user to complete login
        print("\n" + "!"*60)
        print("WAITING FOR USER LOGIN")
        print("!"*60)
        print("Please interact with the browser window.")
        input("When you are fully logged in and see the Dashboard, press ENTER here: ")
        
        # Verify we are actually logged in
        if "login" in scraper.driver.current_url or "session" in scraper.driver.current_url:
            print("\nWARNING: It looks like you might not be logged in yet.")
            print(f"Current URL: {scraper.driver.current_url}")
            confirm = input("Are you sure you want to save this session? (y/n): ")
            if confirm.lower() != 'y':
                print("Aborting.")
                return

        # Save the session
        scraper.save_session()
        print(f"\nSUCCESS! Session saved to: {scraper.session_file}")
        print("You can now run the continuous scraper.")

    except Exception as e:
        print(f"\nError: {e}")
    finally:
        print("Closing browser...")
        scraper.close()

if __name__ == '__main__':
    main()
