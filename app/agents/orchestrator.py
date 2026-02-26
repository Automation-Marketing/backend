from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.content_agent import ContentAgent
from app.agents.telegram_agent import TelegramAgent
from app.domain.brand.scraping_orchestrator import ScrapingOrchestrator
from app.utils.text_processor import TextProcessor
from app.utils.vector_db import VectorDB


class AgentState(TypedDict):
    brand_id: int
    company_name: str
    icp: str
    tone: str
    description: str
    content_types: List[str]
    template_type: str
    
    instagram_handle: Optional[str]
    twitter_handle: Optional[str]
    linkedin_handle: Optional[str]
    
    scraped_data: dict
    generated_content: dict
    publish_result: dict


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


def generate_node(state: AgentState):
    """Uses ContentAgent to generate the 30-day content calendar via RAG."""
    print(f"[Orchestrator] Running generate_node for '{state['company_name']}'...")
    agent = ContentAgent()
    
    monthly_content = agent.generate_monthly(
        brand=state['company_name'],
        icp=state['icp'],
        tone=state['tone'],
        description=state['description'],
        content_types=state['content_types'],
        template_type=state['template_type']
    )
    
    return {"generated_content": monthly_content}


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
            # Format nicely for Telegram HTML mode
            formatted_val = value.replace("\n", "\n    ")
            message += f"\n<b>{key.replace('_', ' ').capitalize()}</b>: \n{formatted_val}\n"
            
    try:
        result = agent.send_message(message)
        print("[Orchestrator] Published successfully to Telegram.")
        return {"publish_result": {"status": "success", "telegram_result": result}}
    except Exception as e:
        print(f"[Orchestrator] Telegram publish failed: {e}")
        return {"publish_result": {"status": "error", "reason": str(e)}}


def build_orchestrator_graph():
    """Builds and compiles the StateGraph with human-in-the-loop interruption."""
    builder = StateGraph(AgentState)
    
    builder.add_node("scrape", scrape_node)
    builder.add_node("generate", generate_node)
    builder.add_node("publish", publish_node)
    
    builder.add_edge(START, "scrape")
    builder.add_edge("scrape", "generate")
    builder.add_edge("generate", "publish")
    builder.add_edge("publish", END)
    
    # Use MemorySaver checkpointer to persist state across interruptions
    memory = MemorySaver()
    
    # Compile graph to interrupt explicitly before the "publish" node
    graph = builder.compile(checkpointer=memory, interrupt_before=["publish"])
    return graph

# Ensure we have a singleton graph ready to be imported
graph = build_orchestrator_graph()
