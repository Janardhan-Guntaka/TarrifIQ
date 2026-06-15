"""HTS release lifecycle repository."""

from datetime import date
from typing import Any
from uuid import UUID

from backend.db.connection import get_connection


class ReleaseRepository:
    def get_active(self) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, version, status, effective_date, s3_key, sha256,
                       created_at, activated_at
                FROM hts_releases
                WHERE status = 'active'
                ORDER BY activated_at DESC NULLS LAST
                LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None

    def get_by_version(self, version: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, version, status, effective_date, s3_key, sha256,
                       created_at, activated_at
                FROM hts_releases
                WHERE version = %s
                """,
                (version,),
            ).fetchone()
        return dict(row) if row else None

    def create(
        self,
        version: str,
        *,
        effective_date: date | None = None,
        s3_key: str | None = None,
        sha256: str | None = None,
        status: str = "processing",
    ) -> UUID:
        with get_connection() as conn:
            row = conn.execute(
                """
                INSERT INTO hts_releases (version, status, effective_date, s3_key, sha256)
                VALUES (%s, %s::release_status, %s, %s, %s)
                RETURNING id
                """,
                (version, status, effective_date, s3_key, sha256),
            ).fetchone()
            conn.commit()
        return row["id"]

    def list_all(self, limit: int = 50) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, version, status, effective_date, activated_at, created_at
                FROM hts_releases
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def activate(self, release_id: UUID) -> None:
        """Atomically archive current active and activate the given release."""
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE hts_releases
                SET status = 'archived'
                WHERE status = 'active'
                """
            )
            conn.execute(
                """
                UPDATE hts_releases
                SET status = 'active', activated_at = NOW()
                WHERE id = %s
                """,
                (release_id,),
            )
            conn.commit()

    def mark_failed(self, release_id: UUID, error_message: str = "") -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE hts_releases
                SET status = 'failed'
                WHERE id = %s
                """,
                (release_id,),
            )
            conn.commit()

    def create_ingestion_run(self, release_id: UUID, github_run_id: str | None = None) -> UUID:
        with get_connection() as conn:
            row = conn.execute(
                """
                INSERT INTO ingestion_runs (release_id, github_run_id, status, started_at)
                VALUES (%s, %s, 'running', NOW())
                RETURNING id
                """,
                (release_id, github_run_id),
            ).fetchone()
            conn.commit()
        return row["id"]

    def update_ingestion_run(
        self,
        run_id: UUID,
        *,
        status: str,
        step: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE ingestion_runs
                SET status = %s,
                    step = COALESCE(%s, step),
                    error_message = %s,
                    completed_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE completed_at END
                WHERE id = %s
                """,
                (status, step, error_message, status, run_id),
            )
            conn.commit()
