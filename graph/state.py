"""
graph/state.py
--------------
Defines TradeQueryState — the single shared state object that passes
through every node in the LangGraph pipeline.

Every node receives this state, reads what it needs, writes its results,
and returns the updated state. Nothing is stored outside this object
during a single query run.

Flow:
  query_analyzer → hts_classifier → tariff_calculator → synthesizer
                                  ↘ (low confidence)  → escalate
"""

from typing import TypedDict, Optional


class TradeQueryState(TypedDict):

    # ── raw input ─────────────────────────────────────────────────────────────
    raw_query:          str           # exactly what the user typed

    # ── extracted by query_analyzer ──────────────────────────────────────────
    product_description: str          # normalized product description
    hts_search_term:    str           # rephrased for HTS legal vocabulary
    chapter_hint:       str           # 2-digit chapter hint e.g. "85" for electronics
    origin_country:     str           # e.g. "China", "Mexico", ""
    destination:        str           # always "US" for now
    trade_scenario:     str           # "import_duty" | "fta_check" | "origin_check"
    analyzer_notes:     str           # reasoning from analyzer (for debug)

    # ── set by hts_classifier ─────────────────────────────────────────────────
    candidate_headings:  list[dict]   # top heading matches from vector store
    candidate_nodes:     list[dict]   # top node matches from vector store
    selected_hts_code:   str          # best HTS code e.g. "8471.30.01.00"
    selected_heading:    str          # 4-digit heading e.g. "8471"
    selected_chapter:    str          # 2-digit chapter e.g. "84"
    classification_reasoning: str     # GRI rule chain reasoning
    confidence_score:    float        # 0.0 - 1.0

    # ── set by tariff_calculator ──────────────────────────────────────────────
    general_rate:        str          # MFN duty rate e.g. "Free" or "6.7%"
    special_rate:        str          # FTA rates string
    other_rate:          str          # Column 2 rate
    applicable_rate:     str          # final rate after FTA check
    rate_basis:          str          # "MFN" | "USMCA" | "FTA" | "Column2"
    section_301:         bool         # True if China Section 301 applies
    section_301_rate:    str          # additional tariff if applicable
    total_rate_estimate: str          # combined rate e.g. "7.5% + 25% = 32.5%"

    # ── set by synthesizer ────────────────────────────────────────────────────
    final_answer:        str          # full natural language answer
    citations:           list[str]    # HTS codes and rule references cited
    disclaimer:          str          # legal disclaimer appended to every answer

    # ── routing flags ─────────────────────────────────────────────────────────
    escalate:            bool         # True → route to "consult broker" message
    escalate_reason:     str          # why escalation was triggered
    error:               str          # non-empty if a node failed


def empty_state(raw_query: str) -> TradeQueryState:
    """Return a fresh state with only raw_query populated."""
    return TradeQueryState(
        raw_query           = raw_query,
        product_description = "",
        hts_search_term     = "",
        chapter_hint        = "",
        origin_country      = "",
        destination         = "US",
        trade_scenario      = "import_duty",
        analyzer_notes      = "",
        candidate_headings  = [],
        candidate_nodes     = [],
        selected_hts_code   = "",
        selected_heading    = "",
        selected_chapter    = "",
        classification_reasoning = "",
        confidence_score    = 0.0,
        general_rate        = "",
        special_rate        = "",
        other_rate          = "",
        applicable_rate     = "",
        rate_basis          = "",
        section_301         = False,
        section_301_rate    = "",
        total_rate_estimate = "",
        final_answer        = "",
        citations           = [],
        disclaimer          = (
            "DISCLAIMER: This is an informational estimate only and does not "
            "constitute a binding tariff classification or legal advice. "
            "Duty rates may vary based on transaction value, country of origin "
            "documentation, and other factors. For a binding ruling, submit a "
            "ruling request to U.S. Customs and Border Protection at "
            "rulings.cbp.gov."
        ),
        escalate            = False,
        escalate_reason     = "",
        error               = "",
    )