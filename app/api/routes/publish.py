"""
Publishing Routes — Multi-platform social media publishing

Endpoints:
  POST /publish/credentials          — Save/update API credentials for a brand + platform
  GET  /publish/credentials/{bid}    — List connected platforms for a brand
  POST /publish/instagram            — Publish to Instagram (Graph API)
  POST /publish/linkedin             — Publish to LinkedIn (API v2)
  POST /publish/twitter              — Publish to Twitter/X (API v2 via tweepy)
  POST /publish/telegram             — Publish to Telegram (existing)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import requests
import json
import os
import tempfile
import urllib.parse

from app.utils.db_service import get_connection
from app.agents.telegram_agent import TelegramAgent

router = APIRouter()
telegram_agent = TelegramAgent()


# ──────────────────────────────────────────────
# Request Models
# ──────────────────────────────────────────────

class PublishRequest(BaseModel):
    brand_id: int
    content_type: str  # "canonical", "image", "carousel", "video_script"
    data: Dict[str, Any]


class CredentialsSave(BaseModel):
    brand_id: int
    platform: str  # "instagram", "twitter", "linkedin"
    access_token: Optional[str] = None
    access_token_secret: Optional[str] = None  # Twitter only
    api_key: Optional[str] = None              # Twitter only
    api_secret: Optional[str] = None           # Twitter only
    platform_account_id: Optional[str] = None  # IG business ID / LinkedIn URN


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _get_brand_credentials(brand_id: int, platform: str) -> dict:
    """Fetch stored credentials for a brand + platform from DB."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM brand_social_credentials WHERE brand_id = %s AND platform = %s",
            (brand_id, platform),
        )
        row = cur.fetchone()
        if not row:
            return {}
        return dict(row)
    finally:
        cur.close()
        conn.close()


def _format_post_text(data: Dict[str, Any], content_type: str) -> str:
    """Build a single caption string from the content data."""
    if content_type in ("canonical", "canonical_post", "image"):
        text = data.get("canonical_post", "")
        tags = data.get("tags", [])
    elif content_type == "carousel":
        carousel = data.get("carousel", {})
        title = carousel.get("title", "")
        slides = carousel.get("slides", [])
        cta = carousel.get("cta_slide", {})
        parts = [title]
        for s in slides:
            parts.append(f"• {s.get('title', '')}")
        if cta:
            parts.append(f"\n👉 {cta.get('title', '')}: {cta.get('body', '')}")
        text = "\n".join(parts)
        tags = data.get("tags", [])
    elif content_type == "video_script":
        script = data.get("video_script", {})
        text = (
            f"🎬 Video Script\n\n"
            f"Hook: {script.get('hook', '')}\n\n"
            f"Body: {script.get('body', '')}\n\n"
            f"CTA: {script.get('cta', '')}\n\n"
            f"Caption: {script.get('caption', '')}"
        )
        tags = data.get("tags", [])
    else:
        text = str(data)
        tags = []

    if tags:
        tag_str = " ".join([f"#{tag.lstrip('#')}" for tag in tags])
        text += f"\n\n{tag_str}"
    return text


def _to_local_path(url: str) -> str:
    if not url:
        return url
    if "/static/" in url:
        return "data/media/" + url.split("/static/")[-1]
    return url


# ──────────────────────────────────────────────
# Credentials CRUD
# ──────────────────────────────────────────────

