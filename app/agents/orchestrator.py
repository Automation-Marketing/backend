import os
from typing import TypedDict, List, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.content_agent import ContentAgent
from app.agents.image_generator import ImageGenerator
from app.agents.video_generator import VideoGenerator
from app.agents.telegram_agent import TelegramAgent
from app.agents.competition_agent import CompetitionAgent
from app.agents.usecase_agent import UsecaseAgent
from app.agents.objectives_agent import ObjectivesAgent
from app.agents.audience_agent import AudienceAgent
from app.agents.positioning_agent import PositioningAgent
from app.domain.brand.scraping_orchestrator import ScrapingOrchestrator
from app.utils.text_processor import TextProcessor
from app.utils.vector_db import VectorDB

import json

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))


class AgentState(TypedDict):
    brand_id: int
    campaign_id: int
    company_name: str
    product_service: str
    icp: str
    tone: str
    description: str
    content_types: List[str]
    template_type: str

    instagram_handle: Optional[str]
    twitter_handle: Optional[str]
    linkedin_handle: Optional[str]

    scraped_data: dict
    ai_brain: dict
    generated_content: dict
    publish_result: dict


# ---------------------------------------------------------------------------
# Node 1: Scrape social media platforms and populate the vector DB
# ---------------------------------------------------------------------------
async def scrape_node(state: AgentState):
    """Integrates ScrapingOrchestrator to pull data and populate the vector DB."""
    print(f"[Orchestrator] Running scrape_node for '{state['company_name']}'...")

    scraped_data = await ScrapingOrchestrator.scrape_all_platforms(
        instagram_handle=state.get("instagram_handle"),
        linkedin_handle=state.get("linkedin_handle"),
        twitter_handle=state.get("twitter_handle")
    )

    if scraped_data:
        text_processor = TextProcessor()
        vector_db = VectorDB()
        chunks = text_processor.process_all_platforms(scraped_data, state['company_name'])

        if chunks:
            print(f"[Orchestrator] Embedding {len(chunks)} chunks...")
            vector_db.add_posts(state['company_name'], chunks)

    return {"scraped_data": scraped_data or {}}


