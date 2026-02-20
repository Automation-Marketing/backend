"""
Campaign Route — LangChain RAG Content Generation

POST /campaign/create
  - Accepts brand_id, icp, tone, description, content_types, template_type
  - Performs semantic search on campaign description (RAG) via ChromaDB
  - Runs the selected LangChain prompt template through Llama3 (ChatOllama)
  - Returns strict JSON: canonical_post + carousel + video_script + tags
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal
from services.db_service import get_connection
from agents.content_agent import ContentAgent
from services.image_service import image_service
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
                "draft",
            ),
        )
        campaign_id = cur.fetchone()["id"]
        conn.commit()

        agent = get_agent()
        generated_content = agent.generate(
            brand=company_name,
            icp=data.icp,
            tone=data.tone,
            description=data.description,
            content_types=data.content_types,
            template_type=data.template_type,
        )

        filtered_content = {
            "template_type": generated_content.get("template_type"),
            "tags":          generated_content.get("tags", []),
        }

        if "image" in data.content_types or "canonical_post" in data.content_types:
            filtered_content["canonical_post"] = generated_content.get("canonical_post", "")
            img_url = image_service.generate_image(generated_content.get("visual_direction", data.description))
            filtered_content["image_url"] = img_url
            generated_content["image_url"] = img_url # Keep sync with full object

        if "carousel" in data.content_types:
            carousel_data = generated_content.get("carousel", {})
            slides = carousel_data.get("slides", [])
            for slide in slides:
                slide_prompt = slide.get("image_prompt", f"Slide: {slide.get('title')}")
                slide["image_url"] = image_service.generate_image(slide_prompt)
            
            cta_slide = carousel_data.get("cta_slide", {})
            if cta_slide:
                cta_prompt = cta_slide.get("image_prompt", "Call to action")
                cta_slide["image_url"] = image_service.generate_image(cta_prompt)
                
            filtered_content["carousel"] = carousel_data

        if "video_script" in data.content_types:
            filtered_content["video_script"] = generated_content.get("video_script")

        cur.execute(
            """
            UPDATE campaigns
            SET generated_content = %s, status = %s
            WHERE id = %s;
            """,
            (json.dumps(generated_content), "completed", campaign_id),
        )
        conn.commit()

        return {
            "success": True,
            "campaign_id": campaign_id,
            "company": company_name,
            "template_type": data.template_type,
            "generated_content": filtered_content,
        }

    except Exception as e:
        conn.rollback()
        print(f"[campaign] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cur.close()
        conn.close()
