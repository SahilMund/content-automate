from graph.state import AgentState
from tools.video_generator import generate_remotion_video


def video_node(state: AgentState) -> AgentState:
    video_path = generate_remotion_video(state["topic"], state["content_brief"])
    return {**state, "video_path": video_path}
