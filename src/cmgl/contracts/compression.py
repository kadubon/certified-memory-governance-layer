from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import CompressionFailureClass
from cmgl.contracts.receipts import MetricResult


class CompressionCertificate(CMGLModel):
    schema_version: Literal["cmgl.compression_certificate.v1"] = "cmgl.compression_certificate.v1"
    compressed_memory_id: str
    source_memory_ids: list[str]
    compression_ratio: float = Field(ge=0)
    recoverability_check: Literal["pass", "fail", "not_checked"]
    source_coverage: float = Field(ge=0, le=1)
    lost_uncertainties: list[str] = Field(default_factory=list)
    lost_exceptions: list[str] = Field(default_factory=list)
    source_digest_map: dict[str, str] = Field(default_factory=dict)
    recoverability_probes: dict[str, bool] = Field(default_factory=dict)
    lost_uncertainty_severity: Literal["none", "low", "medium", "high"] = "none"
    accountability_budget: int = Field(default=0, ge=0)
    collapse_budget: int = Field(default=0, ge=0)
    alias_hazards: list[str] = Field(default_factory=list)
    decision: Literal["admit_as_summary_not_fact", "reject", "shadow"]
    certificate_digest: str
    timestamp: datetime

    @field_validator("certificate_digest")
    @classmethod
    def validate_certificate_digest(cls, value: str) -> str:
        return validate_digest(value)

    @field_validator("source_digest_map")
    @classmethod
    def validate_source_digest_map(cls, value: dict[str, str]) -> dict[str, str]:
        return {key: validate_digest(digest) for key, digest in value.items()}


class CompressionAuditReport(CMGLModel):
    schema_version: Literal["cmgl.compression_audit_report.v1"] = "cmgl.compression_audit_report.v1"
    certificate_digest: str
    exact_declared_state: bool
    exact_accountability_state: bool
    deployable_exact_recovery: bool
    failure_classes: list[CompressionFailureClass] = Field(default_factory=list)
    metrics: list[MetricResult] = Field(default_factory=list)
    report_digest: str
    timestamp: datetime

    @field_validator("certificate_digest", "report_digest")
    @classmethod
    def validate_report_digest(cls, value: str) -> str:
        return validate_digest(value)


class CompressionBridgeProbe(CMGLModel):
    schema_version: Literal["cmgl.compression_bridge_probe.v1"] = "cmgl.compression_bridge_probe.v1"
    probe_id: str
    passed: bool
    source_memory_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    probe_digest: str
    timestamp: datetime

    @field_validator("probe_digest")
    @classmethod
    def validate_bridge_probe_digest(cls, value: str) -> str:
        return validate_digest(value)


class CompressionGluingProbe(CMGLModel):
    schema_version: Literal["cmgl.compression_gluing_probe.v1"] = "cmgl.compression_gluing_probe.v1"
    probe_id: str
    passed: bool
    alias_hazards: list[str] = Field(default_factory=list)
    lost_uncertainties: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    probe_digest: str
    timestamp: datetime

    @field_validator("probe_digest")
    @classmethod
    def validate_gluing_probe_digest(cls, value: str) -> str:
        return validate_digest(value)


class CompressionDeploymentProbe(CMGLModel):
    schema_version: Literal["cmgl.compression_deployment_probe.v1"] = (
        "cmgl.compression_deployment_probe.v1"
    )
    probe_id: str
    passed: bool
    recoverability_check: Literal["pass", "fail", "not_checked"]
    accountability_passed: bool
    reason_codes: list[str] = Field(default_factory=list)
    probe_digest: str
    timestamp: datetime

    @field_validator("probe_digest")
    @classmethod
    def validate_deployment_probe_digest(cls, value: str) -> str:
        return validate_digest(value)
