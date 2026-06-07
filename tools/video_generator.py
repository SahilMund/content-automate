"""
Video generation via Remotion (motion graphics) and Manim (concept animation).

Both are driven by the LLM — it fills in props/code per topic.
Output: local MP4 path ready to post to Instagram Reels / LinkedIn video.
"""
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

from config import OUTPUTS_DIR
from tools.llm import get_model
from tools.progress import emit

REMOTION_DIR = Path(__file__).parent.parent / "video" / "remotion"


# ── LLM prompt helpers ────────────────────────────────────────

_REMOTION_PROMPT = """
You are generating props for a Remotion video composition about: {topic}

Based on this content brief:
{brief}

Return ONLY valid JSON with exactly these keys:
{{
  "topic":       "short punchy title (max 6 words)",
  "stat":        "the single most impressive number/percentage from the research (e.g. '57%', '$4.2B', '10x')",
  "statLabel":   "what that number represents (max 5 words)",
  "points":      ["insight 1 (max 8 words)", "insight 2 (max 8 words)", "insight 3 (max 8 words)"],
  "handle":      "@the.undefined.parts",
  "accentColor": "a hex color that fits the topic mood",
  "bgColor":     "#0F0F1A"
}}

Rules:
- stat must be a real number from the research, not made up
- points must be punchy, concrete, and specific
- accentColor: purple for AI/ML, green for finance, blue for tech infra, orange for creative
- Return ONLY the JSON, no markdown fences
"""


def _llm_remotion_props(topic: str, brief: str) -> dict:
    llm = get_model("groq/llama-3.3-70b-versatile")
    prompt = _REMOTION_PROMPT.format(topic=topic, brief=brief[:2000])
    raw = llm.invoke(prompt).content.strip()
    raw = re.sub(r"^```json?\s*|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# ── Remotion renderer ─────────────────────────────────────────

def generate_remotion_video(topic: str, brief: str) -> Optional[str]:
    """
    Ask LLM for props, inject into Remotion, render MP4.
    Returns local path to rendered MP4 or None on failure.
    """
    emit("🎬 Generating <b>Remotion</b> motion graphics video…")
    try:
        # 1. Get props from LLM
        props = _llm_remotion_props(topic, brief)
        print(f"[remotion] Props: topic='{props['topic']}' stat='{props['stat']}'")

        # 2. Make sure node_modules exist
        if not (REMOTION_DIR / "node_modules").exists():
            print("[remotion] Installing npm packages…")
            subprocess.run(["npm", "install"], cwd=REMOTION_DIR, check=True,
                           capture_output=True)

        # 3. Build output path
        safe = topic.lower().replace(" ", "_").replace("/", "-")[:40]
        out_dir = Path(OUTPUTS_DIR) / "videos"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"remotion_{safe}_{date.today().isoformat()}.mp4"

        # 4. Render
        cmd = [
            "npx", "remotion", "render",
            "src/index.ts",
            "DraftPilotVideo",
            str(out_path),
            f"--props={json.dumps(props)}",
        ]
        result = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"[remotion] Render failed:\n{result.stderr[-1000:]}")
            return None

        print(f"[remotion] Rendered → {out_path}")
        emit("🎬 Remotion video ready")
        return str(out_path)

    except Exception as e:
        print(f"[remotion] Error: {e}")
        return None


