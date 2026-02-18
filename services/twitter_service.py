import asyncio
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import json


async def get_twitter_data(username: str = "elonmusk"):
    """
    Scrape Twitter data WITHOUT requiring login or session files.
    Uses multiple fallback methods to get public Twitter data.
    
    Args:
        username: Twitter username (without @)
    
    Returns:
        dict: Contains platform name and list of posts
    """
    
    # Method 1: Try Nitter instances (Twitter mirrors that don't require login)
    nitter_instances = [
        f"https://nitter.net/{username}",
        f"https://nitter.poast.org/{username}",
        f"https://nitter.privacydev.net/{username}",
    ]
    
    print(f"Attempting to scrape Twitter data for @{username}...")
    
    # Try Nitter instances first (fastest, no login required)
    for nitter_url in nitter_instances:
        try:
            print(f"Trying Nitter instance: {nitter_url}")
            response = requests.get(nitter_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                tweets = []
                
                # Find tweet containers
                tweet_containers = soup.find_all('div', class_='tweet-content')
                
                for tweet in tweet_containers[:25]:
                    text = tweet.get_text(strip=True)
                    if text:
                        tweets.append({"content": text})
                
                if tweets:
                    print(f"✅ Successfully scraped {len(tweets)} tweets from Nitter")
                    return {"platform": "twitter", "posts": tweets}
        
        except Exception as e:
            print(f"Failed with {nitter_url}: {str(e)}")
            continue
    
    # Method 2: Use Playwright to scrape public Twitter page (no login)
    print("Nitter instances failed. Trying direct Twitter scraping...")
    try:
        tweets = await scrape_twitter_playwright(username)
        if tweets:
            return {"platform": "twitter", "posts": tweets}
    except Exception as e:
        print(f"Playwright scraping failed: {str(e)}")
    
    # If all methods fail
    print("⚠️ All scraping methods failed. Returning empty results.")
    return {"platform": "twitter", "posts": []}


async def scrape_twitter_playwright(username: str):
    """
    Scrape public Twitter data using Playwright (no login required).
    This scrapes publicly visible tweets only.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        
        # Hide automation
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = await context.new_page()
        
        try:
            url = f"https://x.com/{username}"
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(5000)  # Initial load wait
            
            # Scroll down multiple times to load more tweets (increased iterations)
            print("Scrolling to load more tweets...")
            previous_height = 0
            
            for i in range(10):  # Increased from 5 to 10 scrolls
                # Scroll down
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(2000)  # Increased wait time for content to load
                
                # Check if we've loaded new content
                current_height = await page.evaluate("document.body.scrollHeight")
                if current_height == previous_height and i > 3:
                    print(f"No new content loaded after {i} scrolls, stopping...")
                    break
                previous_height = current_height
            
            # Scroll back to top to ensure we capture all loaded tweets
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(2000)
            
            tweets = []
            
            # Try to get tweet text from public view
            articles = await page.query_selector_all("article")
            print(f"Found {len(articles)} tweet articles after scrolling")
            
            for article in articles[:25]:
                try:
                    # Try multiple selectors for tweet text
                    text_element = await article.query_selector("div[lang]")
                    if not text_element:
                        text_element = await article.query_selector("div[data-testid='tweetText']")
                    
                    if text_element:
                        text = await text_element.inner_text()
                        if text and text not in [t["content"] for t in tweets]:  # Avoid duplicates
                            tweets.append({"content": text})
                except:
                    continue
            
            await browser.close()
            
            if tweets:
                print(f"✅ Successfully scraped {len(tweets)} tweets from Twitter directly")
            
            return tweets
            
        except Exception as e:
            await browser.close()
            raise e


# For testing
if __name__ == "__main__":
    result = asyncio.run(get_twitter_data("jpmorgan"))
    print(json.dumps(result, indent=2))
