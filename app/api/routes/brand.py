from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.utils.db_service import get_connection
from app.domain.brand.company_resolver import CompanyResolver

router = APIRouter()

company_resolver = CompanyResolver()


class BrandCreate(BaseModel):
    company_name: str
    instagram_handle: Optional[str] = None
    twitter_handle: Optional[str] = None
    linkedin_url: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None


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

    try:
        linkedin_handle_clean = data.linkedin_handle.strip() if data.linkedin_handle else data.company_name.lower().replace(' ', '-')

        cur.execute(
            """
            INSERT INTO brands (company_name, instagram_handle, twitter_handle, linkedin_url, industry, region)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (data.company_name, data.instagram_handle, data.twitter_handle, data.linkedin_url, data.industry, data.region)
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

    try:
        handles = company_resolver.resolve(
            data.company_name,
            instagram=data.instagram_handle,
            linkedin=data.linkedin_handle,
            twitter=data.twitter_handle
        )
        print(f"[brand/create] Resolved handles: {handles}")

        return {
            "success": True,
            "brand_id": brand_id,
            "company_name": data.company_name,
            "message": "Brand and social handles saved successfully. Scraping will occur during campaign creation.",
            "handles": handles
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[brand/create] Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=f"Brand onboarding failed: {str(e)}")
