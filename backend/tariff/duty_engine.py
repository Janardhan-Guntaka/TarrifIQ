"""Deterministic duty rate arithmetic (no LLM)."""

import re
from typing import Sequence


class DutyEngine:
    @staticmethod
    def parse_rate_to_float(rate_str: str) -> float | None:
        if not rate_str:
            return None
        r = rate_str.strip().lower()
        if r in ("free", "0%", "0.0%"):
            return 0.0
        m = re.search(r"([\d.]+)\s*%", r)
        return float(m.group(1)) if m else None

    @staticmethod
    def combine_rates(base_rate: str, *additions: str) -> str:
        additions = [a for a in additions if a]
        if not additions:
            return base_rate

        base_lower = (base_rate or "").lower().strip()
        if base_lower in ("free", "0%", ""):
            base_f = 0.0
            base_label = "Free"
        else:
            base_f = DutyEngine.parse_rate_to_float(base_rate)
            base_label = base_rate

        add_floats = [DutyEngine.parse_rate_to_float(a) for a in additions]
        parts = [base_label] + list(additions)

        if base_f is not None and all(f is not None for f in add_floats):
            total = base_f + sum(add_floats)
            return " + ".join(parts) + f" = {total:.1f}%"

        return " + ".join(parts)

    @staticmethod
    def duty_usd(total_rate_str: str, customs_value: float | None) -> float | None:
        if customs_value is None:
            return None
        matches = re.findall(r"([\d.]+)\s*%", total_rate_str)
        if not matches:
            if "free" in total_rate_str.lower():
                return 0.0
            return None
        return round(customs_value * float(matches[-1]) / 100, 2)

    @staticmethod
    def check_fta_eligibility(
        origin: str,
        special_rate: str,
        country_codes: dict[str, list[str]],
    ) -> tuple[bool, str, str]:
        if not origin or not special_rate:
            return False, "", ""

        origin_lower = origin.lower().strip()
        codes = country_codes.get(origin_lower, [])
        if not codes:
            return False, "", ""

        m = re.match(r"(.+?)\s*\(([^)]+)\)", special_rate.strip())
        if not m:
            return False, "", ""

        rate_val = m.group(1).strip()
        listed = [c.strip() for c in m.group(2).split(",")]

        for code in codes:
            if code in listed:
                return True, rate_val, code
            if code in ("A", "A+", "A*"):
                matched = next((c for c in ("A", "A+", "A*") if c in listed), None)
                if matched:
                    return True, rate_val, f"GSP ({matched})"

        return False, "", ""
