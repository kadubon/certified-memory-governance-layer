from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, JsonContent, validate_digest
from cmgl.contracts.enums import (
    AbsenceNoticeType,
    BackendName,
    ChallengeStatus,
    ContaminationLane,
    MemoryEventType,
    MemoryStatus,
)


class MemoryEvent(CMGLModel):
    schema_version: Literal["cmgl.memory_event.v1"] = "cmgl.memory_event.v1"
    trace_id: str
    run_id: str
    agent_id: str
    backend: BackendName | str
    event_type: MemoryEventType
    memory_id: str
    memory_update_id: str | None = None
    content: JsonContent = None
    content_digest: str
    source_event_hashes: list[str] = Field(default_factory=list)
    lane: ContaminationLane
    provenance_depth: int = Field(ge=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    authority_scope: str
    status: MemoryStatus
    checker_version: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content_digest")
    @classmethod
    def validate_content_digest(cls, value: str) -> str:
        return validate_digest(value)

    @field_validator("source_event_hashes")
    @classmethod
    def validate_source_event_hashes(cls, value: list[str]) -> list[str]:
        return [validate_digest(item) for item in value]


class MemoryCandidate(CMGLModel):
    schema_version: Literal["cmgl.memory_candidate.v1"] = "cmgl.memory_candidate.v1"
    candidate_id: str
    event: MemoryEvent
    normalized_content_digest: str
    supersedes: list[str] = Field(default_factory=list)
    contradicted_by: list[str] = Field(default_factory=list)
    tombstone_of: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("normalized_content_digest")
    @classmethod
    def validate_normalized_digest(cls, value: str) -> str:
        return validate_digest(value)


class VersionedMemoryRef(CMGLModel):
    schema_version: Literal["cmgl.versioned_memory_ref.v1"] = "cmgl.versioned_memory_ref.v1"
    memory_id: str
    memory_update_id: str
    content_digest: str
    status: MemoryStatus | None = None

    @field_validator("content_digest")
    @classmethod
    def validate_ref_digest(cls, value: str) -> str:
        return validate_digest(value)


class EvidenceManifest(CMGLModel):
    schema_version: Literal["cmgl.evidence_manifest.v1"] = "cmgl.evidence_manifest.v1"
    candidate_id: str
    memory_ref: VersionedMemoryRef
    source_event_hashes: list[str] = Field(default_factory=list)
    normalized_content_digest: str
    checker_version: str
    manifest_digest: str
    created_at: datetime

    @field_validator("source_event_hashes")
    @classmethod
    def validate_manifest_sources(cls, value: list[str]) -> list[str]:
        return [validate_digest(item) for item in value]

    @field_validator("normalized_content_digest", "manifest_digest")
    @classmethod
    def validate_manifest_digest(cls, value: str) -> str:
        return validate_digest(value)


class MemoryRevision(CMGLModel):
    schema_version: Literal["cmgl.memory_revision.v1"] = "cmgl.memory_revision.v1"
    revision_id: str
    memory_id: str
    from_update_id: str | None = None
    to_update_id: str | None = None
    from_status: MemoryStatus
    to_status: MemoryStatus
    reason_codes: list[str] = Field(default_factory=list)
    revision_digest: str
    timestamp: datetime

    @field_validator("revision_digest")
    @classmethod
    def validate_revision_digest(cls, value: str) -> str:
        return validate_digest(value)


class MemoryStateSnapshot(CMGLModel):
    schema_version: Literal["cmgl.memory_state_snapshot.v1"] = "cmgl.memory_state_snapshot.v1"
    memory_id: str
    current_update_id: str | None = None
    current_status: MemoryStatus | None = None
    current_event_digest: str | None = None
    historical_update_ids: list[str] = Field(default_factory=list)
    superseded_update_ids: list[str] = Field(default_factory=list)
    tombstoned_update_ids: list[str] = Field(default_factory=list)
    quarantined_update_ids: list[str] = Field(default_factory=list)
    snapshot_digest: str
    timestamp: datetime

    @field_validator("current_event_digest", "snapshot_digest")
    @classmethod
    def validate_snapshot_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)


class CurrentMemoryView(CMGLModel):
    schema_version: Literal["cmgl.current_memory_view.v1"] = "cmgl.current_memory_view.v1"
    snapshots: list[MemoryStateSnapshot] = Field(default_factory=list)
    current_memory_ids: list[str] = Field(default_factory=list)
    audit_memory_ids: list[str] = Field(default_factory=list)
    view_digest: str
    timestamp: datetime

    @field_validator("view_digest")
    @classmethod
    def validate_view_digest(cls, value: str) -> str:
        return validate_digest(value)


class MemoryChallengeRecord(CMGLModel):
    schema_version: Literal["cmgl.memory_challenge_record.v1"] = "cmgl.memory_challenge_record.v1"
    challenge_id: str
    memory_id: str
    memory_update_id: str | None = None
    status: ChallengeStatus
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    record_digest: str
    timestamp: datetime

    @field_validator("record_digest")
    @classmethod
    def validate_challenge_digest(cls, value: str) -> str:
        return validate_digest(value)


class RecordAbsenceNotice(CMGLModel):
    schema_version: Literal["cmgl.record_absence_notice.v1"] = "cmgl.record_absence_notice.v1"
    notice_id: str
    notice_type: AbsenceNoticeType
    memory_id: str | None = None
    missing_record_digest: str | None = None
    disclosure_digest: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    notice_digest: str
    timestamp: datetime

    @field_validator("missing_record_digest", "disclosure_digest", "notice_digest")
    @classmethod
    def validate_absence_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)
