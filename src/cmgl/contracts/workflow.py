from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import AdmissionDecision, WorkflowLayer, WorkflowReportMode
from cmgl.contracts.receipts import MetricResult


class WorkflowEvidenceSet(CMGLModel):
    schema_version: Literal["cmgl.workflow_evidence_set.v1"] = "cmgl.workflow_evidence_set.v1"
    workflow_id: str
    receipt_counts: dict[AdmissionDecision, int] = Field(default_factory=dict)
    audit_metrics: list[MetricResult] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_digest: str
    timestamp: datetime

    @field_validator("evidence_digest")
    @classmethod
    def validate_evidence_digest(cls, value: str) -> str:
        return validate_digest(value)


class MemoryGovernanceEvidenceContract(CMGLModel):
    schema_version: Literal["cmgl.memory_governance_evidence_contract.v1"] = (
        "cmgl.memory_governance_evidence_contract.v1"
    )
    contract_id: str
    workflow_id: str
    report_terms: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    witness_ids: list[str] = Field(default_factory=list)
    contract_digest: str
    timestamp: datetime

    @field_validator("contract_digest")
    @classmethod
    def validate_contract_digest(cls, value: str) -> str:
        return validate_digest(value)


class VerificationWitness(CMGLModel):
    schema_version: Literal["cmgl.verification_witness.v1"] = "cmgl.verification_witness.v1"
    witness_id: str
    accepted: bool
    evidence_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    witness_digest: str
    timestamp: datetime

    @field_validator("witness_digest")
    @classmethod
    def validate_witness_digest(cls, value: str) -> str:
        return validate_digest(value)


class ReportTermBinding(CMGLModel):
    schema_version: Literal["cmgl.report_term_binding.v1"] = "cmgl.report_term_binding.v1"
    term: str
    witness_id: str
    evidence_id: str
    accepted: bool
    binding_digest: str
    timestamp: datetime

    @field_validator("binding_digest")
    @classmethod
    def validate_binding_digest(cls, value: str) -> str:
        return validate_digest(value)


class WorkflowBottleneckReport(CMGLModel):
    schema_version: Literal["cmgl.workflow_bottleneck_report.v1"] = (
        "cmgl.workflow_bottleneck_report.v1"
    )
    workflow_id: str
    layer: WorkflowLayer = WorkflowLayer.MEMORY_GOVERNANCE
    mode: WorkflowReportMode = WorkflowReportMode.DIAGNOSTIC_ONLY
    lower_bound: float = Field(ge=0)
    net_certified_throughput: float = Field(ge=0)
    bottleneck_layers: list[WorkflowLayer] = Field(default_factory=list)
    diagnostic_scores: dict[str, float] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    report_digest: str
    timestamp: datetime

    @field_validator("report_digest")
    @classmethod
    def validate_report_digest(cls, value: str) -> str:
        return validate_digest(value)
