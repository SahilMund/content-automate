import os
from datetime import date
from typing import List

from config import OUTPUTS_DIR, RESEARCH_MODEL
from graph.state import AgentState
from tools.image_fetcher import fetch_images
from tools.llm import get_model
from tools.progress import emit
from tools.scraper import ScrapedItem, scrape_all

RESEARCH_PROMPT = """\
You are a content research assistant. Analyse the scraped data below and produce a \
structured research document for the topic: "{topic}".

Today's date: {date}
Number of sources scraped: {source_count}

--- SCRAPED DATA ---
{context}
--- END SCRAPED DATA ---

Write a research document using EXACTLY this markdown structure (keep all headings):

# Raw Research: {topic}
**Date:** {date}
**Sources:** {source_count} items

## Top Trends & Findings
- (5–8 bullet points — most important / surprising / timely findings)

## Key Stats & Numbers
- (any specific numbers, percentages, benchmarks from the data — skip if none)

## Key Quotes & Snippets
- (1–3 direct quotes or headline-worthy phrases from the sources)

## Source Links
- [title](url) — one line per source

## Video Talking Points
1. (punchy opening hook)
2. (main insight to explain)
3. (counter-intuitive angle or practical takeaway)
4. (CTA / what the viewer should do next)

## Image Generation Prompt
- (One detailed prompt for an AI image generator. IMPORTANT RULES:
  1. Visualise the KEY TECHNICAL or CONCEPTUAL idea from the research — NOT the surface-level topic word.
     E.g. for "fashion CLIP embeddings" → show neural network vector spaces, not a fashion model.
     E.g. for "AI agents" → show autonomous robots or node graphs, not generic tech.
  2. Style: flat design or 3D render, minimalist, professional, no text, no letters, no words.
  3. Colours: suggest a specific palette (e.g. "deep blue and electric purple", "warm orange and white").
  4. Format: suitable as a LinkedIn or Instagram post image — square or landscape, clean background.
  5. Under 80 words.)
"""


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
    print(f"\n[research] Starting research for: {topic} {label}")
    emit(f"🧠 <b>Research Agent</b> starting {label}…")

    # 1. Scrape (scraper emits its own per-source steps)
    scraped = scrape_all(topic)
    if not scraped:
        return {**state, "error": f"No data scraped for topic: {topic}"}

    emit(f"✅ Scraped <b>{len(scraped)} items</b> — calling LLM…")

    # 2. Build prompt
    context = _format_context(scraped)
    prompt = RESEARCH_PROMPT.format(
        topic=topic,
        date=date.today().isoformat(),
        source_count=len(scraped),
        context=context,
    )

    # 3. Call LLM
    print(f"[research] Calling LLM ({RESEARCH_MODEL})...")
    llm = get_model(RESEARCH_MODEL)
    response = llm.invoke(prompt)
    raw_research = response.content

    # 4. Fetch images
    emit("🖼 Generating image with <b>Gemini AI</b>…")
    images, image_urls = fetch_images(raw_research, topic)
    emit(f"🖼 <b>{len(images)} images</b> saved")

    # 5. Save to disk
    path = _save_output(raw_research, topic)
    print(f"[research] Saved → {path}")

    return {
        **state,
        "raw_research": raw_research,
        "images": images,
        "image_urls": image_urls,
        "error": None,
    }
