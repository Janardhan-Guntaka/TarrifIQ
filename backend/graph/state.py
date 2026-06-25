"""TradeQueryState — shared LangGraph state (V2)."""

from typing import Any, TypedDict


class TradeQueryState(TypedDict):
    raw_query: str

    product_description: str
    hts_search_term: str
    chapter_hint: str
    origin_country: str
    destination: str
    trade_scenario: str
    analyzer_notes: str
    customs_value: float | None

    release_id: str
    hts_release: str
    policy_version: str

    candidate_headings: list[dict]
    candidate_nodes: list[dict]
    legal_notes: list[dict]
    selected_hts_code: str
    selected_heading: str
    selected_chapter: str
    classification_reasoning: str
    confidence_score: float
    rate_source: str

    general_rate: str
    special_rate: str
    other_rate: str
    applicable_rate: str
    rate_basis: str
    section_301: bool
    section_301_rate: str
    ieepa_applies: bool
    ieepa_rate: str
    ieepa_note: str
    total_rate_estimate: str
    duty_usd: float | None

    final_answer: str
    citations: list[str]
    disclaimer: str

    escalate: bool
    escalate_reason: str
    error: str

    in_domain: bool
    off_topic_message: str

    request_id: str
    user_id: str


DEFAULT_DISCLAIMER = (
    "DISCLAIMER: This is an informational estimate only and does not "
    "constitute a binding tariff classification or legal advice. "
    "Duty rates may vary based on transaction value, country of origin "
    "documentation, and other factors. For a binding ruling, submit a "
    "ruling request to U.S. Customs and Border Protection at "
    "rulings.cbp.gov."
)


def empty_state(
    raw_query: str,
    *,
    customs_value: float | None = None,
    release_id: str = "",
    hts_release: str = "",
    policy_version: str = "",
    user_id: str = "",
    request_id: str = "",
) -> TradeQueryState:
    return TradeQueryState(
        raw_query=raw_query,
        product_description="",
        hts_search_term="",
        chapter_hint="",
        origin_country="",
        destination="US",
        trade_scenario="import_duty",
        analyzer_notes="",
        customs_value=customs_value,
        release_id=release_id,
        hts_release=hts_release,
        policy_version=policy_version,
        candidate_headings=[],
        candidate_nodes=[],
        legal_notes=[],
        selected_hts_code="",
        selected_heading="",
        selected_chapter="",
        classification_reasoning="",
        confidence_score=0.0,
        rate_source="",
        general_rate="",
        special_rate="",
        other_rate="",
        applicable_rate="",
        rate_basis="",
        section_301=False,
        section_301_rate="",
        ieepa_applies=False,
        ieepa_rate="",
        ieepa_note="",
        total_rate_estimate="",
        duty_usd=None,
        final_answer="",
        citations=[],
        disclaimer=DEFAULT_DISCLAIMER,
        escalate=False,
        escalate_reason="",
        error="",
        in_domain=True,
        off_topic_message="",
        request_id=request_id,
        user_id=user_id,
    )
