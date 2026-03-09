"""
LangChain Prompt Templates for ContentAgent (StoryWeaver)

IMPORTANT — Brace escaping rules:
  {{ / }}  → literal { / } in the final rendered prompt (LangChain escaping)
  {var}    → LangChain input variable
  TMPL_TYPE → plain string-replaced before ChatPromptTemplate is built
"""

from langchain_core.prompts import ChatPromptTemplate

# ---------------------------------------------------------------------------
# System preamble — marketing-focused identity
# ---------------------------------------------------------------------------
_SYSTEM_PREAMBLE = (
    "You are StoryWeaver, a world-class social-media MARKETING content strategist. "
    "Your sole mission is to create content that drives engagement, conversions, and brand awareness. "
    "Every piece of content you produce MUST be designed for marketing impact — attracting attention, "
    "building trust, and compelling the audience to take action.\n\n"
    "BRAND IDENTITY ANALYSIS:\n"
    "You will be given the company's website URL. Before generating any content, mentally analyze:\n"
    "- The company's color palette and dominant brand colors\n"
    "- Their logo style (minimalist, illustrative, wordmark, etc.)\n"
    "- Their typography style (modern, classic, playful, corporate)\n"
    "- Their overall brand aesthetic (premium, playful, bold, clean, tech-forward, etc.)\n"
    "- Their value proposition and brand voice from the website copy\n"
    "ALL visual descriptions (image prompts, video prompts) MUST reflect "
    "the company's actual brand colors, logo style, and visual identity.\n\n"
    "PAST-POST PERFORMANCE ANALYSIS:\n"
    "You will receive the brand's past social media posts as context. Analyze them to identify:\n"
    "- Which content patterns, hooks, and formats appear most engaging\n"
    "- What tone and style resonates best with the audience\n"
    "- Common themes in their high-performing content\n"
    "Use these performance insights to guide your new content — replicate what works, "
    "improve what doesn't, and bring fresh angles to proven formats.\n\n"
    "You ALWAYS reply with ONLY a valid JSON object — no markdown, no explanation, "
    "no extra text before or after the JSON. "
    "Follow the schema exactly."
)

# ---------------------------------------------------------------------------
# JSON schemas — with marketing-focused field descriptions
# ---------------------------------------------------------------------------
_SCHEMA_BASE = """\
Return ONLY this JSON (no other text):
{{
  "template_type": "TMPL_TYPE",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
"""

_SCHEMA_CANONICAL = """\
  "canonical_post": "150-200 word {tone} MARKETING post — must include a strong hook in the first line, deliver clear value, and end with a compelling CTA that drives engagement or conversion",
  "visual_direction": "detailed photorealistic image description for this post — MUST incorporate the brand's color palette, logo style, and visual identity from their website. Describe specific colors (e.g. 'brand blue #2563EB'), include brand logo placement, and match the company's overall aesthetic. The image must look like an official branded marketing asset, not a generic stock photo",
"""

_SCHEMA_CAROUSEL = """\
  "carousel": {{
    "title": "carousel series title — compelling marketing headline",
    "slides": [
      {{"slide_number": 1, "title": "Hook (Attention Grabber) - large bold text, e.g. '5 Marketing Mistakes...'", "body": "Minimal words. This slide decides if people will swipe.", "image_prompt": "photorealistic branded image with strong visual or icon — use the company's exact color palette, logo, and visual style from their website. Describe specific brand colors."}},
      {{"slide_number": 2, "title": "The Problem - show you understand their pain point", "body": "Explain the problem + add one supporting line. Purpose: Make audience feel 'This is exactly my problem.'", "image_prompt": "branded image consistent with slide 1 — same color scheme, logo placement, and brand aesthetic"}},
      {{"slide_number": 3, "title": "Key Insight - explain why the problem happens", "body": "Deliver a key insight and highlight a key phrase (e.g. 'Customers don\\'t buy products — they buy solutions.')", "image_prompt": "branded image maintaining visual consistency — company colors, logo, and style"}},
      {{"slide_number": 4, "title": "Provide Value (Tips / Framework) - actionable advice", "body": "Give actionable advice (e.g. 3 bullet points). This is where the educational value is.", "image_prompt": "branded image with company's visual identity — colors, logo, and aesthetic"}},
      {{"slide_number": 5, "title": "Powerful Takeaway - memorable statement", "body": "Deliver a memorable statement or mini framework. This slide often gets saved and shared.", "image_prompt": "branded image leading into the CTA — company colors and logo prominently featured"}}
    ],
    "cta_slide": {{"title": "CTA (Call To Action) - e.g. 'Follow us...', 'Comment X...'", "body": "Tell readers exactly what to do next. Provide clear instructions.", "image_prompt": "bold branded CTA image — company's primary brand color as background, logo prominently displayed, action-oriented design"}}
  }},
"""

