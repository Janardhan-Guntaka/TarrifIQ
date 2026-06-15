"""Retrieve legal notes for context only — does not affect rate calculation."""

from uuid import UUID

from backend.core.deps import get_deps
from backend.graph.state import TradeQueryState


def legal_notes_retriever(state: TradeQueryState) -> TradeQueryState:
    if state.get("escalate") or state.get("error"):
        return state

    release_id_str = state.get("release_id", "")
    if not release_id_str:
        return {**state, "legal_notes": []}

    search_term = (
        state.get("hts_search_term")
        or state.get("product_description", "")
    )
    chapter = state.get("selected_chapter", "") or state.get("chapter_hint", "")

    deps = get_deps()
    try:
        hits = deps.vector.search_legal_notes(
            UUID(release_id_str),
            search_term,
            n=4,
            chapter=chapter,
        )
        notes = [
            {
                "document": h.document[:500],
                "metadata": h.metadata,
                "score": h.score,
            }
            for h in hits
        ]
    except Exception:
        notes = []

    return {**state, "legal_notes": notes}
