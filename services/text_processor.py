import re
from typing import List, Dict
from datetime import datetime


class TextProcessor:
    """
    Process and clean social media text data for embedding.
    Handles text cleaning, normalization, and metadata extraction.
    """
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean and normalize text for embedding.
        
        Args:
            text: Raw text from social media post
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove URLs (but keep the context)
        text = re.sub(r'http\S+|www\.\S+', '', text)
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """Extract hashtags from text."""
        return re.findall(r'#\w+', text)
    
    @staticmethod
    def extract_mentions(text: str) -> List[str]:
        """Extract @mentions from text."""
        return re.findall(r'@\w+', text)
    
    @staticmethod
    def chunk_posts(posts: List[Dict], platform: str, company: str) -> List[Dict]:
        """
        Convert social media posts into chunks ready for embedding.
        Uses semantic chunking - each post is one chunk with metadata.
        
        Args:
            posts: List of posts from scraper
            platform: Platform name (instagram, linkedin, twitter)
            company: Company name
            
        Returns:
            List of chunks with text and metadata
        """
        chunks = []
        
        for post in posts:
            # Get text content
            text = post.get("content", "") or post.get("caption", "")
            
            if not text or len(text.strip()) < 10:  # Skip very short posts
                continue
            
            # Clean text
            cleaned_text = TextProcessor.clean_text(text)
            
            # Extract hashtags and mentions
            hashtags = TextProcessor.extract_hashtags(text)
            mentions = TextProcessor.extract_mentions(text)
            
            # Extract metadata
            metadata = {
                "platform": platform,
                "company": company,
                "post_date": post.get("post_date", datetime.now().isoformat()),
                "post_url": post.get("post_url", ""),
            }
            
            # Add hashtags and mentions only if they exist (ChromaDB doesn't allow empty lists)
            if hashtags:
                metadata["hashtags"] = ", ".join(hashtags)  # Convert list to string
            if mentions:
                metadata["mentions"] = ", ".join(mentions)  # Convert list to string
            
            # Platform-specific metadata
            if platform == "instagram":
                if post.get("likes"):
                    metadata["likes"] = str(post.get("likes", ""))
                if post.get("image_url"):
                    metadata["image_url"] = post.get("image_url", "")
                metadata["media_type"] = post.get("media_type", "post")
            elif platform == "linkedin":
                if post.get("company_url"):
                    metadata["company_url"] = post.get("company_url", "")
            elif platform == "twitter":
                # Twitter-specific fields can be added here
                pass
            
            chunks.append({
                "text": cleaned_text,
                "metadata": metadata
            })
        
        return chunks
    
    @staticmethod
    def process_all_platforms(scraped_data: Dict, company: str) -> List[Dict]:
        """
        Process scraped data from all platforms into unified chunks.
        
        Args:
            scraped_data: Dictionary with keys 'instagram', 'linkedin', 'twitter'
            company: Company name
            
        Returns:
            List of all chunks from all platforms
        """
        all_chunks = []
        
        # Process Instagram
        if "instagram" in scraped_data and scraped_data["instagram"]:
            instagram_posts = scraped_data["instagram"].get("last_10_posts_and_reels", [])
            chunks = TextProcessor.chunk_posts(instagram_posts, "instagram", company)
            all_chunks.extend(chunks)
            print(f"Processed {len(chunks)} Instagram posts")
        
        # Process LinkedIn
        if "linkedin" in scraped_data and scraped_data["linkedin"]:
            linkedin_posts = scraped_data["linkedin"].get("recent_posts", [])
            chunks = TextProcessor.chunk_posts(linkedin_posts, "linkedin", company)
            all_chunks.extend(chunks)
            print(f"Processed {len(chunks)} LinkedIn posts")
        
        # Process Twitter
        if "twitter" in scraped_data and scraped_data["twitter"]:
            twitter_posts = scraped_data["twitter"].get("posts", [])
            chunks = TextProcessor.chunk_posts(twitter_posts, "twitter", company)
            all_chunks.extend(chunks)
            print(f"Processed {len(chunks)} Twitter posts")
        
        print(f"Total chunks created: {len(all_chunks)}")
        return all_chunks


# Test the text processor
if __name__ == "__main__":
    # Test data
    test_posts = [
        {
            "content": "Check out our new product! z#AI #Innovation https://example.com @tech_news",
            "post_date": "2026-02-17",
            "likes": "1234",
            "post_url": "https://instagram.com/p/123"
        },
        {
            "content": "   Excited   to   share   our   Q4   results!   ",
            "post_date": "2026-02-16"
        }
    ]
    
    processor = TextProcessor()
    
    # Test cleaning
    print("Testing text cleaning:")
    for post in test_posts:
        cleaned = processor.clean_text(post["content"])
        print(f"Original: {post['content']}")
        print(f"Cleaned:  {cleaned}\n")
    
    # Test chunking
    print("Testing chunking:")
    chunks = processor.chunk_posts(test_posts, "instagram", "TestCompany")
    for i, chunk in enumerate(chunks, 1):
        print(f"\nChunk {i}:")
        print(f"Text: {chunk['text']}")
        print(f"Metadata: {chunk['metadata']}")