_SCHEMA_VIDEO = """\
  "video_script": {{
    "hook": "opening line that stops the scroll (first 3 seconds) — must create curiosity or urgency",
    "body": "main script (3-4 sentences) delivering marketing value — showcase the product/service benefits",
    "cta": "closing call-to-action driving immediate response (visit, sign up, buy, DM, etc.)",
    "caption": "caption with strategic hashtags for discoverability and reach",
    "video_prompt": "detailed prompt for text-to-video generation — MUST describe scenes using the brand's actual color palette, logo overlays, and visual style from their website. Include specific brand colors, logo placement, and the overall brand aesthetic. The video should look like a professional branded marketing reel, not generic content"
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


# ---------------------------------------------------------------------------
# Strategy-specific human prompt bases — with website & performance analysis
# ---------------------------------------------------------------------------
_EDUCATIONAL_HUMAN_BASE = """\
Brand: {brand}
Website: {website_url}
Audience: {icp}
Tone: {tone}
Topic: {description}

BRAND IDENTITY (analyze from the website above):
Before generating content, analyze the website at {website_url} to identify:
- The exact brand color palette (primary, secondary, accent colors)
- Logo style and how it should be incorporated in visuals
- Overall brand aesthetic and design language
- Key messaging and value propositions

PAST PERFORMANCE ANALYSIS (learn from these posts):
{context}

INSTRUCTIONS FOR PAST POSTS:
- Study the posts above carefully — identify patterns in the ones that would get the most engagement
- Note which hooks, formats, and topics resonate with {icp}
- Use these insights to create content that builds on proven successes
- Bring fresh angles while maintaining what works

MARKETING OBJECTIVE: Every piece of content must be designed to drive engagement, build brand authority, and convert followers into customers/leads.

Strategy: Educational — lead with a surprising insight, give 3 actionable tips, end with a transformation + CTA that drives the audience to take a specific action (visit website, DM, sign up, etc.).

"""

_PROBLEM_SOLUTION_HUMAN_BASE = """\
Brand: {brand}
Website: {website_url}
Audience: {icp}
Tone: {tone}
Topic: {description}

BRAND IDENTITY (analyze from the website above):
Before generating content, analyze the website at {website_url} to identify:
- The exact brand color palette (primary, secondary, accent colors)
- Logo style and how it should be incorporated in visuals
- Overall brand aesthetic and design language
- Key messaging and value propositions

PAST PERFORMANCE ANALYSIS (learn from these posts):
{context}

INSTRUCTIONS FOR PAST POSTS:
- Study the posts above carefully — identify patterns in the ones that would get the most engagement
- Note which hooks, formats, and topics resonate with {icp}
- Use these insights to create content that builds on proven successes
- Bring fresh angles while maintaining what works

MARKETING OBJECTIVE: Every piece of content must be designed to drive engagement, build brand authority, and convert followers into customers/leads.

Strategy: Problem-Solution — agitate a real pain point the audience faces, show the consequences of ignoring it, present the brand's solution as the answer, and end with a clear next step (visit, buy, book a call, etc.).

"""

_TRUST_STORY_HUMAN_BASE = """\
Brand: {brand}
Website: {website_url}
Audience: {icp}
Tone: {tone}
Topic: {description}

BRAND IDENTITY (analyze from the website above):
Before generating content, analyze the website at {website_url} to identify:
- The exact brand color palette (primary, secondary, accent colors)
- Logo style and how it should be incorporated in visuals
- Overall brand aesthetic and design language
- Key messaging and value propositions

PAST PERFORMANCE ANALYSIS (learn from these posts):
{context}

INSTRUCTIONS FOR PAST POSTS:
- Study the posts above carefully — identify patterns in the ones that would get the most engagement
- Note which hooks, formats, and topics resonate with {icp}
- Use these insights to create content that builds on proven successes
- Bring fresh angles while maintaining what works

MARKETING OBJECTIVE: Every piece of content must be designed to drive engagement, build brand authority, and convert followers into customers/leads.

Strategy: Trust Story — introduce a relatable customer persona, describe their struggle, reveal the result/win using the brand's product or service. End with a CTA inviting readers to get similar results (link, DM, free trial, etc.).

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


