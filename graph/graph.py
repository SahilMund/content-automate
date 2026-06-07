from langgraph.graph import END, StateGraph

from agents.analysis_agent import analysis_node
from agents.editing_agent import editing_node
from agents.research_agent import research_node
from agents.video_agent import video_node
from config import MAX_RETRIES, QUALITY_THRESHOLD
from graph.state import AgentState

# ── Routing logic ────────────────────────────────────────────

def should_retry(state: AgentState) -> str:
    """Route back to research if quality is low and retries remain."""
    if (
        state["quality_score"] < QUALITY_THRESHOLD
        and state["retry_count"] < MAX_RETRIES
    ):
        return "retry"
    return "done"


# ── Graph assembly ───────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("research", research_node)
    graph.add_node("editing", editing_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("video", video_node)

    graph.set_entry_point("research")
    graph.add_edge("research", "editing")
    graph.add_edge("editing", "analysis")
    graph.add_conditional_edges(
        "analysis",
        should_retry,
        {
            "retry": "research",
            "done": "video",
        },
    )
    graph.add_edge("video", END)

    return graph.compile()


app = build_graph()
