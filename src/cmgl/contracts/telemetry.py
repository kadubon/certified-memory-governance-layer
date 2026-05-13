from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import GovernanceProfile, TelemetryEventType, TelemetryOutcomeStatus
from cmgl.contracts.memory import VersionedMemoryRef
from cmgl.contracts.receipts import MetricResult


class TelemetryWritePayload(CMGLModel):
    schema_version: Literal["cmgl.telemetry_write_payload.v1"] = "cmgl.telemetry_write_payload.v1"
    memory_ref: VersionedMemoryRef
    ttl_seconds: int | None = Field(default=None, ge=0)
    risk_weight: float = Field(default=1.0, ge=0)


class TelemetryReplacePayload(CMGLModel):
    schema_version: Literal["cmgl.telemetry_replace_payload.v1"] = (
        "cmgl.telemetry_replace_payload.v1"
    )
    old_ref: VersionedMemoryRef
    new_ref: VersionedMemoryRef


class TelemetryDeletePayload(CMGLModel):
    schema_version: Literal["cmgl.telemetry_delete_payload.v1"] = "cmgl.telemetry_delete_payload.v1"
    memory_ref: VersionedMemoryRef
    reason: str | None = None


class TelemetryReadUsePayload(CMGLModel):
    schema_version: Literal["cmgl.telemetry_read_use_payload.v1"] = (
        "cmgl.telemetry_read_use_payload.v1"
    )
    memory_refs: list[VersionedMemoryRef] = Field(default_factory=list)
    query_digest: str | None = None
    risk_weight: float = Field(default=1.0, ge=0)

    @field_validator("query_digest")
    @classmethod
    def validate_query_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)


class TelemetryVerifyPayload(CMGLModel):
    schema_version: Literal["cmgl.telemetry_verify_payload.v1"] = "cmgl.telemetry_verify_payload.v1"
    memory_ref: VersionedMemoryRef | None = None
    verdict: Literal["pass", "fail", "not_checked"]
    verify_deadline: datetime | None = None


class TelemetryCorrectPayload(CMGLModel):
    schema_version: Literal["cmgl.telemetry_correct_payload.v1"] = (
        "cmgl.telemetry_correct_payload.v1"
    )
    corrected_ref: VersionedMemoryRef | None = None
    correction_of_event_id: str


class TelemetryRetrievePayload(CMGLModel):
    schema_version: Literal["cmgl.telemetry_retrieve_payload.v1"] = (
        "cmgl.telemetry_retrieve_payload.v1"
    )
    query_digest: str
    raw_hits: int = Field(ge=0)
    returned_refs: list[VersionedMemoryRef] = Field(default_factory=list)

    @field_validator("query_digest")
    @classmethod
    def validate_retrieve_query_digest(cls, value: str) -> str:
        return validate_digest(value)


TelemetryPayload = (
    TelemetryWritePayload
    | TelemetryReplacePayload
    | TelemetryDeletePayload
    | TelemetryReadUsePayload
    | TelemetryVerifyPayload
    | TelemetryCorrectPayload
    | TelemetryRetrievePayload
)


class MemoryTelemetryEvent(CMGLModel):
    schema_version: Literal["cmgl.memory_telemetry_event.v1"] = "cmgl.memory_telemetry_event.v1"
    event_type: TelemetryEventType
    collector_id: str
    collector_seq: int = Field(ge=0)
    event_id: str
    obs_time: datetime
    skew_budget_ms: int = Field(default=0, ge=0)
    memory_refs: list[VersionedMemoryRef] = Field(default_factory=list)
    trace_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    payload: TelemetryPayload | None = None
    event_digest: str

    @field_validator("event_digest")
    @classmethod
    def validate_telemetry_digest(cls, value: str) -> str:
        return validate_digest(value)


class TelemetryAuditReport(CMGLModel):
    schema_version: Literal["cmgl.telemetry_audit_report.v1"] = "cmgl.telemetry_audit_report.v1"
    profile: GovernanceProfile = GovernanceProfile.STRICT
    metrics: list[MetricResult]
    telemetry_events: int = Field(ge=0)
    read_use_events: int = Field(ge=0)
    report_digest: str
    timestamp: datetime

    @field_validator("report_digest")
    @classmethod
    def validate_report_digest(cls, value: str) -> str:
        return validate_digest(value)


class RationalValue(CMGLModel):
    schema_version: Literal["cmgl.rational_value.v1"] = "cmgl.rational_value.v1"
    numerator: int
    denominator: int = Field(gt=0)

    @property
    def value(self) -> float:
        return self.numerator / self.denominator


class TelemetryLineDiagnostic(CMGLModel):
    schema_version: Literal["cmgl.telemetry_line_diagnostic.v1"] = (
        "cmgl.telemetry_line_diagnostic.v1"
    )
    line: int
    event_id: str | None = None
    status: str
    reason_codes: list[str] = Field(default_factory=list)


class TelemetryEventOutcome(CMGLModel):
    schema_version: Literal["cmgl.telemetry_event_outcome.v1"] = "cmgl.telemetry_event_outcome.v1"
    event_id: str | None = None
    line: int
    status: TelemetryOutcomeStatus
    reason_codes: list[str] = Field(default_factory=list)


class TelemetryIngestResult(CMGLModel):
    schema_version: Literal["cmgl.telemetry_ingest_result.v1"] = "cmgl.telemetry_ingest_result.v1"
    profile: GovernanceProfile
    accepted_events: int = Field(ge=0)
    rejected_events: int = Field(ge=0)
    deduplicated_events: int = Field(default=0, ge=0)
    downgraded_events: int = Field(default=0, ge=0)
    diagnostics: list[TelemetryLineDiagnostic] = Field(default_factory=list)
    outcomes: list[TelemetryEventOutcome] = Field(default_factory=list)
    result_digest: str
    timestamp: datetime

    @field_validator("result_digest")
    @classmethod
    def validate_result_digest(cls, value: str) -> str:
        return validate_digest(value)


class TelemetryReplayReport(CMGLModel):
    schema_version: Literal["cmgl.telemetry_replay_report.v1"] = "cmgl.telemetry_replay_report.v1"
    profile: GovernanceProfile
    metrics: list[MetricResult]
    outcomes: list[TelemetryEventOutcome] = Field(default_factory=list)
    replay_digest: str
    timestamp: datetime

    @field_validator("replay_digest")
    @classmethod
    def validate_replay_digest(cls, value: str) -> str:
        return validate_digest(value)


class TelemetryStateReplay(CMGLModel):
    schema_version: Literal["cmgl.telemetry_state_replay.v1"] = "cmgl.telemetry_state_replay.v1"
    profile: GovernanceProfile
    profile_level: Literal["P0", "P1", "P2"]
    metrics: list[MetricResult]
    rational_metrics: dict[str, RationalValue] = Field(default_factory=dict)
    outcomes: list[TelemetryEventOutcome] = Field(default_factory=list)
    declared_memory_ids: list[str] = Field(default_factory=list)
    current_memory_ids: list[str] = Field(default_factory=list)
    replay_digest: str
    timestamp: datetime

    @field_validator("replay_digest")
    @classmethod
    def validate_state_replay_digest(cls, value: str) -> str:
        return validate_digest(value)
