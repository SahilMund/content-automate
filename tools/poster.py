import os

import requests
from dotenv import load_dotenv

load_dotenv()

LI_ACCESS_TOKEN  = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LI_USER_SUB      = os.getenv("LINKEDIN_USER_SUB", "")


def _upload_image_to_linkedin(image_path: str) -> str:
    """Register + upload an image asset to LinkedIn. Returns asset URN."""
    author = f"urn:li:person:{LI_USER_SUB}"
    headers = {
        "Authorization": f"Bearer {LI_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Step 1 — register upload
    register = requests.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        headers=headers,
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": author,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }],
            }
        },
        timeout=15,
    )
    register.raise_for_status()
    data = register.json()["value"]
    upload_url = data["uploadMechanism"][
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]["uploadUrl"]
    asset_urn = data["asset"]

    # Step 2 — PUT the binary
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    put = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {LI_ACCESS_TOKEN}"},
        data=img_bytes,
        timeout=30,
    )
    put.raise_for_status()
    return asset_urn


def post_to_linkedin(text: str, image_path: str | None = None) -> str:
    """
    Post to LinkedIn with optional image attachment.
    Returns best-effort feed URL.
    """
    if not LI_ACCESS_TOKEN or not LI_USER_SUB:
        raise RuntimeError(
            "LinkedIn credentials not set. Run python auth_linkedin.py first."
        )

    author = f"urn:li:person:{LI_USER_SUB}"
    share_content: dict = {
        "shareCommentary": {"text": text},
        "shareMediaCategory": "NONE",
    }

    if image_path and os.path.exists(image_path):
        try:
            asset_urn = _upload_image_to_linkedin(image_path)
            share_content["shareMediaCategory"] = "IMAGE"
            share_content["media"] = [{
                "status": "READY",
                "description": {"text": "AI-generated post image"},
                "media": asset_urn,
                "title": {"text": "Post image"},
            }]
            print(f"[linkedin] Image uploaded → {asset_urn}")
        except Exception as e:
            print(f"[linkedin] Image upload failed, posting text only: {e}")

    payload = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        json=payload,
        headers={
            "Authorization": f"Bearer {LI_ACCESS_TOKEN}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()

    post_id = resp.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/  (post id: {post_id})"


def post_to_instagram(caption: str, image_path: str) -> str:
    """Post a single image to Instagram via Playwright."""
    from tools.instagram_browser import post_to_instagram_browser
    return post_to_instagram_browser(caption, image_path)


def post_carousel_to_instagram(caption: str, image_paths: list[str]) -> str:
    """Post multiple slides as an Instagram carousel via Playwright."""
    from tools.instagram_browser import post_carousel_to_instagram_browser
    return post_carousel_to_instagram_browser(caption, image_paths)


def post_reel_to_instagram(caption: str, video_path: str) -> str:
    """Post a video as an Instagram Reel via Playwright. Returns Instagram home URL."""
    from tools.instagram_browser import post_reel_to_instagram_browser
    return post_reel_to_instagram_browser(caption, video_path)


def _upload_video_to_linkedin(video_path: str) -> str:
    """Register + upload a video asset to LinkedIn. Returns asset URN."""
    import time
    author = f"urn:li:person:{LI_USER_SUB}"
    headers = {
        "Authorization": f"Bearer {LI_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Step 1 — register upload
    register = requests.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        headers=headers,
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                "owner": author,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }],
            }
        },
        timeout=15,
    )
    register.raise_for_status()
    data = register.json()["value"]
    upload_url = data["uploadMechanism"][
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]["uploadUrl"]
    asset_urn = data["asset"]

    # Step 2 — PUT the binary
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    put = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {LI_ACCESS_TOKEN}"},
        data=video_bytes,
        timeout=120,
    )
    put.raise_for_status()

    # Step 3 — poll until AVAILABLE (max 3 min)
    print(f"[linkedin] Waiting for video processing… (asset: {asset_urn})")
    for _ in range(18):  # 18 × 10s = 3 min
        time.sleep(10)
        check = requests.get(
            f"https://api.linkedin.com/v2/assets/{asset_urn.split(':')[-1]}",
            headers={**headers, "Content-Type": "application/json"},
            timeout=15,
        )
        if check.ok:
            status = check.json().get("recipes", [{}])[0].get("status", "")
            print(f"[linkedin] Video status: {status}")
            if status == "AVAILABLE":
                break
    return asset_urn


def post_video_to_linkedin(text: str, video_path: str) -> str:
    """Upload a video to LinkedIn and post it. Returns best-effort feed URL."""
    if not LI_ACCESS_TOKEN or not LI_USER_SUB:
        raise RuntimeError(
            "LinkedIn credentials not set. Run python auth_linkedin.py first."
        )
    if not video_path or not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    author = f"urn:li:person:{LI_USER_SUB}"
    asset_urn = _upload_video_to_linkedin(video_path)
    print(f"[linkedin] Video uploaded → {asset_urn}")

    share_content = {
        "shareCommentary": {"text": text},
        "shareMediaCategory": "VIDEO",
        "media": [{
            "status": "READY",
            "description": {"text": "AI-generated concept video"},
            "media": asset_urn,
            "title": {"text": "Watch this"},
        }],
    }

    payload = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        json=payload,
        headers={
            "Authorization": f"Bearer {LI_ACCESS_TOKEN}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    post_id = resp.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/  (post id: {post_id})"
