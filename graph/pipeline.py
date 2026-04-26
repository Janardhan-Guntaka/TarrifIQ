"""
graph/pipeline.py
-----------------
Assembles the LangGraph StateGraph for trade query processing.

Flow:
  START
    │
    ▼
  query_analyzer          extracts product, origin, trade scenario
    │
    ▼
  hts_classifier          searches vector store, selects HTS code
    │
    ├─(escalate=True)──→  synthesizer   (escalation answer)
    │
    ▼
  tariff_calculator       looks up rates, checks FTA + Section 301
    │
    ▼
  synthesizer             generates final answer
    │
    ▼
  END

Usage:
    from graph.pipeline import run

    result = run("gaming laptop from China, what's the import duty?")
    print(result["final_answer"])
    print(result["citations"])
"""

from langgraph.graph import StateGraph, START, END

from graph.state import TradeQueryState, empty_state
from graph.nodes.query_analyzer   import query_analyzer
from graph.nodes.hts_classifier   import hts_classifier
from graph.nodes.tariff_calculator import tariff_calculator
from graph.nodes.synthesizer      import synthesizer


# ── routing function ──────────────────────────────────────────────────────────

def route_after_classifier(state: TradeQueryState) -> str:
    """
    After hts_classifier: if escalate flag is set, skip tariff_calculator
    and go straight to synthesizer (which handles the escalation message).
    """
    if state.get("escalate") or state.get("error"):
        return "synthesizer"
    return "tariff_calculator"


# ── build graph ───────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(TradeQueryState)

    # add nodes
    graph.add_node("query_analyzer",    query_analyzer)
    graph.add_node("hts_classifier",    hts_classifier)
    graph.add_node("tariff_calculator", tariff_calculator)
    graph.add_node("synthesizer",       synthesizer)

    # add edges
    graph.add_edge(START, "query_analyzer")
    graph.add_edge("query_analyzer", "hts_classifier")

    # conditional edge: escalate OR continue
    graph.add_conditional_edges(
        "hts_classifier",
        route_after_classifier,
        {
            "tariff_calculator": "tariff_calculator",
            "synthesizer":       "synthesizer",
        },
    )

    graph.add_edge("tariff_calculator", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph


# ── compiled graph (singleton) ────────────────────────────────────────────────

_compiled = None

def get_compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph().compile()
    return _compiled


# ── public run function ───────────────────────────────────────────────────────

def run(raw_query: str) -> TradeQueryState:
    """
    Run the full pipeline for a trade query.
    Returns the complete final state.

    Example:
        result = run("gaming laptop from China")
        print(result["final_answer"])
        print(result["total_rate_estimate"])
        print(result["selected_hts_code"])
    """
    graph = get_compiled_graph()
    initial_state = empty_state(raw_query)
    return graph.invoke(initial_state)


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
            "gaming laptop imported from China, what is the import duty?"

    print(f"Query: {query}")
    print("─" * 60)

    result = run(query)

    print(f"\n[ANALYZER]")
    print(f"  Product      : {result['product_description']}")
    print(f"  HTS term     : {result['hts_search_term']}")
    print(f"  Origin       : {result['origin_country']}")
    print(f"  Scenario     : {result['trade_scenario']}")
    print(f"  Notes        : {result['analyzer_notes']}")

    print(f"\n[CLASSIFIER]")
    print(f"  HTS Code     : {result['selected_hts_code']}")
    print(f"  Heading      : {result['selected_heading']}")
    print(f"  Chapter      : {result['selected_chapter']}")
    print(f"  Confidence   : {result['confidence_score']:.0%}")
    print(f"  Escalate     : {result['escalate']}")
    if result['escalate']:
        print(f"  Reason       : {result['escalate_reason']}")

    print(f"\n[TARIFF]")
    print(f"  General rate : {result['general_rate']}")
    print(f"  Applicable   : {result['applicable_rate']} ({result['rate_basis']})")
    print(f"  Section 301  : {result['section_301']} {result['section_301_rate']}")
    print(f"  Total est.   : {result['total_rate_estimate']}")

    print(f"\n[ANSWER]")
    print(result["final_answer"])

    print(f"\n[CITATIONS]")
    for c in result["citations"]:
        print(f"  • {c}")

    print(f"\n[DISCLAIMER]")
    print(result["disclaimer"])