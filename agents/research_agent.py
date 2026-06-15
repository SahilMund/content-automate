import os
from datetime import date
from typing import List

from config import OUTPUTS_DIR
from graph.state import AgentState
from tools.progress import emit
from tools.scraper import ScrapedItem, scrape_all


def _format_context(items: List[ScrapedItem]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. [{item['source']}] {item['title']}\n"
            f"   URL: {item['url']}\n"
            f"   Snippet: {item['snippet']}\n"
        )
    return "\n".join(lines)


def _save_output(content: str, topic: str) -> str:
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    safe_topic = topic.lower().replace("/", "-").replace(" ", "_")
    filename = f"raw_research_{safe_topic}_{date.today().isoformat()}.md"
    path = os.path.join(OUTPUTS_DIR, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


def research_node(state: AgentState) -> AgentState:
    topic = state["topic"]
    retry = state["retry_count"]
    label = f"(retry {retry})" if retry > 0 else ""
    raw_content = state.get("raw_content", "").strip()

    print(f"\n[research] Fetching data for: {topic} {label}")
    emit("STEP:research")

    images: list = []
    image_urls: list = []

    # ── Use provided content (URL or pasted text) ──────────────
    if raw_content:
        if raw_content.startswith(("http://", "https://")):
            from tools.scraper import fetch_url_content
            emit("NOTE:Fetching article from URL…")
            print(f"[research] Fetching URL: {raw_content[:80]}")
            fetched = fetch_url_content(raw_content)
            if not fetched:
                emit("DONE:research")
                return {**state, "error": f"Could not fetch content from URL: {raw_content[:80]}"}
            raw_research = (
                f"# Source Article: {topic}\n"
                f"**Date:** {date.today().isoformat()}\n"
                f"**URL:** {raw_content}\n\n"
                f"## Content\n{fetched}"
            )
        else:
            raw_research = (
                f"# Provided Content: {topic}\n"
                f"**Date:** {date.today().isoformat()}\n\n"
                f"## Content\n{raw_content}"
            )
        path = _save_output(raw_research, topic)
        print(f"[research] Using provided content → {path}")
        emit("DONE:research")
        return {
            **state,
            "raw_research": raw_research,
            "images": images,
            "image_urls": image_urls,
            "error": None,
        }

    # ── Default: web scraping ───────────────────────────────────
    scraped = scrape_all(topic)
    if not scraped:
        emit("DONE:research")
        return {**state, "error": f"No data scraped for topic: {topic}"}

    raw_research = (
        f"# Raw Research: {topic}\n"
        f"**Date:** {date.today().isoformat()}\n"
        f"**Sources:** {len(scraped)} items\n\n"
        + _format_context(scraped)
    )

    path = _save_output(raw_research, topic)
    print(f"[research] Saved → {path}")
    emit("DONE:research")

    return {
        **state,
        "raw_research": raw_research,
        "images": images,
        "image_urls": image_urls,
        "error": None,
    }
