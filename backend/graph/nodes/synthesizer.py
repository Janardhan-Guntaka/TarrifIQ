"""Response synthesizer — rephrases structured data only (no invented rates)."""

from backend.core.deps import get_deps
from backend.graph.state import DEFAULT_DISCLAIMER, TradeQueryState

SYSTEM_PROMPT = """You are a U.S. customs compliance assistant helping importers understand tariff classifications.

Generate a clear answer based ONLY on the structured data provided.
CRITICAL RULES:
- NEVER say "no additional tariffs" if data shows Section 301 or IEEPA tariffs
- ALWAYS state which country the IEEPA applies to — use the ORIGIN COUNTRY from the data
- The TOTAL ESTIMATED DUTY in the data is authoritative — quote it exactly
- Do not invent or omit any rates
- 3-4 sentences maximum
- End with: "Verify this with your customs broker before importing."
"""


def _build_context(state: TradeQueryState) -> str:
    lines = [
        f"Product: {state.get('product_description', state['raw_query'])}",
        f"Origin country: {state.get('origin_country') or 'not specified'}",
        f"HTS Code: {state.get('selected_hts_code') or 'not determined'}",
        f"HTS Heading: {state.get('selected_heading')}",
        f"Chapter: {state.get('selected_chapter')}",
        f"Classification confidence: {state.get('confidence_score', 0):.0%}",
        f"HTS Release: {state.get('hts_release')}",
        f"MFN general duty rate: {state.get('general_rate') or 'not found'}",
        f"Applicable rate: {state.get('applicable_rate') or 'unknown'} ({state.get('rate_basis')})",
    ]
    if state.get("section_301"):
        lines.append(f"Section 301 additional: {state.get('section_301_rate')}")
    if state.get("ieepa_applies"):
        lines.append(f"IEEPA: {state.get('ieepa_rate')} — {state.get('ieepa_note')}")
    lines.append(f"TOTAL ESTIMATED DUTY: {state.get('total_rate_estimate')}")
    if state.get("duty_usd") is not None:
        lines.append(f"Estimated duty USD: ${state.get('duty_usd'):,.2f}")

    notes = state.get("legal_notes") or []
    if notes:
        lines.append("Legal notes (context only):")
        for n in notes[:3]:
            lines.append(f"  - {n.get('document', '')[:200]}")

    if state.get("escalate"):
        lines.append(f"ESCALATION: {state.get('escalate_reason')}")

    return "\n".join(lines)


def _template_answer(state: TradeQueryState) -> str:
    if state.get("escalate"):
        return (
            f"We could not classify this product with sufficient confidence "
            f"({state.get('confidence_score', 0):.0%}). "
            f"{state.get('escalate_reason', '')} "
            f"Please consult a licensed customs broker."
        )

    code = state.get("selected_hts_code") or "undetermined"
    origin = state.get("origin_country") or "unspecified origin"
    total = state.get("total_rate_estimate") or state.get("applicable_rate") or "unknown"
    return (
        f"Based on HTS {code} for goods from {origin}, "
        f"the estimated total duty is {total}. "
        f"Verify this with your customs broker before importing."
    )


def _build_citations(state: TradeQueryState) -> list[str]:
    cites = []
    if state.get("selected_hts_code"):
        cites.append(f"HTS {state['selected_hts_code']}")
    if state.get("hts_release"):
        cites.append(f"HTS Release {state['hts_release']}")
    if state.get("policy_version"):
        cites.append(f"Policy {state['policy_version']}")
    return cites


def synthesizer(state: TradeQueryState) -> TradeQueryState:
    if state.get("error") and not state.get("escalate"):
        return {
            **state,
            "final_answer": f"An error occurred: {state['error']}",
            "citations": _build_citations(state),
        }

    context = _build_context(state)
    answer = ""

    try:
        deps = get_deps()
        answer = deps.llm_service.chat_text_sync(SYSTEM_PROMPT, context)
    except Exception:
        answer = ""

    if not answer:
        answer = _template_answer(state)

    return {
        **state,
        "final_answer": answer,
        "citations": _build_citations(state),
        "disclaimer": state.get("disclaimer") or DEFAULT_DISCLAIMER,
    }