@router.post("/publish/credentials")
def save_credentials(data: CredentialsSave):
    """Save or update API credentials for a brand + platform."""
    if data.platform not in ("instagram", "twitter", "linkedin"):
        raise HTTPException(status_code=400, detail="Platform must be 'instagram', 'twitter', or 'linkedin'")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO brand_social_credentials
                (brand_id, platform, access_token, access_token_secret, api_key, api_secret, platform_account_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (brand_id, platform)
            DO UPDATE SET
                access_token = EXCLUDED.access_token,
                access_token_secret = EXCLUDED.access_token_secret,
                api_key = EXCLUDED.api_key,
                api_secret = EXCLUDED.api_secret,
                platform_account_id = EXCLUDED.platform_account_id;
            """,
            (
                data.brand_id, data.platform,
                data.access_token, data.access_token_secret,
                data.api_key, data.api_secret,
                data.platform_account_id,
            ),
        )
        conn.commit()
        return {"success": True, "message": f"{data.platform} credentials saved."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.get("/publish/credentials/{brand_id}")
def get_connected_platforms(brand_id: int):
    """Return which platforms have credentials saved (without exposing tokens)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT platform, platform_account_id, created_at FROM brand_social_credentials WHERE brand_id = %s",
            (brand_id,),
        )
        rows = cur.fetchall()
        platforms = {}
        for row in rows:
            platforms[row["platform"]] = {
                "connected": True,
                "account_id": row["platform_account_id"],
                "connected_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        return {"success": True, "brand_id": brand_id, "platforms": platforms}
    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────
# Instagram Publishing (Graph API)
# ──────────────────────────────────────────────

@router.post("/publish/instagram")
def publish_to_instagram(req: PublishRequest):
    """Publish content to Instagram via the Graph API."""
    creds = _get_brand_credentials(req.brand_id, "instagram")
    if not creds or not creds.get("access_token"):
        raise HTTPException(
            status_code=400,
            detail="No Instagram credentials found for this brand. Please add your Instagram access token and business account ID in settings.",
        )

    access_token = creds["access_token"]
    ig_account_id = creds.get("platform_account_id")
    if not ig_account_id:
        raise HTTPException(status_code=400, detail="Instagram Business Account ID is missing. Please update your credentials.")

    GRAPH_URL = "https://graph.facebook.com/v19.0"
    content_type = req.content_type
    data = req.data
    caption = _format_post_text(data, content_type)

    try:
        if content_type in ("canonical", "canonical_post", "image"):
            image_url = data.get("image_url")
            if image_url and not image_url.startswith("http"):
                public_url = os.getenv("PUBLIC_URL")
                if not public_url:
                    raise HTTPException(status_code=400, detail="PUBLIC_URL environment variable is not set. Instagram cannot download locally hosted images. Please run 'ngrok http 8000', copy the HTTPS URL, and add PUBLIC_URL=https://... to your backend/.env file, then restart the backend.")
                image_url = f"{public_url.rstrip('/')}{image_url}"

            if image_url:
                # Step 1: Create media container
                container_res = requests.post(
                    f"{GRAPH_URL}/{ig_account_id}/media",
                    params={
                        "image_url": image_url,
                        "caption": caption,
                        "access_token": access_token,
                    },
                )
                container_data = container_res.json()
                if "id" not in container_data:
                    raise HTTPException(status_code=500, detail=f"Instagram container creation failed: {container_data}")

                # Step 2: Publish the container
                publish_res = requests.post(
                    f"{GRAPH_URL}/{ig_account_id}/media_publish",
                    params={
                        "creation_id": container_data["id"],
                        "access_token": access_token,
                    },
                )
                result = publish_res.json()
            else:
                raise HTTPException(status_code=400, detail="Instagram requires an image for posting. No image URL found.")

        elif content_type == "carousel":
            carousel = data.get("carousel", {})
            slides = carousel.get("slides", [])
            cta = carousel.get("cta_slide", {})

            # Create child containers for each slide
            child_ids = []
            all_slides = slides + ([cta] if cta and cta.get("image_url") else [])
            for slide in all_slides:
                img_url = slide.get("image_url", "")
                if img_url and not img_url.startswith("http"):
                    public_url = os.getenv("PUBLIC_URL")
                    if not public_url:
                        raise HTTPException(status_code=400, detail="PUBLIC_URL environment variable is not set. Instagram requires a public URL for media. Please set up ngrok and add PUBLIC_URL to your .env file.")
                    img_url = f"{public_url.rstrip('/')}{img_url}"
                if not img_url:
                    continue
                child_res = requests.post(
                    f"{GRAPH_URL}/{ig_account_id}/media",
                    params={
                        "image_url": img_url,
                        "is_carousel_item": "true",
                        "access_token": access_token,
                    },
                )
                child_data = child_res.json()
                if "id" in child_data:
                    child_ids.append(child_data["id"])

            if not child_ids:
                raise HTTPException(status_code=400, detail="No valid images found for carousel slides.")

            # Create carousel container
            container_res = requests.post(
                f"{GRAPH_URL}/{ig_account_id}/media",
                params={
                    "media_type": "CAROUSEL",
                    "caption": caption,
                    "children": ",".join(child_ids),
                    "access_token": access_token,
                },
            )
            container_data = container_res.json()
            if "id" not in container_data:
                raise HTTPException(status_code=500, detail=f"Instagram carousel container failed: {container_data}")

            publish_res = requests.post(
                f"{GRAPH_URL}/{ig_account_id}/media_publish",
                params={
                    "creation_id": container_data["id"],
                    "access_token": access_token,
                },
            )
            result = publish_res.json()

        elif content_type == "video_script":
            raise HTTPException(status_code=400, detail="Instagram does not support text-only posts. Video scripts need an accompanying image or video.")

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported content type: {content_type}")

        return {"success": True, "platform": "instagram", "response": result}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Instagram Publisher] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# LinkedIn Publishing (API v2)
