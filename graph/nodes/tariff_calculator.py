"""
graph/nodes/tariff_calculator.py
---------------------------------
Node 3 of 4 in the LangGraph pipeline.

Responsibility:
  Given the selected HTS code and origin country, calculate:
    - MFN (Most Favored Nation) general duty rate
    - Applicable FTA rate if origin qualifies
    - Section 301 additional tariff if China origin
    - Final combined rate estimate

Rate sources (all from ChromaDB metadata — no external calls):
  - general_rate  from the selected HTS node metadata
  - special_rate  FTA program codes e.g. "Free (A+,AU,BH,CA,CL,CO...)"
  - Section 301   rule-based lookup for China + specific chapters

FTA program codes in special_rate field:
  A/A+  = GSP (Generalized System of Preferences)
  AU    = Australia FTA
  BH    = Bahrain FTA
  CA    = USMCA (Canada)
  CL    = Chile FTA
  CO    = Colombia FTA
  D     = AGOA (Africa)
  E     = Caribbean Basin Initiative
  IL    = Israel FTA
  JO    = Jordan FTA
  KR    = KORUS (South Korea)
  MA    = Morocco FTA
  MX    = USMCA (Mexico) — note: appears as P in some schedules
  OM    = Oman FTA
  P/PA  = Panama FTA
  PE    = Peru FTA
  S/SG  = Singapore FTA
"""

import re

from graph.state import TradeQueryState

# ── FTA country → program code mapping ───────────────────────────────────────
FTA_COUNTRY_CODES: dict[str, list[str]] = {
    "australia":   ["AU"],
    "bahrain":     ["BH"],
    "canada":      ["CA"],
    "chile":       ["CL"],
    "colombia":    ["CO"],
    "israel":      ["IL"],
    "jordan":      ["JO"],
    "south korea": ["KR"],
    "korea":       ["KR"],
    "mexico":      ["MX", "CA"],
    "morocco":     ["MA"],
    "oman":        ["OM"],
    "panama":      ["PA", "P"],
    "peru":        ["PE"],
    "singapore":   ["SG", "S"],
    # GSP beneficiaries — code A or A+ or A*
    "india":       ["A", "A+", "A*"],
    "indonesia":   ["A", "A*"],
    "philippines": ["A", "A*"],
    "thailand":    ["A", "A*"],
    "bangladesh":  ["A", "A+", "A*"],   # GSP eligible
    "cambodia":    ["A", "A*"],
    "pakistan":    ["A", "A*"],
    "sri lanka":   ["A", "A*"],
    "ethiopia":    ["D"],               # AGOA
    "kenya":       ["D"],
    "ghana":       ["D"],
    "vietnam":     [],                  # NOT GSP (graduated out 2020)
}

# ── Section 301 — China additional tariffs by chapter ────────────────────────
# List 1 = 25%, List 2 = 25%, List 3 = 25%, List 4A = 7.5%
# Source: USTR Section 301 Federal Register notices
SECTION_301_CHAPTERS: dict[str, str] = {
    # List 1 (25%) — industrial goods, machinery, electronics
    "84": "25%",   # machinery, computers
    "85": "25%",   # electronics, motors
    "86": "25%",   # railway equipment
    "87": "25%",   # vehicles (partial)
    "88": "25%",   # aircraft parts
    "89": "25%",   # ships
    "90": "25%",   # optical, medical instruments
    # List 2 (25%) — industrial materials
    "40": "25%",   # rubber
    "68": "25%",   # stone articles
    "69": "25%",   # ceramic products
    "70": "25%",   # glass
    "73": "25%",   # steel articles
    "74": "25%",   # copper
    "75": "25%",   # nickel
    "76": "25%",   # aluminum
    "82": "25%",   # tools, cutlery
    "83": "25%",   # miscellaneous metal
    # List 3 (25%) — consumer goods, industrial
    "33": "25%",   # cosmetics (partial)
    "36": "25%",   # explosives/matches
    "37": "25%",   # photographic goods
    "38": "25%",   # chemicals
    "39": "25%",   # plastics
    "42": "25%",   # leather goods
    "43": "25%",   # furskins
    "44": "25%",   # wood products
    "45": "25%",   # cork
    "46": "25%",   # straw articles
    "47": "25%",   # pulp
    "48": "25%",   # paper
    "49": "25%",   # books/printed matter
    "56": "25%",   # wadding, felt
    "57": "25%",   # carpets
    "58": "25%",   # special woven fabric
    "59": "25%",   # coated textile
    "72": "25%",   # iron and steel
    "94": "25%",   # furniture
    # List 4A (7.5%) — consumer goods
    "61": "7.5%",  # knitted apparel
    "62": "7.5%",  # woven apparel
    "63": "7.5%",  # home textiles
    "64": "7.5%",  # footwear
    "65": "7.5%",  # headgear
    "95": "7.5%",  # toys, games, sports
    "96": "7.5%",  # miscellaneous manufactured
}

