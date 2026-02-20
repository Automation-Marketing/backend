import os
import requests
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

class TelegramAgent:
    """Agent for publishing generated content to Telegram."""

    def __init__(self):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("WARNING: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set in .env")

    def _ensure_api_ready(self):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")

    def send_message(self, text: str) -> dict:
        """Sends a standard text message."""
        self._ensure_api_ready()
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        res = requests.post(f"{API_URL}/sendMessage", json=payload)
        res.raise_for_status()
        return res.json()

    def send_photo(self, photo_path: str, caption: str = "") -> dict:
        """Sends a single photo with an optional caption."""
        self._ensure_api_ready()
        
        if photo_path.startswith("http") and "localhost" not in photo_path:
            # Fallback for public URLs (not used in our current setup)
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "photo": photo_path,
                "caption": caption,
                "parse_mode": "HTML"
            }
            res = requests.post(f"{API_URL}/sendPhoto", json=payload)
        else:
            # Upload local file
            with open(photo_path, 'rb') as f:
                payload = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": caption,
                    "parse_mode": "HTML"
                }
                res = requests.post(f"{API_URL}/sendPhoto", data=payload, files={"photo": f})
                
        res.raise_for_status()
        return res.json()

    def send_media_group(self, media_paths: List[str], caption: str = "") -> dict:
        """Sends multiple photos as an album/carousel."""
        self._ensure_api_ready()
        
        if not media_paths:
            raise ValueError("Must provide at least one image path for media group.")

        import json
        media = []
        files = {}
        open_files = []
        
        try:
            for i, path in enumerate(media_paths):
                file_name = f"file{i}"
                
                # Check if it's a valid local path
                if not path.startswith("http"):
                    f = open(path, 'rb')
                    open_files.append(f)
                    files[file_name] = f
                    media_val = f"attach://{file_name}"
                else:
                    media_val = path

                item = {
                    "type": "photo",
                    "media": media_val,
                }
                if i == 0 and caption:
                    item["caption"] = caption
                    item["parse_mode"] = "HTML"
                media.append(item)

            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "media": json.dumps(media)
            }
            
            if files:
                res = requests.post(f"{API_URL}/sendMediaGroup", data=payload, files=files)
            else:
                res = requests.post(f"{API_URL}/sendMediaGroup", json=payload)
                
            res.raise_for_status()
            return res.json()
            
        finally:
            for f in open_files:
                f.close()
