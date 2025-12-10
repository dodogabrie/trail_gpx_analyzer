#!/usr/bin/env python3
"""
Check Strava session status and detect rate limiting.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.selenium_scraper import StravaSeleniumScraper

def main():
    print("Checking Strava session status...")
    
    # Initialize in headless mode for a quick check
    scraper = StravaSeleniumScraper(headless=True)
    
    try:
        scraper.setup_driver()
        
        if not scraper.load_session():
            print("\n[!] No valid session file found (strava_session.json).")
            print("    Please run 'python scripts/manual_login.py' to login.")
            return

        print("\nNavigating to Strava Dashboard...")
        scraper.driver.get("https://www.strava.com/dashboard")
        time.sleep(3)
        
        title = scraper.driver.title
        print(f"Page Title: {title}")
        
        page_text = scraper.driver.find_element("tag name", "body").text
        
        if "Too Many Requests" in page_text or "429" in title:
            print("\n[!!!] RATE LIMIT DETECTED [!!!]")
            print("Strava is blocking requests from this IP/Session.")
            print("Recommendation: Wait 1-2 hours or change IP (VPN/Mobile Hotspot).")
        elif "Log In" in title or "Login" in title:
            print("\n[!] Session Expired.")
            print("    The scraper is being redirected to the login page.")
            print("    Please run 'python scripts/manual_login.py' to re-login.")
        else:
            print("\n[OK] Session appears valid.")
            print(f"     Current URL: {scraper.driver.current_url}")
            
            # Try accessing the specific athlete that failed
            athlete_id = 23708131
            print(f"\nChecking access to Athlete {athlete_id}...")
            scraper.driver.get(f"https://www.strava.com/athletes/{athlete_id}")
            time.sleep(3)
            print(f"Page Title: {scraper.driver.title}")
            
            if "Too Many Requests" in scraper.driver.page_source:
                 print("\n[!!!] RATE LIMIT DETECTED on Profile Page [!!!]")
            elif "Page Not Found" in scraper.driver.page_source:
                 print("\n[!] Profile Page Not Found (404).")
            else:
                 # Check for intervals
                 try:
                     bars = scraper.driver.find_elements("css selector", "li.interval")
                     print(f"[OK] Found {len(bars)} interval bars on profile.")
                 except:
                     print("[?] No interval bars found (might be private profile or layout change).")

    except Exception as e:
        print(f"\n[!] Error during check: {e}")
    finally:
        scraper.close()

if __name__ == '__main__':
    main()
