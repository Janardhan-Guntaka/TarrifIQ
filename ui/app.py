"""
ui/app.py
---------
TariffIQ — US Import Duty Calculator
Streamlit frontend for small importers, Shopify/FBA sellers, small manufacturers.

Run:
  python run.py ui
  streamlit run ui/app.py
"""

import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure working directory is project root so .chroma/ and data/ are found
import os
os.chdir(ROOT)

# Load OpenAI key from Streamlit secrets when running on cloud
try:
    import streamlit as st
    if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

import streamlit as st
from typing import Optional

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TariffIQ — US Import Duty Calculator",
    page_icon="🛃",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── styles ────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.main .block-container { max-width: 780px; padding-top: 1.5rem; padding-bottom: 3rem; }

/* rate display */
.rate-big   { font-size: 2.8rem; font-weight: 600; line-height: 1.1; }
.rate-free  { color: #1D9E75; }
.rate-low   { color: #BA7517; }
.rate-high  { color: #A32D2D; }
.rate-label { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }

/* hts code */
.hts-code { font-family: monospace; font-size: 1.2rem; font-weight: 600; letter-spacing: 0.04em; }
.hts-sub  { font-size: 0.8rem; color: #888; margin-top: 2px; }

/* badges */
.badge { display: inline-block; font-size: 11px; font-weight: 500; padding: 3px 9px; border-radius: 20px; }
.b-green  { background:#d4edda; color:#155724; }
.b-amber  { background:#fff3cd; color:#856404; }
.b-red    { background:#f8d7da; color:#721c24; }
.b-blue   { background:#cce5ff; color:#004085; }
.b-gray   { background:#e2e3e5; color:#383d41; }
.b-purple { background:#e2d9f3; color:#4a235a; }

/* breakdown table */
.bd-row { display:flex; align-items:baseline; gap:8px;
          padding: 6px 0; border-bottom: 0.5px solid #eee; font-size:13px; }
.bd-label { flex:0 0 200px; color:#555; }
.bd-rate  { flex:0 0 80px; font-weight:500; font-family:monospace; }
.bd-note  { color:#888; font-size:12px; }

/* alert boxes */
.alert-ieepa { background:#fdf0f0; border:1px solid #f5c6cb;
               border-left:4px solid #dc3545; border-radius:8px;
               padding:.9rem 1.1rem; margin:.5rem 0; font-size:13px; }
.alert-301   { background:#fff8e6; border:1px solid #ffc107;
               border-left:4px solid #e6a817; border-radius:8px;
               padding:.9rem 1.1rem; margin:.5rem 0; font-size:13px; }
.alert-gsp   { background:#eaf6f1; border:1px solid #28a745;
               border-left:4px solid #1D9E75; border-radius:8px;
               padding:.9rem 1.1rem; margin:.5rem 0; font-size:13px; }
.alert-warn  { background:#fff8e6; border:1px solid #ffc107;
               border-left:4px solid #e6a817; border-radius:8px;
               padding:.9rem 1.1rem; margin:.5rem 0; font-size:13px; }

/* disclaimer */
.disclaimer { background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px;
              padding:.8rem 1rem; font-size:12px; color:#666; margin-top:1rem; }

/* example chips */
.chip-row { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 12px; }

/* dollar amount */
.duty-amount { font-size:2.2rem; font-weight:600; color:#A32D2D; line-height:1.1; }
.duty-free   { font-size:2.2rem; font-weight:600; color:#1D9E75; line-height:1.1; }
</style>
""", unsafe_allow_html=True)

# ── example queries per segment ───────────────────────────────────────────────

SEGMENTS = {
    "🛍️ Shopify / FBA": [
        "phone case from China",
        "yoga mat from Vietnam",
        "LED desk lamp from China",
        "wooden cutting board from China",
        "cotton tote bag from Bangladesh",
        "bluetooth earbuds from China",
        "silicone kitchen utensils from China",
    ],
    "👗 Apparel & fashion": [
        "cotton t-shirt from Bangladesh",
        "hoodie from Vietnam",
        "running shoes from Indonesia",
        "leather handbag from Italy",
        "wool sweater from India",
        "denim jeans from Bangladesh",
    ],
    "🏠 Home & furniture": [
        "office chair from China",
        "LED floor lamp from China",
        "bed sheets from India",
        "sofa from China",
        "bamboo flooring from Vietnam",
        "ceramic mugs from Portugal",
    ],
    "⚙️ Machinery & B2B": [
        "hydraulic pump from Germany",
        "electric motor from Mexico",
        "steel pipe fittings from Canada",
        "air compressor from China",
        "heat exchanger from South Korea",
    ],
}

# ── pipeline call ─────────────────────────────────────────────────────────────

def run_query(query: str, value: Optional[float] = None) -> dict | None:
    """Call pipeline directly (no API needed for local use)."""
    try:
        from graph.pipeline import run as _run
        full = query
        if value:
            full = f"{full} (shipment value ${value:,.0f})"
        result = _run(full)

        # compute IEEPA
        origin = result.get("origin_country", "")
        basis  = result.get("rate_basis", "")
        ieepa_map = {
            "china":     ("20%", "IEEPA additional tariff — China, effective Feb 4 2025"),
            "hong kong": ("20%", "IEEPA additional tariff — HK, effective Feb 4 2025"),
            "mexico":    ("25%", "IEEPA tariff on non-USMCA goods — effective Mar 4 2025"),
            "canada":    ("25%", "IEEPA tariff on non-USMCA goods — effective Mar 4 2025"),
        }
        ieepa_ok, ieepa_rate, ieepa_note = False, "", ""
        for key, (r, n) in ieepa_map.items():
            if key in origin.lower():
                if key in ("mexico", "canada") and "FTA" in basis:
                    break
                ieepa_ok, ieepa_rate, ieepa_note = True, r, n
                break

        # build total rate
        app_rate  = result.get("applicable_rate", "") or result.get("general_rate", "")
        s301      = result.get("section_301", False)
        s301_rate = result.get("section_301_rate", "")

        def to_f(s):
            if not s: return 0.0
            if "free" in s.lower(): return 0.0
            m = re.search(r"([\d.]+)%", s)
            return float(m.group(1)) if m else 0.0

        total_pct = to_f(app_rate) + (to_f(s301_rate) if s301 else 0) + (to_f(ieepa_rate) if ieepa_ok else 0)

        parts = []
        if app_rate:
            parts.append("Free" if to_f(app_rate) == 0 else app_rate)
        if s301 and s301_rate:
            parts.append(f"+{s301_rate} Sec.301")
        if ieepa_ok and ieepa_rate:
            parts.append(f"+{ieepa_rate} IEEPA")

        if len(parts) > 1:
            total_str = " ".join(parts) + f" = {total_pct:.1f}%"
        else:
            total_str = app_rate or "—"

        duty = round(value * total_pct / 100, 2) if value and total_pct >= 0 else None

        return {
            "hts_code":           result.get("selected_hts_code", ""),
            "heading":            result.get("selected_heading", ""),
            "chapter":            result.get("selected_chapter", ""),
            "confidence_pct":     int(result.get("confidence_score", 0) * 100),
            "product_description": result.get("product_description", ""),
            "origin_country":     origin,
            "general_rate":       result.get("general_rate", ""),
            "applicable_rate":    app_rate,
            "rate_basis":         basis,
            "section_301":        s301,
            "section_301_rate":   s301_rate,
            "ieepa":              ieepa_ok,
            "ieepa_rate":         ieepa_rate,
            "ieepa_note":         ieepa_note,
            "total_rate":         total_str,
            "total_pct":          total_pct,
            "duty_usd":           duty,
            "shipment_value":     value,
            "answer":             result.get("final_answer", ""),
            "citations":          result.get("citations", []),
            "disclaimer":         result.get("disclaimer", ""),
            "escalate":           result.get("escalate", False),
            "escalate_reason":    result.get("escalate_reason", ""),
        }
    except Exception as e:
        import traceback
        st.error(f"Pipeline error: {e}")
        st.code(traceback.format_exc())
        return None


# ── rate helpers ──────────────────────────────────────────────────────────────

def rate_color_class(pct: float) -> str:
    if pct == 0:    return "rate-free"
    if pct <= 10:   return "rate-low"
    return "rate-high"


def rate_display(pct: float, app_rate: str) -> str:
    if "free" in app_rate.lower() and pct == 0:
        return "Free"
    return f"{pct:.1f}%"


def conf_badge(pct: int) -> str:
    if pct >= 75: return f'<span class="badge b-green">✓ {pct}% match</span>'
    if pct >= 55: return f'<span class="badge b-amber">~ {pct}% match</span>'
    return f'<span class="badge b-red">⚠ {pct}% match</span>'


# ── main ──────────────────────────────────────────────────────────────────────

def main():

    # ── header ────────────────────────────────────────────────────────────────
    st.markdown("## 🛃 TariffIQ")
    st.markdown("**US import duty calculator** — paste any product and country, get instant HTS classification, duty rates, and FTA savings.")

    st.markdown("---")

    # ── segment tabs ──────────────────────────────────────────────────────────
    st.markdown("**Try an example:**")
    tabs = st.tabs(list(SEGMENTS.keys()))
    for tab, (segment, examples) in zip(tabs, SEGMENTS.items()):
        with tab:
            cols = st.columns(len(examples))
            for col, ex in zip(cols, examples):
                if col.button(ex, key=f"ex_{ex}", use_container_width=True):
                    st.session_state["query_input"] = ex
                    st.rerun()

    st.markdown("")

    # ── input form ────────────────────────────────────────────────────────────

    with st.form("query_form", clear_on_submit=False):
        col_q, col_v = st.columns([3, 1])

        with col_q:
            query = st.text_input(
                "What are you importing?",
                key="query_input",
                placeholder='e.g. "cotton hoodie from Bangladesh" or "LED lamp from China"',
                label_visibility="collapsed",
            )

        with col_v:
            value_input = st.text_input(
                "Value (USD)",
                placeholder="Shipment $",
                label_visibility="collapsed",
            )

        submitted = st.form_submit_button(
            "🔍  Calculate import duty",
            type="primary",
            use_container_width=True,
        )

    # parse value
    shipment_value: Optional[float] = None
    if value_input:
        try:
            shipment_value = float(value_input.replace(",", "").replace("$", ""))
        except ValueError:
            st.warning("Enter a number for shipment value, e.g. 10000")

    # ── results ───────────────────────────────────────────────────────────────
    if submitted and query.strip():

        with st.spinner("Classifying product…"):
            t0 = time.time()
            result = run_query(query.strip(), shipment_value)
            elapsed = time.time() - t0

        if not result:
            st.error("Could not classify. Check your OpenAI API key is set in Streamlit secrets, or Ollama is running locally.")
            st.stop()

        st.markdown("---")

        # ── escalation ────────────────────────────────────────────────────────
        if result["escalate"]:
            st.markdown(
                f'<div class="alert-warn">⚠️ <strong>Broker review recommended</strong><br>'
                f'{result["escalate_reason"]}</div>',
                unsafe_allow_html=True,
            )
            if result.get("heading"):
                st.info(f"Closest heading found: **{result['heading']}** — specific subheading needs manual review.")
            st.markdown(
                "**Recommended:** Submit a free binding ruling at "
                "[rulings.cbp.gov](https://rulings.cbp.gov) or contact a licensed customs broker."
            )
            st.markdown(
                f'<div class="disclaimer">{result["disclaimer"]}</div>',
                unsafe_allow_html=True,
            )
            st.stop()

        # ── top 3 metric cards ────────────────────────────────────────────────
        total_pct = result.get("total_pct", 0)
        c1, c2, c3 = st.columns(3)

        with c1:
            hts = result["hts_code"] or result["heading"] or "—"
            st.markdown('<div class="rate-label">HTS Code</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="hts-code">{hts}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="hts-sub">Ch. {result["chapter"]} · {result["product_description"][:30]}</div>', unsafe_allow_html=True)
            st.markdown(conf_badge(result["confidence_pct"]), unsafe_allow_html=True)

        with c2:
            color = rate_color_class(total_pct)
            display = rate_display(total_pct, result["applicable_rate"])
            st.markdown('<div class="rate-label">Total duty rate</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="rate-big {color}">{display}</div>', unsafe_allow_html=True)
            basis_label = result["rate_basis"] or "MFN"
            origin_label = result["origin_country"] or "unknown origin"
            st.markdown(
                f'<span class="badge b-blue">{basis_label}</span> '
                f'<span class="badge b-gray">{origin_label}</span>',
                unsafe_allow_html=True,
            )

        with c3:
            if shipment_value and result["duty_usd"] is not None:
                st.markdown('<div class="rate-label">Estimated duty on shipment</div>', unsafe_allow_html=True)
                if result["duty_usd"] == 0:
                    st.markdown('<div class="duty-free">$0.00</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="duty-amount">${result["duty_usd"]:,.2f}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="hts-sub">on ${shipment_value:,.0f} shipment</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="rate-label">MFN base rate</div>', unsafe_allow_html=True)
                base = result["general_rate"] or "—"
                color2 = rate_color_class(0 if "free" in base.lower() else 10)
                st.markdown(f'<div class="rate-big {color2}" style="font-size:2rem">{base}</div>', unsafe_allow_html=True)
                st.markdown('<div class="hts-sub">Add shipment value for dollar estimate</div>', unsafe_allow_html=True)

        st.markdown("")

        # ── rate breakdown ─────────────────────────────────────────────────────
        with st.expander("📊 Full rate breakdown", expanded=True):
            rows = [
                ("MFN general rate",    result["general_rate"] or "—",      "Standard rate for all countries"),
                ("Applicable rate",     result["applicable_rate"] or "—",   f"After {result['rate_basis']} applied"),
            ]
            if result["section_301"]:
                rows.append(("+ Section 301 (China)", result["section_301_rate"], "USTR additional tariff"))
            if result["ieepa"]:
                rows.append(("+ IEEPA additional",    result["ieepa_rate"],        result["ieepa_note"]))

            rows.append(("= Total estimated",  f"**{rate_display(total_pct, result['applicable_rate'])}**", "All tariffs combined"))

            for label, rate, note in rows:
                st.markdown(
                    f'<div class="bd-row">'
                    f'<span class="bd-label">{label}</span>'
                    f'<span class="bd-rate">{rate}</span>'
                    f'<span class="bd-note">{note}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ── contextual alerts ─────────────────────────────────────────────────

        if result["ieepa"]:
            st.markdown(
                f'<div class="alert-ieepa">'
                f'🚨 <strong>IEEPA additional tariff applies</strong><br>'
                f'{result["ieepa_note"]}<br>'
                f'This is <strong>on top of</strong> any Section 301 tariffs. '
                f'Many importers are unaware of this 2025 change.'
                f'</div>',
                unsafe_allow_html=True,
            )
        elif result["section_301"]:
            st.markdown(
                f'<div class="alert-301">'
                f'⚠️ <strong>Section 301 tariff: {result["section_301_rate"]} additional</strong><br>'
                f'China-origin goods in this category carry extra duties. '
                f'Consider Vietnam, Bangladesh, or Mexico to reduce this cost.'
                f'</div>',
                unsafe_allow_html=True,
            )

        if result["rate_basis"] and "GSP" in result["rate_basis"]:
            st.markdown(
                f'<div class="alert-gsp">'
                f'✅ <strong>GSP duty-free savings applied</strong><br>'
                f'{result["origin_country"]} qualifies under the Generalized System of Preferences. '
                f'You save {result["general_rate"]} on this shipment.'
                f'</div>',
                unsafe_allow_html=True,
            )

        if "FTA" in result.get("rate_basis", "") and result.get("origin_country", "") in ("Mexico", "Canada"):
            st.markdown(
                f'<div class="alert-gsp">'
                f'✅ <strong>USMCA rate applied</strong><br>'
                f'{result["origin_country"]}-origin goods qualify for preferential USMCA rates. '
                f'IEEPA surcharge does not apply to qualifying USMCA goods.'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── sourcing suggestion ───────────────────────────────────────────────
        if total_pct > 30 and result.get("origin_country", "").lower() == "china":
            alternatives = {
                "61": "Bangladesh (GSP Free)", "62": "Bangladesh (GSP Free)",
                "85": "Vietnam (MFN only, no Sec.301)",
                "84": "Mexico (USMCA Free)",
                "94": "Vietnam or Malaysia (MFN only)",
                "95": "Vietnam (MFN 0-7.5%)",
            }
            alt = alternatives.get(result["chapter"], "Vietnam or Bangladesh")
            st.info(
                f"💡 **Sourcing tip:** At {total_pct:.0f}% total duty, consider sourcing from "
                f"**{alt}** to significantly reduce your import costs."
            )

        # ── classification detail ─────────────────────────────────────────────
        with st.expander("📋 Classification analysis", expanded=False):
            st.markdown(result["answer"])

        # ── citations ─────────────────────────────────────────────────────────
        with st.expander("📚 Sources", expanded=False):
            for c in result["citations"]:
                st.markdown(f"• {c}")
            st.markdown(f"• USITC HTS 2026 Rev 6")
            st.markdown(f"• USTR Section 301 lists (2018–2024)")
            st.markdown(f"• IEEPA Executive Orders (2025)")
            st.caption(f"Response in {elapsed:.1f}s")

        # ── disclaimer ─────────────────────────────────────────────────────────
        st.markdown(
            f'<div class="disclaimer">⚖️ {result["disclaimer"]}</div>',
            unsafe_allow_html=True,
        )

        # ── feedback ───────────────────────────────────────────────────────────
        st.markdown("")
        fb_cols = st.columns([1, 1, 4])
        if fb_cols[0].button("👍 Helpful"):
            st.success("Thanks — helps us improve accuracy.")
        if fb_cols[1].button("👎 Wrong"):
            wrong = st.text_input(
                "What was incorrect?",
                placeholder="e.g. wrong HTS code, wrong rate...",
                key="wrong_input",
            )

    # ── sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### TariffIQ — Beta")
        st.markdown(
            "Free US import duty estimator for:\n"
            "- Shopify / Amazon FBA sellers\n"
            "- Small manufacturers\n"
            "- Fashion & apparel importers\n"
            "- Furniture & home goods\n"
        )
        st.markdown("---")
        st.markdown("**Data sources**")
        st.markdown(
            "- USITC HTS 2026 Rev 6\n"
            "- USTR Section 301 (Lists 1–4A)\n"
            "- IEEPA Executive Orders 2025\n"
            "- FTA/GSP preference schedules\n"
        )
        st.markdown("---")
        st.markdown(
            "⚠️ Research tool only. Always verify "
            "classifications with a licensed customs broker "
            "before importing.\n\n"
            "[Get a binding ruling →](https://rulings.cbp.gov)"
        )
        st.markdown("---")
        st.caption("v0.1 · Built with LangGraph + ChromaDB")


if __name__ == "__main__":
    main()