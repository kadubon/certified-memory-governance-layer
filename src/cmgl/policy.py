from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from cmgl.authority import StrictAuthorityVerifier
from cmgl.digest import sha256_digest
from cmgl.evidence import build_evidence_manifest
from cmgl.models import (
    AdmissionDecision,
    AuthorityBundle,
    AuthorityEvidenceBundle,
    AuthorityReceipt,
    ContaminationLane,
    EvidenceManifest,
    MemoryCandidate,
    MemoryChallengeRecord,
    MemoryEventType,
    MemoryStatus,
    PromotionReceipt,
    ProtectedAction,
    RecordAbsenceNotice,
)
from cmgl.time import now_utc

PROTECTED_EVENT_TYPES = {
    MemoryEventType.MEMORY_WRITE,
    MemoryEventType.MEMORY_UPDATE,
    MemoryEventType.MEMORY_DELETE,
    MemoryEventType.MEMORY_TOMBSTONE,
}

PROTECTED_EVENT_ACTIONS = {
    MemoryEventType.MEMORY_WRITE: ProtectedAction.PERSISTENT_MEMORY_WRITE,
    MemoryEventType.MEMORY_UPDATE: ProtectedAction.PERSISTENT_MEMORY_UPDATE,
    MemoryEventType.MEMORY_DELETE: ProtectedAction.PERSISTENT_MEMORY_DELETE,
    MemoryEventType.MEMORY_TOMBSTONE: ProtectedAction.MEMORY_TOMBSTONE,
}


