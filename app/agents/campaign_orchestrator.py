import os
from langchain_google_genai import ChatGoogleGenerativeAI
from app.utils.vector_db import VectorDB

from .competition_agent import CompetitionAgent
from .usecase_agent import UsecaseAgent
from .objectives_agent import ObjectivesAgent
from .audience_agent import AudienceAgent
from .positioning_agent import PositioningAgent

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))

class CampaignOrchestrator:
    def __init__(self):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.7,
            max_output_tokens=8192,
            timeout=LLM_TIMEOUT,
        )
        self.vector_db = VectorDB()

        self.competition_agent = CompetitionAgent(self.llm)
        self.usecase_agent = UsecaseAgent(self.llm)
        self.objectives_agent = ObjectivesAgent(self.llm)
        self.audience_agent = AudienceAgent(self.llm)
        self.positioning_agent = PositioningAgent(self.llm)

    def _get_brand_context(self, company_name: str, query: str, top_k: int = 10) -> str:
        try:
            results = self.vector_db.search(company_name=company_name, query=query, top_k=top_k)
            if not results: return "No past context available."
            chunks = [f"[Context {i}]\n{r.get('text', '').strip()}" for i, r in enumerate(results, 1) if r.get('text', '').strip()]
            return "\n\n".join(chunks)
        except Exception as e:
            print(f"[Orchestrator] Vector DB retrieval failed: {e}")
            return "Context retrieval failed."

    def _save_to_memory(self, company_name: str, campaign_id: int, agent_type: str, data_str: str):
        try:
            self.vector_db.add_texts(
                company=company_name,
                texts=[data_str],
                metadatas=[{"type": "agent_insight", "campaign_id": campaign_id, "agent": agent_type}]
            )
        except Exception as e:
            print(f"[Orchestrator] Failed to save memory to vector DB: {e}")

    def run_pipeline(self, company_name: str, product_service: str, icp: str, tone: str, description: str, campaign_id: int) -> dict:
        print(f"\n{'='*50}\n[Orchestrator] Starting AI Brain Pipeline for {company_name}\n{'='*50}")

        scraped_context = self._get_brand_context(company_name, f"{company_name} brand context, {product_service}, {description}", top_k=15)
        
        print("[Agent 1/5] Running CompetitionAgent...")
        competition_out = self.competition_agent.run(company_name, product_service, description, scraped_context)
        self._save_to_memory(company_name, campaign_id, "competition", str(competition_out))

        print("[Agent 2/5] Running UsecaseAgent...")
        usecase_out = self.usecase_agent.run(company_name, product_service, description, scraped_context, str(competition_out))
        self._save_to_memory(company_name, campaign_id, "usecase", str(usecase_out))

        print("[Agent 3/5] Running ObjectivesAgent...")
        objectives_out = self.objectives_agent.run(company_name, product_service, description, str(competition_out), str(usecase_out))
        self._save_to_memory(company_name, campaign_id, "objectives", str(objectives_out))

        print("[Agent 4/5] Running AudienceAgent...")
        audience_out = self.audience_agent.run(company_name, product_service, icp, description, str(competition_out), str(usecase_out))
        self._save_to_memory(company_name, campaign_id, "audience", str(audience_out))

        print("[Agent 5/5] Running PositioningAgent...")
        positioning_out = self.positioning_agent.run(company_name, product_service, tone, description, str(competition_out), str(usecase_out), str(audience_out))
        self._save_to_memory(company_name, campaign_id, "positioning", str(positioning_out))

        ai_brain = {
            "competitors": competition_out.get("competitors", []),
            "alternative_product": competition_out.get("alternative_product", ""),
            "advantages": competition_out.get("advantages", ""),
            "use_cases": usecase_out.get("use_cases", []),
            "objectives": objectives_out.get("objectives", []),
            "target_users": audience_out.get("target_users", {}),
            "positioning": positioning_out.get("positioning", {})
        }

        print("[Orchestrator] AI Brain Generation Complete!")
        return ai_brain