# ---------------------------------------------------------------------------
# Node 2: AI Brain — run the 5 strategy agents sequentially
# ---------------------------------------------------------------------------
def ai_brain_node(state: AgentState):
    """Runs Competition → Usecase → Objectives → Audience → Positioning agents."""
    company_name = state["company_name"]
    product_service = state.get("product_service", "")
    icp = state.get("icp", "")
    tone = state.get("tone", "")
    description = state.get("description", "")
    campaign_id = state.get("campaign_id", 0)

    print(f"\n{'='*50}")
    print(f"[Orchestrator] Starting AI Brain Pipeline for {company_name}")
    print(f"{'='*50}")

    # --- Shared LLM & vector DB ------------------------------------------
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0.7,
        max_output_tokens=8192,
        timeout=LLM_TIMEOUT,
    )
    vector_db = VectorDB()

    # --- Retrieve scraped context from vector DB -------------------------
    def _get_brand_context(query: str, top_k: int = 10) -> str:
        try:
            results = vector_db.search(company_name=company_name, query=query, top_k=top_k)
            if not results:
                return "No past context available."
            chunks = [
                f"[Context {i}]\n{r.get('text', '').strip()}"
                for i, r in enumerate(results, 1)
                if r.get('text', '').strip()
            ]
            return "\n\n".join(chunks)
        except Exception as e:
            print(f"[Orchestrator] Vector DB retrieval failed: {e}")
            return "Context retrieval failed."

    def _save_to_memory(agent_type: str, data_str: str):
        try:
            vector_db.add_texts(
                company=company_name,
                texts=[data_str],
                metadatas=[{"type": "agent_insight", "campaign_id": campaign_id, "agent": agent_type}]
            )
        except Exception as e:
            print(f"[Orchestrator] Failed to save memory to vector DB: {e}")

    scraped_context = _get_brand_context(
        f"{company_name} brand context, {product_service}, {description}", top_k=15
    )

    # --- Agent 1: Competition --------------------------------------------
    print("[Agent 1/5] Running CompetitionAgent...")
    competition_agent = CompetitionAgent(llm)
    competition_out = competition_agent.run(company_name, product_service, description, scraped_context)
    _save_to_memory("competition", str(competition_out))

    # --- Agent 2: Use-case ------------------------------------------------
    print("[Agent 2/5] Running UsecaseAgent...")
    usecase_agent = UsecaseAgent(llm)
    usecase_out = usecase_agent.run(company_name, product_service, description, scraped_context, str(competition_out))
    _save_to_memory("usecase", str(usecase_out))

    # --- Agent 3: Objectives ----------------------------------------------
    print("[Agent 3/5] Running ObjectivesAgent...")
    objectives_agent = ObjectivesAgent(llm)
    objectives_out = objectives_agent.run(company_name, product_service, description, str(competition_out), str(usecase_out))
    _save_to_memory("objectives", str(objectives_out))

    # --- Agent 4: Audience ------------------------------------------------
    print("[Agent 4/5] Running AudienceAgent...")
    audience_agent = AudienceAgent(llm)
    audience_out = audience_agent.run(company_name, product_service, icp, description, str(competition_out), str(usecase_out))
    _save_to_memory("audience", str(audience_out))

    # --- Agent 5: Positioning ---------------------------------------------
    print("[Agent 5/5] Running PositioningAgent...")
    positioning_agent = PositioningAgent(llm)
    positioning_out = positioning_agent.run(company_name, product_service, tone, description, str(competition_out), str(usecase_out), str(audience_out))
    _save_to_memory("positioning", str(positioning_out))

    # --- Assemble AI Brain ------------------------------------------------
    ai_brain = {
        "competitors": competition_out.get("competitors", []),
        "alternative_product": competition_out.get("alternative_product", ""),
        "advantages": competition_out.get("advantages", ""),
        "use_cases": usecase_out.get("use_cases", []),
        "objectives": objectives_out.get("objectives", []),
        "target_users": audience_out.get("target_users", {}),
        "positioning": positioning_out.get("positioning", {}),
    }

    print("[Orchestrator] AI Brain Generation Complete!")
    return {"ai_brain": ai_brain}


# ---------------------------------------------------------------------------
# Node 3: Content generation — 7-day calendar via RAG
# ---------------------------------------------------------------------------
def generate_node(state: AgentState):
    """Uses ContentAgent to generate the 7-day content calendar via RAG."""
    print(f"[Orchestrator] Running generate_node for '{state['company_name']}'...")
    agent = ContentAgent()

    # Enhance the description with the AI Brain context
    ai_brain = state.get("ai_brain", {})
    enhanced_description = (
        f"{state['description']}\n\nStrategic Constraints (AI Brain):\n{json.dumps(ai_brain)}"
        if ai_brain
        else state["description"]
    )

    monthly_content = agent.generate_monthly(
        brand=state['company_name'],
        icp=state['icp'],
        tone=state['tone'],
        description=enhanced_description,
        content_types=state['content_types'],
        template_type=state['template_type']
    )

    return {"generated_content": monthly_content}


# ---------------------------------------------------------------------------
# Node 3b: Image generation — generate images from visual descriptions
# ---------------------------------------------------------------------------
def image_gen_node(state: AgentState):
    """Generates images for canonical posts using their visual descriptions."""
    print(f"[Orchestrator] Running image_gen_node for '{state['company_name']}'...")

    generated_content = state.get("generated_content", {})
    days = generated_content.get("days", [])
    campaign_id = state.get("campaign_id", 0)

    if not days:
        print("[Orchestrator] No days to generate images for.")
        return {"generated_content": generated_content}

    try:
        image_gen = ImageGenerator()
        updated_days = image_gen.generate_for_days(days, campaign_id)
        generated_content["days"] = updated_days
        print(f"[Orchestrator] Image generation complete for {len(updated_days)} days.")
    except Exception as e:
        print(f"[Orchestrator] Image generation failed (non-fatal): {e}")

    return {"generated_content": generated_content}


