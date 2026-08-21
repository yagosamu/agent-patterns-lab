"""The supervisor node and the routing function."""

from langchain_core.messages import HumanMessage, SystemMessage
from src import state
from src.config import MAX_STEPS, MODEL_SUPERVISOR, make_llm
from src.prompts import SUPERVISOR_PROMPT
from src.state import ContentState, Route


# Low temperature: routing should be deterministic, not creative.
_router = make_llm(MODEL_SUPERVISOR, temperature=0.0).with_structured_output(Route)

def _status(state: ContentState) -> str:
    """Plain-English snapshot of progress for the supervisor to reason over."""

    verdict = state.get("editor_verdict", "none")

    return (
            f"research done:{bool(state.get('research'))}\n"
            f"draft done:{bool(state.get('draft'))}\n"
            f"edited done:{bool(state.get('edited'))}\n"
            f"editor verdict:{verdict}\n"
            f"revisions so far:{state.get('revision_count', 0)}\n"
            f"seo done:{bool(state.get('seo'))}"
    )


def supervisor_node(state: ContentState) -> dict:
    """Decide which agent runs next, or FINISH."""

    step = state.get("step", 0) + 1
    # Safety valve: never route past the cap.
    if step > MAX_STEPS:
        return {
            "next": "FINISH",
            "step": step,
            "history": [f"supervisor: hit MAX_STEPS ({MAX_STEPS}), finishing"],
        }
    
    user = f"Topic:{state['topic']}\n\nCurrent progress:\n{_status(state)}"
    route: Route = _router.invoke(
        [SystemMessage(SUPERVISOR_PROMPT), HumanMessage(user)]
    )
    return {
        "next": route.next,
        "step": step,
        "history": [f"supervisor ->{route.next} ({route.reason})"],
    }


def route_decision(state: ContentState) -> str:
    """Read the supervisor's decision for the conditional edge."""
    
    return state.get("next", "FINISH")
    
    
    