# ──────────────────────────────────────────────

@router.post("/publish/linkedin")
def publish_to_linkedin(req: PublishRequest):
    """Publish content to LinkedIn via the API v2."""
    creds = _get_brand_credentials(req.brand_id, "linkedin")
    if not creds or not creds.get("access_token"):
        raise HTTPException(
            status_code=400,
            detail="No LinkedIn credentials found for this brand. Please add your LinkedIn access token and person/org URN in settings.",
        )

    access_token = creds["access_token"]
    author_urn = creds.get("platform_account_id")  # e.g. "urn:li:person:XXXXX" or "urn:li:organization:XXXXX"
    if not author_urn:
        raise HTTPException(status_code=400, detail="LinkedIn author URN is missing. Please update your credentials.")

    API_URL = "https://api.linkedin.com/v2"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202401",
    }

    content_type = req.content_type
    data = req.data
    text = _format_post_text(data, content_type)

    try:
        image_url = data.get("image_url")
        if image_url and not image_url.startswith("http"):
            image_url = f"http://localhost:8000{image_url}"

        # If we have an image, upload it first
        image_urn = None
        if image_url and content_type in ("canonical", "canonical_post", "image"):
            # Step 1: Register upload
            register_body = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": author_urn,
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent",
                        }
                    ],
                }
            }
            register_res = requests.post(
                f"{API_URL}/assets?action=registerUpload",
                headers=headers,
                json=register_body,
            )
            register_data = register_res.json()
            upload_url = register_data.get("value", {}).get("uploadMechanism", {}).get(
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {}
            ).get("uploadUrl")
            image_urn = register_data.get("value", {}).get("asset")

            if upload_url:
                # Step 2: Upload the image binary
                img_response = requests.get(image_url)
                requests.put(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "image/png",
                    },
                    data=img_response.content,
                )

        # Step 3: Create the post
        post_body: Dict[str, Any] = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        if image_urn:
            post_body["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
            post_body["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                {
                    "status": "READY",
                    "media": image_urn,
                }
            ]

        post_res = requests.post(f"{API_URL}/ugcPosts", headers=headers, json=post_body)
        result = post_res.json()

        print(f"[LinkedIn Publisher] Status: {post_res.status_code}, Response: {result}")

        if post_res.status_code >= 400:
            error_msg = result.get("message", str(result))
            if post_res.status_code == 403:
                error_msg += " — This usually means your access token doesn't have permission to post as this author. If using an organization URN, you need the 'w_organization_social' scope (requires Marketing Developer Platform). Try using your person URN (urn:li:person:XXXXX) instead."
            raise HTTPException(status_code=post_res.status_code, detail=f"LinkedIn API error: {error_msg}")

        return {"success": True, "platform": "linkedin", "response": result}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[LinkedIn Publisher] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Twitter/X Publishing (API v2 via tweepy)
# ──────────────────────────────────────────────

