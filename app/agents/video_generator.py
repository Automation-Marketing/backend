"""
VideoGenerator — Gemini Veo 3.1 Video Generation Agent

Uses the google-genai SDK to generate short-form videos (9:16 reels)
from video prompts produced by the ContentAgent. Saves videos to
data/media/generated/ and returns static URL paths for the frontend.
"""

import os
import time
import uuid
from pathlib import Path

from google import genai

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
VIDEO_MODEL = "veo-3.1-generate-preview"
GENERATED_DIR = Path("data/media/generated")

# Polling config
POLL_INTERVAL_SECONDS = 10
MAX_POLL_ATTEMPTS = 20  # ~3 minutes max wait


class VideoGenerator:
    """Generates short-form videos from text prompts using Gemini Veo 3.1."""

    def __init__(self):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    def generate_video(self, prompt: str, filename: str | None = None, company_name: str = "", website_url: str = "", visual_identity: str = "") -> str | None:
        """
        Generate a video from a text prompt.

        Args:
            prompt: The video description / scene prompt.
            filename: Optional filename (without extension). Auto-generated if None.
            company_name: Name of the company for branding context.
            website_url: Website URL for branding context.
            visual_identity: Comprehensive summary of the brand's visual identity.

        Returns:
            Static URL path (e.g. /static/generated/abc123.mp4) or None on failure.
        """
        if not prompt or not prompt.strip():
            print("[VideoGenerator] Empty prompt, skipping.")
            return None

        if not filename:
            filename = uuid.uuid4().hex[:12]

        try:
            print(f"[VideoGenerator] Generating video for: {prompt[:80]}...")

            enhanced_prompt = prompt
            if company_name:
                website_ctx = f" (website: {website_url})" if website_url else ""
                enhanced_prompt = f"Brand Identity Instructions:\nYou are generating an official marketing video for the brand '{company_name}'{website_ctx}. Please incorporate their exact visual identity, brand colors, typography, logos, and aesthetic style into the video.\n\nTask: {enhanced_prompt}"
            if visual_identity and visual_identity != "No specific visual identity analyzed.":
                enhanced_prompt += f"\n\n--- STRICT VISUAL BRAND GUIDELINES FROM PAST POSTS ---\n{visual_identity}\n-----------------------------------------------------------"

            operation = self.client.models.generate_videos(
                model=VIDEO_MODEL,
                prompt=enhanced_prompt,
                config={
                    "aspect_ratio": "9:16",
                    "person_generation": "allow_all",
                },
            )

            # Poll until the video generation is complete
            attempts = 0
            while not operation.done:
                attempts += 1
                if attempts > MAX_POLL_ATTEMPTS:
                    print("[VideoGenerator] Timed out waiting for video generation.")
                    return None
                print(f"[VideoGenerator] Waiting for video generation... (attempt {attempts})")
                time.sleep(POLL_INTERVAL_SECONDS)
                operation = self.client.operations.get(operation)

            # Download the generated video
            generated_video = operation.response.generated_videos[0]
            self.client.files.download(file=generated_video.video)

            output_path = GENERATED_DIR / f"{filename}.mp4"
            generated_video.video.save(str(output_path))

            static_url = f"/static/generated/{filename}.mp4"
            print(f"[VideoGenerator] Video saved: {static_url}")
            return static_url

        except Exception as e:
            print(f"[VideoGenerator] Video generation failed: {e}")
            return None

    def generate_for_days(self, days: list[dict], campaign_id: int, company_name: str = "", website_url: str = "", visual_identity: str = "") -> list[dict]:
        """
        Generate videos for all video_script days in a content calendar.

        Args:
            days: List of day dicts from the content calendar.
            campaign_id: Campaign ID for filename uniqueness.
            company_name: Name of the company for branding context.
            website_url: Website URL for branding context.
            visual_identity: Text analysis of the brand's visual style.

        Returns:
            Updated list of day dicts with video_url populated.
        """
        for day in days:
            content_type = day.get("content_type", "")

            if content_type == "video_script":
                video_script = day.get("video_script", {})
                video_prompt = video_script.get("video_prompt", "") if isinstance(video_script, dict) else ""

                if video_prompt:
                    filename = f"campaign_{campaign_id}_day_{day.get('day', 0)}"
                    video_url = self.generate_video(video_prompt, filename, company_name, website_url, visual_identity)
                    if video_url:
                        day["video_url"] = video_url
                        print(f"[VideoGenerator] Day {day.get('day')}: {video_url}")
                    else:
                        print(f"[VideoGenerator] Day {day.get('day')}: Video generation failed, continuing.")
                else:
                    print(f"[VideoGenerator] Day {day.get('day')}: No video_prompt found in video_script.")

        return days
