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
import json

router = APIRouter()

# Singleton agent (reuse LLM connection across requests)
_agent: ContentAgent | None = None


def get_agent() -> ContentAgent:
    global _agent
    if _agent is None:
        _agent = ContentAgent()
    return _agent


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class CampaignCreate(BaseModel):
    brand_id: int
    icp: str                            # Ideal Customer Profile
    tone: str                           # e.g. Professional, Casual, Bold
    description: str                    # Campaign topic / description
    content_types: List[str]            # ["image", "carousel", "video_script"]
    template_type: Literal[
        "educational",
        "problem_solution",
        "trust_story",
    ] = Field(
        default="educational",
        description="Prompt template strategy for content generation",
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/campaign/create")
def create_campaign(data: CampaignCreate):
    conn = get_connection()
    cur = conn.cursor()

    try:
        # ── 1. Resolve brand ────────────────────────────────────────────────
        cur.execute(
            "SELECT company_name FROM brands WHERE id = %s",
            (data.brand_id,),
        )
        brand = cur.fetchone()

        if not brand:
            return {"error": "Brand not found"}

        company_name = brand["company_name"]

        # ── 2. Persist campaign record ──────────────────────────────────────
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

        # ── 3. RAG content generation via LangChain + Llama3 ───────────────
        agent = get_agent()
        generated_content = agent.generate(
            brand=company_name,
            icp=data.icp,
            tone=data.tone,
            description=data.description,
            template_type=data.template_type,
        )

        # ── 4. Filter to only requested content_types ───────────────────────
        #   The agent always generates all variants; we expose only what the
        #   user requested so the frontend tab logic is preserved.
        filtered_content = {
            "template_type": generated_content.get("template_type"),
            "tags":          generated_content.get("tags", []),
            "canonical_post": generated_content.get("canonical_post", ""),
        }
        if "image" in data.content_types or "carousel" in data.content_types:
            filtered_content["carousel"] = generated_content.get("carousel")
        if "video_script" in data.content_types:
            filtered_content["video_script"] = generated_content.get("video_script")

        # ── 5. Persist generated content ────────────────────────────────────
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