@router.post("/publish/twitter")
def publish_to_twitter(req: PublishRequest):
    """Publish a tweet to Twitter/X."""
    global os  # Explicitly use the global os module to avoid shadow errors
    creds = _get_brand_credentials(req.brand_id, "twitter")
    if not creds or not creds.get("access_token"):
        raise HTTPException(
            status_code=400,
            detail="No Twitter credentials found for this brand. Please add your Twitter API keys and access tokens in settings.",
        )

    try:
        import tweepy
    except ImportError:
        raise HTTPException(status_code=500, detail="tweepy is not installed. Run: pip install tweepy")

    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    access_token = creds["access_token"]
    access_token_secret = creds.get("access_token_secret")

    if not all([api_key, api_secret, access_token_secret]):
        raise HTTPException(
            status_code=400,
            detail="Incomplete Twitter credentials. Ensure api_key, api_secret, access_token, and access_token_secret are all provided.",
        )

    content_type = req.content_type
    data = req.data
    text = _format_post_text(data, content_type)

    # Twitter has a 280-char limit for tweets
    if len(text) > 280:
        text = text[:277] + "..."

    try:
        # Authenticate
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

        image_url = data.get("image_url")
        if image_url and content_type in ("canonical", "canonical_post", "image"):
            # For media upload we need v1.1 API
            auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
            api_v1 = tweepy.API(auth)

            # Download image and upload to Twitter
            if not image_url.startswith("http"):
                image_url = f"http://localhost:8000{image_url}"

            img_response = requests.get(image_url)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(img_response.content)
                tmp_path = tmp.name

            try:
                media = api_v1.media_upload(filename=tmp_path)
                result = client.create_tweet(text=text, media_ids=[media.media_id])
            finally:
                os.unlink(tmp_path)
        else:
            result = client.create_tweet(text=text)

        return {
            "success": True,
            "platform": "twitter",
            "response": {"tweet_id": str(result.data["id"])} if result.data else {},
        }

    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        print(f"[Twitter Publisher] Error: {error_str}")
        
        # Check for 402/403 (Free tier limitations)
        if "402" in error_str or "forbidden" in error_str.lower() or "403" in error_str:
            encoded_text = urllib.parse.quote(text)
            intent_url = f"https://twitter.com/intent/tweet?text={encoded_text}"
            return {
                "success": True,
                "platform": "twitter",
                "fallback": True,
                "publish_url": intent_url,
                "message": "Twitter Free Tier detected. Please click to post manually for free."
            }
        
        raise HTTPException(status_code=500, detail=error_str)


# ──────────────────────────────────────────────
# Telegram Publishing (existing)
# ──────────────────────────────────────────────

@router.post("/publish/telegram")
def publish_to_telegram(req: PublishRequest):
    """Publish generated AI content to Telegram."""
    try:
        content_type = req.content_type
        data = req.data

        if content_type == "canonical" or content_type == "canonical_post" or content_type == "image":
            text = data.get("canonical_post", "No text provided.")
            image_url = _to_local_path(data.get("image_url"))
            tags = data.get("tags", [])
            tag_str = " ".join([f"#{tag.lstrip('#')}" for tag in tags])
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

            for slide in slides:
                caption_parts.append(f"• {slide.get('title', '')}")
                if "image_url" in slide and slide["image_url"]:
                    image_urls.append(_to_local_path(slide["image_url"]))
            if cta and "image_url" in cta and cta["image_url"]:
                image_urls.append(_to_local_path(cta["image_url"]))

            caption = "\n".join(caption_parts)
            if cta:
                caption += f"\n\n👉 {cta.get('title', '')}: {cta.get('body', '')}"

            tags = data.get("tags", [])
            if tags:
                tag_str = " ".join([f"#{tag.lstrip('#')}" for tag in tags])
                caption += f"\n\n{tag_str}"

            if image_urls:
                result = telegram_agent.send_media_group(media_paths=image_urls, caption=caption)
            else:
                result = telegram_agent.send_message(text=caption)

        elif content_type == "video_script":
            script = data.get("video_script", {})
            text = f"🎬 <b>Video Script</b>\n\n<b>Hook:</b> {script.get('hook', '')}\n\n<b>Body:</b> {script.get('body', '')}\n\n<b>CTA:</b> {script.get('cta', '')}\n\n<b>Caption:</b> {script.get('caption', '')}"

            tags = data.get("tags", [])
            if tags:
                tag_str = " ".join([f"#{tag.lstrip('#')}" for tag in tags])
                text += f"\n\n{tag_str}"

            result = telegram_agent.send_message(text=text)

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported content type for publishing: {content_type}")

        return {
            "success": True,
            "platform": "telegram",
            "telegram_response": result,
        }

    except Exception as e:
        print(f"[Telegram Publisher] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
