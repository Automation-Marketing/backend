import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

COMPANY_URL = "https://www.linkedin.com/company/odoo/"
LIMIT = 10


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
            print("1️ Launching browser...")
            try:
                browser = await p.chromium.launch(headless=True)
                print("Browser launched successfully\n")
            except Exception as e:
                print(f"   ❌ Failed to launch browser: {e}")
                raise
            
            try:
                print("2️ Loading session file...")
                session_file = Path(__file__).parent / "session_storage" / "linkedin_session.json"
                print(f"   Session file path: {session_file}")
                
                if not session_file.exists():
                    print(f"   ❌ Session file not found!")
                    print(f"   Please run linkedin_login.py first to create a session")
                    await browser.close()
                    return {
                        "company_url": company_url,
                        "company_info": {"error": "Session file not found"},
                        "recent_posts": [],
                        "total_collected": 0
                    }
                
                print(f"Session file found\n")
                
                context = await browser.new_context(storage_state=str(session_file))
                page = await context.new_page()
                print("Browser context created with session\n")
            except Exception as e:
                print(f"Failed to load session: {e}")
                await browser.close()
                raise

            try:
                print(f"3️ Navigating to company page: {company_url}")
                await page.goto(company_url, timeout=60000)
                await page.wait_for_timeout(5000)
                print("Page loaded successfully\n")
            except Exception as e:
                print(f"Failed to load page: {e}")
                await browser.close()
                raise

            try:
                print("4️ Scrolling to load posts...")
                for i in range(5):
                    await page.mouse.wheel(0, 8000)
                    await page.wait_for_timeout(2000)
                    print(f"Scroll {i+1}/5 complete")
                print("Scrolling complete\n")
            except Exception as e:
                print(f"Scrolling error (continuing anyway): {e}\n")

            try:
                print("5️⃣ Extracting page content...")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                print("Page content extracted\n")
            except Exception as e:
                print(f"Failed to extract content: {e}")
                await browser.close()
                raise

            try:
                print("6️ Extracting company info...")
                company_data = {}

                title = soup.find("title")
                if title:
                    company_data["company_name"] = title.text.strip()
                    print(f"Company: {company_data['company_name']}")
                else:
                    print(f"No company name found")

                about_section = soup.find("p")
                if about_section:
                    company_data["about"] = about_section.text.strip()
                    print(f"   About: {company_data['about'][:50]}...")
                else:
                    print(f"No about section found")
                
                print("Company info extracted\n")
            except Exception as e:
                print(f"Failed to extract company info: {e}")
                company_data = {}

            try:
                print("7️ Finding posts...")
                posts = []
                post_blocks = soup.find_all("div", class_="feed-shared-update-v2")
                
                print(f"   Found {len(post_blocks)} post blocks")
                
                if len(post_blocks) == 0:
                    print(f"No posts found with class 'feed-shared-update-v2'")
                    print(f"   This might mean:")
                    print(f"      - Session expired (run linkedin_login.py again)")
                    print(f"      - LinkedIn changed their HTML structure")
                    print(f"      - Page didn't load properly")

                for idx, block in enumerate(post_blocks[:LIMIT], 1):
                    try:
                        text = block.get_text(" ", strip=True)
                        
                        if text and len(text) > 10:
                            posts.append({
                                "content": text,
                                "post_date": "",  
                                "post_url": company_url
                            })
                            print(f"   Post {idx}: {text[:50]}...")
                        else:
                            print(f"   Post {idx}:Too short or empty")
                    except Exception as e:
                        print(f"   Post {idx}: ❌ Failed to extract - {e}")
                        continue

                print(f"Extracted {len(posts)} posts\n")
            except Exception as e:
                print(f"   ❌ Failed to find posts: {e}")
                posts = []

            await browser.close()
            
            print(f"\n{'='*60}")
            print(f"LINKEDIN SCRAPING COMPLETE")
            print(f"   Company info: {'✅' if company_data else '❌'}")
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
        print(f"❌ LINKEDIN SCRAPING FAILED")
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

