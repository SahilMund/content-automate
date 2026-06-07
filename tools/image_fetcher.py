import base64
import io
import os
import re
from datetime import date
from typing import List, Optional

import requests

from config import OUTPUTS_DIR

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
HF_TOKEN        = os.getenv("HF_TOKEN", "")
PEXELS_API_KEY  = os.getenv("PEXELS_API_KEY", "")


def _parse_image_prompt(raw_research: str) -> Optional[str]:
    """Extract the Gemini image generation prompt from the research doc."""
    match = re.search(
        r"## Image Generation Prompt\n(.*?)(?:\n##|\Z)",
        raw_research,
        re.DOTALL,
    )
    if not match:
        return None
    return match.group(1).strip().lstrip("-•*").strip().strip('"').strip()


def _img_dir(topic: str) -> str:
    safe = topic.lower().replace("/", "-").replace(" ", "_")
    path = os.path.join(OUTPUTS_DIR, "images", f"{safe}_{date.today().isoformat()}")
    os.makedirs(path, exist_ok=True)
    return path


# ── Tier 1: Gemini (requires paid Google AI billing) ─────────────────────────

def _generate_gemini(prompt: str, dest: str) -> bool:
    if not GEMINI_API_KEY:
        return False
    try:
        from google import genai
        from google.genai import types
        from PIL import Image

        client = genai.Client(api_key=GEMINI_API_KEY)
        full_prompt = (
            f"{prompt}. Clean, modern, flat design. "
            "No text overlays. Professional color palette. LinkedIn visual."
        )
        # gemini-2.5-flash-image (requires billing)
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                data = base64.b64decode(part.inline_data.data)
                Image.open(io.BytesIO(data)).save(dest)
                print(f"[images] Gemini → {dest}")
                return True
        return False
    except Exception as e:
        print(f"[images] Gemini skipped: {e}")
        return False


# ── Tier 2: Hugging Face FLUX.1-schnell (free with HF token) ─────────────────

def _generate_huggingface(prompt: str, dest: str) -> bool:
    if not HF_TOKEN:
        print("[images] HF_TOKEN not set — skipping HuggingFace")
        return False
    try:
        from huggingface_hub import InferenceClient
        from PIL import Image

        print("[images] Generating via HuggingFace FLUX.1-schnell (free)…")
        client = InferenceClient(token=HF_TOKEN)
        image: Image.Image = client.text_to_image(
            prompt,
            model="black-forest-labs/FLUX.1-schnell",
        )
        image.save(dest)
        print(f"[images] HuggingFace FLUX → {dest}")
        return True
    except Exception as e:
        print(f"[images] HuggingFace failed: {e}")
        return False


# ── Tier 3: Pexels stock photos (free, always works) ─────────────────────────

def _pexels_query_from_prompt(prompt: str, topic: str) -> str:
    """Turn a long generation prompt into a short Pexels search query."""
    # Take the first ~5 meaningful words of the prompt
    words = [w for w in prompt.split() if len(w) > 3][:5]
    return " ".join(words) if words else topic


def _generate_pexels(prompt: str, topic: str, dest: str) -> bool:
    if not PEXELS_API_KEY:
        print("[images] PEXELS_API_KEY not set — skipping Pexels")
        return False
    try:
        query = _pexels_query_from_prompt(prompt, topic)
        print(f"[images] Pexels fallback search: '{query}'…")
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            timeout=10,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return False
        img_url = photos[0]["src"]["large"]
        img_resp = requests.get(img_url, timeout=15, stream=True)
        img_resp.raise_for_status()

        from PIL import Image
        Image.open(io.BytesIO(img_resp.content)).save(dest)
        print(f"[images] Pexels → {dest}")
        return True
    except Exception as e:
        print(f"[images] Pexels failed: {e}")
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_images(raw_research: str, topic: str) -> tuple[List[str], List[str]]:
    """
    Generate one image for the topic using the best available method:
      1. Gemini AI (requires Google billing)
      2. HuggingFace FLUX.1-schnell (free with free HF account)
      3. Pexels stock photos (free API key)
    Returns (local_paths, []).
    """
    prompt = _parse_image_prompt(raw_research)
    if not prompt:
        prompt = f"Professional illustration representing: {topic}"

    img_dir = _img_dir(topic)
    dest = os.path.join(img_dir, f"ai_image_{date.today().isoformat()}.png")

    success = (
        _generate_gemini(prompt, dest)
        or _generate_huggingface(prompt, dest)
        or _generate_pexels(prompt, topic, dest)
    )

    if success:
        print("[images] Done — image saved")
        return [dest], []

    print("[images] All image sources failed — continuing without image")
    return [], []
