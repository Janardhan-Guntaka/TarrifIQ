"""LangGraph pipeline — V2 with legal notes retriever."""

from langgraph.graph import END, START, StateGraph

from backend.graph.nodes.hts_classifier import hts_classifier
from backend.graph.nodes.legal_notes_retriever import legal_notes_retriever
from backend.graph.nodes.query_analyzer import query_analyzer
from backend.graph.nodes.synthesizer import synthesizer
from backend.graph.nodes.tariff_calculator import tariff_calculator
from backend.graph.state import TradeQueryState, empty_state

_compiled = None


def route_after_classifier(state: TradeQueryState) -> str:
    if state.get("escalate") or state.get("error"):
        return "synthesizer"
    return "legal_notes_retriever"


def build_graph() -> StateGraph:
    graph = StateGraph(TradeQueryState)

    graph.add_node("query_analyzer", query_analyzer)
    graph.add_node("hts_classifier", hts_classifier)
    graph.add_node("legal_notes_retriever", legal_notes_retriever)
    graph.add_node("tariff_calculator", tariff_calculator)
    graph.add_node("synthesizer", synthesizer)

    graph.add_edge(START, "query_analyzer")
    graph.add_edge("query_analyzer", "hts_classifier")
    graph.add_conditional_edges(
        "hts_classifier",
        route_after_classifier,
        {
            "legal_notes_retriever": "legal_notes_retriever",
            "synthesizer": "synthesizer",
        },
    )
    graph.add_edge("legal_notes_retriever", "tariff_calculator")
    graph.add_edge("tariff_calculator", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph


def get_compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph().compile()
    return _compiled


def run_pipeline(state: TradeQueryState) -> TradeQueryState:
    graph = get_compiled_graph()
    return graph.invoke(state)
