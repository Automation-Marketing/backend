"""
LinkedIn Login Script
--------------------
Opens a browser for manual LinkedIn login.
Saves the session cookies for use by the scraper.
Uses stealth mode to avoid detection during login.
"""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.utils.stealth_browser import create_stealth_browser, create_stealth_context, create_stealth_page, STEALTH_ARGS, DEFAULT_USER_AGENT


async def save_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=STEALTH_ARGS
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=DEFAULT_USER_AGENT,
            locale="en-US",
            timezone_id="Asia/Calcutta",
        )
        page = await context.new_page()

        await page.goto("https://www.linkedin.com/login")
        print("=" * 50)
        print("LOGIN MANUALLY in the browser window.")
        print("Waiting for you to log in...")
        print("=" * 50)

        for i in range(60):
            await page.wait_for_timeout(2000)
            current_url = page.url
            if "feed" in current_url or "mynetwork" in current_url or "messaging" in current_url:
                print(f"\nLogin detected! Current URL: {current_url}")
                break
            if "login" not in current_url.lower() and "checkpoint" not in current_url.lower():
                print(f"\nURL changed to: {current_url}")
                break
        else:
            print("\nTimeout after 120 seconds. Saving session anyway...")

        await page.wait_for_timeout(3000)

        base_dir = Path(__file__).resolve().parent.parent 
        session_path = base_dir / "session_storage" / "linkedin_session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        
        await context.storage_state(path=str(session_path))
        print(f"\nSession saved to: {session_path}")
        print("You can now run linkedin_service.py to scrape.")
        await browser.close()

asyncio.run(save_session())
