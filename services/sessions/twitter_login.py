import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.stealth_browser import create_stealth_browser, create_stealth_context, create_stealth_page


async def save_session():
    async with async_playwright() as p:
        browser = await create_stealth_browser(p, headless=False)
        context = await create_stealth_context(browser)
        page = await create_stealth_page(context)
        
        print("Opening Twitter login page...")
        try:
            await page.goto("https://x.com/login", timeout=60000)
        except Exception as e:
            print(f"Note: Page load timeout (this is normal for Twitter). Continuing...")
        
        print("\n" + "="*60)
        print("🐦 TWITTER LOGIN INSTRUCTIONS:")
        print("="*60)
        print("1. Login manually in the browser window")
        print("2. Complete any verification steps (email, phone, etc.)")
        print("3. Wait until you see your Twitter feed/home page")
        print("4. The script will auto-save after 60 seconds")
        print("="*60 + "\n")
        
        await page.wait_for_timeout(60000)

        base_dir = Path(__file__).resolve().parent.parent  # Go up to backend/services
        session_path = base_dir / "session_storage" / "twitter_session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        
        await context.storage_state(path=str(session_path))
        print("\n✅ Session saved successfully to:", session_path)
        await browser.close()

asyncio.run(save_session())
