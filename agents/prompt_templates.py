"""
LangChain Prompt Templates for ContentAgent (StoryWeaver)

IMPORTANT — Brace escaping rules:
  {{ / }}  → literal { / } in the final rendered prompt (LangChain escaping)
  {var}    → LangChain input variable
  TMPL_TYPE → plain string-replaced before ChatPromptTemplate is built
"""

from langchain_core.prompts import ChatPromptTemplate

# ---------------------------------------------------------------------------
# Shared system preamble
# ---------------------------------------------------------------------------

_SYSTEM_PREAMBLE = (
    "You are StoryWeaver, an expert social-media content strategist. "
    "You ALWAYS reply with ONLY a valid JSON object — no markdown, no explanation, "
    "no extra text before or after the JSON. "
    "Follow the schema exactly."
)

# ---------------------------------------------------------------------------
# Compact JSON schema — kept small so Llama3 generates it quickly
# ---------------------------------------------------------------------------

_JSON_SCHEMA = """\
Return ONLY this JSON (no other text):
{{
  "template_type": "TMPL_TYPE",
  "tags": ["tag1", "tag2", "tag3"],
  "canonical_post": "150-200 word {tone} social post about the topic",
  "carousel": {{
    "title": "carousel series title",
    "slides": [
      {{"slide_number": 1, "title": "slide 1 headline", "body": "slide 1 body (2 sentences)"}},
      {{"slide_number": 2, "title": "slide 2 headline", "body": "slide 2 body (2 sentences)"}},
      {{"slide_number": 3, "title": "slide 3 headline", "body": "slide 3 body (2 sentences)"}}
    ],
    "cta_slide": {{"title": "CTA headline", "body": "CTA body (1 sentence)"}}
  }},
  "video_script": {{
    "hook": "opening line (first 3 seconds)",
    "body": "main script (3-4 sentences)",
    "cta": "closing call-to-action line",
    "caption": "caption with hashtags"
  }}
}}"""


def _make_schema(template_type: str) -> str:
    return _JSON_SCHEMA.replace("TMPL_TYPE", template_type)


# ---------------------------------------------------------------------------
# 1. Educational Template
# ---------------------------------------------------------------------------

_EDUCATIONAL_HUMAN = """\
Brand: {brand}
Audience: {icp}
Tone: {tone}
Topic: {description}

Brand voice reference (past posts):
{context}

Strategy: Educational — lead with a surprising insight, give 3 actionable tips (one per slide), end with a transformation + CTA.

""" + _make_schema("educational")

EDUCATIONAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PREAMBLE),
    ("human", _EDUCATIONAL_HUMAN),
])

# ---------------------------------------------------------------------------
# 2. Problem-Solution Template
# ---------------------------------------------------------------------------

_PROBLEM_SOLUTION_HUMAN = """\
Brand: {brand}
Audience: {icp}
Tone: {tone}
Topic: {description}

Brand voice reference (past posts):
{context}

Strategy: Problem-Solution — Slide 1: agitate the problem. Slide 2: consequences of ignoring it. Slide 3: present the solution. CTA: clear next step.

""" + _make_schema("problem_solution")

PROBLEM_SOLUTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PREAMBLE),
    ("human", _PROBLEM_SOLUTION_HUMAN),
])

# ---------------------------------------------------------------------------
# 3. Trust Story Template
# ---------------------------------------------------------------------------

_TRUST_STORY_HUMAN = """\
Brand: {brand}
Audience: {icp}
Tone: {tone}
Topic: {description}

Brand voice reference (past posts):
{context}

Strategy: Trust Story — Slide 1: introduce the customer persona. Slide 2: their struggle. Slide 3: the result / win. CTA: invite readers to get similar results.

""" + _make_schema("trust_story")

TRUST_STORY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PREAMBLE),
    ("human", _TRUST_STORY_HUMAN),
])

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TEMPLATE_REGISTRY = {
    "educational": EDUCATIONAL_PROMPT,
    "problem_solution": PROBLEM_SOLUTION_PROMPT,
    "trust_story": TRUST_STORY_PROMPT,
}
