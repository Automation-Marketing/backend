"""
Campaign Route — Gemini 2.5 Flash RAG Content Generation

POST /campaign/create
  - Accepts brand_id, icp, tone, description, content_types, template_type
  - Performs semantic search on campaign description (RAG) via ChromaDB
  - Generates a 30-day content calendar using Gemini 2.5 Flash
  - Returns strict JSON with daily content assignments
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal
from app.utils.db_service import get_connection
from app.agents.content_agent import ContentAgent
import json

router = APIRouter()

_agent: ContentAgent | None = None


def get_agent() -> ContentAgent:
    global _agent
    if _agent is None:
        _agent = ContentAgent()
    return _agent

class CampaignCreate(BaseModel):
    brand_id: int
    icp: str                            
    tone: str                           
    description: str
    content_types: List[str]            
    template_type: Literal[
        "educational",
        "problem_solution",
        "trust_story",
    ] = Field(
        default="educational",
        description="Prompt template strategy for content generation",
    )

@router.post("/campaign/create")
def create_campaign(data: CampaignCreate):
    conn = get_connection()
    cur = conn.cursor()
    print(f"DEBUG: Received content_types: {data.content_types}", flush=True)

    try:
        cur.execute(
            "SELECT company_name FROM brands WHERE id = %s",
            (data.brand_id,),
        )
        brand = cur.fetchone()

        if not brand:
            return {"error": "Brand not found"}

        company_name = brand["company_name"]

        cur.execute(
            """
            INSERT INTO campaigns
                (brand_id, icp, tone, description, content_type, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                data.brand_id,
                data.icp,
                data.tone,
                data.description,
                ",".join(data.content_types),
                "generating",
            ),
        )
        campaign_id = cur.fetchone()["id"]
        conn.commit()

        print(f"[campaign] Generating 30-day content calendar for '{company_name}'...")

        agent = get_agent()
        monthly_content = agent.generate_monthly(
            brand=company_name,
            icp=data.icp,
            tone=data.tone,
            description=data.description,
            content_types=data.content_types,
            template_type=data.template_type,
        )

        cur.execute(
            """
            UPDATE campaigns
            SET generated_content = %s, status = %s
            WHERE id = %s;
            """,
            (json.dumps(monthly_content), "completed", campaign_id),
        )
        conn.commit()

        print(f"[campaign] 30-day calendar saved. Total days: {monthly_content.get('total_days', 0)}")

        return {
            "success": True,
            "campaign_id": campaign_id,
            "company": company_name,
            "template_type": data.template_type,
            "total_days": monthly_content.get("total_days", 0),
            "generated_content": monthly_content,
        }

    except Exception as e:
        conn.rollback()
        print(f"[campaign] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cur.close()
        conn.close()


@router.get("/campaign/{campaign_id}")
def get_campaign(campaign_id: int):
    """Fetch an existing campaign by ID, including its 30-day generated content."""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """
            SELECT c.*, b.company_name 
            FROM campaigns c
            JOIN brands b ON c.brand_id = b.id
            WHERE c.id = %s
            """,
            (campaign_id,)
        )
        campaign = cur.fetchone()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
            
        return {
            "success": True,
            "campaign": {
                "id": campaign["id"],
                "company_name": campaign["company_name"],
                "icp": campaign["icp"],
                "tone": campaign["tone"],
                "description": campaign["description"],
                "status": campaign["status"],
                "generated_content": campaign["generated_content"],
                "created_at": campaign["created_at"].isoformat() if campaign["created_at"] else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[campaign] Fetch Error: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    finally:
        cur.close()
        conn.close()
