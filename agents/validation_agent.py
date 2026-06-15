import json
import re

from config import ANALYSIS_MODEL
from graph.state import AgentState
from tools.llm import get_model
from tools.progress import emit

MAX_VALIDATION_ATTEMPTS = 1

VALIDATION_PROMPT = """\
You are an editor for @the.undefined.parts, a developer Instagram page.
Check ONLY these 3 hard rules against the Instagram Caption in the brief below.

--- CONTENT BRIEF ---
{content_brief}
--- END ---

RULE 1 — Single angle
The entire post must be about ONE specific thing (one API, one tool, one event, one technique).
FAIL only if the post tries to cover multiple unrelated concepts or is a generic topic overview.

RULE 2 — Punchy first line
The first line must make someone stop scrolling — a bold statement, surprising fact, specific problem, or provocative question.
FAIL only if the first line is bland praise like "X is a great tool 🚀" or a generic definition.

RULE 3 — No banned phrases
Zero tolerance for these exact phrases anywhere in the caption:
"game-changer", "rapidly growing", "in today's world", "leverage", "this is important", "developers need to know"
FAIL if any of these appear verbatim.

Do NOT fail for: analogies (they are encouraged), benefit statements, tone, style choices, or anything else.

Respond ONLY with valid JSON, no other text:
{{
  "passed": true or false,
  "issues": ["short description of each failing rule — empty list if passed"],
  "rewrite_instruction": "one specific sentence on what to fix — empty string if passed"
}}
"""


def _parse_json(text: str) -> dict:
    # strip markdown code fences if the model wraps output
    clean = re.sub(r"```(?:json)?|```", "", text).strip()
    return json.loads(clean)


def validation_node(state: AgentState) -> AgentState:
    topic = state["topic"]
    attempts = state.get("validation_attempts", 0) + 1
    print(f"\n[validation] Checking content for: {topic} (attempt {attempts})")
    emit("STEP:validation")

    llm = get_model(ANALYSIS_MODEL)
    prompt = VALIDATION_PROMPT.format(content_brief=state["content_brief"])
    response = llm.invoke(prompt)

    try:
        result = _parse_json(response.content)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[validation] JSON parse failed: {e} — treating as passed")
        result = {"passed": True, "issues": [], "rewrite_instruction": ""}

    passed = result.get("passed", True)
    issues = result.get("issues", [])
    feedback = result.get("rewrite_instruction", "")

    if passed:
        print("[validation] ✅ Content passed")
        emit("DONE:validation")
    else:
        print(f"[validation] ❌ Failed — {issues}")
        emit(f"NOTE:Validation failed — rewriting ({attempts}/{MAX_VALIDATION_ATTEMPTS})")

    return {
        **state,
        "validation_feedback": "" if passed else feedback,
        "validation_attempts": attempts,
    }


def should_rewrite(state: AgentState) -> str:
    feedback = state.get("validation_feedback", "")
    attempts = state.get("validation_attempts", 0)
    if feedback and attempts < MAX_VALIDATION_ATTEMPTS:
        return "rewrite"
    return "done"
