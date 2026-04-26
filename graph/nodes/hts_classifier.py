"""
graph/nodes/hts_classifier.py
------------------------------
Node 2 of 4 in the LangGraph pipeline.

Responsibility:
  Use the hts_search_term from query_analyzer to search both ChromaDB
  collections, then apply GRI (General Rules of Interpretation) logic
  to select the best HTS code with a confidence score.

GRI rules applied (simplified for MVP):
  Rule 1: Classification by heading text and section/chapter notes
          → heading match score > 0.65 → use that heading
  Rule 2: If Rule 1 ambiguous → look at tariff_item level matches
  Rule 3: If still ambiguous → pick most specific (longest code) with best score

Escalation triggers:
  - confidence_score < 0.55 → escalate (too ambiguous for a reliable answer)
  - top 2 candidates differ by < 0.02 score → escalate (genuinely ambiguous)
  - selected chapter is 98 or 99 (special provisions) → escalate
"""

from graph.state import TradeQueryState
from stores.vector_store import (
    get_client,
    get_embedding_fn,
    query_collection,
    COL_NODES,
    COL_HEADINGS,
)

# ── confidence thresholds ─────────────────────────────────────────────────────
MIN_CONFIDENCE     = 0.55   # below this → escalate
AMBIGUITY_GAP      = 0.02   # if top-2 scores within this → ambiguous
HEADING_THRESHOLD  = 0.65   # minimum score to trust a heading match

# ── special chapters to escalate ─────────────────────────────────────────────
SPECIAL_CHAPTERS   = {"98", "99"}


def build_gri_reasoning(
    heading_results: list[dict],
    node_results:    list[dict],
    selected_code:   str,
    selected_heading: str,
) -> str:
    """Build a brief GRI rule chain explanation."""
    lines = ["GRI Analysis:"]

    top_heading = heading_results[0] if heading_results else None
    top_node    = node_results[0]    if node_results    else None

    # Rule 1 check
    if top_heading and top_heading["score"] >= HEADING_THRESHOLD:
        h = top_heading["metadata"]["heading"]
        lines.append(
            f"Rule 1: Heading {h} matches by description "
            f"(score {top_heading['score']:.3f} ≥ {HEADING_THRESHOLD})."
        )
    else:
        lines.append(
            f"Rule 1: No heading match above {HEADING_THRESHOLD} threshold. "
            f"Proceeding to Rule 2."
        )

    # Rule 2/3 check
    if top_node:
        lines.append(
            f"Rule 2/3: Most specific matching subheading/statistical item: "
            f"{selected_code} (score {top_node['score']:.3f})."
        )

    # ambiguity note
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
    node_results:    list[dict],
) -> tuple[str, str, str, float]:
    """
    Returns (hts_code, heading, chapter, confidence_score).
    Applies simplified GRI logic.
    """
    if not node_results and not heading_results:
        return "", "", "", 0.0

    # prefer tariff_item or statistical nodes (most specific + have rates)
    preferred = [
        r for r in node_results
        if r["metadata"].get("node_type") in ("tariff_item", "statistical", "subheading")
        and r["metadata"].get("chapter") not in SPECIAL_CHAPTERS
    ]

    if not preferred:
        preferred = node_results

    if not preferred:
        # fall back to heading
        top = heading_results[0]
        m   = top["metadata"]
        return "", m.get("heading", ""), m.get("chapter", ""), top["score"] * 0.8

    top  = preferred[0]
    meta = top["metadata"]

    hts_code = meta.get("hts_code", "")
    heading  = meta.get("heading",  "")
    chapter  = meta.get("chapter",  "")
    score    = top["score"]

    # boost confidence if heading match also confirms the same chapter
    heading_chapters = {r["metadata"].get("chapter") for r in heading_results[:3]}
    if chapter in heading_chapters:
        score = min(1.0, score + 0.05)

    return hts_code, heading, chapter, score


# ── main node function ────────────────────────────────────────────────────────

def hts_classifier(state: TradeQueryState) -> TradeQueryState:
    """
    LangGraph node — classifies the product and selects an HTS code.
    """
    search_term  = state.get("hts_search_term") or state.get("product_description", "")
    chapter_hint = state.get("chapter_hint", "")

    try:
        client   = get_client()
        embed_fn = get_embedding_fn()

        # ── step 1: broad heading search ────────────────────────────────────
        col_headings = client.get_collection(COL_HEADINGS, embedding_function=embed_fn)
        heading_results = query_collection(
            col_headings, search_term,
            n=5,
            chapter=chapter_hint,
        )

        # ── step 2: granular node search ────────────────────────────────────
        col_nodes = client.get_collection(COL_NODES, embedding_function=embed_fn)

        # first try with top heading's chapter as filter for precision
        top_chapter = ""
        if heading_results and heading_results[0]["score"] >= HEADING_THRESHOLD:
            top_chapter = heading_results[0]["metadata"].get("chapter", "")

        node_results = query_collection(
            col_nodes, search_term,
            n=8,
            chapter=top_chapter,
        )

        # if filtered results are weak, retry without chapter filter
        if not node_results or node_results[0]["score"] < 0.60:
            node_results_broad = query_collection(col_nodes, search_term, n=8)
            if node_results_broad and (
                not node_results or
                node_results_broad[0]["score"] > node_results[0]["score"]
            ):
                node_results = node_results_broad

    except Exception as e:
        return {
            **state,
            "error":    f"hts_classifier: vector store error: {e}",
            "escalate": True,
            "escalate_reason": "Vector store unavailable",
        }

    # ── step 3: select best code via GRI ────────────────────────────────────
    hts_code, heading, chapter, confidence = select_best_code(
        heading_results, node_results
    )

    # ── step 4: check escalation conditions ─────────────────────────────────
    escalate        = False
    escalate_reason = ""

    if confidence < MIN_CONFIDENCE:
        escalate        = True
        escalate_reason = (
            f"Low classification confidence ({confidence:.2f} < {MIN_CONFIDENCE}). "
            f"Product description may be too vague or span multiple HTS chapters."
        )
    elif chapter in SPECIAL_CHAPTERS:
        escalate        = True
        escalate_reason = (
            f"Classified into Chapter {chapter} (special provisions). "
            f"These require case-by-case customs determination."
        )
    elif len(node_results) >= 2:
        gap = node_results[0]["score"] - node_results[1]["score"]
        if gap < AMBIGUITY_GAP and confidence < 0.70:
            escalate        = True
            escalate_reason = (
                f"Top two HTS candidates within {gap:.3f} score gap. "
                f"Classification is genuinely ambiguous — consult a licensed broker."
            )

    # ── step 5: build reasoning ──────────────────────────────────────────────
    reasoning = build_gri_reasoning(
        heading_results, node_results, hts_code, heading
    )

    return {
        **state,
        "candidate_headings":       heading_results,
        "candidate_nodes":          node_results,
        "selected_hts_code":        hts_code,
        "selected_heading":         heading,
        "selected_chapter":         chapter,
        "classification_reasoning": reasoning,
        "confidence_score":         round(confidence, 4),
        "escalate":                 escalate,
        "escalate_reason":          escalate_reason,
    }