"""Versioned policy snapshot repository."""

import json
from typing import Any

from backend.db.connection import get_connection


class PolicyRepository:
    def get_active_bundle(self) -> dict[str, dict[str, Any]]:
        """
        Load latest snapshot per policy_type.
        Returns {policy_type: {version, policy_json}}.
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (policy_type)
                    version, policy_type, policy_json, effective_date
                FROM policy_snapshots
                ORDER BY policy_type, effective_date DESC, created_at DESC
                """
            ).fetchall()

        bundle: dict[str, dict[str, Any]] = {}
        for row in rows:
            bundle[row["policy_type"]] = {
                "version": row["version"],
                "policy_json": row["policy_json"],
                "effective_date": row["effective_date"],
            }
        return bundle

    def get_composite_version(self) -> str:
        bundle = self.get_active_bundle()
        parts = sorted(f"{k}:{v['version']}" for k, v in bundle.items())
        return "|".join(parts) if parts else "none"

    def insert_snapshot(
        self,
        version: str,
        policy_type: str,
        policy_json: dict[str, Any],
        effective_date: str | None = None,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO policy_snapshots (version, policy_type, effective_date, policy_json)
                VALUES (%s, %s, COALESCE(%s::date, CURRENT_DATE), %s::jsonb)
                ON CONFLICT (version, policy_type) DO NOTHING
                """,
                (version, policy_type, effective_date, json.dumps(policy_json)),
            )
            conn.commit()
