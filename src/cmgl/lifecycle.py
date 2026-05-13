from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from cmgl.digest import sha256_digest
from cmgl.evidence import versioned_ref_from_event
from cmgl.models import (
    ActivePromotionReceipt,
    AdmissionDecision,
    LeaseReceipt,
    MemoryCandidate,
    MemoryEvent,
    MemoryStatus,
    QuarantineRecord,
    RollbackReceipt,
    RollbackSnapshot,
    ShadowTrialReceipt,
    VersionedMemoryRef,
)
from cmgl.time import now_utc
from cmgl.transitions import LifecyclePolicy

LIFECYCLE_POLICY = LifecyclePolicy(allow_noop=True)


def _candidate_ref(candidate: MemoryCandidate) -> VersionedMemoryRef:
    ref = versioned_ref_from_event(candidate.event)
    if ref is None:
        raise ValueError("candidate event must include memory_update_id")
    return ref


def make_shadow_trial_receipt(
    candidate: MemoryCandidate,
    *,
    admitted: bool,
    reason_codes: list[str] | None = None,
    timestamp: datetime | None = None,
) -> ShadowTrialReceipt:
    receipt_time = timestamp or now_utc()
    if candidate.event.status != MemoryStatus.VERIFIED_SHADOW:
        LIFECYCLE_POLICY.require_transition(candidate.event.status, MemoryStatus.VERIFIED_SHADOW)
    decision = AdmissionDecision.SHADOW if admitted else AdmissionDecision.BLOCK
    body = {
        "schema_version": "cmgl.shadow_trial_receipt.v1",
        "trial_id": f"shadow:{uuid4()}",
        "candidate_id": candidate.candidate_id,
        "memory_ref": _candidate_ref(candidate),
        "decision": decision,
        "reason_codes": list(reason_codes or []),
        "timestamp": receipt_time,
    }
    return ShadowTrialReceipt(**body, receipt_digest=sha256_digest(body))


def make_lease_receipt(
    candidate: MemoryCandidate,
    *,
    lease_seconds: int,
    admitted: bool,
    reason_codes: list[str] | None = None,
    timestamp: datetime | None = None,
) -> LeaseReceipt:
    receipt_time = timestamp or now_utc()
    if candidate.event.status != MemoryStatus.VERIFIED_SHADOW:
        LIFECYCLE_POLICY.require_transition(candidate.event.status, MemoryStatus.VERIFIED_SHADOW)
    body = {
        "schema_version": "cmgl.lease_receipt.v1",
        "lease_id": f"lease:{uuid4()}",
        "candidate_id": candidate.candidate_id,
        "memory_ref": _candidate_ref(candidate),
        "lease_expires_at": receipt_time + timedelta(seconds=lease_seconds),
        "decision": AdmissionDecision.SHADOW if admitted else AdmissionDecision.BLOCK,
        "reason_codes": list(reason_codes or []),
        "timestamp": receipt_time,
    }
    return LeaseReceipt(**body, receipt_digest=sha256_digest(body))


def make_active_promotion_receipt(
    candidate: MemoryCandidate,
    *,
    source_receipt_digest: str,
    admitted: bool,
    reason_codes: list[str] | None = None,
    timestamp: datetime | None = None,
) -> ActivePromotionReceipt:
    receipt_time = timestamp or now_utc()
    LIFECYCLE_POLICY.require_transition(candidate.event.status, MemoryStatus.CERTIFIED)
    body = {
        "schema_version": "cmgl.active_promotion_receipt.v1",
        "promotion_id": f"promotion:{uuid4()}",
        "candidate_id": candidate.candidate_id,
        "memory_ref": _candidate_ref(candidate),
        "source_receipt_digest": source_receipt_digest,
        "decision": AdmissionDecision.ADMIT if admitted else AdmissionDecision.BLOCK,
        "reason_codes": list(reason_codes or []),
        "timestamp": receipt_time,
    }
    return ActivePromotionReceipt(**body, receipt_digest=sha256_digest(body))


def make_rollback_snapshot(
    events: list[MemoryEvent],
    *,
    timestamp: datetime | None = None,
) -> RollbackSnapshot:
    refs = [ref for event in events if (ref := versioned_ref_from_event(event)) is not None]
    body = {
        "schema_version": "cmgl.rollback_snapshot.v1",
        "snapshot_id": f"rollback-snapshot:{uuid4()}",
        "memory_refs": refs,
        "timestamp": timestamp or now_utc(),
    }
    return RollbackSnapshot(**body, snapshot_digest=sha256_digest(body))


def make_rollback_receipt(
    snapshot: RollbackSnapshot,
    *,
    restored_memory_ids: list[str],
    admitted: bool,
    reason_codes: list[str] | None = None,
    timestamp: datetime | None = None,
) -> RollbackReceipt:
    body = {
        "schema_version": "cmgl.rollback_receipt.v1",
        "rollback_id": f"rollback:{uuid4()}",
        "snapshot_digest": snapshot.snapshot_digest,
        "restored_memory_ids": restored_memory_ids,
        "decision": AdmissionDecision.ADMIT if admitted else AdmissionDecision.BLOCK,
        "reason_codes": list(reason_codes or []),
        "timestamp": timestamp or now_utc(),
    }
    return RollbackReceipt(**body, receipt_digest=sha256_digest(body))


def make_quarantine_record(
    *,
    target: object,
    target_type: str,
    reason_codes: list[str],
    release_conditions: list[str] | None = None,
    timestamp: datetime | None = None,
) -> QuarantineRecord:
    target_digest = sha256_digest(target)
    body = {
        "schema_version": "cmgl.quarantine_record.v1",
        "quarantine_id": f"quarantine:{uuid4()}",
        "target_digest": target_digest,
        "target_type": target_type,
        "reason_codes": reason_codes,
        "release_conditions": list(release_conditions or []),
        "timestamp": timestamp or now_utc(),
    }
    return QuarantineRecord(**body, record_digest=sha256_digest(body))
