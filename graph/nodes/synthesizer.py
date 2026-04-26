"""
graph/nodes/synthesizer.py
---------------------------
Node 4 of 4 in the LangGraph pipeline.

Responsibility:
  Take all structured results from previous nodes and produce:
    - A clear, cited natural language answer for the importer
    - An escalation message if confidence is too low
    - Always appends the legal disclaimer

Uses Ollama llama3.1:8b for natural language generation.
Falls back to a template-based answer if Ollama unavailable.

The synthesizer NEVER invents information — it only rephrases what
the previous nodes found. Every claim in the answer cites an HTS code.
"""

from graph.state import TradeQueryState

import os

try:
    from openai import OpenAI as _OpenAI
    OPENAI_AVAILABLE = bool(os.getenv("OPENAI_API_KEY"))
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import ollama as _ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

OPENAI_MODEL = "gpt-4o-mini"
OLLAMA_MODEL = "llama3.1:8b"

SYSTEM_PROMPT = """You are a U.S. customs compliance assistant helping importers understand tariff classifications.

Generate a clear answer based ONLY on the structured data provided.
CRITICAL RULES:
- NEVER say "no additional tariffs" if data shows Section 301 or IEEPA tariffs
- ALWAYS state which country the IEEPA applies to — use the ORIGIN COUNTRY from the data, not China
- The TOTAL ESTIMATED DUTY in the data is authoritative — quote it exactly
- Do not invent or omit any rates
- 3-4 sentences maximum
- End with: "Verify this with your customs broker before importing."
"""


def build_context(state: TradeQueryState) -> str:
    """Build the structured context string to pass to the LLM."""
    origin = state.get("origin_country", "")
    s301   = state.get("section_301", False)
    total  = state.get("total_rate_estimate", "")

    # detect IEEPA from total vs s301+base
    import re as _re
    app_rate  = state.get("applicable_rate", "") or ""
    s301_rate = state.get("section_301_rate", "") or ""
    base_f = 0.0 if "free" in app_rate.lower() else (
        float(_re.search(r"([\d.]+)%", app_rate).group(1))
        if _re.search(r"([\d.]+)%", app_rate) else 0.0
    )
    s301_f = float(_re.search(r"([\d.]+)%", s301_rate).group(1)) if s301_rate else 0.0
    total_m = _re.search(r"=\s*([\d.]+)%", total)
    ieepa_note = ""
    # get IEEPA info from tariff_calculator's stored rates
    from graph.nodes.tariff_calculator import IEEPA_RATES
    ieepa_date = ""
    for key, (rate, note) in IEEPA_RATES.items():
        if key in origin.lower():
            ieepa_date = note
            break

    if total_m:
        total_f = float(total_m.group(1))
        if total_f > base_f + s301_f + 0.5:
            ieepa_f = total_f - base_f - s301_f
            ieepa_note = (
                f"IEEPA additional tariff: {ieepa_f:.0f}% on {origin}-origin goods. "
                f"{ieepa_date}"
            )

    lines = [
        f"Product: {state.get('product_description', state['raw_query'])}",
        f"Origin country: {origin or 'not specified'}",
        f"HTS Code: {state.get('selected_hts_code') or 'not determined'}",
        f"HTS Heading: {state.get('selected_heading')}",
        f"Chapter: {state.get('selected_chapter')}",
        f"Classification confidence: {state.get('confidence_score', 0):.0%}",
        f"",
        f"MFN general duty rate: {state.get('general_rate') or 'not found'}",
        f"Special/FTA rates: {state.get('special_rate') or 'none'}",
        f"Applicable rate: {app_rate or 'unknown'}",
    ]
    if s301:
        lines.append(f"Section 301 additional (China): {s301_rate}")
    if ieepa_note:
        lines.append(ieepa_note)
    lines.append(f"TOTAL estimated duty: {total}")
    lines.append(f"")
    lines.append(f"Classification reasoning: {state.get('classification_reasoning', '')}")
    return "\n".join(lines)


def generate_with_llm(state: TradeQueryState) -> str:
    """Use OpenAI (cloud) or Ollama (local) to generate a natural language answer."""
    context  = build_context(state)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User question: {state['raw_query']}\n\n"
                f"Structured classification data:\n{context}\n\n"
                f"Write the answer now:"
            ),
        },
    ]

    # ── try OpenAI first ──────────────────────────────────────────────────────
    if OPENAI_AVAILABLE:
        try:
            client   = _OpenAI()
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=300,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            pass

    # ── fallback to Ollama ────────────────────────────────────────────────────
    if OLLAMA_AVAILABLE:
        try:
            response = _ollama.chat(
                model=OLLAMA_MODEL,
                messages=messages,
                options={"temperature": 0.2},
            )
            return response["message"]["content"].strip()
        except Exception:
            pass

    return ""


