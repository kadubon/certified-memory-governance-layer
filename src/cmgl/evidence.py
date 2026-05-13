from __future__ import annotations

from datetime import datetime

from cmgl.digest import sha256_digest
from cmgl.models import (
    ActivePromotionReceipt,
    EvidenceManifest,
    InputSetManifest,
    MemoryCandidate,
    MemoryEvent,
    PromotionEvidenceBundle,
    ReplayEvidence,
    ShadowTrialReceipt,
    VersionedMemoryRef,
)
from cmgl.time import now_utc


def versioned_ref_from_event(event: MemoryEvent) -> VersionedMemoryRef | None:
    """Return a version-bound memory reference when an event has an update id."""

    if event.memory_update_id is None:
        return None
    return VersionedMemoryRef(
        memory_id=event.memory_id,
        memory_update_id=event.memory_update_id,
        content_digest=event.content_digest,
        status=event.status,
    )


def build_evidence_manifest(
    candidate: MemoryCandidate,
    *,
    timestamp: datetime | None = None,
) -> EvidenceManifest | None:
    """Build the minimal CMGL evidence manifest for a candidate.

    The manifest binds candidate id, current memory update id, content digest, normalized
    digest, source event hashes, and checker version. It does not claim factual truth.
    """

    memory_ref = versioned_ref_from_event(candidate.event)
    if memory_ref is None:
        return None

    created_at = timestamp or now_utc()
    body = {
        "schema_version": "cmgl.evidence_manifest.v1",
        "candidate_id": candidate.candidate_id,
        "memory_ref": memory_ref,
        "source_event_hashes": candidate.event.source_event_hashes,
        "normalized_content_digest": candidate.normalized_content_digest,
        "checker_version": candidate.event.checker_version,
        "created_at": created_at,
    }
    return EvidenceManifest(**body, manifest_digest=sha256_digest(body))


def build_input_set_manifest(
    candidate: MemoryCandidate,
    *,
    input_event_ids: list[str] | None = None,
    input_event_digests: list[str] | None = None,
    timestamp: datetime | None = None,
) -> InputSetManifest:
    if candidate.event.memory_update_id is None:
        raise ValueError("input set manifest requires memory_update_id")
    created_at = timestamp or now_utc()
    candidate_digest = sha256_digest(candidate)
    body = {
        "schema_version": "cmgl.input_set_manifest.v1",
        "manifest_id": f"input-set:{candidate.candidate_id}",
        "candidate_id": candidate.candidate_id,
        "memory_id": candidate.event.memory_id,
        "memory_update_id": candidate.event.memory_update_id,
        "candidate_digest": candidate_digest,
        "content_digest": candidate.event.content_digest,
        "input_event_ids": input_event_ids or [],
        "input_event_digests": input_event_digests or candidate.event.source_event_hashes,
        "replay_digest": sha256_digest(
            {
                "candidate_digest": candidate_digest,
                "input_event_digests": input_event_digests or candidate.event.source_event_hashes,
            }
        ),
        "created_at": created_at,
    }
    return InputSetManifest(**body, manifest_digest=sha256_digest(body))


def build_replay_evidence(
    input_set: InputSetManifest,
    *,
    checker_version: str,
    accepted: bool = True,
    reason_codes: list[str] | None = None,
    timestamp: datetime | None = None,
) -> ReplayEvidence:
    body = {
        "schema_version": "cmgl.replay_evidence.v1",
        "replay_id": f"replay:{input_set.manifest_id}",
        "input_set_manifest_digest": input_set.manifest_digest,
        "replay_digest": input_set.replay_digest,
        "checker_version": checker_version,
        "accepted": accepted,
        "reason_codes": list(reason_codes or []),
        "timestamp": timestamp or now_utc(),
    }
    return ReplayEvidence(**body, evidence_digest=sha256_digest(body))


def build_promotion_evidence_bundle(
    candidate: MemoryCandidate,
    *,
    evidence_manifest: EvidenceManifest,
    input_set_manifest: InputSetManifest,
    replay_evidence: ReplayEvidence,
    shadow_receipt: ShadowTrialReceipt | None = None,
    active_promotion_receipt: ActivePromotionReceipt | None = None,
    timestamp: datetime | None = None,
) -> PromotionEvidenceBundle:
    body = {
        "schema_version": "cmgl.promotion_evidence_bundle.v1",
        "candidate": candidate,
        "evidence_manifest": evidence_manifest,
        "input_set_manifest": input_set_manifest,
        "replay_evidence": replay_evidence,
        "shadow_receipt": shadow_receipt,
        "active_promotion_receipt": active_promotion_receipt,
        "timestamp": timestamp or now_utc(),
    }
    return PromotionEvidenceBundle(**body, bundle_digest=sha256_digest(body))
