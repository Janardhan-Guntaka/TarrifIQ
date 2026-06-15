"""Versioned trade policy application (IEEPA, Section 301, FTA)."""

from typing import Any

from backend.core.types import DutyResult, HtsRateRecord, PolicyAdjustment
from backend.repositories.policy import PolicyRepository
from backend.tariff.duty_engine import DutyEngine


class PolicyEngine:
    def __init__(self, policy_repo: PolicyRepository | None = None) -> None:
        self._repo = policy_repo or PolicyRepository()
        self._duty = DutyEngine()

    def get_policy_version(self) -> str:
        return self._repo.get_composite_version()

    def _load_bundle(self) -> dict[str, dict[str, Any]]:
        return self._repo.get_active_bundle()

    def calculate(
        self,
        *,
        rate_record: HtsRateRecord,
        origin_country: str,
        chapter: str,
        customs_value: float | None = None,
    ) -> DutyResult:
        bundle = self._load_bundle()
        general = rate_record.general_rate
        special = rate_record.special_rate
        other = rate_record.other_rate

        fta_data = bundle.get("FTA", {}).get("policy_json", {})
        country_codes = fta_data.get("country_codes", {})

        fta_ok, fta_rate, fta_code = self._duty.check_fta_eligibility(
            origin_country, special, country_codes
        )

        if fta_ok:
            applicable_rate = fta_rate
            rate_basis = f"FTA ({fta_code})"
        elif general:
            applicable_rate = general
            rate_basis = "MFN"
        else:
            applicable_rate = "Rate not found — check HTS directly"
            rate_basis = "unknown"

        s301_json = bundle.get("SECTION_301", {}).get("policy_json", {})
        s301_ok, s301_rate = self._section_301(origin_country, chapter, s301_json)

        ieepa_json = bundle.get("IEEPA", {}).get("policy_json", {})
        ieepa_ok, ieepa_rate, ieepa_note = self._ieepa(
            origin_country, rate_basis, ieepa_json
        )

        extras: list[str] = []
        adjustments: list[PolicyAdjustment] = []

        if s301_ok:
            extras.append(s301_rate)
            adjustments.append(PolicyAdjustment("SECTION_301", s301_rate))
        if ieepa_ok:
            extras.append(ieepa_rate)
            adjustments.append(
                PolicyAdjustment("IEEPA", ieepa_rate, ieepa_note)
            )

        total = self._duty.combine_rates(applicable_rate, *extras)
        duty_usd = self._duty.duty_usd(total, customs_value)

        return DutyResult(
            general_rate=general,
            special_rate=special,
            other_rate=other,
            applicable_rate=applicable_rate,
            rate_basis=rate_basis,
            section_301=s301_ok,
            section_301_rate=s301_rate if s301_ok else "",
            ieepa_applies=ieepa_ok,
            ieepa_rate=ieepa_rate if ieepa_ok else "",
            ieepa_note=ieepa_note,
            total_rate_estimate=total,
            duty_usd=duty_usd,
            adjustments=adjustments,
        )

    @staticmethod
    def _section_301(
        origin: str, chapter: str, policy: dict[str, Any]
    ) -> tuple[bool, str]:
        origins = policy.get("china_origins", [])
        o = origin.lower().strip()
        if not any(x in o for x in origins):
            return False, ""
        rate = policy.get("chapter_rates", {}).get(chapter, "")
        return bool(rate), rate

    @staticmethod
    def _ieepa(
        origin: str, rate_basis: str, policy: dict[str, Any]
    ) -> tuple[bool, str, str]:
        o = origin.lower().strip()
        rates = policy.get("rates", {})
        exempt = policy.get("usmca_exempt_keys", [])

        for key, data in rates.items():
            if key in o:
                if key in exempt and "FTA" in rate_basis:
                    return False, "", ""
                return True, data.get("rate", ""), data.get("note", "")
        return False, "", ""
