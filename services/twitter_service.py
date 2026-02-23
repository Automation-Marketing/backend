import asyncio
from playwright.async_api import async_playwright
import json
from stealth_browser import create_stealth_browser, create_stealth_context, create_stealth_page


async def get_twitter_data(username: str = "elonmusk"):
    """
    Scrape Twitter/X data using Playwright stealth mode.
    No login or session files required — scrapes publicly visible tweets.

    Args:
        username: Twitter username (without @)

    Returns:
        dict: Contains platform name and list of posts
    """
    print(f"\n{'='*60}")
    print(f"TWITTER SCRAPER STARTED")
    print(f"{'='*60}")
    print(f"Username: @{username}\n")

    try:
        async with async_playwright() as p:
            print("1️ Launching stealth browser...")
            try:
                browser = await create_stealth_browser(p, headless=True)
                context = await create_stealth_context(browser)
                page = await create_stealth_page(context)
                print("Stealth browser launched successfully\n")
            except Exception as e:
                print(f"Failed to launch browser: {e}")
                raise

            try:
                url = f"https://x.com/{username}"
                print(f"2️ Navigating to: {url}")
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                print("Page loaded\n")
            except Exception as e:
                print(f"Failed to load page: {e}")
                await browser.close()
                raise

            # Dismiss login modal / popups that Twitter shows
            print("2.5️ Dismissing any login popups...")
            try:
                for _ in range(3):
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)

                # Try clicking common dismiss buttons
                dismiss_selectors = [
                    '[data-testid="xMigrationBottomBar"] button',
                    '[role="button"][aria-label="Close"]',
                    'text="Not now"',
                    'text="Refuse non-essential cookies"',
                    'text="Accept all cookies"',
                ]
                for selector in dismiss_selectors:
                    try:
                        btn = await page.query_selector(selector)
                        if btn and await btn.is_visible():
                            await btn.click()
                            print(f"   Clicked: {selector}")
                            await page.wait_for_timeout(500)
                    except:
                        pass

                print("Login popup check complete\n")
            except Exception as e:
                print(f"Modal dismiss: {e}\n")

            # Wait for tweets to render
            print("2.6️ Waiting for tweets to render...")
            try:
                await page.wait_for_selector("article", timeout=15000)
                print("Tweets detected!\n")
            except:
                print("No tweets after 15s, retrying with page reload...")
                try:
                    await page.reload(timeout=60000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    # Dismiss popups again
                    for _ in range(3):
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(500)
                    await page.wait_for_selector("article", timeout=15000)
                    print("Tweets detected after reload!\n")
                except:
                    print("Still no tweets after reload. Will attempt extraction anyway.\n")

            print("3️ Scrolling and extracting tweets...")
            tweets = []
            max_scrolls = 30
            no_new_count = 0

            try:
                for i in range(max_scrolls):
                    # Dismiss any popup that might appear during scrolling
                    if i % 5 == 0 and i > 0:
                        try:
                            await page.keyboard.press("Escape")
                        except:
                            pass

                    # Extract tweets from currently loaded articles
                    articles = await page.query_selector_all("article")
                    old_count = len(tweets)

                    for article in articles:
                        try:
                            text_element = await article.query_selector("div[data-testid='tweetText']")
                            if not text_element:
                                text_element = await article.query_selector("div[lang]")

                            if text_element:
                                text = await text_element.inner_text()
                                if text and text not in [t["content"] for t in tweets]:
                                    tweets.append({"content": text})
                        except:
                            continue

                    print(f"   Scroll {i+1}/{max_scrolls} — {len(tweets)}/25 tweets collected")

                    if len(tweets) >= 25:
                        print("   Target reached!")
                        break

                    # Check if we got new tweets this round
                    if len(tweets) == old_count:
                        no_new_count += 1
                    else:
                        no_new_count = 0

                    # Only stop if no new tweets after many consecutive scrolls
                    if no_new_count >= 5:
                        print(f"   No new tweets after {no_new_count} consecutive scrolls, stopping...")
                        break

                    # Scroll down
                    await page.evaluate("window.scrollBy(0, 800)")
                    await page.wait_for_timeout(2000)

                print(f"\n   Total unique tweets extracted: {len(tweets)}\n")
            except Exception as e:
                print(f"Scrolling/extraction error: {e}\n")

            await browser.close()

            print(f"{'='*60}")
            print(f"TWITTER SCRAPING COMPLETE")
            print(f"   Tweets scraped: {len(tweets)}/25")
            print(f"{'='*60}\n")

            return {"platform": "twitter", "posts": tweets}

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"TWITTER SCRAPING FAILED")
        print(f"Error: {str(e)}")
        print(f"Error Type: {type(e).__name__}")
        print(f"{'='*60}\n")

        return {"platform": "twitter", "posts": []}


if __name__ == "__main__":
    result = asyncio.run(get_twitter_data("Tesla"))
    print(json.dumps(result, indent=2))
