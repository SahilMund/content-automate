import os
from datetime import date

from config import OUTPUTS_DIR, RESEARCH_MODEL
from graph.state import AgentState
from tools.llm import get_model
from tools.progress import emit

EDITING_PROMPT = """\
You are a senior content editor. Your job is to take raw research and structure it into \
a clean, well-organised brief that a social media writer can use directly.

Topic: {topic}
Date: {date}

--- RAW RESEARCH ---
{raw_research}
--- END RAW RESEARCH ---

Extract and organise the best content into EXACTLY this structure (keep all headings):

# Structured Brief: {topic}
**Date:** {date}

## Big Story
(The single most important finding, trend, or breakthrough. 2-3 sentences max. \
Must be specific — include numbers, names, or a concrete example. \
This is the headline that makes someone stop scrolling.)

## Why It Matters Now
(1-2 sentences on the timing — why is this relevant today specifically, not 6 months ago?)

## Top Papers
(List up to 3 Arxiv or academic papers found in the research. \
Format: "**Title** — one-line summary of what it proves or shows." \
Skip this section entirely if no papers were found.)

## Notable GitHub Repos
(List up to 3 GitHub repos found in the research. \
Format: "**owner/repo** (⭐ stars) — one-line description of what it does." \
Skip this section entirely if no repos were found.)

## Key Stats & Numbers
- (stat 1 — include source context)
- (stat 2 — include source context)
- (stat 3 — include source context)
(Include only stats that appear in the research. Skip any you need to invent.)

## Practical Angle
(One concrete thing a developer or AI practitioner can DO with this knowledge today. \
E.g. "Use library X to build Y in under Z minutes." Be specific and actionable.)

## Contrarian Take
(One non-obvious angle or thing most people get wrong about this topic. \
This is the insight that makes someone feel smart for reading.)

## Suggested Hook Lines
1. (hook option 1 — surprising stat format)
2. (hook option 2 — bold claim format)
3. (hook option 3 — question format)
"""


def _save_output(content: str, topic: str) -> str:
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    safe_topic = topic.lower().replace("/", "-").replace(" ", "_")
    filename = f"structured_brief_{safe_topic}_{date.today().isoformat()}.md"
    path = os.path.join(OUTPUTS_DIR, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


def editing_node(state: AgentState) -> AgentState:
    topic = state["topic"]
    print(f"\n[editing] Structuring research for: {topic}")
    emit("✏️ <b>Editing Agent</b> — structuring research into brief…")

    prompt = EDITING_PROMPT.format(
        topic=topic,
        date=date.today().isoformat(),
        raw_research=state["raw_research"],
    )

    llm = get_model(RESEARCH_MODEL)
    response = llm.invoke(prompt)
    structured_brief = response.content.strip()

    path = _save_output(structured_brief, topic)
    print(f"[editing] Saved → {path}")
    emit("✅ Brief structured — writing posts…")

    return {**state, "structured_brief": structured_brief}
