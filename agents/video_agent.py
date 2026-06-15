from graph.state import AgentState
from tools.progress import emit


def video_node(state: AgentState) -> AgentState:
    emit("STEP:video")
    # video generation disabled
    emit("DONE:video")
    return {**state, "video_path": None}
