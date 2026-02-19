from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from services.db_service import get_connection

router = APIRouter()

class CampaignCreate(BaseModel):
    brand_id: int
    icp: str
    tone: str
    description: str
    content_types: List[str]   # e.g. ["image", "carousel", "video_script"]


@router.post("/campaign/create")
def create_campaign(data: CampaignCreate):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO campaigns (brand_id, icp, tone, description, content_type, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                data.brand_id,
                data.icp,
                data.tone,
                data.description,
                ",".join(data.content_types),   # store as "image,carousel,video_script"
                "draft"
            )
        )

        campaign_id = cur.fetchone()["id"]
        conn.commit()

        return {
            "success": True,
            "message": "Campaign created successfully",
            "campaign_id": campaign_id
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cur.close()
        conn.close()