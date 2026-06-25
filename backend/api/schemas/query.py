from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    query: str = Field(..., description="Product description and context")
    country: Optional[str] = Field(None, description="Country of origin")
    customs_value: Optional[float] = Field(None, ge=0, description="Shipment value USD")


class ClassifyResponse(BaseModel):
    query_id: Optional[str] = None
    release_version: str = ""
    policy_version: str = ""
    classification: dict[str, Any] = Field(default_factory=dict)
    duty: dict[str, Any] = Field(default_factory=dict)
    legal_notes: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str = ""
    sources: list[str] = Field(default_factory=list)
    disclaimer: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class QueryListItem(BaseModel):
    id: UUID
    raw_query: str
    country: Optional[str] = None
    selected_hts_code: Optional[str] = None
    confidence: Optional[float] = None
    hts_release: Optional[str] = None
    latency_ms: Optional[int] = None
    escalate: bool = False
    created_at: Any = None
    response_json: Optional[dict[str, Any]] = None
