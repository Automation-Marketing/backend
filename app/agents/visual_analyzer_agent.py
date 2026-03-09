import os
import httpx
from google import genai
from google.genai import types

class VisualAnalyzerAgent:
    """
    Downloads scraped images from a company's social media and uses Gemini
    to analyze their visual brand identity (colors, logo style, aesthetic).
    """
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"
        
    async def analyze_images(self, company_name: str, image_urls: list[str]) -> str:
        """
        Downloads the images and sends them to Gemini for visual analysis.
        Returns a detailed visual identity guideline string.
        """
        # Filter out empty or duplicate URLs
        unique_urls = list(set([url for url in image_urls if url]))
        
        if not unique_urls:
            return "No visual context available from past posts."
            
        # Limit to top 5 images to keep the payload size manageable and fast
        unique_urls = unique_urls[:5]
        print(f"[VisualAnalyzer] Analyzing {len(unique_urls)} images for {company_name}")
        
        image_parts = []
        async with httpx.AsyncClient() as http_client:
            for url in unique_urls:
                try:
                    response = await http_client.get(url, timeout=10.0)
                    if response.status_code == 200:
                        mime_type = response.headers.get("content-type", "image/jpeg")
                        # Default to image/jpeg if it's some generic binary stream
                        if "image" not in mime_type:
                            mime_type = "image/jpeg"
                            
                        image_parts.append(
                            types.Part.from_bytes(
                                data=response.content,
                                mime_type=mime_type
                            )
                        )
                except Exception as e:
                    print(f"   [VisualAnalyzer] Failed to download image {url}: {e}")
                    
        if not image_parts:
            return "Failed to retrieve any visual context."
            
        prompt = f"""
        You are an expert brand aesthetics analyst and marketing designer.
        Analyze these past marketing images from the brand '{company_name}'.
        
        Identify and describe in extreme detail:
        1. Brand Color Palette: Determine the exact primary and secondary colors being used. Provide hex codes if possible, or highly descriptive color names (e.g. 'Deep Navy Blue', 'Vibrant Coral'). 
        2. Logo Usage: Note if a logo is present, how it is styled, and where it is typically placed.
        3. Typography Style: If there's text in the graphics, what kind of fonts are used (e.g., bold sans-serif, elegant serif, script)?
        4. Overall Visual Aesthetic: Describe the mood, lighting, photography style, and graphics style (e.g., minimalistic, vibrant, dark mode, corporate, playful, highly-produced, authentic/UGC).
        
        Output a detailed 'Visual Brand Identity Guideline'. This will be used by an AI image generator to create NEW on-brand marketing assets, so give actionable, descriptive rules that another AI can follow to perfectly replicate this brand's visual style.
        """
        
        # Pass the text prompt first, then the images
        contents = [prompt] + image_parts
        
        try:
            print(f"[VisualAnalyzer] Sending {len(image_parts)} images to {self.model_name}")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
            )
            print("[VisualAnalyzer] Analysis complete.")
            return response.text
        except Exception as e:
            print(f"[VisualAnalyzer] Failed to analyze images: {e}")
            return "Error analyzing visual context."
