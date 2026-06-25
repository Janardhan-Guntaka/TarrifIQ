"""Domain guard — TariffIQ only handles US import HTS / duty queries."""

from __future__ import annotations

import re

from backend.core.deps import get_deps
from backend.graph import vocab

OFF_TOPIC_REPLY = (
    "TariffIQ only handles U.S. import classification and duty questions. "
    "Describe a product with origin and value when possible — for example: "
    "\"wireless earbuds from Vietnam, customs value $45 per unit\"."
)

# Obvious small-talk (no LLM spend)
_OFF_TOPIC_RE = [
    re.compile(p, re.I)
    for p in (
        r"^(hi|hello|hey|hiya|yo|sup|greetings)[\s!.?,]*$",
        r"^(hi|hello|hey|hiya|yo|sup|greetings)(\s+(there|everyone|all|friend))[\s!.?,]*$",
        r"^how\s+are\s+you",
        r"^how'?s\s+it\s+going",
        r"^what'?s\s+up",
        r"^(good\s+)?(morning|afternoon|evening|night)[\s!.?]*$",
        r"^thanks?(?:\s+you)?[\s!.?]*$",
        r"^thank\s+you[\s!.?]*$",
        r"^who\s+are\s+you\??$",
        r"^what\s+can\s+you\s+do\??$",
        r"^help\s*$",
        r"^test\s*$",
        r"^(bye|goodbye|see\s+ya)[\s!.?]*$",
        r"^tell\s+me\s+(a\s+)?joke",
        r"^what\s+is\s+the\s+weather",
        r"^(can|could)\s+you\s+",
    )
]

_TRADE_KEYWORDS = frozenset(
    """
    import imported importing importer importation
    export exported exporting
    duty duties tariff tariffs rate rates
    hts htsus harmonized tariff schedule
    customs cbp border clearance entry
    classify classification code coding
    chapter heading subheading statistical
    origin country manufacture mfn fta
    section 301 ieepa usmca
    broker brokerage compliance
    shipment landed cost customs value
    usitc merchandise product goods sku
    """.split()
)

_VALUE_RE = re.compile(
    r"\$\s*\d|customs\s+value|shipment\s+value|value\s+of\s+\$|\d+\s*(usd|dollars?)",
    re.I,
)


_CHITCHAT_WORDS = frozenset(
    """
    hi hello hey hiya yo sup greetings there everyone all friend
    how are you doing going whats up thanks thank bye goodbye
    morning afternoon evening night help test who
    """.split()
)


def _is_chitchat_only(text: str) -> bool:
    tokens = [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 1]
    return bool(tokens) and all(t in _CHITCHAT_WORDS for t in tokens)


def _has_trade_keyword(text: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return bool(words & _TRADE_KEYWORDS)


def _has_strong_trade_signal(text: str) -> bool:
    q = text.lower()
    if _VALUE_RE.search(q):
        return True
    if vocab.extract_country_rule_based(text):
        return True
    if vocab.get_chapter_hint(text):
        return True
    return _has_trade_keyword(q)


def _looks_like_product_description(text: str) -> bool:
    """Longer free-text product descriptions without explicit trade keywords."""
    q = text.lower()
    tokens = [w for w in re.findall(r"[a-z]+", q) if len(w) > 2]
    noise = {"the", "and", "for", "you", "your", "are", "how", "what", "this", "that", "from", "with"}
    content = [t for t in tokens if t not in noise]
    return len(content) >= 3


def _looks_like_product_query(text: str) -> bool:
    """Heuristic: mentions a plausible product noun phrase."""
    if _is_chitchat_only(text):
        return False
    if _has_strong_trade_signal(text):
        return True
    normalized = re.sub(r"\s+", " ", text.strip())
    if len(normalized.split()) <= 5:
        return False
    return _looks_like_product_description(text)

def _llm_in_domain(raw_query: str) -> bool:
    """Cheap yes/no when rules are ambiguous."""
    system = """You gate a US import tariff classification API.
Reply ONLY with JSON: {"in_domain": true} or {"in_domain": false}

in_domain=true ONLY if the user asks about:
- classifying a product for US import (HTS)
- import duties, tariffs, landed cost, customs
- trade compliance for a specific product/shipment

in_domain=false for greetings, chitchat, general knowledge, coding help, unrelated topics."""
    try:
        parsed = get_deps().llm_service.chat_json_sync(system, raw_query[:500])
        return bool(parsed.get("in_domain"))
    except Exception:
        # Fail open for ambiguous product-like text; fail closed for very short
        return len(raw_query.split()) >= 4


def check_domain(raw_query: str) -> tuple[bool, str]:
    """
    Returns (in_domain, off_topic_message).
    off_topic_message is set when in_domain is False.
    """
    text = (raw_query or "").strip()
    if not text:
        return False, "Please enter a product description to classify."

    normalized = re.sub(r"\s+", " ", text)
    if len(normalized) <= 120:
        for pattern in _OFF_TOPIC_RE:
            if pattern.search(normalized):
                return False, OFF_TOPIC_REPLY

    if _is_chitchat_only(text):
        return False, OFF_TOPIC_REPLY

    if _looks_like_product_query(text):
        return True, ""

    # Short vague message without trade signals
    if len(normalized.split()) <= 5:
        return False, OFF_TOPIC_REPLY

    if _llm_in_domain(text):
        return True, ""

    return False, OFF_TOPIC_REPLY
