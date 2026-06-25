"""Intent guard node — reject off-topic queries before expensive pipeline steps."""

from backend.graph.intent_guard import check_domain
from backend.graph.state import TradeQueryState


def intent_guard(state: TradeQueryState) -> TradeQueryState:
    in_domain, message = check_domain(state["raw_query"])
    if in_domain:
        return {**state, "in_domain": True, "off_topic_message": ""}
    return {
        **state,
        "in_domain": False,
        "off_topic_message": message,
        "final_answer": message,
        "escalate": False,
        "error": "",
    }
