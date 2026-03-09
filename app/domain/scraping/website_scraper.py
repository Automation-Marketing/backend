"""
WebsiteScraper — Crawl a company's website and extract text content.

Strategy:
  1. Try direct HTTP (requests + BeautifulSoup) first — works for
     server-rendered sites.
  2. If direct crawl yields little/no text (JS-rendered SPA), fall back
     to Gemini to extract website content.
"""

import re
import os
from urllib.parse import urljoin, urlparse
from typing import Optional

import requests
from bs4 import BeautifulSoup
from google import genai

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Subpaths to attempt crawling in addition to the homepage
_KEY_SUBPATHS = [
    "/about", "/about-us", "/aboutus",
    "/products", "/services", "/solutions",
    "/features", "/pricing",
    "/company", "/team", "/our-story",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_TIMEOUT = 20
_MAX_CHARS_PER_PAGE = 4000


def _extract_text_from_html(html: str) -> tuple[str, str, str]:
    """
    Extract title, meta description, and body text from raw HTML.
    Returns (title, meta_description, content).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Meta description
    meta_desc = ""
    for attr in [{"name": "description"}, {"property": "og:description"}]:
        tag = soup.find("meta", attrs=attr)
        if tag and tag.get("content"):
            meta_desc = tag["content"].strip()
            break

    # Body content — try structured tags first
    text_parts = []
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li",
                               "blockquote", "td", "th", "article", "section"]):
        t = tag.get_text(separator=" ", strip=True)
        if t and len(t) > 10:
            text_parts.append(t)

    content = " ".join(text_parts)
    content = re.sub(r"\s+", " ", content).strip()

    # Fallback: ALL visible text
    if len(content) < 100:
        for tag in soup.find_all(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()
        content = soup.get_text(separator=" ", strip=True)
        content = re.sub(r"\s+", " ", content).strip()

    return title, meta_desc, content


def _crawl_with_gemini(website_url: str) -> str:
    """
    Use Gemini to extract content from a website URL.
    Gemini 2.5 Flash supports URL context and can fetch page content.
    """
    if not GOOGLE_API_KEY:
        print("[WebsiteScraper] No GOOGLE_API_KEY set, skipping Gemini fallback.")
        return ""

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)

        prompt = f"""You are a web content extractor. Visit this website and extract ALL the visible text content from it.

Website URL: {website_url}

Instructions:
- Extract ALL headings, paragraphs, product descriptions, about info, feature lists, etc.
- Return ONLY the raw text content from the website
- Do NOT add any analysis, commentary, or markdown formatting
- Do NOT make up content — only return what's actually on the website
- Include any pricing info, team info, company descriptions, etc. that you find"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text.strip() if response.text else ""
        if text:
            print(f"[WebsiteScraper] Gemini extracted {len(text)} chars for {website_url}")
        return text

    except Exception as e:
        print(f"[WebsiteScraper] Gemini fallback failed for {website_url}: {e}")
        return ""


def _crawl_page(url: str) -> Optional[dict]:
    """
    Crawl a single page. Tries direct HTTP first, then Gemini fallback.
    """
    title = ""
    meta_desc = ""
    content = ""

    # --- Attempt 1: Direct HTTP ---
    try:
        r = requests.get(url, timeout=_TIMEOUT, headers=_HEADERS, allow_redirects=True)
        if r.status_code == 200 and len(r.text) > 200:
            title, meta_desc, content = _extract_text_from_html(r.text)
    except Exception as e:
        print(f"[WebsiteScraper] requests failed for {url}: {e}")

    # --- Attempt 2: Gemini fallback for JS-rendered pages ---
    if len(content) < 100:
        print(f"[WebsiteScraper] Direct crawl got {len(content)} chars, trying Gemini fallback for {url}...")
        gemini_content = _crawl_with_gemini(url)
        if gemini_content and len(gemini_content) > len(content):
            content = gemini_content

    if len(content) < 30:
        return None

    content = content[:_MAX_CHARS_PER_PAGE]

    return {
        "url": url,
        "title": title,
        "meta_description": meta_desc,
        "content": content,
    }


def scrape_website(website_url: str) -> dict:
    """
    Scrape a company website.

    Args:
        website_url: Base URL (e.g. https://example.com)

    Returns:
        {"url": "...", "pages": [{"url", "title", "meta_description", "content"}, ...]}
    """
    if not website_url.startswith("http"):
        website_url = "https://" + website_url
    website_url = website_url.rstrip("/")

    parsed = urlparse(website_url)
    base_origin = f"{parsed.scheme}://{parsed.netloc}"

    pages: list[dict] = []
    visited: set[str] = set()

    # Homepage + key subpaths
    urls_to_try = [website_url]
    for subpath in _KEY_SUBPATHS:
        urls_to_try.append(urljoin(base_origin, subpath))

    print(f"\n{'='*60}")
    print(f"[WebsiteScraper] 🌐 Crawling website: {website_url}")
    print(f"{'='*60}\n")

    for url in urls_to_try:
        normalised = url.rstrip("/").lower()
        if normalised in visited:
            continue
        visited.add(normalised)

        page_data = _crawl_page(url)
        if not page_data:
            continue

        pages.append(page_data)

        # ── Print to console ──
        print(f"\n{'─'*50}")
        print(f"[WebsiteScraper] ✅ Page: {url}")
        print(f"  Title: {page_data['title']}")
        if page_data["meta_description"]:
            print(f"  Meta:  {page_data['meta_description']}")
        print(f"  Content length: {len(page_data['content'])} chars")
        print(f"  Content:\n{page_data['content']}")
        print(f"{'─'*50}")

    print(f"\n[WebsiteScraper] Done — scraped {len(pages)} pages from {website_url}\n")

    return {
        "url": website_url,
        "pages": pages,
    }