# ---------------------------------------------------------------------------
# Monthly (7-day calendar) templates — with branding & performance analysis
# ---------------------------------------------------------------------------
_MONTHLY_SYSTEM = (
    "You are StoryWeaver, a world-class social-media MARKETING content strategist. "
    "You are generating a WEEKLY content calendar optimized for maximum marketing impact. "
    "Each day MUST have UNIQUE, FRESH content — never repeat ideas, angles, or hooks. "
    "Vary the tone subtly across days while staying on-brand. "
    "Every piece of content must be designed to drive engagement, conversions, and brand awareness.\n\n"
    "BRAND IDENTITY: Analyze the company's website to understand their color palette, logo, "
    "typography, and overall visual identity. ALL visual prompts must reflect the brand's actual colors and style.\n\n"
    "PAST-POST ANALYSIS: Study the provided past posts to identify what content patterns, "
    "hooks, and formats drive the most engagement. Use these insights to create higher-performing content.\n\n"
    "You ALWAYS reply with ONLY a valid JSON object — no markdown, no explanation."
)

_MONTHLY_HUMAN_BASE = """\
Brand: {brand}
Website: {website_url}
Audience: {icp}
Tone: {tone}
Campaign Topic: {description}

BRAND IDENTITY (analyze from the website above):
Before generating content, analyze the website at {website_url} to identify the brand's exact color palette, logo style, visual aesthetic, and key messaging. ALL image and video prompts must use the brand's actual colors and incorporate their logo.

PAST PERFORMANCE REFERENCE (learn from these posts):
{context}

Analyze the past posts above — identify which content styles, hooks, and formats are most engaging. Use these patterns to inform your content calendar while bringing fresh, unique angles.

MARKETING FOCUS: Every post, image, and video must be explicitly designed for marketing purposes — driving engagement, building brand authority, generating leads, or converting followers. Include clear CTAs in every piece.

Generate content for Days {day_start} to {day_end} of a 7-day weekly calendar.
Each day gets a DIFFERENT content piece. The content type for each day is assigned below.

{day_assignments}

IMPORTANT:
- Every day must have completely unique content — different angles, hooks, and ideas.
- Match the assigned content_type for each day exactly.
- Keep the brand voice consistent but vary the approach.
- ALL visual prompts (image_prompt, visual_direction, video_prompt) must describe the brand's actual colors, logo, and visual style.
- Every post must include a marketing CTA.

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
            f'"canonical_post": "150-200 word marketing post with hook + value + CTA", '
            f'"visual_direction": "photorealistic BRANDED image — use the company\'s exact colors, logo, and visual style from their website", '
            f'"tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]}}'
        )
    elif content_type == "carousel":
        return (
            f'    {{"day": {day}, "content_type": "carousel", '
            f'"carousel": {{"title": "...", "slides": ['
            f'{{"slide_number": 1, "title": "Hook (Attention Grabber)", "body": "Minimal words deciding if people swipe", "image_prompt": "branded image with strong visual/icon, company colors and logo"}}, '
            f'{{"slide_number": 2, "title": "The Problem", "body": "Show you understand their pain point", "image_prompt": "branded image consistent with slide 1"}}, '
            f'{{"slide_number": 3, "title": "Key Insight", "body": "Explain why problem happens + key phrase", "image_prompt": "branded image maintaining visual consistency"}}, '
            f'{{"slide_number": 4, "title": "Provide Value", "body": "Actionable advice (e.g. 3 bullet points)", "image_prompt": "branded image with company identity"}}, '
            f'{{"slide_number": 5, "title": "Powerful Takeaway", "body": "Memorable statement/mini framework", "image_prompt": "branded image leading to CTA"}}'
            f'], "cta_slide": {{"title": "CTA (Call To Action)", "body": "Tell readers what to do next", "image_prompt": "bold branded CTA with company logo prominently displayed"}}}}, '
            f'"tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]}}'
        )
    elif content_type == "video_script":
        return (
            f'    {{"day": {day}, "content_type": "video_script", '
            f'"video_script": {{"hook": "scroll-stopping opener", "body": "marketing value delivery", "cta": "action-driving close", '
            f'"caption": "caption with strategic hashtags", "video_prompt": "branded video using company colors, logo overlay, and brand aesthetic"}}, '
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
    if template_type == "educational":
        strategy = "Educational – lead with surprising insights, deliver actionable tips, end with transformation + marketing CTA."
    elif template_type == "problem_solution":
        strategy = "Problem-Solution – agitate the pain, show consequences, present the brand's solution, drive a specific action."
    elif template_type == "trust_story":
        strategy = "Trust Story – relatable customer persona, their struggle, the result/win, CTA inviting similar results."
    else:
        strategy = "Educational."

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