# ---------------------------------------------------------------------------
# Node 3c: Video generation — generate videos from video prompts
# ---------------------------------------------------------------------------
def video_gen_node(state: AgentState):
    """Generates videos for video_script days using their video prompts."""
    print(f"[Orchestrator] Running video_gen_node for '{state['company_name']}'...")

    generated_content = state.get("generated_content", {})
    days = generated_content.get("days", [])
    campaign_id = state.get("campaign_id", 0)

    if not days:
        print("[Orchestrator] No days to generate videos for.")
        return {"generated_content": generated_content}

    try:
        video_gen = VideoGenerator()
        updated_days = video_gen.generate_for_days(days, campaign_id)
        generated_content["days"] = updated_days
        print(f"[Orchestrator] Video generation complete for {len(updated_days)} days.")
    except Exception as e:
        print(f"[Orchestrator] Video generation failed (non-fatal): {e}")

    return {"generated_content": generated_content}


# ---------------------------------------------------------------------------
# Router: decide whether to run image_gen or video_gen after content generation
# ---------------------------------------------------------------------------
def route_media_generation(state: AgentState) -> str:
    """Route to image_gen or video_gen based on the content types requested."""
    content_types = state.get("content_types", [])

    if "video_script" in content_types:
        print("[Orchestrator] Routing to video_gen_node (video_script detected)")
        return "video_gen"
    else:
        print("[Orchestrator] Routing to image_gen_node (canonical_post / image detected)")
        return "image_gen"


# ---------------------------------------------------------------------------
# Node 4: Publish to Telegram
# ---------------------------------------------------------------------------
def publish_node(state: AgentState):
    """Uses TelegramAgent to publish the first generated post to Telegram."""
    print(f"[Orchestrator] Running publish_node for '{state['company_name']}'...")

    generated_content = state.get("generated_content", {})
    days = generated_content.get("days", [])

    if not days:
        print("[Orchestrator] No content generated to publish.")
        return {"publish_result": {"status": "skipped", "reason": "No days generated"}}

    first_post = days[0]

    agent = TelegramAgent()
    message = f"🚀 <b>New Campaign Launched: {state['company_name']}</b>\n\n"
    message += f"<b>Day 1 Content</b> ({first_post.get('content_type', 'Post')}):\n"

    for key, value in first_post.items():
        if key not in ["day", "content_type"] and isinstance(value, str):
            formatted_val = value.replace("\n", "\n    ")
            message += f"\n<b>{key.replace('_', ' ').capitalize()}</b>: \n{formatted_val}\n"

    try:
        result = agent.send_message(message)
        print("[Orchestrator] Published successfully to Telegram.")
        return {"publish_result": {"status": "success", "telegram_result": result}}
    except Exception as e:
        print(f"[Orchestrator] Telegram publish failed: {e}")
        return {"publish_result": {"status": "error", "reason": str(e)}}


# ---------------------------------------------------------------------------
# Build the LangGraph
# ---------------------------------------------------------------------------
def build_orchestrator_graph():
    """Builds and compiles the StateGraph with human-in-the-loop interruption.

    Flow:
      scrape → ai_brain → generate → [router]
        ├─ canonical_post/image → image_gen → publish
        └─ video_script         → video_gen → publish
    """
    builder = StateGraph(AgentState)

    builder.add_node("scrape", scrape_node)
    builder.add_node("ai_brain", ai_brain_node)
    builder.add_node("generate", generate_node)
    builder.add_node("image_gen", image_gen_node)
    builder.add_node("video_gen", video_gen_node)
    builder.add_node("publish", publish_node)

    builder.add_edge(START, "scrape")
    builder.add_edge("scrape", "ai_brain")
    builder.add_edge("ai_brain", "generate")

    # Conditional routing after content generation
    builder.add_conditional_edges(
        "generate",
        route_media_generation,
        {"image_gen": "image_gen", "video_gen": "video_gen"},
    )

    builder.add_edge("image_gen", "publish")
    builder.add_edge("video_gen", "publish")
    builder.add_edge("publish", END)

    # Use MemorySaver checkpointer to persist state across interruptions
    memory = MemorySaver()

    # Compile graph to interrupt explicitly before the "publish" node
    graph = builder.compile(checkpointer=memory, interrupt_before=["publish"])
    return graph

# Ensure we have a singleton graph ready to be imported
graph = build_orchestrator_graph()
