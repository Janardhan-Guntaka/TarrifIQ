"""Orchestrates classify requests with audit logging."""

import time
from typing import Any
from uuid import UUID

from backend.core.deps import get_deps
from backend.graph.pipeline import run_pipeline
from backend.graph.state import empty_state


class QueryService:
    def classify(
        self,
        *,
        raw_query: str,
        country: str | None = None,
        customs_value: float | None = None,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        deps = get_deps()
        active = deps.releases.get_active()
        if not active:
            raise RuntimeError(
                "No active HTS release. Run ingestion and activate a release first."
            )

        policy_version = deps.policy.get_composite_version()
        full_query = raw_query.strip()
        if country and country.lower() not in full_query.lower():
            full_query = f"{full_query} from {country}"
        if customs_value is not None:
            full_query = f"{full_query} (customs value ${customs_value:,.0f})"

        initial = empty_state(
            full_query,
            customs_value=customs_value,
            release_id=str(active["id"]),
            hts_release=active["version"],
            policy_version=policy_version,
            user_id=str(user_id) if user_id else "",
        )
        if country:
            initial["origin_country"] = country

        t0 = time.perf_counter()
        result = run_pipeline(initial)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        response = self._build_response(result, latency_ms)

        retrieval_candidates = {
            "headings": result.get("candidate_headings", []),
            "nodes": result.get("candidate_nodes", []),
            "legal_notes": result.get("legal_notes", []),
        }

        query_id = deps.queries.create(
            user_id=user_id,
            raw_query=raw_query,
            country=result.get("origin_country") or country,
            customs_value=customs_value,
            selected_hts_code=result.get("selected_hts_code", ""),
            confidence=float(result.get("confidence_score", 0)),
            policy_version=result.get("policy_version", policy_version),
            hts_release=result.get("hts_release", active["version"]),
            response_json=response,
            retrieval_candidates=retrieval_candidates,
            latency_ms=latency_ms,
            escalate=bool(result.get("escalate")),
        )

        response["query_id"] = str(query_id)
        return response

    @staticmethod
    def _build_response(state: dict[str, Any], latency_ms: int) -> dict[str, Any]:
        return {
            "release_version": state.get("hts_release", ""),
            "policy_version": state.get("policy_version", ""),
            "classification": {
                "hts_code": state.get("selected_hts_code", ""),
                "heading": state.get("selected_heading", ""),
                "chapter": state.get("selected_chapter", ""),
                "confidence_pct": int(state.get("confidence_score", 0) * 100),
                "product_description": state.get("product_description", ""),
                "origin_country": state.get("origin_country", ""),
                "reasoning": state.get("classification_reasoning", ""),
                "escalate": state.get("escalate", False),
                "escalate_reason": state.get("escalate_reason", ""),
                "rate_source": state.get("rate_source", ""),
            },
            "duty": {
                "general_rate": state.get("general_rate", ""),
                "special_rate": state.get("special_rate", ""),
                "applicable_rate": state.get("applicable_rate", ""),
                "rate_basis": state.get("rate_basis", ""),
                "section_301": state.get("section_301", False),
                "section_301_rate": state.get("section_301_rate", ""),
                "ieepa": state.get("ieepa_applies", False),
                "ieepa_rate": state.get("ieepa_rate", ""),
                "ieepa_note": state.get("ieepa_note", ""),
                "total_rate": state.get("total_rate_estimate", ""),
                "duty_usd": state.get("duty_usd"),
            },
            "legal_notes": state.get("legal_notes", []),
            "explanation": state.get("final_answer", ""),
            "sources": state.get("citations", []),
            "disclaimer": state.get("disclaimer", ""),
            "meta": {
                "latency_ms": latency_ms,
                "off_topic": state.get("in_domain") is False,
                "models": {
                    "embed": get_deps().embedding_service.model_name,
                    "llm": get_deps().llm_service.model_name,
                },
            },
        }
