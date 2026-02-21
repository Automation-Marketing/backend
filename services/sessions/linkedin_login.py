import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright


async def save_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.linkedin.com/login")
        print("Login manually within 60 seconds...")
        await page.wait_for_timeout(20000)

        base_dir = Path(__file__).resolve().parent.parent  # Go up to backend/services
        session_path = base_dir / "session_storage" / "linkedin_session.json"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        
        await context.storage_state(path=str(session_path))
        print("Session saved successfully.")
        await browser.close()

asyncio.run(save_session())
