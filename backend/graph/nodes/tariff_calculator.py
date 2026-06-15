"""
Tariff calculator — authoritative hts_nodes rates + PolicyEngine (Rule 1 & 2).
Never reads rates from vector metadata.
"""

from uuid import UUID

from backend.core.deps import get_deps
from backend.graph.state import TradeQueryState
from backend.tariff.policy_engine import PolicyEngine


def tariff_calculator(state: TradeQueryState) -> TradeQueryState:
    release_id_str = state.get("release_id", "")
    if not release_id_str:
        return {
            **state,
            "error": "tariff_calculator: no active release",
            "applicable_rate": "Rate not found",
            "rate_basis": "unknown",
        }

    deps = get_deps()
    release_id = UUID(release_id_str)

    rate_record = deps.hts_nodes.get_rates(
        release_id,
        state.get("selected_hts_code", ""),
        state.get("selected_heading", ""),
    )

    if not rate_record:
        return {
            **state,
            "general_rate": "",
            "special_rate": "",
            "other_rate": "",
            "applicable_rate": "Rate not found — check HTS directly",
            "rate_basis": "unknown",
            "total_rate_estimate": "",
            "rate_source": "none",
        }

    policy_engine = PolicyEngine(deps.policy)
    duty = policy_engine.calculate(
        rate_record=rate_record,
        origin_country=state.get("origin_country", ""),
        chapter=state.get("selected_chapter", ""),
        customs_value=state.get("customs_value"),
    )

    return {
        **state,
        "policy_version": policy_engine.get_policy_version(),
        "general_rate": duty.general_rate,
        "special_rate": duty.special_rate,
        "other_rate": duty.other_rate,
        "applicable_rate": duty.applicable_rate,
        "rate_basis": duty.rate_basis,
        "section_301": duty.section_301,
        "section_301_rate": duty.section_301_rate,
        "ieepa_applies": duty.ieepa_applies,
        "ieepa_rate": duty.ieepa_rate,
        "ieepa_note": duty.ieepa_note,
        "total_rate_estimate": duty.total_rate_estimate,
        "duty_usd": duty.duty_usd,
        "rate_source": rate_record.rate_source,
    }
