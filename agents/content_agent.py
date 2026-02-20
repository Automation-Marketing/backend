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

from langchain_groq import ChatGroq
from langchain_core.output_parsers import JsonOutputParser

from agents.prompt_templates import get_template_for_type
from services.vector_db import VectorDB

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))

VALID_TEMPLATE_TYPES = {"educational", "problem_solution", "trust_story"}

class ContentAgent:
    """
    LangChain RAG agent that:
      1. Retrieves semantic context from ChromaDB (brand's past posts)
      2. Selects the right prompt template (educational / problem_solution / trust_story)
      3. Invokes ChatGroq (llama-3.3-70b-versatile) for content generation
      4. Parses and validates the JSON output
    """

    def __init__(self):
        if not GROQ_API_KEY:
             raise ValueError("GROQ_API_KEY environment variable is not set")
             
        self.llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=GROQ_API_KEY,
            temperature=0.5,         
            max_tokens=1024,        
            timeout=LLM_TIMEOUT,
            model_kwargs={"response_format": {"type": "json_object"}}, 
        )
        self.parser = JsonOutputParser()
        self.vector_db = VectorDB()

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

    @staticmethod
    def _extract_json(raw: str) -> dict:
        """
        Attempt to parse model output as JSON.
        Strips any markdown fences if the model erroneously adds them.
        """
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse model output as JSON:\n{raw[:500]}")

    def generate(
        self,
        brand: str,
        icp: str,
        tone: str,
        description: str,
        content_types: list[str],
        template_type: str = "educational",
    ) -> dict:
        """
        Full RAG + generation pipeline.

        Args:
            brand:         Brand / company name (used for ChromaDB lookup)
            icp:           Target audience description
            tone:          Writing tone (Professional, Casual, etc.)
            description:   Campaign description / topic
            content_types: List of requested content types ("image", "carousel", "video_script")
            template_type: One of 'educational', 'problem_solution', 'trust_story'

        Returns:
            Validated dict matching the strict JSON schema in prompt_templates.py
        """
        template_type = template_type.lower().strip()
        if template_type not in VALID_TEMPLATE_TYPES:
            raise ValueError(
                f"Invalid template_type '{template_type}'. "
                f"Must be one of: {VALID_TEMPLATE_TYPES}"
            )

        query = self._build_semantic_query(icp, tone, description, template_type)
        print(f"[ContentAgent] Semantic query: {query}")

        context = self._get_context(brand, query, top_k=5)
        print(f"[ContentAgent] Retrieved {len(context)} chars of context")

        prompt = get_template_for_type(template_type, content_types)

        chain = prompt | self.llm | self.parser

        print(f"[ContentAgent] Invoking Groq ({GROQ_MODEL}) with template '{template_type}' "
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
            print("\n=== LLM OUTPUT START ===")
            print(result)
            print("=== LLM OUTPUT END ===\n")
            executor.shutdown(wait=False)
            return result

        except FuturesTimeoutError:
            executor.shutdown(wait=False)
            raise TimeoutError(
                f"Groq API did not respond within {LLM_TIMEOUT}s. "
                "Check your internet connection and API key."
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
                    f"Groq fallback also timed out after {LLM_TIMEOUT}s."
                )

            raw_text = (
                raw_response.content
                if hasattr(raw_response, "content")
                else str(raw_response)
            )
            print("\n=== RAW LLM FALLBACK OUTPUT START ===")
            print(raw_text)
            print("=== RAW LLM FALLBACK OUTPUT END ===\n")
            return self._extract_json(raw_text)


