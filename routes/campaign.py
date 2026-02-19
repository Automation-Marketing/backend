from fastapi import APIRouter
from pydantic import BaseModel
from services.db_service import get_connection

router = APIRouter()

class CampaignCreate(BaseModel):
    brand_id: int
    icp: str
    tone: str
    description: str
    content_type: str


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
                data.content_type,
                "draft"
            )
        )

        campaign_id = cur.fetchone()["id"]
        conn.commit()

        return {
            "message": "Campaign created successfully",
            "campaign_id": campaign_id
        }

    finally:
        cur.close()
        conn.close()