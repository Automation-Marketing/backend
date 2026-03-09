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
    website_url: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None


@router.post("/brand/create")
async def create_brand(data: BrandCreate):
    """
    Brand onboarding:
    1. Store brand + social handles + website URL in DB
    2. Resolve social handles
    (Website + social media scraping happens during campaign creation)
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        linkedin_handle_clean = data.linkedin_url.strip() if data.linkedin_url else data.company_name.lower().replace(' ', '-')

        cur.execute(
            """
            INSERT INTO brands (company_name, instagram_handle, twitter_handle, linkedin_url, website_url, industry, region)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (data.company_name, data.instagram_handle, data.twitter_handle, data.linkedin_url, data.website_url, data.industry, data.region)
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
            linkedin=data.linkedin_url,
            twitter=data.twitter_handle
        )
        print(f"[brand/create] Resolved handles: {handles}")

        return {
            "success": True,
            "brand_id": brand_id,
            "company_name": data.company_name,
            "message": "Brand saved successfully. Scraping will occur during campaign creation.",
            "handles": handles,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[brand/create] Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=f"Brand onboarding failed: {str(e)}")
