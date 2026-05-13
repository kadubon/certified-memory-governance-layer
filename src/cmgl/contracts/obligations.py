from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import ConformanceProfile, ObligationStatus


class EvidenceBindingReport(CMGLModel):
    schema_version: Literal["cmgl.evidence_binding_report.v1"] = "cmgl.evidence_binding_report.v1"
    subject_type: str
    subject_digest: str | None = None
    memory_id: str | None = None
    memory_update_id: str | None = None
    status: ObligationStatus
    required_record_types: list[str] = Field(default_factory=list)
    matched_record_digests: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    report_digest: str
    timestamp: datetime

    @field_validator("subject_digest", "report_digest")
    @classmethod
    def validate_report_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)

    @field_validator("matched_record_digests")
    @classmethod
    def validate_matched_digests(cls, value: list[str]) -> list[str]:
        return [validate_digest(item) for item in value]


class ObligationGraph(CMGLModel):
    schema_version: Literal["cmgl.obligation_graph.v1"] = "cmgl.obligation_graph.v1"
    profile: ConformanceProfile
    ok: bool
    reports: list[EvidenceBindingReport] = Field(default_factory=list)
    graph_digest: str
    timestamp: datetime

    @field_validator("graph_digest")
    @classmethod
    def validate_graph_digest(cls, value: str) -> str:
        return validate_digest(value)
