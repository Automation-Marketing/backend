"""
Stealth Browser Utility
-----------------------
Provides stealth-enabled Playwright browser and context creation
to avoid bot detection on social media platforms.

Uses playwright-stealth v2 Stealth class which patches:
- navigator.webdriver detection
- Chrome runtime checks  
- Plugin/language enumeration
- WebGL vendor/renderer fingerprinting
- Permissions API, error prototype, and more
"""

import random
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext
from playwright_stealth import Stealth

_stealth = Stealth()


DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-background-timer-throttling",
    "--disable-popup-blocking",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-component-update",
    "--disable-features=TranslateUI",
    "--disable-ipc-flooding-protection",
]


async def create_stealth_browser(playwright: Playwright, headless: bool = True) -> Browser:
    """
    Launch a Chromium browser with stealth arguments.
    """
    browser = await playwright.chromium.launch(
        headless=headless,
        args=STEALTH_ARGS
    )
    return browser


async def create_stealth_context(
    browser: Browser,
    storage_state: str = None
) -> BrowserContext:
    """
    Create a browser context with realistic fingerprints.
    Uses a fixed user agent for session consistency.
    """
    context_options = {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": DEFAULT_USER_AGENT,
        "locale": "en-US",
        "timezone_id": "Asia/Calcutta",
        "color_scheme": "light",
    }

    if storage_state:
        context_options["storage_state"] = storage_state

    context = await browser.new_context(**context_options)

    return context


async def create_stealth_page(context: BrowserContext):
    """
    Create a new page with playwright-stealth v2 evasions applied.
    """
    await _stealth.apply_stealth_async(context)
    page = await context.new_page()
    return page
