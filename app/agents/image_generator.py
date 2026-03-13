"""
ImageGenerator — Gemini Native Image Generation Agent

Uses the google-genai SDK to generate images from visual descriptions
produced by the ContentAgent. Saves images to data/media/generated/
and returns static URL paths for the frontend.
"""

import os
import uuid
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
IMAGE_MODEL = "gemini-2.5-flash-image"
GENERATED_DIR = Path("data/media/generated")


class ImageGenerator:
    """Generates images from text prompts using Gemini's native image generation."""

    def __init__(self):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    def generate_image(
        self,
        prompt: str,
        filename: str | None = None,
        company_name: str = "",
        website_url: str = "",
        visual_identity: str = "",
        logo_path: str | None = None,
        post_text: str = "",
    ) -> str | None:
        """
        Generate a marketing-ad style image from a visual description + campaign text.

        Args:
            prompt: The visual scene description (visual_direction).
            filename: Optional filename (without extension). Auto-generated if None.
            company_name: Name of the company for branding context.
            website_url: Website URL for branding context.
            visual_identity: Comprehensive summary of the brand's visual identity.
            logo_path: Absolute or relative path to the brand logo image file.
            post_text: The full caption/post text for this day — used to extract
                       campaign highlights (offers, discounts, features, CTAs) that
                       will be rendered as overlaid text in the marketing image.

        Returns:
            Static URL path (e.g. /static/generated/abc123.png) or None on failure.
        """
        if not prompt or not prompt.strip():
            print("[ImageGenerator] Empty prompt, skipping.")
            return None

        if not filename:
            filename = uuid.uuid4().hex[:12]

        try:
            print(f"[ImageGenerator] Generating image for: {prompt[:80]}...")

            # ── Build the marketing-ad image prompt ──────────────────────────
            logo_instruction = ""
            if logo_path and Path(logo_path).exists():
                logo_instruction = (
                    "The EXACT brand logo is provided as a reference image. "
                    "Replicate it faithfully (same shape, colors, text, style) and place it prominently "
                    "in the TOP-LEFT corner of the image — do NOT alter or invent the logo."
                )
            else:
                logo_instruction = (
                    f"Place the '{company_name}' brand logo (use the brand's actual logo style) "
                    "prominently in the top-left corner."
                )

            campaign_highlights = ""
            if post_text and post_text.strip():
                campaign_highlights = (
                    f"\n\nCAMPAIGN MESSAGE TO EMBED IN THE IMAGE:\n"
                    f"\"\"\"{post_text.strip()[:600]}\"\"\""
                    f"\n\nExtract the key marketing highlights from the campaign message above "
                    f"(e.g. headline/hook, offer percentages, key benefits, features, CTA phrase) "
                    f"and render them as OVERLAID TEXT on the image using these rules:\n"
                    f"  • TOP SECTION: Large bold headline (the hook or main offer, e.g. '20% OFF Summer Membership')\n"
                    f"  • MIDDLE SECTION: 2-4 key benefit/offer callouts in styled pill or card boxes "
                    f"    (e.g. 'Large book collection', 'Doorstep delivery', '10% OFF 6-month plan')\n"
                    f"  • BOTTOM SECTION: Bold CTA button or banner (e.g. 'Start Reading Today', 'Enroll Now')\n"
                    f"Use clean, modern typography. Text must be clearly legible — high contrast against the background."
                )

            website_ctx = f" (website: {website_url})" if website_url else ""
            visual_identity_block = ""
            if visual_identity and visual_identity != "No specific visual identity analyzed.":
                visual_identity_block = (
                    f"\n\n--- BRAND VISUAL GUIDELINES ---\n{visual_identity}\n-------------------------------"
                )

            enhanced_prompt = (
                f"You are generating a PROFESSIONAL MARKETING ADVERTISEMENT image for the brand '{company_name}'{website_ctx}.\n"
                f"This image will be posted on social media (Instagram / LinkedIn) as a marketing campaign asset.\n\n"
                f"=== LOGO ===\n{logo_instruction}\n\n"
                f"=== VISUAL SCENE ===\n"
                f"Background / photorealistic scene: {prompt}\n"
                f"The scene should occupy the full image and serve as the backdrop for the marketing text overlays.\n"
                f"{campaign_highlights}"
                f"{visual_identity_block}\n\n"
                f"=== FINAL IMAGE REQUIREMENTS ===\n"
                f"• Square 1:1 format, social-media ready\n"
                f"• Professional, polished marketing layout — similar to a premium brand advertisement\n"
                f"• Text overlays must be bold, clean, and highly readable\n"
                f"• Use the brand's color palette for text, boxes, and CTA button backgrounds\n"
                f"• The overall feel must be: eye-catching, conversion-focused, brand-consistent\n"
                f"• Do NOT make it look like a generic stock photo — it must look like an official branded marketing ad"
            )

            # Build contents — include logo image part if available
            contents: list = []
            if logo_path and Path(logo_path).exists():
                try:
                    import io as _io
                    logo_bytes = Path(logo_path).read_bytes()
                    # Detect mime type from extension
                    ext = Path(logo_path).suffix.lower()
                    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
                    logo_mime = mime_map.get(ext, "image/jpeg")
                    contents.append(
                        types.Part.from_bytes(data=logo_bytes, mime_type=logo_mime)
                    )
                    print(f"[ImageGenerator] Logo attached from: {logo_path}")
                except Exception as logo_err:
                    print(f"[ImageGenerator] Could not load logo (non-fatal): {logo_err}")
            contents.append(enhanced_prompt)

            response = self.client.models.generate_content(
                model=IMAGE_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="1:1",
                    ),
                ),
            )

            # Extract image from response parts
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        import io
                        image_bytes = part.inline_data.data
                        image = Image.open(io.BytesIO(image_bytes))

                        output_path = GENERATED_DIR / f"{filename}.png"
                        image.save(str(output_path), "PNG")

                        static_url = f"/static/generated/{filename}.png"
                        print(f"[ImageGenerator] Image saved: {static_url}")
                        return static_url

            print("[ImageGenerator] No image data in response.")
            return None

        except Exception as e:
            print(f"[ImageGenerator] Image generation failed: {e}")
            return None

    def generate_for_days(self, days: list[dict], campaign_id: int, company_name: str = "", website_url: str = "", visual_identity: str = "", logo_path: str | None = None) -> list[dict]:
        """
        Generate images for all canonical post days in a content calendar.

        Args:
            days: List of day dicts from the content calendar.
            campaign_id: Campaign ID for filename uniqueness.
            company_name: Name of the company for branding context.
            website_url: Website URL for branding context.
            visual_identity: Text analysis of the brand's visual style.
            logo_path: Path to the brand logo image to embed in generated images.

        Returns:
            Updated list of day dicts with image_url populated.
        """
        for day in days:
            content_type = day.get("content_type", "")

            if content_type in ("canonical_post", "image"):
                visual_desc = day.get("visual_direction") or day.get("visual_description", "")
                # Extract the campaign caption to embed marketing highlights in the image
                post_text = day.get("canonical_post", "")
                if visual_desc:
                    filename = f"campaign_{campaign_id}_day_{day.get('day', 0)}"
                    image_url = self.generate_image(
                        visual_desc, filename, company_name, website_url, visual_identity,
                        logo_path=logo_path, post_text=post_text
                    )
                    if image_url:
                        day["image_url"] = image_url
                        print(f"[ImageGenerator] Day {day.get('day')}: {image_url}")
                    else:
                        print(f"[ImageGenerator] Day {day.get('day')}: Image generation failed, continuing.")
                else:
                    print(f"[ImageGenerator] Day {day.get('day')}: No visual description found.")
            elif content_type == "carousel":
                carousel_data = day.get("carousel", {})
                carousel_title = carousel_data.get("title", "")

                # Generate for normal slides
                slides = carousel_data.get("slides", [])
                for idx, slide in enumerate(slides):
                    visual_desc = slide.get("image_prompt", "")
                    if visual_desc:
                        # Build post_text from carousel title + this slide's title and body
                        slide_title = slide.get("title", "")
                        slide_body = slide.get("body", "")
                        slide_post_text = "\n".join(filter(None, [
                            carousel_title,
                            slide_title,
                            slide_body,
                        ]))
                        filename = f"campaign_{campaign_id}_day_{day.get('day', 0)}_slide_{idx+1}"
                        image_url = self.generate_image(
                            visual_desc, filename, company_name, website_url, visual_identity,
                            logo_path=logo_path, post_text=slide_post_text
                        )
                        if image_url:
                            slide["image_url"] = image_url
                            print(f"[ImageGenerator] Day {day.get('day')} Slide {idx+1}: {image_url}")
                        else:
                            print(f"[ImageGenerator] Day {day.get('day')} Slide {idx+1}: Image generation failed.")

                # Generate for CTA slide
                cta_slide = carousel_data.get("cta_slide", {})
                if cta_slide:
                    visual_desc = cta_slide.get("image_prompt", "")
                    if visual_desc:
                        # CTA slide gets its own title + body + overall carousel title
                        cta_title = cta_slide.get("title", "")
                        cta_body = cta_slide.get("body", "")
                        cta_post_text = "\n".join(filter(None, [
                            carousel_title,
                            cta_title,
                            cta_body,
                        ]))
                        filename = f"campaign_{campaign_id}_day_{day.get('day', 0)}_slide_cta"
                        image_url = self.generate_image(
                            visual_desc, filename, company_name, website_url, visual_identity,
                            logo_path=logo_path, post_text=cta_post_text
                        )
                        if image_url:
                            cta_slide["image_url"] = image_url
                            print(f"[ImageGenerator] Day {day.get('day')} CTA Slide: {image_url}")
                        else:
                            print(f"[ImageGenerator] Day {day.get('day')} CTA Slide: Image generation failed.")

        return days
