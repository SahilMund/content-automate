import os

from dotenv import load_dotenv

load_dotenv()

# ── Model config ─────────────────────────────────────────────
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", "groq/llama-3.3-70b-versatile")
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "groq/llama-3.3-70b-versatile")

# ── Quality control ──────────────────────────────────────────
QUALITY_THRESHOLD = float(os.getenv("QUALITY_THRESHOLD", "7.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))

# ── Topic domains ────────────────────────────────────────────
TOPICS = [
    "AI/LLM",
    "React",
    "Python",
    "FastAPI",
    "DevOps",
    "System Design",
]

# ── Substack feeds to monitor ────────────────────────────────
SUBSTACK_FEEDS = [
    "https://www.latent.space/feed",
    "https://tldr.tech/ai/rss",
    "https://newsletter.pragmaticengineer.com/feed",
]

# ── Output paths ─────────────────────────────────────────────
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
