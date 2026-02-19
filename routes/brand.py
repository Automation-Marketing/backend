from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.db_service import get_connection
from services.company_resolver import CompanyResolver
from services.scraping_orchestrator import ScrapingOrchestrator
from services.text_processor import TextProcessor
from services.vector_db import VectorDB

router = APIRouter()

# Shared service instances
company_resolver = CompanyResolver()
text_processor = TextProcessor()
vector_db = VectorDB()


# Request model
class BrandCreate(BaseModel):
    company_name: str
    instagram_handle: Optional[str] = None
    twitter_handle: Optional[str] = None
    linkedin_url: Optional[str] = None


@router.post("/brand/create")
async def create_brand(data: BrandCreate):
    """
    Full onboarding pipeline:
    1. Store brand + social handles in DB
    2. Scrape all provided social media platforms
    3. Process & chunk the scraped content
    4. Embed and store in vector DB
    """
    conn = get_connection()
    cur = conn.cursor()

    # ── Step 1: Save brand to Postgres ──────────────────────────────────────
    try:
        cur.execute(
            """
            INSERT INTO brands (company_name, instagram_handle, twitter_handle, linkedin_url)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (data.company_name, data.instagram_handle, data.twitter_handle, data.linkedin_url)
        )
        brand_id = cur.fetchone()["id"]
        conn.commit()
        print(f"[brand/create] Brand '{data.company_name}' saved with id={brand_id}")

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"DB insert failed: {str(e)}")

    finally:
        cur.close()
        conn.close()

    # ── Step 2: Resolve social handles ──────────────────────────────────────
    try:
        handles = company_resolver.resolve(
            data.company_name,
            instagram=data.instagram_handle,
            linkedin=data.linkedin_url,
            twitter=data.twitter_handle
        )
        print(f"[brand/create] Resolved handles: {handles}")

        if not any(handles.values()):
            # No social handles provided — skip scraping but still return success
            return {
                "success": True,
                "brand_id": brand_id,
                "company_name": data.company_name,
                "message": "Brand saved. No social handles provided — scraping skipped.",
                "platforms_scraped": [],
                "chunks_created": 0
            }

        # ── Step 3: Scrape all platforms in parallel ─────────────────────────
        print(f"[brand/create] Starting scraping for '{data.company_name}'...")
        scraped_data = await ScrapingOrchestrator.scrape_all_platforms(
            instagram_handle=handles.get("instagram") or None,
            linkedin_url=handles.get("linkedin") or None,
            twitter_handle=handles.get("twitter") or None
        )

        if not scraped_data:
            return {
                "success": True,
                "brand_id": brand_id,
                "company_name": data.company_name,
                "message": "Brand saved. Scraping returned no data.",
                "platforms_scraped": [],
                "chunks_created": 0
            }

        # ── Step 4: Process & chunk scraped content ──────────────────────────
        print(f"[brand/create] Processing scraped content...")
        chunks = text_processor.process_all_platforms(scraped_data, data.company_name)

        if not chunks:
            return {
                "success": True,
                "brand_id": brand_id,
                "company_name": data.company_name,
                "message": "Brand saved. No valid content found to embed.",
                "platforms_scraped": list(scraped_data.keys()),
                "chunks_created": 0
            }

        # ── Step 5: Embed & store in vector DB ──────────────────────────────
        print(f"[brand/create] Embedding {len(chunks)} chunks into vector DB...")
        vector_db.add_posts(data.company_name, chunks)

        stats = vector_db.get_company_stats(data.company_name)
        print(f"[brand/create] Done! Total posts in vector DB: {stats['total_posts']}")

        return {
            "success": True,
            "brand_id": brand_id,
            "company_name": data.company_name,
            "message": f"Brand onboarded successfully with {len(chunks)} chunks embedded.",
            "platforms_scraped": list(scraped_data.keys()),
            "chunks_created": len(chunks),
            "total_posts_in_db": stats["total_posts"]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[brand/create] Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping/embedding pipeline failed: {str(e)}")
