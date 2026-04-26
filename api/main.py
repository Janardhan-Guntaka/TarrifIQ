"""
api/main.py
-----------
FastAPI backend for TariffIQ.

Endpoints:
  POST /query     — classify product, return HTS code + all duty rates
  GET  /health    — liveness check (keeps Render free tier awake)
  GET  /manifest  — current HTS version on disk

Run:
  python run.py api
  uvicorn api.main:app --reload --port 8000
"""

import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from graph.pipeline import run as run_pipeline

# ── app setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TariffIQ",
    description="US import duty calculator for small importers",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MANIFEST = pathlib.Path("data/manifest.json")


# ── models ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query:          str            = Field(..., description="Natural language product query")
    shipment_value: Optional[float] = Field(None, description="Shipment value USD (optional)")
    origin_country: Optional[str]  = Field(None, description="Override origin country")


class TariffResponse(BaseModel):
    # classification
    hts_code:           str
    heading:            str
    chapter:            str
    confidence_pct:     int
    product_description: str
    origin_country:     str

    # rates
    general_rate:       str
    applicable_rate:    str
    rate_basis:         str
    section_301:        bool
    section_301_rate:   str
    ieepa:              bool
    ieepa_rate:         str
    ieepa_note:         str
    total_rate:         str

    # dollar estimate
    duty_usd:           Optional[float]
    shipment_value:     Optional[float]

    # answer
    answer:             str
    citations:          list[str]
    disclaimer:         str

    # routing
    escalate:           bool
    escalate_reason:    str

    # meta
    hts_release:        str
    latency_ms:         int


# ── IEEPA table (separate from Section 301) ───────────────────────────────────

IEEPA = {
    "china":     ("20%", "IEEPA additional tariff on China — effective Feb 4, 2025"),
    "hong kong": ("20%", "IEEPA additional tariff on Hong Kong — effective Feb 4, 2025"),
    "mexico":    ("25%", "IEEPA tariff on non-USMCA goods from Mexico — effective Mar 4, 2025"),
    "canada":    ("25%", "IEEPA tariff on non-USMCA goods from Canada — effective Mar 4, 2025"),
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _pct(s: str) -> Optional[float]:
    """Extract numeric percentage from a rate string."""
    if not s:
        return None
    if "free" in s.lower():
        return 0.0
    m = re.search(r"([\d.]+)\s*%", s)
    return float(m.group(1)) if m else None


def _combine(base: str, *additions: str) -> str:
    """
    Combine base rate with one or more additional rates.
    Returns a human-readable string like 'Free + 25% + 20% = 45%'
    """
    parts = [base if base.lower() != "free" else "Free (0%)"]
    parts += [a for a in additions if a]

    base_f = _pct(base) or 0.0
    total  = base_f + sum((_pct(a) or 0.0) for a in additions if a)

    if len(parts) > 1:
        return " + ".join(parts) + f" = {total:.1f}%"
    return base


def _check_ieepa(origin: str, rate_basis: str) -> tuple[bool, str, str]:
    """Returns (applies, rate, note). USMCA goods exempt."""
    o = origin.lower().strip()
    for key, (rate, note) in IEEPA.items():
        if key in o:
            if key in ("mexico", "canada") and rate_basis.startswith("FTA"):
                return False, "", ""
            return True, rate, note
    return False, "", ""


def _duty_usd(total_rate_str: str, value: Optional[float]) -> Optional[float]:
    if not value:
        return None
    matches = re.findall(r"([\d.]+)\s*%", total_rate_str)
    if not matches:
        return 0.0 if "free" in total_rate_str.lower() else None
    return round(value * float(matches[-1]) / 100, 2)


def _read_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text())
        except Exception:
            pass
    return {}


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "tariffiq"}


@app.get("/manifest")
def manifest():
    return _read_manifest()


@app.post("/query", response_model=TariffResponse)
def query(req: QueryRequest):
    t0 = time.time()

    # build full query string
    full = req.query.strip()
    if req.origin_country:
        o = req.origin_country.strip()
        if o.lower() not in full.lower():
            full = f"{full} from {o}"
    if req.shipment_value:
        full = f"{full} (shipment value ${req.shipment_value:,.0f})"

    try:
        result = run_pipeline(full)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    origin    = result.get("origin_country", "")
    chapter   = result.get("selected_chapter", "")
    s301      = result.get("section_301", False)
    s301_rate = result.get("section_301_rate", "")
    app_rate  = result.get("applicable_rate", "")
    basis     = result.get("rate_basis", "")

    ieepa_ok, ieepa_rate, ieepa_note = _check_ieepa(origin, basis)

    # build total
    extras = []
    if s301:     extras.append(s301_rate)
    if ieepa_ok: extras.append(ieepa_rate)
    total = _combine(app_rate, *extras)

    duty = _duty_usd(total, req.shipment_value)

    return TariffResponse(
        hts_code            = result.get("selected_hts_code", ""),
        heading             = result.get("selected_heading", ""),
        chapter             = chapter,
        confidence_pct      = int(result.get("confidence_score", 0) * 100),
        product_description = result.get("product_description", ""),
        origin_country      = origin,
        general_rate        = result.get("general_rate", ""),
        applicable_rate     = app_rate,
        rate_basis          = basis,
        section_301         = s301,
        section_301_rate    = s301_rate,
        ieepa               = ieepa_ok,
        ieepa_rate          = ieepa_rate,
        ieepa_note          = ieepa_note,
        total_rate          = total,
        duty_usd            = duty,
        shipment_value      = req.shipment_value,
        answer              = result.get("final_answer", ""),
        citations           = result.get("citations", []),
        disclaimer          = result.get("disclaimer", ""),
        escalate            = result.get("escalate", False),
        escalate_reason     = result.get("escalate_reason", ""),
        hts_release         = _read_manifest().get("hts_release", "2026HTSRev6"),
        latency_ms          = int((time.time() - t0) * 1000),
    )