# ── IEEPA additional tariffs ───────────────────────────────────────────────────
# On top of Section 301 where applicable
IEEPA_RATES = {
    "china":         ("20%", "IEEPA additional tariff on China-origin goods effective Feb 4, 2025"),
    "hong kong":     ("20%", "IEEPA additional tariff on Hong Kong-origin goods effective Feb 4, 2025"),
    "mexico":        ("25%", "IEEPA tariff on non-USMCA goods from Mexico effective Mar 4, 2025"),
    "canada":        ("25%", "IEEPA tariff on non-USMCA goods from Canada effective Mar 4, 2025"),
}


def parse_rate_to_float(rate_str: str) -> float | None:
    """
    Convert rate string to float for arithmetic.
    "6.7%"  → 6.7
    "Free"  → 0.0
    "1¢/kg" → None (specific duty, can't combine simply)
    ""      → None
    """
    if not rate_str:
        return None
    r = rate_str.strip().lower()
    if r in ("free", "0%", "0.0%"):
        return 0.0
    m = re.search(r"([\d.]+)\s*%", r)
    if m:
        return float(m.group(1))
    return None   # specific duty (¢/kg etc.) — can't combine as percentage


def check_fta_eligibility(origin: str, special_rate: str) -> tuple[bool, str, str]:
    """
    Check if origin country qualifies for an FTA rate.
    Returns (eligible, rate_string, program_code).
    """
    if not origin or not special_rate:
        return False, "", ""

    origin_lower  = origin.lower().strip()
    country_codes = FTA_COUNTRY_CODES.get(origin_lower, [])

    if not country_codes:
        return False, "", ""

    # parse special_rate field: "Free (A+,AU,BH,CA,CL,CO,...)"
    # format can be "Free (codes)" or "X% (codes)"
    m = re.match(r"(.+?)\s*\(([^)]+)\)", special_rate.strip())
    if not m:
        return False, "", ""

    rate_val = m.group(1).strip()
    codes    = [c.strip() for c in m.group(2).split(",")]

    for code in country_codes:
        # exact match
        if code in codes:
            return True, rate_val, code
        # GSP variants A / A+ / A* are all equivalent preference programs
        if code in ("A", "A+", "A*"):
            matched = next((c for c in ("A", "A+", "A*") if c in codes), None)
            if matched:
                return True, rate_val, f"GSP ({matched})"

    return False, "", ""


def get_section_301(origin: str, chapter: str) -> tuple[bool, str]:
    """
    Check if Section 301 additional tariff applies.
    Returns (applies, rate_string).
    Section 301 only applies to China-origin goods.
    """
    if origin.lower().strip() not in (
        "china", "prc", "people's republic of china", "hong kong"
    ):
        return False, ""
    rate = SECTION_301_CHAPTERS.get(chapter, "")
    return bool(rate), rate


def get_ieepa(origin: str, rate_basis: str) -> tuple[bool, str, str]:
    """
    Check if IEEPA additional tariff applies.
    For Mexico/Canada: only applies if NOT using USMCA (rate_basis != FTA).
    Returns (applies, rate, note).
    """
    o = origin.lower().strip()
    for key, (rate, note) in IEEPA_RATES.items():
        if key in o:
            # USMCA goods from Mexico/Canada are exempt from IEEPA
            if key in ("mexico", "canada") and "FTA" in rate_basis:
                return False, "", ""
            return True, rate, note
    return False, "", ""


def combine_rates(base_rate: str, *additions: str) -> str:
    """
    Combine base rate with one or more additional rates in a single pass.
    combine_rates("2%", "25%", "20%")  → "2% + 25% + 20% = 47.0%"
    combine_rates("Free", "25%", "20%") → "Free + 25% + 20% = 45.0%"
    combine_rates("6.7%", "25%")        → "6.7% + 25% = 31.7%"
    """
    # filter empty additions
    additions = [a for a in additions if a]
    if not additions:
        return base_rate

    # parse base
    base_lower = (base_rate or "").lower().strip()
    if base_lower in ("free", "0%", ""):
        base_f = 0.0
        base_label = "Free"
    else:
        m = parse_rate_to_float(base_rate)
        base_f = m if m is not None else None
        base_label = base_rate

    # parse additions
    add_floats = [parse_rate_to_float(a) for a in additions]

    # build string parts
    parts = [base_label] + list(additions)

    # compute total if all rates are numeric
    if base_f is not None and all(f is not None for f in add_floats):
        total = base_f + sum(add_floats)
        return " + ".join(parts) + f" = {total:.1f}%"

    # if any rate is non-numeric (e.g. ¢/kg specific duty) — just show parts
    return " + ".join(parts)


