from graph.state import AgentState
from tools.carousel_generator import generate_carousel
from tools.progress import emit


def carousel_node(state: AgentState) -> AgentState:
    topic = state["topic"]
    print(f"\n[carousel] Generating slides for: {topic}")
    emit("STEP:carousel")

    try:
        paths = generate_carousel(topic, state["content_brief"])
        print(f"[carousel] Done — {len(paths)} slides")
        emit("DONE:carousel")
        return {**state, "carousel_paths": paths}
    except Exception as e:
        import traceback
        print(f"[carousel] ERROR: {e}")
        traceback.print_exc()
        emit("NOTE:Carousel generation failed — check logs")
        emit("DONE:carousel")
        return {**state, "carousel_paths": []}
