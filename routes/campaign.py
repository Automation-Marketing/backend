from fastapi import APIRouter
from pydantic import BaseModel
from services.db_service import get_connection

router = APIRouter()

# Request model
class CampaignCreate(BaseModel):
    brand_id: int
    description: str


@router.post("/campaign/create")
def create_campaign(data: CampaignCreate):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO campaigns (brand_id, description) VALUES (%s, %s) RETURNING id;",
            (data.brand_id, data.description)
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
