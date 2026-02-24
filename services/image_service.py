"""
Image Service — Gemini 2.5 Flash Image Generation
Uses Google's Gemini API for text-to-image generation.
"""

import os
import uuid
from pathlib import Path
from google import genai
from google.genai import types

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


class ImageService:
    def __init__(self):
        if not GOOGLE_API_KEY:
            print("[ImageService] WARNING: GOOGLE_API_KEY not found in environment.")

        self.output_dir = Path("static/generated_images")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

    def generate_image(self, prompt: str) -> str:
        """
        Generates an image via Gemini 2.5 Flash Image API and saves it to static folder.
        Returns the path relative to the backend root.
        """
        if not self.client:
            print("[ImageService] Skipping generation: GOOGLE_API_KEY missing.")
            return ""

        print(f"[ImageService] Generating image: {prompt[:60]}...")

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            # Extract image from response parts
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image = part.as_image()

                    filename = f"img_{uuid.uuid4().hex[:8]}.png"
                    filepath = self.output_dir / filename

                    image.save(str(filepath))
                    print(f"[ImageService] Image saved to {filepath}")

                    return f"/static/generated_images/{filename}"

            print("[ImageService] No image in response.")
            return ""

        except Exception as e:
            print(f"[ImageService] Error: {e}")
            return ""


image_service = ImageService()
