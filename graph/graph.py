from langgraph.graph import END, StateGraph

from agents.analysis_agent import analysis_node
from agents.carousel_agent import carousel_node
from agents.research_agent import research_node
from agents.validation_agent import should_rewrite, validation_node
from agents.video_agent import video_node
from config import MAX_RETRIES, QUALITY_THRESHOLD
from graph.state import AgentState


def should_retry(state: AgentState) -> str:
    if (
        state["quality_score"] < QUALITY_THRESHOLD
        and state["retry_count"] < MAX_RETRIES
    ):
        return "retry"
    return "validate"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("research", research_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("validation", validation_node)
    graph.add_node("carousel", carousel_node)
    graph.add_node("video", video_node)

    graph.set_entry_point("research")
    graph.add_edge("research", "analysis")

    graph.add_conditional_edges(
        "analysis",
        should_retry,
        {"retry": "research", "validate": "validation"},
    )

    graph.add_conditional_edges(
        "validation",
        should_rewrite,
        {"rewrite": "analysis", "done": "carousel"},
    )

    graph.add_edge("carousel", "video")
    graph.add_edge("video", END)

    return graph.compile()


app = build_graph()
