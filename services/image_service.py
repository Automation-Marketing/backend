import os
import requests
import uuid
import time
from pathlib import Path

HUGGINGFACEHUB_API_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")
# Using SD-XL as it's guaranteed to be supported by the free Inference API
MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
# Standard Inference API endpoint (should still work for supported models)
API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"
# Use router as fallback if the above fails with 410
ROUTER_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_ID}"

class ImageService:
    def __init__(self):
        if not HUGGINGFACEHUB_API_TOKEN:
            print("[ImageService] WARNING: HUGGINGFACEHUB_API_TOKEN not found in environment.")
        
        # Ensure static/generated_images exists
        self.output_dir = Path("static/generated_images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.headers = {"Authorization": f"Bearer {HUGGINGFACEHUB_API_TOKEN}"}

    def generate_image(self, prompt: str) -> str:
        """
        Generates an image via HF Inference API and saves it to static folder.
        Returns the path relative to the backend root.
        """
        if not HUGGINGFACEHUB_API_TOKEN:
            print("[ImageService] Skipping generation: API token missing.")
            return ""

        payload = {
            "inputs": prompt,
            "options": {"wait_for_model": True}
        }

        print(f"[ImageService] Requesting image for prompt: {prompt[:50]}...")
        
        try:
            # Try the standard endpoint first
            response = requests.post(API_URL, headers=self.headers, json=payload, timeout=60)
            
            # If 410 (Gone), try the router endpoint
            if response.status_code == 410:
                print("[ImageService] 410 Gone, trying router endpoint...")
                response = requests.post(ROUTER_URL, headers=self.headers, json=payload, timeout=60)

            if response.status_code != 200:
                print(f"[ImageService] API Error ({response.status_code}): {response.text}")
                return ""

            # The response content is the image bytes
            filename = f"img_{uuid.uuid4().hex[:8]}.png"
            filepath = self.output_dir / filename
            
            with open(filepath, "wb") as f:
                f.write(response.content)
            
            print(f"[ImageService] Image saved to {filepath}")
            
            # Return URL path
            return f"/static/generated_images/{filename}"

        except Exception as e:
            print(f"[ImageService] Exception during generation: {e}")
            return ""

image_service = ImageService()
