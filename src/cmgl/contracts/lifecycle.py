from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import AdmissionDecision
from cmgl.contracts.memory import VersionedMemoryRef


class ShadowTrialReceipt(CMGLModel):
    schema_version: Literal["cmgl.shadow_trial_receipt.v1"] = "cmgl.shadow_trial_receipt.v1"
    trial_id: str
    candidate_id: str
    memory_ref: VersionedMemoryRef
    decision: AdmissionDecision
    reason_codes: list[str] = Field(default_factory=list)
    receipt_digest: str
    timestamp: datetime

    @field_validator("receipt_digest")
    @classmethod
    def validate_shadow_digest(cls, value: str) -> str:
        return validate_digest(value)


class LeaseReceipt(CMGLModel):
    schema_version: Literal["cmgl.lease_receipt.v1"] = "cmgl.lease_receipt.v1"
    lease_id: str
    candidate_id: str
    memory_ref: VersionedMemoryRef
    lease_expires_at: datetime
    decision: AdmissionDecision
    reason_codes: list[str] = Field(default_factory=list)
    receipt_digest: str
    timestamp: datetime

    @field_validator("receipt_digest")
    @classmethod
    def validate_lease_digest(cls, value: str) -> str:
        return validate_digest(value)


class ActivePromotionReceipt(CMGLModel):
    schema_version: Literal["cmgl.active_promotion_receipt.v1"] = "cmgl.active_promotion_receipt.v1"
    promotion_id: str
    candidate_id: str
    memory_ref: VersionedMemoryRef
    source_receipt_digest: str
    decision: AdmissionDecision
    reason_codes: list[str] = Field(default_factory=list)
    receipt_digest: str
    timestamp: datetime

    @field_validator("source_receipt_digest", "receipt_digest")
    @classmethod
    def validate_active_promotion_digest(cls, value: str) -> str:
        return validate_digest(value)


class RollbackSnapshot(CMGLModel):
    schema_version: Literal["cmgl.rollback_snapshot.v1"] = "cmgl.rollback_snapshot.v1"
    snapshot_id: str
    memory_refs: list[VersionedMemoryRef]
    snapshot_digest: str
    timestamp: datetime

    @field_validator("snapshot_digest")
    @classmethod
    def validate_snapshot_digest(cls, value: str) -> str:
        return validate_digest(value)


class RollbackReceipt(CMGLModel):
    schema_version: Literal["cmgl.rollback_receipt.v1"] = "cmgl.rollback_receipt.v1"
    rollback_id: str
    snapshot_digest: str
    restored_memory_ids: list[str]
    decision: AdmissionDecision
    reason_codes: list[str] = Field(default_factory=list)
    receipt_digest: str
    timestamp: datetime

    @field_validator("snapshot_digest", "receipt_digest")
    @classmethod
    def validate_rollback_digest(cls, value: str) -> str:
        return validate_digest(value)


class QuarantineRecord(CMGLModel):
    schema_version: Literal["cmgl.quarantine_record.v1"] = "cmgl.quarantine_record.v1"
    quarantine_id: str
    target_digest: str
    target_type: str
    reason_codes: list[str]
    release_conditions: list[str] = Field(default_factory=list)
    record_digest: str
    timestamp: datetime

    @field_validator("target_digest", "record_digest")
    @classmethod
    def validate_quarantine_digest(cls, value: str) -> str:
        return validate_digest(value)
