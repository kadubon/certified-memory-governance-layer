from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import ConformanceLevel, ConformanceProfile, ConformanceSeverity


class ReceiptObligation(CMGLModel):
    schema_version: Literal["cmgl.receipt_obligation.v1"] = "cmgl.receipt_obligation.v1"
    obligation_id: str
    subject_digest: str | None = None
    required_rule_ids: list[str] = Field(default_factory=list)
    satisfied: bool
    reason_codes: list[str] = Field(default_factory=list)
    obligation_digest: str
    timestamp: datetime

    @field_validator("subject_digest", "obligation_digest")
    @classmethod
    def validate_obligation_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)


class ConformanceFinding(CMGLModel):
    schema_version: Literal["cmgl.conformance_finding.v1"] = "cmgl.conformance_finding.v1"
    reference: str
    level: ConformanceLevel
    severity: ConformanceSeverity
    summary: str
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ConformanceReport(CMGLModel):
    schema_version: Literal["cmgl.conformance_report.v1"] = "cmgl.conformance_report.v1"
    profile: ConformanceProfile
    ok: bool
    findings: list[ConformanceFinding] = Field(default_factory=list)
    obligations: list[ReceiptObligation] = Field(default_factory=list)
    report_digest: str
    timestamp: datetime

    @field_validator("report_digest")
    @classmethod
    def validate_report_digest(cls, value: str) -> str:
        return validate_digest(value)
