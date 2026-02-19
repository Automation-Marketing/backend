"""
ContentAgent (StoryWeaver) - LangChain RAG Content Generation Pipeline

Flow:
  user inputs → semantic search (ChromaDB) → LangChain prompt template
              → ChatOllama (llama3) → JSON output parser → validated dict
"""

import json
import re
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

from langchain_ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser

from agents.prompt_templates import TEMPLATE_REGISTRY
from services.vector_db import VectorDB

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Ollama base URL — uses localhost when running outside Docker.
# Override with OLLAMA_BASE_URL env var if needed.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Hard timeout (seconds) for a single LLM generation call
# Llama3 7B on CPU ≈ 0.75 tok/s; 300-token JSON output needs ~400s
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))

VALID_TEMPLATE_TYPES = {"educational", "problem_solution", "trust_story"}


# ---------------------------------------------------------------------------
# ContentAgent
# ---------------------------------------------------------------------------

class ContentAgent:
    """
    LangChain RAG agent that:
      1. Retrieves semantic context from ChromaDB (brand's past posts)
      2. Selects the right prompt template (educational / problem_solution / trust_story)
      3. Invokes ChatOllama (llama3) with format="json" for strict JSON output
      4. Parses and validates the JSON output
    """

    def __init__(self):
        self.llm = ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            format="json",           # Forces Ollama to return raw JSON
            temperature=0.5,         # Lower temp = more deterministic JSON
            num_predict=1024,        # Cap output length — keeps generation fast
            request_timeout=600,     # Must match LLM_TIMEOUT
            keep_alive="10m",        # Keep model loaded between requests
        )
        self.parser = JsonOutputParser()
        self.vector_db = VectorDB()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def _build_semantic_query(
        self,
        icp: str,
        tone: str,
        description: str,
        template_type: str,
    ) -> str:
        """
        Compose a rich semantic query string so ChromaDB finds the
        most relevant past content for this campaign.
        """
        return (
            f"{description}. "
            f"Target audience: {icp}. "
            f"Tone: {tone}. "
            f"Content style: {template_type.replace('_', ' ')}."
        )

    def _get_context(
        self,
        company_name: str,
        query: str,
        top_k: int = 5,
    ) -> str:
        """
        Semantic search over the company's ChromaDB collection.
        Returns retrieved chunks joined as a single context block.
        """
        try:
            results = self.vector_db.search(
                company_name=company_name,
                query=query,
                top_k=top_k,
            )
            if not results:
                return "No past content available for this brand."

            chunks = []
            for i, r in enumerate(results, 1):
                platform = r.get("metadata", {}).get("platform", "unknown")
                text = r.get("text", "").strip()
                if text:
                    chunks.append(f"[Post {i} — {platform}]\n{text}")

            return "\n\n".join(chunks) if chunks else "No past content available."

        except Exception as e:
            print(f"[ContentAgent] Vector DB search failed: {e}")
            return "Context retrieval failed — generating without past content."

    # ------------------------------------------------------------------
    # JSON repair helper
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(raw: str) -> dict:
        """
        Attempt to parse model output as JSON.
        Strips any markdown fences if the model erroneously adds them.
        """
        # Remove ```json ... ``` fences
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try to extract the first {...} blob
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse model output as JSON:\n{raw[:500]}")

    # ------------------------------------------------------------------
    # Main generate method
    # ------------------------------------------------------------------

    def generate(
        self,
        brand: str,
        icp: str,
        tone: str,
        description: str,
        template_type: str = "educational",
    ) -> dict:
        """
        Full RAG + generation pipeline.

        Args:
            brand:         Brand / company name (used for ChromaDB lookup)
            icp:           Target audience description
            tone:          Writing tone (Professional, Casual, etc.)
            description:   Campaign description / topic
            template_type: One of 'educational', 'problem_solution', 'trust_story'

        Returns:
            Validated dict matching the strict JSON schema in prompt_templates.py
        """
        # Normalise template type
        template_type = template_type.lower().strip()
        if template_type not in VALID_TEMPLATE_TYPES:
            raise ValueError(
                f"Invalid template_type '{template_type}'. "
                f"Must be one of: {VALID_TEMPLATE_TYPES}"
            )

        # Step 1 — Build semantic query & retrieve context
        query = self._build_semantic_query(icp, tone, description, template_type)
        print(f"[ContentAgent] Semantic query: {query}")

        context = self._get_context(brand, query, top_k=5)
        print(f"[ContentAgent] Retrieved {len(context)} chars of context")

        # Step 2 — Select prompt template
        prompt = TEMPLATE_REGISTRY[template_type]

        # Step 3 — Build LangChain chain: prompt | llm | parser
        chain = prompt | self.llm | self.parser

        # Step 4 — Invoke with hard wall-clock timeout.
        # IMPORTANT: do NOT use `with ThreadPoolExecutor()` — its __exit__
        # calls shutdown(wait=True), which blocks until the future finishes and
        # defeats the purpose of the timeout entirely.
        print(f"[ContentAgent] Invoking Llama3 with template '{template_type}' "
              f"(timeout={LLM_TIMEOUT}s)...")

        invoke_inputs = {
            "brand": brand,
            "icp": icp,
            "tone": tone,
            "description": description,
            "context": context,
        }

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(chain.invoke, invoke_inputs)
        try:
            result = future.result(timeout=LLM_TIMEOUT)
            print("[ContentAgent] Generation successful.")
            executor.shutdown(wait=False)
            return result

        except FuturesTimeoutError:
            executor.shutdown(wait=False)
            raise TimeoutError(
                f"Llama3 did not respond within {LLM_TIMEOUT}s. "
                "Make sure Ollama is running: ollama run llama3"
            )

        except Exception as e:
            print(f"[ContentAgent] Chain parse failed ({e}), attempting raw fallback...")
            raw_chain = prompt | self.llm
            raw_future = executor.submit(raw_chain.invoke, invoke_inputs)
            try:
                raw_response = raw_future.result(timeout=LLM_TIMEOUT)
                executor.shutdown(wait=False)
            except FuturesTimeoutError:
                executor.shutdown(wait=False)
                raise TimeoutError(
                    f"Llama3 fallback also timed out after {LLM_TIMEOUT}s."
                )

            raw_text = (
                raw_response.content
                if hasattr(raw_response, "content")
                else str(raw_response)
            )
            return self._extract_json(raw_text)


