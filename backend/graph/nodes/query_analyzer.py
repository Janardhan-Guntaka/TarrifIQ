"""Query analyzer — OpenAI + rule-based fallback (no Ollama)."""

import re

from backend.core.deps import get_deps
from backend.graph import vocab
from backend.graph.state import TradeQueryState

SYSTEM_PROMPT = """You are a U.S. customs classification assistant.
Extract structured information from the user's trade query.

Respond ONLY with a valid JSON object — no preamble, no markdown.
JSON fields:
  product_description  : clean product description (string)
  hts_search_term      : rephrase using official HTS/HTSUS legal vocabulary
  origin_country       : country of manufacture/export, or "" if not mentioned
  trade_scenario       : one of: "import_duty", "fta_check", "origin_check"
  analyzer_notes       : one sentence explaining your reasoning

Rules:
  - Use precise HTS legal terminology in hts_search_term
  - Do not invent information not present in the query
"""


def _extract_with_llm(raw_query: str) -> dict:
    deps = get_deps()
    try:
        parsed = deps.llm_service.chat_json_sync(SYSTEM_PROMPT, raw_query)
        return {
            "product_description": str(parsed.get("product_description", "")),
            "hts_search_term": str(parsed.get("hts_search_term", "")),
            "origin_country": str(parsed.get("origin_country", "")),
            "trade_scenario": str(parsed.get("trade_scenario", "import_duty")),
            "analyzer_notes": str(parsed.get("analyzer_notes", "")),
        }
    except Exception as e:
        return {"_error": str(e)}


def query_analyzer(state: TradeQueryState) -> TradeQueryState:
    raw = re.sub(r"\(shipment value[^)]*\)", "", state["raw_query"]).strip()
    raw = re.sub(r"\(customs value[^)]*\)", "", raw, flags=re.I).strip()

    extracted: dict = {}
    used_llm = False

    try:
        result = _extract_with_llm(raw)
        if "_error" not in result:
            extracted = result
            used_llm = True
    except Exception:
        pass

    if not extracted.get("origin_country"):
        extracted["origin_country"] = vocab.extract_country_rule_based(raw)

    if not extracted.get("trade_scenario"):
        extracted["trade_scenario"] = vocab.extract_scenario_rule_based(raw)

    if not extracted.get("hts_search_term"):
        extracted["hts_search_term"] = vocab.rephrase_to_hts_rule_based(raw)

    if not extracted.get("product_description"):
        noise = {
            "what", "is", "the", "a", "an", "of", "for", "my", "to", "i",
            "want", "need", "how", "much", "duty", "tariff", "rate", "import",
        }
        country_words = {c.lower() for c in vocab.COUNTRIES}
        words = [w for w in raw.lower().split() if w not in noise and w not in country_words]
        extracted["product_description"] = " ".join(words[:6]).strip() or raw

    if not extracted.get("analyzer_notes"):
        mode = "OpenAI" if used_llm else "rule-based"
        extracted["analyzer_notes"] = f"Extracted via {mode} analyzer."

    return {
        **state,
        "product_description": extracted["product_description"],
        "hts_search_term": extracted["hts_search_term"],
        "origin_country": extracted["origin_country"],
        "trade_scenario": extracted["trade_scenario"],
        "analyzer_notes": extracted["analyzer_notes"],
        "chapter_hint": vocab.get_chapter_hint(raw),
    }
