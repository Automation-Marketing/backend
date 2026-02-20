from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
from agents.telegram_agent import TelegramAgent

router = APIRouter()
telegram_agent = TelegramAgent()

class PublishRequest(BaseModel):
    content_type: str  # "canonical", "carousel", or "video_script"
    data: Dict[str, Any]
    # The frontend needs to pass absolute URLs (e.g. http://localhost:8000/static/...)
    # for the bot to fetch them, since telegram's API requires valid HTTP URLs or file uploads.
    # To keep it simple, we expect the frontend to provide full URLs if it wants images attached.

def _to_local_path(url: str) -> str:
    if not url: return url
    # Convert http://localhost:8000/static/abc.jpg -> static/abc.jpg
    if "/static/" in url:
        return "static/" + url.split("/static/")[-1]
    return url

@router.post("/publish/telegram")
def publish_to_telegram(req: PublishRequest):
    """Publish generated AI content to Telegram."""
    try:
        content_type = req.content_type
        data = req.data
        
        if content_type == "canonical":
            text = data.get("canonical_post", "No text provided.")
            image_url = _to_local_path(data.get("image_url"))
            tags = data.get("tags", [])
            tag_str = " ".join([f"#{tag}" for tag in tags])
            full_caption = f"{text}\n\n{tag_str}" if tags else text
            
            if image_url:
                result = telegram_agent.send_photo(photo_path=image_url, caption=full_caption)
            else:
                result = telegram_agent.send_message(text=full_caption)
                
        elif content_type == "carousel":
            carousel = data.get("carousel", {})
            title = carousel.get("title", "Carousel")
            slides = carousel.get("slides", [])
            cta = carousel.get("cta_slide", {})
            
            image_urls = []
            caption_parts = [f"<b>{title}</b>\n"]
            
            # Extract slide images and texts
            for slide in slides:
                caption_parts.append(f"• {slide.get('title', '')}")
                if "image_url" in slide and slide["image_url"]:
                    image_urls.append(_to_local_path(slide["image_url"]))
            if "image_url" in cta and cta["image_url"]:
                image_urls.append(_to_local_path(cta["image_url"]))
                
            caption = "\n".join(caption_parts)
            if cta:
                caption += f"\n\n👉 {cta.get('title', '')}: {cta.get('body', '')}"

            if image_urls:
                result = telegram_agent.send_media_group(media_urls=image_urls, caption=caption)
            else:
                result = telegram_agent.send_message(text=caption)
                
        elif content_type == "video_script":
            script = data.get("video_script", {})
            text = f"🎬 <b>Video Script</b>\n\n<b>Hook:</b> {script.get('hook', '')}\n\n<b>Body:</b> {script.get('body', '')}\n\n<b>CTA:</b> {script.get('cta', '')}\n\n<b>Caption:</b> {script.get('caption', '')}"
            result = telegram_agent.send_message(text=text)
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported content type for publishing: {content_type}")
            
        return {
            "success": True,
            "telegram_response": result
        }

    except Exception as e:
        print(f"[Telegram Publisher] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
