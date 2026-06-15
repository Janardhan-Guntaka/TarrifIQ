"""Vector repository protocol (Chroma removed from production path)."""

from typing import Protocol
from uuid import UUID

from backend.core.types import RetrievalHit


class VectorRepository(Protocol):
    def search_headings(
        self, release_id: UUID, query_text: str, n: int = 5, chapter: str = ""
    ) -> list[RetrievalHit]: ...

    def search_nodes(
        self, release_id: UUID, query_text: str, n: int = 8, chapter: str = ""
    ) -> list[RetrievalHit]: ...

    def search_legal_notes(
        self, release_id: UUID, query_text: str, n: int = 4, chapter: str = ""
    ) -> list[RetrievalHit]: ...
