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

# --- MODULAR SCHEMA PARTS (single content) ---

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
    with a dynamically built JSON schema (single content piece).
    """
    if template_type == "educational":
        base_prompt = _EDUCATIONAL_HUMAN_BASE
    elif template_type == "problem_solution":
        base_prompt = _PROBLEM_SOLUTION_HUMAN_BASE
    elif template_type == "trust_story":
        base_prompt = _TRUST_STORY_HUMAN_BASE
    else:
        base_prompt = _EDUCATIONAL_HUMAN_BASE

    schema_str = _build_dynamic_schema(template_type, content_types)
    full_human_prompt = base_prompt + schema_str

    return ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PREAMBLE),
        ("human", full_human_prompt),
    ])


# ============================================================
# MONTHLY CONTENT CALENDAR TEMPLATES
# ============================================================

_MONTHLY_SYSTEM = (
    "You are StoryWeaver, an expert social-media content strategist. "
    "You are generating a MONTHLY content calendar. "
    "Each day MUST have UNIQUE, FRESH content — never repeat ideas, angles, or hooks. "
    "Vary the tone subtly across days while staying on-brand. "
    "You ALWAYS reply with ONLY a valid JSON object — no markdown, no explanation."
)

_MONTHLY_HUMAN_BASE = """\
Brand: {brand}
Audience: {icp}
Tone: {tone}
Campaign Topic: {description}

Brand voice reference (past posts):
{context}

Generate content for Days {day_start} to {day_end} of a 30-day calendar.
Each day gets a DIFFERENT content piece. The content type for each day is assigned below.

{day_assignments}

IMPORTANT:
- Every day must have completely unique content — different angles, hooks, and ideas.
- Match the assigned content_type for each day exactly.
- Keep the brand voice consistent but vary the approach.

Return ONLY this JSON:
{{
  "days": [
{day_schema}
  ]
}}"""


def _build_day_schema(day: int, content_type: str) -> str:
    """Build the JSON schema fragment for a single day."""
    if content_type in ("image", "canonical_post"):
        return (
            f'    {{"day": {day}, "content_type": "canonical_post", '
            f'"canonical_post": "150-200 word social post", '
            f'"visual_direction": "photorealistic image description", '
            f'"tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]}}'
        )
    elif content_type == "carousel":
        return (
            f'    {{"day": {day}, "content_type": "carousel", '
            f'"carousel": {{"title": "...", "slides": ['
            f'{{"slide_number": 1, "title": "...", "body": "...", "image_prompt": "..."}}, '
            f'{{"slide_number": 2, "title": "...", "body": "...", "image_prompt": "..."}}, '
            f'{{"slide_number": 3, "title": "...", "body": "...", "image_prompt": "..."}}'
            f'], "cta_slide": {{"title": "...", "body": "...", "image_prompt": "..."}}}}, '
            f'"tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]}}'
        )
    elif content_type == "video_script":
        return (
            f'    {{"day": {day}, "content_type": "video_script", '
            f'"video_script": {{"hook": "...", "body": "...", "cta": "...", '
            f'"caption": "...", "video_prompt": "..."}}, '
            f'"tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]}}'
        )
    else:
        return _build_day_schema(day, "canonical_post")


def get_monthly_template(
    template_type: str,
    content_types: list[str],
    day_start: int,
    day_end: int,
) -> tuple:
    """
    Build a prompt template for a batch of days in the monthly calendar.
    Content types cycle across days.
    Returns: (ChatPromptTemplate, day_schema_str)
    """
    # Select strategy text
    if template_type == "educational":
        strategy = "Educational - lead with surprising insights, actionable tips, transformation + CTA."
    elif template_type == "problem_solution":
        strategy = "Problem-Solution - agitate the problem, consequences, present the solution, clear next step."
    elif template_type == "trust_story":
        strategy = "Trust Story - customer persona, their struggle, the result/win. Invite similar results."
    else:
        strategy = "Educational."

    # Build day assignments and schema
    day_assignments_lines = []
    day_schema_lines = []

    for day in range(day_start, day_end + 1):
        ct_index = (day - 1) % len(content_types)
        ct = content_types[ct_index]
        day_assignments_lines.append(f"- Day {day}: {ct}")
        day_schema_lines.append(_build_day_schema(day, ct))

    day_assignments = "\n".join(day_assignments_lines)
    day_schema = ",\n".join(day_schema_lines)

    human_prompt = _MONTHLY_HUMAN_BASE + f"\n\nStrategy: {strategy}"

    prompt = ChatPromptTemplate.from_messages([
        ("system", _MONTHLY_SYSTEM),
        ("human", human_prompt),
    ])
    
    return prompt, day_schema
