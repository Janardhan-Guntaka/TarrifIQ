"""Query history and audit persistence (Rule 4)."""

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from backend.db.connection import get_connection


class QueryRepository:
    def create(
        self,
        *,
        user_id: UUID | None,
        raw_query: str,
        country: str | None,
        customs_value: float | None,
        selected_hts_code: str,
        confidence: float,
        policy_version: str,
        hts_release: str,
        response_json: dict[str, Any],
        retrieval_candidates: dict[str, Any],
        latency_ms: int,
        escalate: bool,
    ) -> UUID:
        with get_connection() as conn:
            row = conn.execute(
                """
                INSERT INTO queries (
                    user_id, raw_query, country, customs_value,
                    selected_hts_code, confidence, policy_version, hts_release,
                    response_json, retrieval_candidates, latency_ms, escalate
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s, %s
                )
                RETURNING id
                """,
                (
                    user_id,
                    raw_query,
                    country,
                    Decimal(str(customs_value)) if customs_value is not None else None,
                    selected_hts_code,
                    confidence,
                    policy_version,
                    hts_release,
                    json.dumps(response_json),
                    json.dumps(retrieval_candidates),
                    latency_ms,
                    escalate,
                ),
            ).fetchone()
            conn.commit()
        return row["id"]

    def list_for_user(self, user_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, raw_query, country, selected_hts_code, confidence,
                       hts_release, latency_ms, escalate, created_at, response_json
                FROM queries
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_id(self, query_id: UUID, user_id: UUID | None = None) -> dict[str, Any] | None:
        with get_connection() as conn:
            if user_id:
                row = conn.execute(
                    """
                    SELECT * FROM queries WHERE id = %s AND user_id = %s
                    """,
                    (query_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM queries WHERE id = %s",
                    (query_id,),
                ).fetchone()
        return dict(row) if row else None