def generate_template(state: TradeQueryState) -> str:
    """
    Template-based answer — single source of truth is total_rate_estimate from state.
    Never recomputes rates — just formats what tariff_calculator already calculated.
    """
    product   = state.get("product_description") or state["raw_query"]
    # strip shipment value annotation if present
    import re as _re
    product   = _re.sub(r'\(shipment value[^)]*\)', '', product).strip()

    origin    = state.get("origin_country") or "unspecified origin"
    hts_code  = state.get("selected_hts_code") or state.get("selected_heading") or "undetermined"
    heading   = state.get("selected_heading", "")
    conf      = state.get("confidence_score", 0)
    gen_rate  = state.get("general_rate")    or "not found in HTS data"
    fta_rate  = state.get("special_rate")    or "none on file"
    app_rate  = state.get("applicable_rate") or gen_rate
    basis     = state.get("rate_basis")      or "MFN"
    # total_rate_estimate is the single authoritative total — includes 301 + IEEPA
    total     = state.get("total_rate_estimate") or app_rate
    s301      = state.get("section_301", False)
    s301_rate = state.get("section_301_rate", "")
    reasoning = state.get("classification_reasoning", "")

    # detect IEEPA from total string — if total > s301+base, IEEPA is included
    ieepa_in_total = False
    ieepa_rate_str = ""
    if origin.lower() in ("china", "hong kong") and s301:
        # check if total already includes IEEPA (will show =45% not =25%)
        base_f = 0.0 if "free" in (app_rate or "").lower() else (
            float(_re.search(r"([\d.]+)%", app_rate).group(1))
            if _re.search(r"([\d.]+)%", app_rate) else 0.0
        )
        s301_f = float(_re.search(r"([\d.]+)%", s301_rate).group(1)) if s301_rate else 0.0
        total_m = _re.search(r"=\s*([\d.]+)%", total)
        if total_m:
            total_f = float(total_m.group(1))
            if total_f > base_f + s301_f + 0.5:
                ieepa_in_total = True
                ieepa_rate_str = f"{total_f - base_f - s301_f:.0f}%"

    lines = [
        f"**Tariff Classification for: {product}**",
        f"",
        f"**HTS Code:** {hts_code}  (Heading {heading}, confidence {conf:.0%})",
        f"",
        f"**Duty Rates ({origin}):**",
        f"• MFN general rate: {gen_rate}",
        f"• Special/FTA rate: {fta_rate}",
        f"• Applicable rate ({basis}): {app_rate}",
    ]

    if s301:
        lines.append(f"• Section 301 additional tariff (China): {s301_rate}")
    if ieepa_in_total:
        lines.append(f"• IEEPA additional tariff ({origin}, 2025): {ieepa_rate_str}")

    lines.append(f"• **Total estimated duty: {total}**")

    if reasoning:
        lines.append(f"")
        lines.append(f"**Classification basis:** {reasoning}")

    lines.append(f"")
    lines.append(
        f"*Verify this classification and rate with your customs broker or "
        f"submit a binding ruling request at rulings.cbp.gov before importing.*"
    )

    return "\n".join(lines)


def generate_escalation_answer(state: TradeQueryState) -> str:
    """Answer for escalated queries — honest about uncertainty."""
    product = state.get("product_description") or state["raw_query"]
    reason  = state.get("escalate_reason", "Classification confidence too low.")
    heading = state.get("selected_heading", "")

    lines = [
        f"**Classification requires broker review: {product}**",
        f"",
        f"This query could not be automatically classified with sufficient confidence.",
        f"Reason: {reason}",
    ]

    if heading:
        lines.append(f"")
        lines.append(
            f"Closest HTS heading found: **{heading}** — "
            f"but the specific subheading needs manual determination."
        )

    lines.append(f"")
    lines.append("**Recommended next steps:**")
    lines.append("1. Contact a licensed U.S. Customs Broker for classification")
    lines.append("2. Submit a binding ruling request at rulings.cbp.gov (free, ~30 days)")
    lines.append("3. Prepare a detailed product description including materials, function, and end-use")

    return "\n".join(lines)


def build_citations(state: TradeQueryState) -> list[str]:
    """Build a list of source citations for the answer."""
    citations = []

    if state.get("selected_hts_code"):
        citations.append(
            f"HTS {state['selected_hts_code']} "
            f"(USITC 2026 Rev 6)"
        )
    elif state.get("selected_heading"):
        citations.append(
            f"HTS Heading {state['selected_heading']} "
            f"(USITC 2026 Rev 6)"
        )

    if state.get("section_301"):
        citations.append(
            f"USTR Section 301 Action — Chapter {state.get('selected_chapter')} "
            f"additional tariff {state.get('section_301_rate')}"
        )

    if state.get("rate_basis") and state["rate_basis"].startswith("FTA"):
        citations.append(
            f"FTA preference rate — program code {state.get('rate_basis')}"
        )

    return citations


# ── main node function ────────────────────────────────────────────────────────

def synthesizer(state: TradeQueryState) -> TradeQueryState:
    """
    LangGraph node — generates the final answer.
    """
    # ── escalation path ───────────────────────────────────────────────────────
    if state.get("escalate"):
        answer = generate_escalation_answer(state)
        return {
            **state,
            "final_answer": answer,
            "citations":    build_citations(state),
        }

    # ── normal answer path ────────────────────────────────────────────────────
    answer = ""

    if OPENAI_AVAILABLE or OLLAMA_AVAILABLE:
        answer = generate_with_llm(state)

    # fallback to template if LLM failed or unavailable
    if not answer:
        answer = generate_template(state)

    return {
        **state,
        "final_answer": answer,
        "citations":    build_citations(state),
    }