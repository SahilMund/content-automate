import os
import re
from datetime import date

from config import ANALYSIS_MODEL, OUTPUTS_DIR
from graph.state import AgentState
from tools.llm import get_model
from tools.progress import emit

ANALYSIS_PROMPT = """\
You are a sharp tech content creator writing for developers and AI practitioners on Instagram, \
X, and LinkedIn. You write like the best Indian dev creators — direct, opinionated, specific. \
No corporate fluff. No vague generalisations. Real insights, punchy delivery.

Topic: {topic}
Date: {date}

--- RAW RESEARCH ---
{raw_research}
--- END RESEARCH ---

Produce a content brief using EXACTLY this structure (keep all headings):

# Content Brief: {topic}
**Date:** {date}

## Hook
(One line. Make it a scroll-stopper. Options: a surprising number, a bold contrarian claim, \
a "most devs don't know this" opener, or a sharp question. No filler words.)

## Instagram Caption
Write in this EXACT style (use the example below as your template, replace content with {topic}):

EXAMPLE (do not copy this — use it as style reference only):
---
Most developers use Redis wrong. Here's what it actually does. 🧠

Redis isn't a cache. It's a data structure server.
And that distinction changes everything about how you architect systems.

Most teams only use it as a key-value store — but they're leaving 80% of it on the table.

↳ Redis Streams handle 1M+ events/sec — beats Kafka for small-to-mid workloads
↳ Sorted sets give you leaderboards, rate limiting, and geo-search in a single data structure
↳ Pub/Sub + keyspace notifications = real-time features without WebSocket complexity

Have you been using Redis beyond caching? Drop your use case below 👇

.
.
.

#Redis #BackendDevelopment #SystemDesign #SoftwareEngineering #WebDevelopment #DatabaseDesign #DevTips #buildinpublic #devlife #CodingLife #ProgrammingTips #TechTwitter #100DaysOfCode
---

Now write the Instagram Caption for {topic} following this style:
- Hook: first line must use a SPECIFIC stat or bold claim from the research (not generic)
- Body: 3-4 short punchy lines, one idea each, conversational tone
- Bullets: 3 ↳ points with real numbers or concrete details from the research
- CTA: one question that invites comments
- Dot spacers (.\\n.\\n.)
- 10-15 hashtags on one line

## LinkedIn Post
Professional but human. Structure:
Line 1: Hook (shows before "see more" — must make someone stop scrolling. Bold claim or stat.)

[blank line]

1-2 sentence context — why this matters right now.

[blank line]

1-2 sentence insight — the non-obvious angle most people miss.

[blank line]

Here's what this means for you:
→ [actionable point 1]
→ [actionable point 2]
→ [actionable point 3]

[blank line]

Closing line — a question that invites replies, or a strong opinion.

[blank line]

3-5 hashtags.

Total: 700-1200 characters. No bullet-point lists of generic facts. No "I'm excited to share".

## Key Insights
- (insight 1 — specific, has a number or concrete detail)
- (insight 2 — specific, has a number or concrete detail)
- (insight 3 — specific, has a number or concrete detail)

## CTA Options
- (option 1 — drives comments)
- (option 2 — drives saves/shares)

## Hashtags
**Instagram:** #tag1 #tag2 ... (10-15 tags)
**LinkedIn:** #tag1 #tag2 #tag3 #tag4 #tag5

---

After the brief, score the content quality on these four dimensions (each 0-10):
- Novelty: Is this information fresh and non-obvious?
- Relevance: Does it match what {topic} practitioners care about right now?
- Clarity: Are the posts easy to understand for a developer audience?
- Engagement: Would this prompt likes, saves, comments, or replies?

End your response with EXACTLY this line (no other text after it):
QUALITY_SCORE: <average of the four scores as a single decimal, e.g. 7.5>
"""


def _parse_quality_score(text: str) -> float:
    match = re.search(r"QUALITY_SCORE:\s*([0-9]+(?:\.[0-9]+)?)", text)
    if match:
        return min(10.0, max(0.0, float(match.group(1))))
    return 5.0  # default if parsing fails


def _strip_score_line(text: str) -> str:
    return re.sub(r"\nQUALITY_SCORE:.*$", "", text, flags=re.MULTILINE).strip()


def _save_output(content: str, topic: str) -> str:
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    safe_topic = topic.lower().replace("/", "-").replace(" ", "_")
    filename = f"content_brief_{safe_topic}_{date.today().isoformat()}.md"
    path = os.path.join(OUTPUTS_DIR, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


def analysis_node(state: AgentState) -> AgentState:
    topic = state["topic"]
    print(f"\n[analysis] Analysing content for: {topic}")
    emit("📝 <b>Analysis Agent</b> — building X, LinkedIn & Instagram posts…")

    # Prefer the editing agent's structured brief; fall back to raw research
    research_input = state.get("structured_brief") or state["raw_research"]
    prompt = ANALYSIS_PROMPT.format(
        topic=topic,
        date=date.today().isoformat(),
        raw_research=research_input,
    )

    print(f"[analysis] Calling LLM ({ANALYSIS_MODEL})...")
    llm = get_model(ANALYSIS_MODEL)
    response = llm.invoke(prompt)
    full_output = response.content

    quality_score = _parse_quality_score(full_output)
    content_brief = _strip_score_line(full_output)

    print(f"[analysis] Quality score: {quality_score}/10")
    emit(f"📊 Quality score: <b>{quality_score}/10</b> — wrapping up…")

    path = _save_output(content_brief, topic)
    print(f"[analysis] Saved → {path}")

    return {
        **state,
        "content_brief": content_brief,
        "quality_score": quality_score,
        "retry_count": state["retry_count"] + 1,
        "error": None,
    }
