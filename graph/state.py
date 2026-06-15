from typing import List, Optional

from typing_extensions import TypedDict


class AgentState(TypedDict):
    topic: str
    raw_research: str
    content_brief: str
    images: List[str]
    image_urls: List[str]
    structured_brief: str
    quality_score: float
    retry_count: int
    video_path: Optional[str]
    error: Optional[str]
    validation_feedback: str     # critique from validation node; empty string if none
    validation_attempts: int     # how many times validation has run
    carousel_paths: List[str]    # local PNG paths for Instagram carousel slides
    user_feedback: str           # human feedback from Telegram for regeneration
    raw_content: str             # pre-provided URL or full text content (skips scraping)
