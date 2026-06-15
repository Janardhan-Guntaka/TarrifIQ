"""Authoritative HTS node and rate lookups (Rule 2)."""

from typing import Any
from uuid import UUID

from backend.core.types import HtsRateRecord
from backend.db.connection import get_connection


class HtsNodeRepository:
    def bulk_insert(self, release_id: UUID, nodes: list[dict[str, Any]], batch_size: int = 500) -> int:
        """Insert parsed nodes for a release. Returns count inserted."""
        if not nodes:
            return 0

        sql = """
            INSERT INTO hts_nodes (
                release_id, hts_code, node_type, parent_code, description,
                general_rate, special_rate, other_rate,
                chapter, heading, subheading, unit_of_qty, indent_level
            ) VALUES (
                %(release_id)s, %(hts_code)s, %(node_type)s, %(parent_code)s, %(description)s,
                %(general_rate)s, %(special_rate)s, %(other_rate)s,
                %(chapter)s, %(heading)s, %(subheading)s, %(unit_of_qty)s, %(indent_level)s
            )
            ON CONFLICT (release_id, hts_code) DO UPDATE SET
                description = EXCLUDED.description,
                general_rate = EXCLUDED.general_rate,
                special_rate = EXCLUDED.special_rate,
                other_rate = EXCLUDED.other_rate,
                parent_code = EXCLUDED.parent_code
        """
        inserted = 0
        with get_connection() as conn:
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i : i + batch_size]
                for n in batch:
                    n["release_id"] = release_id
                conn.cursor().executemany(sql, batch)
                inserted += len(batch)
            conn.commit()
        return inserted

    def get_rates(
        self,
        release_id: UUID,
        hts_code: str,
        heading: str = "",
    ) -> HtsRateRecord | None:
        """
        Exact lookup by hts_code. Falls back to best tariff_item/statistical
        in same heading — never uses vector metadata.
        """
        code = (hts_code or "").strip()
        if not code:
            return self._heading_fallback(release_id, heading)

        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT hts_code, heading, chapter, node_type, description,
                       general_rate, special_rate, other_rate
                FROM hts_nodes
                WHERE release_id = %s AND hts_code = %s
                """,
                (release_id, code),
            ).fetchone()

        if row and (row["general_rate"] or row["special_rate"]):
            return HtsRateRecord(
                hts_code=row["hts_code"],
                heading=row["heading"] or "",
                chapter=row["chapter"] or "",
                node_type=row["node_type"] or "",
                general_rate=row["general_rate"] or "",
                special_rate=row["special_rate"] or "",
                other_rate=row["other_rate"] or "",
                description=row["description"] or "",
                rate_source="exact",
            )

        return self._heading_fallback(release_id, heading or (row["heading"] if row else ""))

    def _heading_fallback(self, release_id: UUID, heading: str) -> HtsRateRecord | None:
        if not heading:
            return None

        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT hts_code, heading, chapter, node_type, description,
                       general_rate, special_rate, other_rate
                FROM hts_nodes
                WHERE release_id = %s
                  AND heading = %s
                  AND node_type IN ('tariff_item', 'statistical')
                  AND general_rate IS NOT NULL
                  AND general_rate <> ''
                ORDER BY length(hts_code) DESC
                LIMIT 1
                """,
                (release_id, heading),
            ).fetchone()

        if not row:
            return None

        return HtsRateRecord(
            hts_code=row["hts_code"],
            heading=row["heading"] or "",
            chapter=row["chapter"] or "",
            node_type=row["node_type"] or "",
            general_rate=row["general_rate"] or "",
            special_rate=row["special_rate"] or "",
            other_rate=row["other_rate"] or "",
            description=row["description"] or "",
            rate_source="heading_fallback",
        )

    def count_for_release(self, release_id: UUID) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM hts_nodes WHERE release_id = %s",
                (release_id,),
            ).fetchone()
        return int(row["c"]) if row else 0
