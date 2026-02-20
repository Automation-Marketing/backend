"""
LangChain Prompt Templates for ContentAgent (StoryWeaver)

IMPORTANT — Brace escaping rules:
  {{ / }}  → literal { / } in the final rendered prompt (LangChain escaping)
  {var}    → LangChain input variable
  TMPL_TYPE → plain string-replaced before ChatPromptTemplate is built
"""

from langchain_core.prompts import ChatPromptTemplate

_SYSTEM_PREAMBLE = (
    "You are StoryWeaver, an expert social-media content strategist. "
    "You ALWAYS reply with ONLY a valid JSON object - no markdown, no explanation, "
    "no extra text before or after the JSON. "
    "Follow the schema exactly."
)

# --- MODULAR SCHEMA PARTS ---

_SCHEMA_BASE = """\
Return ONLY this JSON (no other text):
{{
  "template_type": "TMPL_TYPE",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
"""

_SCHEMA_CANONICAL = """\
  "canonical_post": "150-200 word {tone} social post about the topic",
  "visual_direction": "brief photorealistic image description for this post",
"""

_SCHEMA_CAROUSEL = """\
  "carousel": {{
    "title": "carousel series title",
    "slides": [
      {{"slide_number": 1, "title": "slide 1 headline", "body": "slide 1 body (2 sentences)", "image_prompt": "photorealistic image description for slide 1"}},
      {{"slide_number": 2, "title": "slide 2 headline", "body": "slide 2 body (2 sentences)", "image_prompt": "photorealistic image description for slide 2"}},
      {{"slide_number": 3, "title": "slide 3 headline", "body": "slide 3 body (2 sentences)", "image_prompt": "photorealistic image description for slide 3"}},
      {{"slide_number": 4, "title": "slide 4 headline", "body": "slide 4 body (2 sentences)", "image_prompt": "photorealistic image description for slide 4"}},
      {{"slide_number": 5, "title": "slide 5 headline", "body": "slide 5 body (2 sentences)", "image_prompt": "photorealistic image description for slide 5"}}
    ],
    "cta_slide": {{"title": "CTA headline", "body": "CTA body (1 sentence)", "image_prompt": "photorealistic image description for CTA slide"}}
  }},
"""

_SCHEMA_VIDEO = """\
  "video_script": {{
    "hook": "opening line (first 3 seconds)",
    "body": "main script (3-4 sentences)",
    "cta": "closing call-to-action line",
    "caption": "caption with hashtags",
    "video_prompt": "detailed prompt for text-to-video generation model describing the scene and action"
  }},
"""

_SCHEMA_CLOSE = """\
}}"""


def _build_dynamic_schema(template_type: str, content_types: list[str]) -> str:
    """
    Constructs a JSON schema string that includes ONLY requested content types.
    """
    schema_parts = [_SCHEMA_BASE.replace("TMPL_TYPE", template_type)]

    # "Canonical Post" is usually represented by "image" in the frontend,
    # or just "canonical_post" if we changed it. The frontend sends ["image", "carousel", ...]
    # Let's support both "image" and "canonical_post" keys just in case.
    if "image" in content_types or "canonical_post" in content_types:
        schema_parts.append(_SCHEMA_CANONICAL)

    if "carousel" in content_types:
        schema_parts.append(_SCHEMA_CAROUSEL)

    if "video_script" in content_types:
        schema_parts.append(_SCHEMA_VIDEO)

    schema_parts.append(_SCHEMA_CLOSE)
    return "".join(schema_parts)


# --- TEMPLATE DEFINITIONS ---

_EDUCATIONAL_HUMAN_BASE = """\
Brand: {brand}
Audience: {icp}
Tone: {tone}
Topic: {description}

Brand voice reference (past posts):
{context}

Strategy: Educational - lead with a surprising insight, give 3 actionable tips, end with a transformation + CTA.

"""

_PROBLEM_SOLUTION_HUMAN_BASE = """\
Brand: {brand}
Audience: {icp}
Tone: {tone}
Topic: {description}

Brand voice reference (past posts):
{context}

Strategy: Problem-Solution - agitate the problem, consequences of ignoring it, present the solution, clear next step.

"""

_TRUST_STORY_HUMAN_BASE = """\
Brand: {brand}
Audience: {icp}
Tone: {tone}
Topic: {description}

Brand voice reference (past posts):
{context}

Strategy: Trust Story - introduce the customer persona, their struggle, the result/win. Invite readers to get similar results.

"""


def get_template_for_type(template_type: str, content_types: list[str]) -> ChatPromptTemplate:
    """
    Factory function to get the correct LangChain prompt template
    with a dynamically built JSON schema.
    """
    # 1. Select base human prompt
    if template_type == "educational":
        base_prompt = _EDUCATIONAL_HUMAN_BASE
    elif template_type == "problem_solution":
        base_prompt = _PROBLEM_SOLUTION_HUMAN_BASE
    elif template_type == "trust_story":
        base_prompt = _TRUST_STORY_HUMAN_BASE
    else:
        # Fallback
        base_prompt = _EDUCATIONAL_HUMAN_BASE

    # 2. Build schema string
    schema_str = _build_dynamic_schema(template_type, content_types)

    # 3. Combine
    full_human_prompt = base_prompt + schema_str

    # 4. Return ChatPromptTemplate
    return ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PREAMBLE),
        ("human", full_human_prompt),
    ])

