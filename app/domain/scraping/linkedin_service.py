import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from app.utils.stealth_browser import create_stealth_browser, create_stealth_context, create_stealth_page

COMPANY_URL = "https://www.linkedin.com/company/odoo/"
LIMIT = 20


async def scrape_linkedin(company_url):
    """
    Scrape LinkedIn company page and posts.
    Requires a valid session file.
    """
    print(f"\n{'='*60}")
    print(f"LINKEDIN SCRAPER STARTED")
    print(f"{'='*60}")
    print(f"Company URL: {company_url}\n")
    
    try:
        async with async_playwright() as p:
            print("1️ Launching stealth browser...")
            try:
                browser = await create_stealth_browser(p, headless=True)
                print("Stealth browser launched successfully\n")
            except Exception as e:
                print(f"   Failed to launch browser: {e}")
                raise
            
            try:
                print("2️ Loading session file...")
                session_file = Path(__file__).parent / "session_storage" / "linkedin_session.json"
                print(f"   Session file path: {session_file}")
                
                if not session_file.exists():
                    print(f"   Session file not found!")
                    print(f"   Please run linkedin_login.py first to create a session")
                    await browser.close()
                    return {
                        "company_url": company_url,
                        "company_info": {"error": "Session file not found"},
                        "recent_posts": [],
                        "total_collected": 0
                    }
                
                print(f"Session file found\n")
                
                context = await create_stealth_context(browser, storage_state=str(session_file))
                page = await create_stealth_page(context)
                print("Stealth browser context created with session\n")
            except Exception as e:
                print(f"Failed to load session: {e}")
                await browser.close()
                raise

            try:
                print(f"3️ Validating session...")
                await page.goto("https://www.linkedin.com/feed/", timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                
                current_url = page.url
                page_title = await page.title()
                print(f"   Page title: {page_title}")
                print(f"   Current URL: {current_url}")
                
                is_logged_out = (
                    "login" in current_url.lower()
                    or "authwall" in current_url.lower()
                    or "signup" in current_url.lower()
                    or "sign-up" in current_url.lower()
                    or "checkpoint" in current_url.lower()
                    or "Sign Up" in page_title
                    or "Log In" in page_title
                    or "Join" in page_title
                )
                
                if is_logged_out:
                    print("\n   SESSION EXPIRED! LinkedIn is not recognizing the session.")
                    print("   Please run: cd sessions && python linkedin_login.py")
                    print("   Log in manually, wait for session to save, then try again.\n")
                    await browser.close()
                    return {
                        "company_url": company_url,
                        "company_info": {"error": "Session expired - run linkedin_login.py again"},
                        "recent_posts": [],
                        "total_collected": 0
                    }
                
                print("Session is valid! Logged in successfully.\n")
            except Exception as e:
                print(f"Session validation failed: {e}")
                await browser.close()
                raise

            try:
                print(f"4️ Navigating to company page: {company_url}")
                await page.goto(company_url, timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                print("Company page loaded successfully\n")
            except Exception as e:
                print(f"Failed to load company page: {e}")
                await browser.close()
                raise

            try:
                print("5️ Scrolling to load posts...")
                for i in range(8):
                    await page.mouse.wheel(0, 5000)
                    await page.wait_for_timeout(2000)
                    print(f"   Scroll {i+1}/8 complete")
                print("Scrolling complete\n")
            except Exception as e:
                print(f"Scrolling error (continuing anyway): {e}\n")

            try:
                print("6️ Extracting page content...")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                print("Page content extracted\n")
            except Exception as e:
                print(f"Failed to extract content: {e}")
                await browser.close()
                raise

            try:
                print("7️ Extracting company info...")
                company_data = {}

                title = soup.find("title")
                if title:
                    company_data["company_name"] = title.text.strip()
                    print(f"   Company: {company_data['company_name']}")

                about_section = soup.find("p", class_="break-words")
                if not about_section:
                    about_section = soup.find("p")
                if about_section:
                    company_data["about"] = about_section.text.strip()
                    print(f"   About: {company_data['about'][:50]}...")
                
                print("Company info extracted\n")
            except Exception as e:
                print(f"Failed to extract company info: {e}")
                company_data = {}

            try:
                print("8️ Finding posts...")
                posts = []
                
                post_selectors = [
                    "div.feed-shared-update-v2",
                    "div[data-urn*='activity']",
                    "div.occludable-update",
                    "article",
                ]
                
                post_blocks = []
                used_selector = None
                for selector in post_selectors:
                    post_blocks = soup.select(selector)
                    if post_blocks:
                        used_selector = selector
                        break
                
                print(f"   Found {len(post_blocks)} post blocks (selector: {used_selector or 'none matched'})")
                
                if len(post_blocks) == 0:
                    print("   Trying Playwright live DOM selectors...")
                    
                    pw_selectors = [
                        "div.feed-shared-update-v2",
                        "[data-urn*='activity']",
                        ".occludable-update",
                        "article",
                    ]
                    
                    for sel in pw_selectors:
                        elements = await page.query_selector_all(sel)
                        if elements:
                            print(f"   Found {len(elements)} elements with selector: {sel}")
                            for idx, elem in enumerate(elements[:LIMIT], 1):
                                try:
                                    text = await elem.inner_text()
                                    if text and len(text.strip()) > 20:
                                        posts.append({
                                            "content": text.strip(),
                                            "post_date": "",
                                            "post_url": company_url
                                        })
                                        print(f"   Post {idx}: {text.strip()[:50]}...")
                                except:
                                    continue
                            break
                else:
                    for idx, block in enumerate(post_blocks[:LIMIT], 1):
                        try:
                            text = block.get_text(" ", strip=True)
                            
                            if text and len(text) > 20:
                                posts.append({
                                    "content": text,
                                    "post_date": "",  
                                    "post_url": company_url
                                })
                                print(f"   Post {idx}: {text[:50]}...")
                        except Exception as e:
                            print(f"   Post {idx}: Failed - {e}")
                            continue

                if not posts:
                    print("   No posts found. Possible reasons:")
                    print("      - Session expired (run linkedin_login.py again)")
                    print("      - LinkedIn changed their HTML structure")
                    print("      - Company page has no recent posts")
                    
                print(f"Extracted {len(posts)} posts\n")
            except Exception as e:
                print(f"   Failed to find posts: {e}")
                posts = []

            await browser.close()
            
            print(f"\n{'='*60}")
            print(f"LINKEDIN SCRAPING COMPLETE")
            print(f"   Company info: {'YES' if company_data else 'NO'}")
            print(f"   Posts scraped: {len(posts)}")
            print(f"{'='*60}\n")

            return {
                "company_url": company_url,
                "company_info": company_data,
                "recent_posts": posts,
                "total_collected": len(posts)
            }
            
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"LINKEDIN SCRAPING FAILED")
        print(f"Error: {str(e)}")
        print(f"Error Type: {type(e).__name__}")
        print(f"{'='*60}\n")
        
        return {
            "company_url": company_url,
            "company_info": {"error": str(e)},
            "recent_posts": [],
            "total_collected": 0
        }


if __name__ == "__main__":
    result = asyncio.run(scrape_linkedin(COMPANY_URL))

    with open("linkedin_output.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("Scraping complete. Data saved to linkedin_output.json")

