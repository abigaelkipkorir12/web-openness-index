from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Confidence(StrEnum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    POSSIBLE = "possible"
    NO_EVIDENCE = "no_evidence"
    UNKNOWN = "unknown"


class Evidence(BaseModel):
    source_url: str
    observed_at: datetime
    http_status: int | None = None
    content_sha256: str | None = None
    note: str | None = None


class Observation(BaseModel):
    value: Any
    confidence: Confidence
    confidence_score: float = Field(ge=0.0, le=1.0)
    method: str
    evidence: list[Evidence] = Field(default_factory=list)


class RequestRecord(BaseModel):
    requested_url: str
    final_url: str | None = None
    started_at: datetime
    elapsed_ms: float = Field(ge=0.0)
    status_code: int | None = None
    response_bytes: int = Field(ge=0)
    response_truncated: bool = False
    content_sha256: str | None = None
    error: str | None = None


class ProbeError(BaseModel):
    probe: str
    message: str


class DomainSnapshot(BaseModel):
    schema_version: str = "0.1.0"
    run_id: str
    domain: str
    origin: str
    started_at: datetime
    completed_at: datetime
    collector_version: str
    request_count: int = Field(ge=0)
    observations: dict[str, Observation]
    requests: list[RequestRecord]
    errors: list[ProbeError] = Field(default_factory=list)
