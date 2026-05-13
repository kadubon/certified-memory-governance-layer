from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.adapters import AdapterOperationReceipt
from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import AdmissionDecision, MetricStatus
from cmgl.contracts.ledger import LedgerAppendReceipt
from cmgl.contracts.lifecycle import ActivePromotionReceipt, ShadowTrialReceipt
from cmgl.contracts.memory import EvidenceManifest, MemoryCandidate, MemoryEvent
from cmgl.contracts.receipts import PromotionReceipt


class InputSetManifest(CMGLModel):
    schema_version: Literal["cmgl.input_set_manifest.v1"] = "cmgl.input_set_manifest.v1"
    manifest_id: str
    candidate_id: str
    memory_id: str
    memory_update_id: str
    candidate_digest: str
    content_digest: str
    input_event_ids: list[str] = Field(default_factory=list)
    input_event_digests: list[str] = Field(default_factory=list)
    replay_digest: str
    manifest_digest: str
    created_at: datetime

    @field_validator(
        "candidate_digest",
        "content_digest",
        "replay_digest",
        "manifest_digest",
    )
    @classmethod
    def validate_manifest_digest(cls, value: str) -> str:
        return validate_digest(value)

    @field_validator("input_event_digests")
    @classmethod
    def validate_input_event_digests(cls, value: list[str]) -> list[str]:
        return [validate_digest(item) for item in value]


class ReplayEvidence(CMGLModel):
    schema_version: Literal["cmgl.replay_evidence.v1"] = "cmgl.replay_evidence.v1"
    replay_id: str
    input_set_manifest_digest: str
    replay_digest: str
    checker_version: str
    accepted: bool
    reason_codes: list[str] = Field(default_factory=list)
    evidence_digest: str
    timestamp: datetime

    @field_validator("input_set_manifest_digest", "replay_digest", "evidence_digest")
    @classmethod
    def validate_replay_digest(cls, value: str) -> str:
        return validate_digest(value)


class PromotionEvidenceBundle(CMGLModel):
    schema_version: Literal["cmgl.promotion_evidence_bundle.v1"] = (
        "cmgl.promotion_evidence_bundle.v1"
    )
    candidate: MemoryCandidate
    evidence_manifest: EvidenceManifest
    input_set_manifest: InputSetManifest
    replay_evidence: ReplayEvidence
    shadow_receipt: ShadowTrialReceipt | None = None
    active_promotion_receipt: ActivePromotionReceipt | None = None
    bundle_digest: str
    timestamp: datetime

    @field_validator("bundle_digest")
    @classmethod
    def validate_bundle_digest(cls, value: str) -> str:
        return validate_digest(value)


class GovernanceReceiptBundle(CMGLModel):
    """Stable high-level result object for public GovernanceLayer integrations."""

    schema_version: Literal["cmgl.governance_receipt_bundle.v1"] = (
        "cmgl.governance_receipt_bundle.v1"
    )
    event: MemoryEvent
    candidate: MemoryCandidate
    evidence_manifest: EvidenceManifest | None = None
    promotion_receipt: PromotionReceipt
    append_receipts: list[LedgerAppendReceipt] = Field(default_factory=list)
    shadow_receipt: ShadowTrialReceipt | None = None
    active_promotion_receipt: ActivePromotionReceipt | None = None
    adapter_operation_receipt: AdapterOperationReceipt | None = None
    quarantine_record_digest: str | None = None
    strict_verification_status: MetricStatus | None = None
    decision: AdmissionDecision
    conformance_ok: bool
    backend_result_digest: str | None = None
    bundle_digest: str
    timestamp: datetime

    @field_validator(
        "quarantine_record_digest",
        "backend_result_digest",
        "bundle_digest",
    )
    @classmethod
    def validate_governance_bundle_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)
