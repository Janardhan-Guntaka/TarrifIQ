"""Shared domain types for repositories and graph nodes."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class RetrievalHit:
    """Normalized vector search result (retrieval only — not authoritative for rates)."""

    document: str
    metadata: dict[str, Any]
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": self.document,
            "metadata": self.metadata,
            "score": self.score,
        }


@dataclass
class HtsRateRecord:
    """Authoritative rate row from hts_nodes."""

    hts_code: str
    heading: str
    chapter: str
    node_type: str
    general_rate: str
    special_rate: str
    other_rate: str
    description: str = ""
    rate_source: str = "exact"  # exact | heading_fallback


@dataclass
class PolicyAdjustment:
    """Single policy overlay applied after base rate."""

    policy_type: str
    rate: str
    note: str = ""


@dataclass
class DutyResult:
    """Output of PolicyEngine + DutyEngine."""

    general_rate: str
    special_rate: str
    other_rate: str
    applicable_rate: str
    rate_basis: str
    section_301: bool
    section_301_rate: str
    ieepa_applies: bool
    ieepa_rate: str
    ieepa_note: str
    total_rate_estimate: str
    duty_usd: float | None = None
    adjustments: list[PolicyAdjustment] = field(default_factory=list)


@dataclass
class ActiveReleaseContext:
    release_id: UUID
    version: str
