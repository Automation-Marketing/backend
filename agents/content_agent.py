"""
ContentAgent (StoryWeaver) - LangChain RAG Content Generation Pipeline

Flow:
  user inputs → semantic search (ChromaDB) → LangChain prompt template
              → Gemini 2.5 Flash → JSON output parser → validated dict
"""

import json
import re
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser

from agents.prompt_templates import get_template_for_type, get_monthly_template
from services.vector_db import VectorDB

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))

VALID_TEMPLATE_TYPES = {"educational", "problem_solution", "trust_story"}

# Batch configuration for monthly generation
DAYS_PER_BATCH = 5
TOTAL_DAYS = 30


class ContentAgent:
    """
    LangChain RAG agent that:
      1. Retrieves semantic context from ChromaDB (brand's past posts)
      2. Selects the right prompt template (educational / problem_solution / trust_story)
      3. Invokes Gemini 2.5 Flash for content generation
      4. Parses and validates the JSON output
    """

    def __init__(self):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.7,
            max_output_tokens=4096,
            timeout=LLM_TIMEOUT,
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

    # =========================================================
    # Single content generation (original)
    # =========================================================

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
        Single content piece generation (original behavior).
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

        print(f"[ContentAgent] Invoking Gemini ({GEMINI_MODEL}) with template '{template_type}'...")

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
            print(json.dumps(result, indent=2))
            print("=== LLM OUTPUT END ===\n")
            executor.shutdown(wait=False)
            return result

        except FuturesTimeoutError:
            executor.shutdown(wait=False)
            raise TimeoutError(
                f"Gemini API did not respond within {LLM_TIMEOUT}s."
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
                raise TimeoutError(f"Gemini fallback also timed out after {LLM_TIMEOUT}s.")

            raw_text = (
                raw_response.content
                if hasattr(raw_response, "content")
                else str(raw_response)
            )
            return self._extract_json(raw_text)

    # =========================================================
    # Monthly content calendar generation (NEW)
    # =========================================================

    def generate_monthly(
        self,
        brand: str,
        icp: str,
        tone: str,
        description: str,
        content_types: list[str],
        template_type: str = "educational",
    ) -> dict:
        """
        Generate a 30-day content calendar.
        Splits into batches of 5 days, calls LLM for each batch,
        and merges results into a single calendar.

        Returns:
            {"days": [{"day": 1, "content_type": "...", ...}, ...]}
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

        all_days = []

        # Generate in batches of DAYS_PER_BATCH
        num_batches = (TOTAL_DAYS + DAYS_PER_BATCH - 1) // DAYS_PER_BATCH

        for batch_idx in range(num_batches):
            day_start = batch_idx * DAYS_PER_BATCH + 1
            day_end = min(day_start + DAYS_PER_BATCH - 1, TOTAL_DAYS)

            print(f"\n[ContentAgent] === Batch {batch_idx + 1}/{num_batches}: Days {day_start}-{day_end} ===")

            # Build day assignments for this batch
            day_assignments_lines = []
            for day in range(day_start, day_end + 1):
                ct_index = (day - 1) % len(content_types)
                ct = content_types[ct_index]
                day_assignments_lines.append(f"- Day {day}: {ct}")

            prompt, day_schema_str = get_monthly_template(
                template_type=template_type,
                content_types=content_types,
                day_start=day_start,
                day_end=day_end,
            )

            invoke_inputs = {
                "brand": brand,
                "icp": icp,
                "tone": tone,
                "description": description,
                "context": context,
                "day_start": str(day_start),
                "day_end": str(day_end),
                "day_assignments": "\n".join(day_assignments_lines),
                "day_schema": day_schema_str,
            }

            print(f"[ContentAgent] Invoking Gemini for Days {day_start}-{day_end}...")

            try:
                chain = prompt | self.llm | self.parser
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(chain.invoke, invoke_inputs)

                try:
                    batch_result = future.result(timeout=LLM_TIMEOUT)
                    executor.shutdown(wait=False)
                except FuturesTimeoutError:
                    executor.shutdown(wait=False)
                    raise TimeoutError(f"Batch {batch_idx + 1} timed out.")
                except Exception as e:
                    # Fallback: try raw parse
                    print(f"[ContentAgent] Parse failed ({e}), trying raw fallback...")
                    raw_chain = prompt | self.llm
                    raw_future = executor.submit(raw_chain.invoke, invoke_inputs)
                    try:
                        raw_response = raw_future.result(timeout=LLM_TIMEOUT)
                        executor.shutdown(wait=False)
                    except FuturesTimeoutError:
                        executor.shutdown(wait=False)
                        raise TimeoutError(f"Batch {batch_idx + 1} fallback timed out.")

                    raw_text = (
                        raw_response.content
                        if hasattr(raw_response, "content")
                        else str(raw_response)
                    )
                    batch_result = self._extract_json(raw_text)

                # Extract days from batch result
                batch_days = batch_result.get("days", [])
                if not batch_days and isinstance(batch_result, list):
                    batch_days = batch_result

                print(f"[ContentAgent] Batch {batch_idx + 1}: Got {len(batch_days)} days")
                print(f"\n[ContentAgent] === LLM OUTPUT START (Batch {batch_idx + 1}) ===")
                print(json.dumps(batch_result, indent=2))
                print("=== LLM OUTPUT END ===\n")

                all_days.extend(batch_days)

            except Exception as e:
                print(f"[ContentAgent] Batch {batch_idx + 1} FAILED: {e}")
                # Add placeholder days for failed batch
                for day in range(day_start, day_end + 1):
                    all_days.append({
                        "day": day,
                        "content_type": "error",
                        "error": str(e),
                    })

        print(f"\n[ContentAgent] Monthly calendar complete: {len(all_days)} days generated")

        return {
            "template_type": template_type,
            "total_days": len(all_days),
            "days": all_days,
        }
