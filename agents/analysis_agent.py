import os
import re
from datetime import date

from config import ANALYSIS_MODEL, OUTPUTS_DIR
from graph.state import AgentState
from tools.llm import get_model
from tools.progress import emit

ANALYSIS_PROMPT = """\
You are a tech content writer for @the.undefined.parts — an Instagram and LinkedIn page \
for software developers. Your job is to read source material and create compelling, \
insight-driven social media content from it.

Topic: {topic}
Date: {date}

--- SOURCE MATERIAL ---
{raw_research}
--- END MATERIAL ---

STEP 1 — Identify content type and pick the angle:

First, determine what kind of content this is:

A) TUTORIAL/TECHNICAL: Content about a specific API, library, tool, coding technique, or concept \
→ Find the single most interesting, underused, or surprising technical thing. Build the post around \
teaching developers ONE concrete thing they can use immediately.

B) NEWS/OPINION/ANALYSIS: Content about an industry event, product launch, policy decision, debate, \
or broader tech story → Find the most interesting angle, implication, or take for a software developer \
audience. What's the insight they'd want to share with their team?

STEP 2 — Write the content using EXACTLY this structure (keep all headings):

# Content Brief: {topic}
**Date:** {date}

## Chosen Angle
(One sentence: what this post is specifically about and why it matters to developers)

## Instagram Caption

For TUTORIAL content, use this structure:
[PAIN POINT HOOK — an action line about the developer problem being solved]
[CURIOSITY LINE — "Ever wondered how..." or "Did you know..."]
Enter [CONCEPT] — [one-line analogy that makes it click]
[CONTRAST: "Most devs use X, but [CONCEPT] is:"]
✅ [Concrete benefit 1]
✅ [Concrete benefit 2]
✅ [Concrete benefit 3]
Slide through to see how 🚀
[ENGAGEMENT QUESTION] 👇

For NEWS/OPINION content, use this structure:
[BOLD HOOK — the most surprising or important thing from this story, in one punchy line]
[CONTEXT — 1-2 sentences: what happened and why developers should care]
[KEY INSIGHT or IMPLICATION — what this actually means for the industry/developers]
✅ [Key point 1 from the story]
✅ [Key point 2 from the story]
✅ [Key point 3 from the story]
Slide through for the full breakdown 📊
[ENGAGEMENT QUESTION — your take on the story] 👇

General caption rules:
- Hook must be punchy — make people stop scrolling
- No phrases: "rapidly growing", "game-changer", "leverage", "in today's world", "this is important"
- Emojis: max 3, only where they add meaning
- End with 10-15 hashtags on one line (mix specific + broad)

## LinkedIn Post

For TUTORIAL content — professional educator tone:
Line 1 (hook, before "see more"): Bold claim or question about the pain point.

2-3 sentences: What is it, why do devs not know/use it, what's the analogy.

Here's when you'd actually use this:
→ [concrete use case 1]
→ [concrete use case 2]
→ [concrete use case 3]

Closing opinion or question that sparks discussion.

3-5 hashtags. Total: 800-1200 characters.

For NEWS/OPINION content — thought leadership tone:
Line 1 (hook, before "see more"): The most interesting/controversial take on the story.

2-3 sentences: What happened, why it matters, your read on it.

The implications for developers and the industry:
→ [implication 1]
→ [implication 2]
→ [implication 3]

Closing: your opinion or prediction, inviting discussion.

3-5 hashtags. Total: 800-1200 characters.

No "I'm excited to share". No generic facts. Write with a distinct voice.

## Code Snippet
(For TUTORIAL content: include 5-15 lines of working code demonstrating the concept)
(For NEWS/OPINION content: skip this section entirely — write "N/A")

## Hashtags
**Instagram:** (10-15 tags)
**LinkedIn:** (3-5 tags)

## Slide Plan
Choose 5-7 slides for the Instagram carousel. Each slide must be on its own SLIDE: block.
Always start with cover and end with cta. Pick types that match the content.

Available types:
  cover     — hero title. Fields: CONCEPT (1-5 words), TAGLINE (6-12 words)
  hook      — "LET ME TELL YOU / WHAT IS X?" — use for tutorials only. Field: CONCEPT
  context   — facts summary for news/events. Fields: TITLE, ITEM ×3
  bullets   — 3-4 key points. Fields: TITLE, ITEM ×3-4
  code      — syntax-highlighted code — ONLY if real useful code exists. Fields: LANGUAGE, CODE: (then raw code on next lines)
  cards     — numbered takeaways 01/02/03. Fields: TITLE, ITEM ×3
  quote     — standout quote for news/opinion. Fields: QUOTE, ATTRIBUTION
  cta       — call to action. Field: QUESTION (what you ask followers)

Rules:
  - Tutorial/Tech → use: cover, hook, bullets(definition), code(if useful), bullets(use cases), cards, cta
  - News/Opinion  → use: cover, context, bullets(why it matters), bullets(developer impact), cards, cta  (NO hook, NO code)
  - Concept/Career → use: cover, hook, bullets(problem), bullets(approach), cards, cta  (NO code)
  - Skip code entirely if the topic is news, opinion, career advice, or has no real implementable code
  - Each ITEM must be concise — max 15 words
  - CONCEPT and TAGLINE must be plain text, no markdown

Example (tutorial):
SLIDE: cover
CONCEPT: Broadcast Channel API
TAGLINE: Sync browser tabs without WebSockets

SLIDE: hook
CONCEPT: Broadcast Channel API

SLIDE: bullets
TITLE: The Gist
ITEM: Built into every modern browser, zero dependencies
ITEM: Pub/sub pattern across same-origin tabs
ITEM: No server, no polling, no WebSockets needed

SLIDE: code
LANGUAGE: javascript
CODE:
const bc = new BroadcastChannel('app');
bc.postMessage({{ type: 'update', data: payload }});
bc.onmessage = (e) => applyUpdate(e.data);

SLIDE: bullets
TITLE: When to Use It
ITEM: Sync shopping cart across open tabs
ITEM: Trigger logout in all tabs at once
ITEM: Push live data between multiple app windows

SLIDE: cards
TITLE: Key Takeaways
ITEM: Zero server overhead — pure browser API
ITEM: Same-origin only — intentional security boundary
ITEM: Use WebSockets for cross-device, not this

SLIDE: cta
QUESTION: How do you currently sync state across browser tabs?

---

After the brief, score on these dimensions (each 0-10):
- Specificity: Is this about ONE concrete angle, not a vague topic?
- Insight quality: Does the content give developers a genuine new perspective?
- Practicality: Would a dev immediately find this relevant to their work?
- Engagement: Would they save this or share it with their team?

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
    user_feedback    = state.get("user_feedback", "")
    val_feedback     = state.get("validation_feedback", "")
    feedback_parts   = [p for p in [user_feedback, val_feedback] if p]
    combined_feedback = "\n\n".join(feedback_parts)
    is_rewrite = bool(combined_feedback)

    label = "rewriting with feedback" if is_rewrite else "building posts"
    print(f"\n[analysis] {label.capitalize()} for: {topic}")
    emit("STEP:analysis")

    research_input = state["raw_research"]
    base_prompt = ANALYSIS_PROMPT.format(
        topic=topic,
        date=date.today().isoformat(),
        raw_research=research_input,
    )

    if is_rewrite:
        prompt = (
            base_prompt
            + f"\n\n--- FEEDBACK (address these in your rewrite) ---\n{combined_feedback}\n---"
        )
    else:
        prompt = base_prompt

    print(f"[analysis] Calling LLM ({ANALYSIS_MODEL})...")
    llm = get_model(ANALYSIS_MODEL)
    response = llm.invoke(prompt)
    full_output = response.content

    quality_score = _parse_quality_score(full_output)
    content_brief = _strip_score_line(full_output)

    print(f"[analysis] Quality score: {quality_score}/10")
    path = _save_output(content_brief, topic)
    print(f"[analysis] Saved → {path}")
    emit("DONE:analysis")

    return {
        **state,
        "content_brief": content_brief,
        "quality_score": quality_score,
        "retry_count": state["retry_count"] + 1,
        "error": None,
    }