# ── pull rate from vector store metadata ─────────────────────────────────────

def get_rates_from_candidates(state: TradeQueryState) -> tuple[str, str, str]:
    """
    Extract the best available duty rates from the classifier's candidates.

    HTS rate hierarchy:
      statistical (10-digit) → has rate
      tariff_item (8-digit)  → has rate
      subheading  (6-digit)  → often NO rate, need to look at children
      heading     (4-digit)  → NO rate

    Strategy: find any node in the same heading that HAS a rate,
    prioritising tariff_item and statistical nodes.
    """
    selected         = state.get("selected_hts_code", "")
    selected_heading = state.get("selected_heading", "")
    nodes            = state.get("candidate_nodes", [])
    headings         = state.get("candidate_headings", [])

    # 1. exact match on selected code AND has a rate
    for r in nodes:
        m = r["metadata"]
        if m.get("hts_code") == selected and m.get("general_rate"):
            return m.get("general_rate",""), m.get("special_rate",""), m.get("other_rate","")

    # 2. tariff_item or statistical node in same heading with a rate
    #    (these are the levels where rates actually live in HTS)
    for node_type in ("tariff_item", "statistical"):
        for r in nodes:
            m = r["metadata"]
            if (m.get("heading")    == selected_heading
                    and m.get("node_type") == node_type
                    and m.get("general_rate")):
                return m.get("general_rate",""), m.get("special_rate",""), m.get("other_rate","")

    # 3. any node with a rate in the same heading regardless of type
    for r in nodes:
        m = r["metadata"]
        if m.get("heading") == selected_heading and m.get("general_rate"):
            return m.get("general_rate",""), m.get("special_rate",""), m.get("other_rate","")

    # 4. query vector store directly for tariff_item nodes under this heading
    #    (handles case where classifier only returned subheading-level nodes)
    try:
        from stores.vector_store import get_client, get_embedding_fn, COL_NODES
        from stores.vector_store import query_collection
        client   = get_client()
        embed_fn = get_embedding_fn()
        col      = client.get_collection(COL_NODES, embedding_function=embed_fn)

        # search for tariff items in the selected heading chapter
        chapter = state.get("selected_chapter", "")
        results = query_collection(
            col,
            state.get("hts_search_term") or state.get("product_description", ""),
            n=10,
            chapter=chapter,
        )
        for r in results:
            m = r["metadata"]
            if (m.get("heading")    == selected_heading
                    and m.get("node_type") in ("tariff_item", "statistical")
                    and m.get("general_rate")):
                return m.get("general_rate",""), m.get("special_rate",""), m.get("other_rate","")
    except Exception:
        pass

    # 5. heading summary rate as last resort
    for r in headings:
        m = r["metadata"]
        if m.get("heading") == selected_heading and m.get("general_rate"):
            return m.get("general_rate",""), m.get("special_rate",""), m.get("other_rate","")

    return "", "", ""


# ── main node function ────────────────────────────────────────────────────────

def tariff_calculator(state: TradeQueryState) -> TradeQueryState:
    """
    LangGraph node — calculates applicable duty rate.
    """
    origin  = state.get("origin_country", "")
    chapter = state.get("selected_chapter", "")

    # get rates from vector store results
    general_rate, special_rate, other_rate = get_rates_from_candidates(state)

    # ── FTA check ────────────────────────────────────────────────────────────
    fta_eligible, fta_rate, fta_code = check_fta_eligibility(origin, special_rate)

    if fta_eligible:
        applicable_rate = fta_rate
        rate_basis      = f"FTA ({fta_code})"
    elif general_rate:
        applicable_rate = general_rate
        rate_basis      = "MFN"
    else:
        applicable_rate = "Rate not found — check HTS directly"
        rate_basis      = "unknown"

    # ── Section 301 check ────────────────────────────────────────────────────
    s301_applies, s301_rate = get_section_301(origin, chapter)

    # ── IEEPA check (separate from 301, affects more countries) ──────────────
    rate_basis_so_far = "FTA" if fta_eligible else "MFN"
    ieepa_applies, ieepa_rate, ieepa_note = get_ieepa(origin, rate_basis_so_far)

    # ── combine rates — single pass, all additions at once ───────────────────
    extras = []
    if s301_applies:   extras.append(s301_rate)
    if ieepa_applies:  extras.append(ieepa_rate)
    total_rate = combine_rates(applicable_rate, *extras)

    return {
        **state,
        "general_rate":        general_rate,
        "special_rate":        special_rate,
        "other_rate":          other_rate,
        "applicable_rate":     applicable_rate,
        "rate_basis":          rate_basis,
        "section_301":         s301_applies,
        "section_301_rate":    s301_rate if s301_applies else "",
        "total_rate_estimate": total_rate,
    }