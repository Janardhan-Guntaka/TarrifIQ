"""
HTS classifier — pgvector retrieval + GRI-style deterministic selection.
Preserves logic from graph/nodes/hts_classifier.py.
"""

from uuid import UUID

from backend.core.deps import get_deps
from backend.core.types import RetrievalHit
from backend.graph.state import TradeQueryState

MIN_CONFIDENCE = 0.35
AMBIGUITY_GAP = 0.005
HEADING_THRESHOLD = 0.40
SPECIAL_CHAPTERS = {"98", "99"}


def _hits_to_dicts(hits: list[RetrievalHit]) -> list[dict]:
    return [h.to_dict() for h in hits]


def build_gri_reasoning(
    heading_results: list[dict],
    node_results: list[dict],
    selected_code: str,
    selected_heading: str,
) -> str:
    lines = ["GRI Analysis:"]
    top_heading = heading_results[0] if heading_results else None
    top_node = node_results[0] if node_results else None

    if top_heading and top_heading["score"] >= HEADING_THRESHOLD:
        h = top_heading["metadata"].get("heading", "")
        lines.append(
            f"Rule 1: Heading {h} matches by description "
            f"(score {top_heading['score']:.3f} ≥ {HEADING_THRESHOLD})."
        )
    else:
        lines.append(
            f"Rule 1: No heading match above {HEADING_THRESHOLD} threshold. "
            f"Proceeding to Rule 2."
        )

    if top_node:
        lines.append(
            f"Rule 2/3: Most specific matching subheading/statistical item: "
            f"{selected_code} (score {top_node['score']:.3f})."
        )

    if len(node_results) >= 2:
        gap = node_results[0]["score"] - node_results[1]["score"]
        if gap < AMBIGUITY_GAP:
            lines.append(
                f"Note: Top two candidates within {gap:.3f} of each other — "
                f"classification may be ambiguous."
            )

    return " ".join(lines)


def select_best_code(
    heading_results: list[dict],
    node_results: list[dict],
) -> tuple[str, str, str, float]:
    if not node_results and not heading_results:
        return "", "", "", 0.0

    ch99_score = 0.0
    for r in node_results:
        if r["metadata"].get("chapter") in SPECIAL_CHAPTERS:
            ch99_score = max(ch99_score, r["score"])

    preferred = [
        r for r in node_results
        if r["metadata"].get("node_type") in ("tariff_item", "statistical", "subheading")
        and r["metadata"].get("chapter") not in SPECIAL_CHAPTERS
    ]

    if not preferred:
        preferred = [
            r for r in node_results
            if r["metadata"].get("chapter") not in SPECIAL_CHAPTERS
        ]

    if not preferred:
        if heading_results:
            top = heading_results[0]
            m = top["metadata"]
            conf = max(top["score"], ch99_score * 0.9)
            return "", m.get("heading", ""), m.get("chapter", ""), conf
        return "", "", "", 0.0

    top = preferred[0]
    meta = top["metadata"]
    hts_code = meta.get("hts_code", "")
    heading = meta.get("heading", "")
    chapter = meta.get("chapter", "")
    score = top["score"]

    if ch99_score > score:
        score = min(1.0, score + (ch99_score - score) * 0.5)

    heading_chapters = {r["metadata"].get("chapter") for r in heading_results[:3]}
    if chapter in heading_chapters:
        score = min(1.0, score + 0.04)

    return hts_code, heading, chapter, score


def hts_classifier(state: TradeQueryState) -> TradeQueryState:
    search_term = state.get("hts_search_term") or state.get("product_description", "")
    chapter_hint = state.get("chapter_hint", "")
    release_id_str = state.get("release_id", "")

    if not release_id_str:
        return {
            **state,
            "error": "hts_classifier: no active HTS release",
            "escalate": True,
            "escalate_reason": "HTS data not loaded — run ingestion first",
        }

    release_id = UUID(release_id_str)
    deps = get_deps()

    try:
        heading_hits = deps.vector.search_headings(
            release_id, search_term, n=5, chapter=chapter_hint
        )
        heading_results = _hits_to_dicts(heading_hits)

        top_chapter = ""
        if heading_results and heading_results[0]["score"] >= HEADING_THRESHOLD:
            top_chapter = heading_results[0]["metadata"].get("chapter", "")

        node_hits = deps.vector.search_nodes(
            release_id, search_term, n=8, chapter=top_chapter
        )
        node_results = _hits_to_dicts(node_hits)

        if not node_results or node_results[0]["score"] < 0.60:
            broad_hits = deps.vector.search_nodes(release_id, search_term, n=8)
            broad_results = _hits_to_dicts(broad_hits)
            if broad_results and (
                not node_results
                or broad_results[0]["score"] > node_results[0]["score"]
            ):
                node_results = broad_results

    except Exception as e:
        return {
            **state,
            "error": f"hts_classifier: vector search error: {e}",
            "escalate": True,
            "escalate_reason": "Vector store unavailable",
        }

    hts_code, heading, chapter, confidence = select_best_code(
        heading_results, node_results
    )

    escalate = False
    escalate_reason = ""

    if confidence < MIN_CONFIDENCE:
        escalate = True
        escalate_reason = (
            f"Low classification confidence ({confidence:.2f} < {MIN_CONFIDENCE}). "
            f"Product description may be too vague or span multiple HTS chapters."
        )
    elif chapter in SPECIAL_CHAPTERS:
        escalate = True
        escalate_reason = (
            f"Classified into Chapter {chapter} (special provisions). "
            f"These require case-by-case customs determination."
        )
    elif len(node_results) >= 2:
        gap = node_results[0]["score"] - node_results[1]["score"]
        if gap < AMBIGUITY_GAP and confidence < 0.40:
            escalate = True
            escalate_reason = (
                f"Top two HTS candidates within {gap:.3f} score gap. "
                f"Classification is genuinely ambiguous — consult a licensed broker."
            )

    reasoning = build_gri_reasoning(
        heading_results, node_results, hts_code, heading
    )

    return {
        **state,
        "candidate_headings": heading_results,
        "candidate_nodes": node_results,
        "selected_hts_code": hts_code,
        "selected_heading": heading,
        "selected_chapter": chapter,
        "classification_reasoning": reasoning,
        "confidence_score": round(confidence, 4),
        "escalate": escalate,
        "escalate_reason": escalate_reason,
    }