def make_promotion_receipt(
    *,
    candidate_id: str,
    decision: AdmissionDecision,
    checks: dict[str, bool | None],
    reason_codes: list[str],
    checker_version: str,
    policy_version: str,
    memory_id: str | None = None,
    memory_update_id: str | None = None,
    content_digest: str | None = None,
    evidence_manifest_digest: str | None = None,
    rule_ids: list[str] | None = None,
    timestamp: datetime | None = None,
) -> PromotionReceipt:
    receipt_time = timestamp or now_utc()
    body = {
        "schema_version": "cmgl.promotion_receipt.v1",
        "candidate_id": candidate_id,
        "decision": decision,
        "checks": checks,
        "reason_codes": reason_codes,
        "checker_version": checker_version,
        "policy_version": policy_version,
        "memory_id": memory_id,
        "memory_update_id": memory_update_id,
        "content_digest": content_digest,
        "evidence_manifest_digest": evidence_manifest_digest,
        "rule_ids": rule_ids or [],
        "timestamp": receipt_time,
    }
    return PromotionReceipt(
        **body,
        receipt_digest=sha256_digest(body),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class AdmissionPolicy:
    """Deterministic admission policy."""

    policy_version: str = "cmgl.policy.v1"
    max_provenance_depth: int = 8
    allow_weak_personal_memory: bool = True
    require_version_binding: bool = True
    require_explicit_evidence_manifest: bool = False
    provenance_exceeded_decision: AdmissionDecision = AdmissionDecision.BLOCK
    require_authority_for_persistent_writes: bool = False
    strict_authority_verification: bool = True
    require_authority_bundle: bool = False
    allowed_statuses: set[MemoryStatus] = field(
        default_factory=lambda: {MemoryStatus.CERTIFIED, MemoryStatus.ADMISSIBLE}
    )
    blocked_statuses: set[MemoryStatus] = field(
        default_factory=lambda: {
            MemoryStatus.RAW,
            MemoryStatus.CANDIDATE,
            MemoryStatus.VERIFIED_SHADOW,
            MemoryStatus.SUPERSEDED,
            MemoryStatus.CONTRADICTED,
            MemoryStatus.TOMBSTONED,
            MemoryStatus.QUARANTINED,
        }
    )
    blocked_fact_lanes: set[ContaminationLane] = field(
        default_factory=lambda: {
            ContaminationLane.MODEL_INFERENCE,
            ContaminationLane.REGENERATED_SUMMARY,
            ContaminationLane.SYNTHETIC_EVAL,
        }
    )

    def evaluate(
        self,
        candidate: MemoryCandidate,
        *,
        as_fact: bool = True,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
        evidence_manifest: EvidenceManifest | None = None,
        challenge_records: list[MemoryChallengeRecord] | None = None,
        absence_notices: list[RecordAbsenceNotice] | None = None,
        now: datetime | None = None,
    ) -> PromotionReceipt:
        event = candidate.event
        check_time = _utc(now or now_utc())
        evidence = evidence_manifest
        if evidence is None and not self.require_explicit_evidence_manifest:
            evidence = build_evidence_manifest(candidate)
        checks: dict[str, bool | None] = {
            "status_allowed": None,
            "lane_allowed": None,
            "version_binding_present": None,
            "evidence_manifest_bound": None,
            "provenance_depth_allowed": None,
            "valid_from_allowed": None,
            "valid_to_allowed": None,
            "source_evidence_present": None,
            "not_contradicted": None,
            "not_tombstone_marker": None,
            "authority_allowed": None,
            "not_open_challenged": None,
            "required_records_present": None,
        }
        reason_codes: list[str] = []

        def fail(name: str, code: str) -> None:
            checks[name] = False
            reason_codes.append(code)

        def pass_check(name: str) -> None:
            checks[name] = True

        if event.status in self.allowed_statuses:
            pass_check("status_allowed")
        else:
            fail("status_allowed", f"status.{event.status.value}.blocked")

        if event.status in {
            MemoryStatus.SUPERSEDED,
            MemoryStatus.CONTRADICTED,
            MemoryStatus.TOMBSTONED,
            MemoryStatus.QUARANTINED,
        }:
            reason_codes.append(f"terminal_status.{event.status.value}")

        if as_fact and event.lane in self.blocked_fact_lanes:
            fail("lane_allowed", f"lane.{event.lane.value}.blocked_as_fact")
        elif as_fact and event.lane == ContaminationLane.SUMMARY:
            fail("lane_allowed", "lane.summary.summary_not_fact")
        else:
            pass_check("lane_allowed")

        if self.require_version_binding and event.memory_update_id is None:
            fail("version_binding_present", "version_binding.missing")
        else:
            pass_check("version_binding_present")

        if self.require_version_binding and evidence is None:
            fail("evidence_manifest_bound", "evidence_manifest.missing")
        elif evidence is not None and (
            evidence.candidate_id != candidate.candidate_id
            or evidence.memory_ref.memory_id != event.memory_id
            or evidence.memory_ref.memory_update_id != event.memory_update_id
            or evidence.memory_ref.content_digest != event.content_digest
            or evidence.normalized_content_digest != candidate.normalized_content_digest
        ):
            fail("evidence_manifest_bound", "evidence_manifest.mismatch")
        else:
            pass_check("evidence_manifest_bound")

        if event.provenance_depth > self.max_provenance_depth:
            fail("provenance_depth_allowed", "provenance_depth.exceeded")
        else:
            pass_check("provenance_depth_allowed")

        if event.valid_from is not None and _utc(event.valid_from) > check_time:
            fail("valid_from_allowed", "valid_from.future")
        else:
            pass_check("valid_from_allowed")

        if event.valid_to is not None and _utc(event.valid_to) < check_time:
            fail("valid_to_allowed", "valid_to.expired")
        else:
            pass_check("valid_to_allowed")

        weak_personal_allowed = (
            event.lane == ContaminationLane.USER_CLAIM and self.allow_weak_personal_memory
        )
        if event.source_event_hashes or weak_personal_allowed:
            pass_check("source_evidence_present")
        else:
            fail("source_evidence_present", "source_event_hashes.missing")

        if candidate.contradicted_by or event.status == MemoryStatus.CONTRADICTED:
            fail("not_contradicted", "candidate.contradicted")
        else:
            pass_check("not_contradicted")

        if candidate.tombstone_of is not None:
            fail("not_tombstone_marker", "candidate.tombstone_marker")
        else:
            pass_check("not_tombstone_marker")

        open_challenges = [
            challenge
            for challenge in challenge_records or []
            if challenge.memory_id == event.memory_id and challenge.status.value == "open"
        ]
        if open_challenges:
            fail("not_open_challenged", "challenge.open")
        else:
            pass_check("not_open_challenged")

        blocking_absences = [
            notice
            for notice in absence_notices or []
            if notice.memory_id == event.memory_id
            and notice.notice_type.value in {"missing_source", "missing_evidence"}
        ]
        if blocking_absences:
            fail(
                "required_records_present",
                blocking_absences[0].reason_codes[0]
                if blocking_absences[0].reason_codes
                else "absence.missing_evidence",
            )
        else:
            pass_check("required_records_present")

        if (
            self.require_authority_for_persistent_writes
            and event.event_type in PROTECTED_EVENT_TYPES
        ):
            receipt = (
                authority_evidence_bundle.receipt
                if authority_evidence_bundle is not None
                else authority_bundle.receipt
                if authority_bundle is not None
                else authority_receipt
            )
            verifier = StrictAuthorityVerifier()
            if (
                self.require_authority_bundle
                and authority_bundle is None
                and authority_evidence_bundle is None
            ):
                fail("authority_allowed", "authority.bundle_missing")
                if (
                    receipt is not None
                    and self.strict_authority_verification
                    and not verifier.allows(receipt)
                ):
                    reason_codes.append("authority.strict_verification_failed")
            elif receipt is None:
                fail("authority_allowed", "authority.missing")
            elif receipt.decision != AdmissionDecision.ADMIT:
                fail("authority_allowed", "authority.blocked")
            elif receipt.authority_scope != event.authority_scope:
                fail("authority_allowed", "authority.scope_mismatch")
            elif receipt.action != PROTECTED_EVENT_ACTIONS[event.event_type]:
                fail("authority_allowed", "authority.action_mismatch")
            elif (
                authority_evidence_bundle is not None
                and authority_evidence_bundle.retained_channel_blocking
            ):
                fail("authority_allowed", "authority.retained_channel_blocking")
            elif (
                (
                    self.strict_authority_verification
                    and authority_evidence_bundle is not None
                    and verifier.verify_evidence_bundle(authority_evidence_bundle).status.value
                    != "valid"
                )
                or (
                    self.strict_authority_verification
                    and authority_bundle is not None
                    and not verifier.allows_bundle(authority_bundle)
                )
                or (
                    self.strict_authority_verification
                    and authority_bundle is None
                    and not verifier.allows(receipt)
                )
            ):
                fail("authority_allowed", "authority.strict_verification_failed")
            else:
                pass_check("authority_allowed")
        else:
            pass_check("authority_allowed")

        failed = [key for key, value in checks.items() if value is False]
        if not failed:
            decision = AdmissionDecision.ADMIT
        elif (
            failed == ["provenance_depth_allowed"]
            and self.provenance_exceeded_decision == AdmissionDecision.SHADOW
        ):
            decision = AdmissionDecision.SHADOW
        else:
            decision = AdmissionDecision.BLOCK

        return make_promotion_receipt(
            candidate_id=candidate.candidate_id,
            decision=decision,
            checks=checks,
            reason_codes=reason_codes,
            checker_version=event.checker_version,
            policy_version=self.policy_version,
            memory_id=event.memory_id,
            memory_update_id=event.memory_update_id,
            content_digest=event.content_digest,
            evidence_manifest_digest=None if evidence is None else evidence.manifest_digest,
            rule_ids=[f"cmgl.rule.{code}" for code in reason_codes]
            or ["cmgl.rule.admission.passed"],
        )
