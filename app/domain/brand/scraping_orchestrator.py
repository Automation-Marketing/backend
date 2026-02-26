import asyncio
from typing import Dict, Optional
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))

from app.domain.scraping.instagram_service import scrape_instagram
from app.domain.scraping.linkedin_service import scrape_linkedin
from app.domain.scraping.twitter_service import get_twitter_data


class ScrapingOrchestrator:
    """
    Orchestrates scraping across all social media platforms.
    Handles parallel execution and error handling.
    """
    
    @staticmethod
    async def scrape_instagram_safe(profile_url: str) -> Optional[Dict]:
        """Safely scrape Instagram"""
        try:
            print(f"Scraping Instagram: {profile_url}")
            result = await scrape_instagram(profile_url)
            print(f"Instagram scraping complete")
            return result
        except Exception as e:
            print(f"Instagram scraping failed: {e}")
            return None
    
    @staticmethod
    async def scrape_linkedin_safe(company_url: str) -> Optional[Dict]:
        """Safely scrape LinkedIn"""
        try:
            print(f"Scraping LinkedIn: {company_url}")
            result = await scrape_linkedin(company_url)
            print(f"LinkedIn scraping complete")
            return result
        except Exception as e:
            print(f"LinkedIn scraping failed: {e}")
            return None
    
    @staticmethod
    async def scrape_twitter_safe(username: str) -> Optional[Dict]:
        """Safely scrape Twitter"""
        try:
            print(f"Scraping Twitter: @{username}")
            result = await get_twitter_data(username)
            print(f"Twitter scraping complete")
            return result
        except Exception as e:
            print(f"Twitter scraping failed: {e}")
            return None
    
    @staticmethod
    async def scrape_all_platforms(
        instagram_handle: Optional[str] = None,
        linkedin_handle: Optional[str] = None,
        twitter_handle: Optional[str] = None
    ) -> Dict:
        """
        Scrape all platforms in parallel.
        
        Args:
            instagram_handle: Instagram username
            linkedin_handle: LinkedIn company handle
            twitter_handle: Twitter username
            
        Returns:
            Dictionary with results from all platforms
        """
        print("\n" + "="*60)
        print("Starting multi-platform scraping...")
        print("="*60 + "\n")
        
        tasks = []
        platform_keys = []
        
        if instagram_handle:
            instagram_url = f"https://www.instagram.com/{instagram_handle}/"
            tasks.append(ScrapingOrchestrator.scrape_instagram_safe(instagram_url))
            platform_keys.append("instagram")
        
        if linkedin_handle:
            linkedin_url = f"https://www.linkedin.com/company/{linkedin_handle}/"
            tasks.append(ScrapingOrchestrator.scrape_linkedin_safe(linkedin_url))
            platform_keys.append("linkedin")
        
        if twitter_handle:
            tasks.append(ScrapingOrchestrator.scrape_twitter_safe(twitter_handle))
            platform_keys.append("twitter")
        
        if not tasks:
            print("No platforms to scrape")
            return {}
        
        results = await asyncio.gather(*tasks)
        
        combined_results = {}
        for key, result in zip(platform_keys, results):
            if result:
                combined_results[key] = result
        
        print("\n" + "="*60)
        print(f"Scraping complete! Collected data from {len(combined_results)} platforms")
        print("="*60 + "\n")
        
        return combined_results


if __name__ == "__main__":
    async def test():
        results = await ScrapingOrchestrator.scrape_all_platforms(
            instagram_handle="teslamotors",
            linkedin_url="https://www.linkedin.com/company/tesla-motors/",
            twitter_handle="tesla"
        )
        
        for platform, data in results.items():
            print(f"\n{platform.upper()}:")
            if platform == "instagram":
                posts = data.get("last_10_posts_and_reels", [])
                print(f"  Posts collected: {len(posts)}")
            elif platform == "linkedin":
                posts = data.get("recent_posts", [])
                print(f"  Posts collected: {len(posts)}")
            elif platform == "twitter":
                posts = data.get("posts", [])
                print(f"  Posts collected: {len(posts)}")
    
    asyncio.run(test())
