"""pgvector retrieval repository (Rule 3 — retrieval only)."""

from typing import Any
from uuid import UUID

from backend.core.types import RetrievalHit
from backend.db.connection import get_connection
from backend.services.embedding_service import OpenAIEmbeddingService


class PgVectorRepository:
    DOC_NODE = "node"
    DOC_HEADING = "heading_summary"
    DOC_LEGAL = "legal_note"

    def __init__(self, embedding_service: OpenAIEmbeddingService) -> None:
        self._embed = embedding_service

    def search(
        self,
        release_id: UUID,
        query_text: str,
        *,
        doc_type: str,
        n: int = 5,
        chapter: str = "",
        node_type: str = "",
    ) -> list[RetrievalHit]:
        query_vector = self._embed.embed_query(query_text)

        conditions = ["release_id = %(release_id)s", "doc_type = %(doc_type)s"]
        params: dict[str, Any] = {
            "release_id": release_id,
            "doc_type": doc_type,
            "embedding": query_vector,
            "limit": n,
        }

        if chapter:
            conditions.append("metadata->>'chapter' = %(chapter)s")
            params["chapter"] = chapter
        if node_type:
            conditions.append("metadata->>'node_type' = %(node_type)s")
            params["node_type"] = node_type

        where_sql = " AND ".join(conditions)

        sql = f"""
            SELECT chunk_text, metadata,
                   1 - (embedding <=> %(embedding)s::vector) AS score
            FROM hts_embeddings
            WHERE {where_sql}
            ORDER BY embedding <=> %(embedding)s::vector
            LIMIT %(limit)s
        """

        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        hits: list[RetrievalHit] = []
        for row in rows:
            meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
            hits.append(
                RetrievalHit(
                    document=row["chunk_text"] or "",
                    metadata=meta,
                    score=round(float(row["score"] or 0), 4),
                )
            )
        return hits

    def search_headings(
        self, release_id: UUID, query_text: str, n: int = 5, chapter: str = ""
    ) -> list[RetrievalHit]:
        return self.search(
            release_id, query_text, doc_type=self.DOC_HEADING, n=n, chapter=chapter
        )

    def search_nodes(
        self, release_id: UUID, query_text: str, n: int = 8, chapter: str = ""
    ) -> list[RetrievalHit]:
        return self.search(
            release_id, query_text, doc_type=self.DOC_NODE, n=n, chapter=chapter
        )

    def search_legal_notes(
        self, release_id: UUID, query_text: str, n: int = 4, chapter: str = ""
    ) -> list[RetrievalHit]:
        return self.search(
            release_id, query_text, doc_type=self.DOC_LEGAL, n=n, chapter=chapter
        )

    def bulk_insert_embeddings(
        self,
        release_id: UUID,
        records: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """Insert embedding rows. Each record: chunk_id, doc_type, chunk_text, embedding, metadata, hts_code."""
        if not records:
            return 0

        sql = """
            INSERT INTO hts_embeddings (
                release_id, chunk_id, hts_code, doc_type, chunk_text, embedding, metadata
            ) VALUES (
                %(release_id)s, %(chunk_id)s, %(hts_code)s, %(doc_type)s,
                %(chunk_text)s, %(embedding)s::vector, %(metadata)s::jsonb
            )
            ON CONFLICT (release_id, chunk_id) DO UPDATE SET
                chunk_text = EXCLUDED.chunk_text,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata
        """
        count = 0
        with get_connection() as conn:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                for r in batch:
                    r["release_id"] = release_id
                conn.cursor().executemany(sql, batch)
                count += len(batch)
            conn.commit()
        return count

    def count_for_release(self, release_id: UUID) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM hts_embeddings WHERE release_id = %s",
                (release_id,),
            ).fetchone()
        return int(row["c"]) if row else 0
