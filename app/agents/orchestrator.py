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
from app.agents.visual_analyzer_agent import VisualAnalyzerAgent
from app.domain.brand.scraping_orchestrator import ScrapingOrchestrator
from app.domain.scraping.website_scraper import scrape_website
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
    website_url: Optional[str]

    scraped_data: dict
    ai_brain: dict
    generated_content: dict
    publish_result: dict


# ---------------------------------------------------------------------------
# Node 1: Scrape social media platforms and populate the vector DB
# ---------------------------------------------------------------------------
async def scrape_node(state: AgentState):
    """Scrapes social media platforms AND the company website, then populates the vector DB."""
    print(f"[Orchestrator] Running scrape_node for '{state['company_name']}'...")

    # ── Social media scraping ─────────────────────────────────────────
    scraped_data = await ScrapingOrchestrator.scrape_all_platforms(
        instagram_handle=state.get("instagram_handle"),
        linkedin_handle=state.get("linkedin_handle"),
        twitter_handle=state.get("twitter_handle")
    )

    if not scraped_data:
        scraped_data = {}

    # ── Website scraping ──────────────────────────────────────────────
    website_url = state.get("website_url")
    if website_url and website_url.strip():
        try:
            print(f"[Orchestrator] Scraping website: {website_url}")
            website_data = scrape_website(website_url.strip())

            pages = website_data.get("pages", [])
            if pages:
                # Print scraped content to console
                print(f"\n{'='*60}")
                print(f"[Orchestrator] WEBSITE SCRAPED CONTENT for '{state['company_name']}'")
                print(f"{'='*60}")
                for page in pages:
                    print(f"\n--- {page['url']} ---")
                    print(f"Title: {page.get('title', 'N/A')}")
                    print(f"Meta:  {page.get('meta_description', 'N/A')}")
                    print(f"Content:\n{page.get('content', '')}")
                print(f"{'='*60}\n")

                # Add to scraped_data so it gets processed together
                scraped_data["website"] = website_data
            else:
                print("[Orchestrator] Website scraping returned no pages.")
        except Exception as e:
            print(f"[Orchestrator] Website scraping failed (non-fatal): {e}")

    # ── Process & embed all scraped data ──────────────────────────────
    if scraped_data:
        text_processor = TextProcessor()
        vector_db = VectorDB()
        chunks = text_processor.process_all_platforms(scraped_data, state['company_name'])

        if chunks:
            print(f"[Orchestrator] Embedding {len(chunks)} chunks into vector DB...")
            vector_db.add_posts(state['company_name'], chunks)

    return {"scraped_data": scraped_data or {}}


# ---------------------------------------------------------------------------
# Node 2: AI Brain — run the strategy agents sequentially
# ---------------------------------------------------------------------------
async def ai_brain_node(state: AgentState):
    """Runs Competition → Usecase → Objectives → Audience → Positioning → VisualAnalyzer agents."""
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

    # --- Agent 6: Visual Analyzer -----------------------------------------
    print("[Agent 6/6] Running VisualAnalyzerAgent...")
    scraped_data = state.get("scraped_data", {})
    image_urls = []
    
    # Extract from Instagram
    ig_data = scraped_data.get("instagram", {})
    if ig_data:
        for post in ig_data.get("last_10_posts_and_reels", []):
            if post.get("image_url"):
                image_urls.append(post.get("image_url"))
                
    # Extract from LinkedIn
    li_data = scraped_data.get("linkedin", {})
    if li_data:
        for post in li_data.get("recent_posts", []):
            if post.get("image_url"):
                image_urls.append(post.get("image_url"))
                
    # Extract from Twitter
    tw_data = scraped_data.get("twitter", {})
    if tw_data:
        for post in tw_data.get("posts", []):
            if post.get("image_url"):
                image_urls.append(post.get("image_url"))
                
    visual_identity = "No visual context analyzed."
    if image_urls:
        visual_agent = VisualAnalyzerAgent()
        visual_identity = await visual_agent.analyze_images(company_name, image_urls)
        _save_to_memory("visual", visual_identity)

    # --- Assemble AI Brain ------------------------------------------------
    ai_brain = {
        "competitors": competition_out.get("competitors", []),
        "alternative_product": competition_out.get("alternative_product", ""),
        "advantages": competition_out.get("advantages", ""),
        "use_cases": usecase_out.get("use_cases", []),
        "objectives": objectives_out.get("objectives", []),
        "target_users": audience_out.get("target_users", {}),
        "positioning": positioning_out.get("positioning", {}),
        "visual_identity": visual_identity,
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
        website_url=state.get('website_url', ''),
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

    if not any(d.get("content_type") in ("canonical_post", "image", "carousel") for d in days):
        print("[Orchestrator] No images/carousels to generate for this campaign.")
        return {"generated_content": generated_content}

    try:
        image_gen = ImageGenerator()
        ai_brain = state.get("ai_brain", {})
        visual_identity = ai_brain.get("visual_identity", "No specific visual identity analyzed.")
        
        updated_days = image_gen.generate_for_days(
            days, 
            campaign_id,
            company_name=state.get("company_name", ""),
            website_url=state.get("website_url", ""),
            visual_identity=visual_identity
        )
        generated_content["days"] = updated_days
        
        count = sum(1 for d in updated_days if "image_url" in d or any(s.get("image_url") for s in d.get("carousel", {}).get("slides", [])))
        print(f"[Orchestrator] Image generation complete. Generated images for {count} days.")
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

    if not any(d.get("content_type") == "video_script" for d in days):
        print("[Orchestrator] No video scripts to generate for this campaign.")
        return {"generated_content": generated_content}

    try:
        video_gen = VideoGenerator()
        ai_brain = state.get("ai_brain", {})
        visual_identity = ai_brain.get("visual_identity", "No specific visual identity analyzed.")
        
        updated_days = video_gen.generate_for_days(
            days, 
            campaign_id,
            company_name=state.get("company_name", ""),
            website_url=state.get("website_url", ""),
            visual_identity=visual_identity
        )
        generated_content["days"] = updated_days
        
        count = sum(1 for d in updated_days if "video_url" in d)
        print(f"[Orchestrator] Video generation complete. Generated videos for {count} days.")
    except Exception as e:
        print(f"[Orchestrator] Video generation failed (non-fatal): {e}")

    return {"generated_content": generated_content}


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
    builder.add_edge("generate", "image_gen")
    builder.add_edge("image_gen", "video_gen")
    builder.add_edge("video_gen", "publish")
    builder.add_edge("publish", END)

    # Use MemorySaver checkpointer to persist state across interruptions
    memory = MemorySaver()

    # Compile graph to interrupt explicitly before the "publish" node
    graph = builder.compile(checkpointer=memory, interrupt_before=["publish"])
    return graph

# Ensure we have a singleton graph ready to be imported
graph = build_orchestrator_graph()
