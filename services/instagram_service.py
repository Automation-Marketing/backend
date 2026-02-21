import asyncio
import json
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

PROFILE_URL = "https://www.instagram.com/pesuventurelabs/"


def extract_hashtags(text):
    return re.findall(r"#\w+", text)


async def scrape_instagram(profile_url):
    """
    Scrape Instagram profile and posts.
    Works for public profiles without login.
    """
    print(f"\n{'='*60}")
    print(f"INSTAGRAM SCRAPER STARTED")
    print(f"{'='*60}")
    print(f"Profile URL: {profile_url}\n")
    
    try:
        username = profile_url.rstrip('/').split('/')[-1]
        print(f"Username: {username}\n")
        
        async with async_playwright() as p:
            print("1️ Launching browser...")
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()
                print("Browser launched successfully\n")
            except Exception as e:
                print(f"Failed to launch browser: {e}")
                raise

            try:
                print(f"2️ Navigating to profile: {profile_url}")
                await page.goto(profile_url, timeout=60000)
                await page.wait_for_timeout(5000)
                print("Page loaded successfully\n")
            except Exception as e:
                print(f"Failed to load page: {e}")
                await browser.close()
                raise

            try:
                print("3️ Extracting profile data...")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                if "Log in to Instagram" in html or "Sign up" in html:
                    print("Instagram is showing login page")
                
                profile_data = {}
                
                meta_desc = soup.find("meta", property="og:description")
                if meta_desc:
                    profile_data["description"] = meta_desc["content"]
                    print(f"   Profile: {meta_desc['content'][:50]}...")
                
                profile_data["profile_url"] = profile_url
                print("Profile data extracted\n")
                
            except Exception as e:
                print(f"Failed to extract profile data: {e}")
                profile_data = {"profile_url": profile_url}

            try:
                print("4️ Scrolling to load posts...")
                for i in range(3):
                    await page.mouse.wheel(0, 5000)
                    await page.wait_for_timeout(2000)
                    print(f"   Scroll {i+1}/3 complete")
                print("Scrolling complete\n")
            except Exception as e:
                print(f"Scrolling error: {e}\n")

            try:
                print("5️ Finding post links...")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                all_links = soup.find_all("a", href=True)
                post_links = []
                
                for a in all_links:
                    href = a["href"]
                    if "/p/" in href or "/reel/" in href or "/tv/" in href:
                        if href.startswith("/"):
                            full_link = f"https://www.instagram.com{href}"
                        else:
                            full_link = href
                        
                        full_link = full_link.split("?")[0]
                        
                        if full_link not in post_links:
                            post_links.append(full_link)
                
                print(f"Found {len(post_links)} post/reel links")
                
            except Exception as e:
                print(f"   ❌ Failed to find post links: {e}")
                post_links = []

            posts_data = []
            
            if not post_links:
                print("No posts to scrape!\n")
                await browser.close()
                return {
                    "profile": profile_data,
                    "last_10_posts_and_reels": []
                }

            print("6️ Scraping individual posts...")
            for idx, link in enumerate(post_links[:10], 1):
                try:
                    print(f"   Post {idx}/10: {link}")
                    await page.goto(link, timeout=30000)
                    await page.wait_for_timeout(3000)

                    post_html = await page.content()
                    post_soup = BeautifulSoup(post_html, "html.parser")

                    caption = ""
                    image_url = ""
                    post_date = ""
                    likes = ""
                    media_type = "reel" if "/reel/" in link else "tv" if "/tv/" in link else "post"

                    desc = post_soup.find("meta", property="og:description")
                    if desc:
                        caption = desc["content"]
                        print(f"      Caption: {caption[:50]}...")
                    else:
                        caption_meta = post_soup.find("meta", attrs={"name": "description"})
                        if caption_meta:
                            caption = caption_meta.get("content", "")

                    img = post_soup.find("meta", property="og:image")
                    if img:
                        image_url = img["content"]

                    time_tag = post_soup.find("time")
                    if time_tag:
                        post_date = time_tag.get("datetime", "")
                        
                    if caption:
                        like_match = re.search(r"([\d,]+)\s+[Ll]ikes", caption)
                        if like_match:
                            likes = like_match.group(1)

                    if caption or image_url:
                        posts_data.append({
                            "media_type": media_type,
                            "post_url": link,
                            "caption": caption,
                            "hashtags": extract_hashtags(caption),
                            "likes": likes,
                            "image_url": image_url,
                            "post_date": post_date
                        })
                        print(f"Post scraped successfully")
                    else:
                        print(f"No content found")

                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"      ❌ Failed: {e}")
                    continue

            await browser.close()
            
            print(f"\n{'='*60}")
            print(f"INSTAGRAM SCRAPING COMPLETE")
            print(f"   Profile data: {'✅' if profile_data else '❌'}")
            print(f"   Posts scraped: {len(posts_data)}/10")
            print(f"{'='*60}\n")

            return {
                "profile": profile_data,
                "last_10_posts_and_reels": posts_data
            }
            
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ INSTAGRAM SCRAPING FAILED")
        print(f"Error: {str(e)}")
        print(f"Error Type: {type(e).__name__}")
        print(f"{'='*60}\n")
        
        return {
            "profile": {"profile_url": profile_url, "error": str(e)},
            "last_10_posts_and_reels": []
        }


if __name__ == "__main__":
    result = asyncio.run(scrape_instagram(PROFILE_URL))

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("Scraping complete. Data saved to output.json")
