from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import AdmissionDecision, MetricStatus


class PromotionReceipt(CMGLModel):
    schema_version: Literal["cmgl.promotion_receipt.v1"] = "cmgl.promotion_receipt.v1"
    candidate_id: str
    decision: AdmissionDecision
    checks: dict[str, bool | None]
    reason_codes: list[str]
    checker_version: str
    policy_version: str
    memory_id: str | None = None
    memory_update_id: str | None = None
    content_digest: str | None = None
    evidence_manifest_digest: str | None = None
    rule_ids: list[str] = Field(default_factory=list)
    receipt_digest: str
    timestamp: datetime

    @field_validator("receipt_digest", "content_digest", "evidence_manifest_digest")
    @classmethod
    def validate_receipt_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)


class RetrievalDecision(CMGLModel):
    schema_version: Literal["cmgl.retrieval_decision.v1"] = "cmgl.retrieval_decision.v1"
    query_digest: str
    raw_hits: int = Field(ge=0)
    admitted_hits: int = Field(ge=0)
    blocked_hits: list[dict[str, str]] = Field(default_factory=list)
    admitted_memory_ids: list[str] = Field(default_factory=list)
    context_digest: str
    timestamp: datetime

    @field_validator("query_digest", "context_digest")
    @classmethod
    def validate_retrieval_digest(cls, value: str) -> str:
        return validate_digest(value)


class MetricResult(CMGLModel):
    schema_version: Literal["cmgl.metric_result.v1"] = "cmgl.metric_result.v1"
    metric_name: str
    status: MetricStatus
    value: int | float | str | None = None
    numerator: int | None = None
    denominator: int | None = None
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    timestamp: datetime
