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

    def generate_image(self, prompt: str, filename: str | None = None) -> str | None:
        """
        Generate an image from a text prompt.

        Args:
            prompt: The visual description to generate an image for.
            filename: Optional filename (without extension). Auto-generated if None.

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

            response = self.client.models.generate_content(
                model=IMAGE_MODEL,
                contents=f"Generate a high-quality, photorealistic social media image: {prompt}",
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
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

    def generate_for_days(self, days: list[dict], campaign_id: int) -> list[dict]:
        """
        Generate images for all canonical post days in a content calendar.

        Args:
            days: List of day dicts from the content calendar.
            campaign_id: Campaign ID for filename uniqueness.

        Returns:
            Updated list of day dicts with image_url populated.
        """
        for day in days:
            content_type = day.get("content_type", "")

            if content_type in ("canonical_post", "image"):
                visual_desc = day.get("visual_direction") or day.get("visual_description", "")
                if visual_desc:
                    filename = f"campaign_{campaign_id}_day_{day.get('day', 0)}"
                    image_url = self.generate_image(visual_desc, filename)
                    if image_url:
                        day["image_url"] = image_url
                        print(f"[ImageGenerator] Day {day.get('day')}: {image_url}")
                    else:
                        print(f"[ImageGenerator] Day {day.get('day')}: Image generation failed, continuing.")
                else:
                    print(f"[ImageGenerator] Day {day.get('day')}: No visual description found.")

        return days
