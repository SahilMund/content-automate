from typing import List, Optional

from typing_extensions import TypedDict


class AgentState(TypedDict):
    topic: str                   # topic being researched this run
    raw_research: str            # raw_research.md content
    content_brief: str           # content_brief.md content
    images: List[str]            # local image paths fetched from Pexels
    image_urls: List[str]        # original Pexels source URLs (needed for Instagram)
    structured_brief: str        # editing agent output — structured sections
    quality_score: float         # 0–10 score from analysis agent
    retry_count: int             # increments each time research loops back
    video_path: Optional[str]    # local MP4 path from Remotion render
    error: Optional[str]         # last error message, None if clean
