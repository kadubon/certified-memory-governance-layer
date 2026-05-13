from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from cmgl.digest import sha256_digest
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import (
    ActivePromotionReceipt,
    AdmissionDecision,
    AuthorityBundle,
    AuthorityEvidenceBundle,
    ConformanceProfile,
    EvidenceBindingReport,
    EvidenceManifest,
    InputSetManifest,
    MemoryCandidate,
    MemoryChallengeRecord,
    MemoryEventType,
    MetricStatus,
    ObligationGraph,
    ObligationStatus,
    PromotionReceipt,
    ProtectedAction,
    RecordAbsenceNotice,
    ReplayEvidence,
    ShadowTrialReceipt,
)
from cmgl.receipt_verifier import PromotionVerifier
from cmgl.rules import unknown_reason_codes, unknown_rule_ids
from cmgl.time import now_utc

_PROTECTED_EVENT_ACTIONS = {
    MemoryEventType.MEMORY_WRITE: ProtectedAction.PERSISTENT_MEMORY_WRITE,
    MemoryEventType.MEMORY_UPDATE: ProtectedAction.PERSISTENT_MEMORY_UPDATE,
    MemoryEventType.MEMORY_DELETE: ProtectedAction.PERSISTENT_MEMORY_DELETE,
    MemoryEventType.MEMORY_TOMBSTONE: ProtectedAction.MEMORY_TOMBSTONE,
}


class ObligationVerifier:
    """Ledger-wide verifier for receipt evidence obligations."""

    def __init__(self, *, profile: ConformanceProfile = ConformanceProfile.STRICT) -> None:
        self.profile = profile

    def verify(
        self,
        ledger: str | Path | AppendOnlyLedger,
    ) -> ObligationGraph:
        active_ledger = ledger if isinstance(ledger, AppendOnlyLedger) else AppendOnlyLedger(ledger)
        records = list(active_ledger.iter_records())
        index = _LedgerIndex.from_records(records)
        reports: list[EvidenceBindingReport] = []

        for receipt in index.promotion_receipts:
            reports.append(self._verify_promotion_receipt(receipt, index))

        graph_ok = self._graph_ok(reports)
        body = {
            "schema_version": "cmgl.obligation_graph.v1",
            "profile": self.profile,
            "ok": graph_ok,
            "reports": reports,
            "timestamp": now_utc(),
        }
        return ObligationGraph(**body, graph_digest=sha256_digest(body))

    def explain_memory(
        self,
        ledger: str | Path | AppendOnlyLedger,
        memory_id: str,
    ) -> list[EvidenceBindingReport]:
        graph = self.verify(ledger)
        return [report for report in graph.reports if report.memory_id == memory_id]

    def _verify_promotion_receipt(
        self,
        receipt: PromotionReceipt,
        index: _LedgerIndex,
    ) -> EvidenceBindingReport:
        candidate = index.candidates.get(receipt.candidate_id)
        required = [
            "memory_candidate",
            "evidence_manifest",
            "input_set_manifest",
            "replay_evidence",
            "shadow_trial_receipt",
            "active_promotion_receipt",
        ]
        matched: list[str] = []
        reason_codes: list[str] = []
        status = ObligationStatus.SATISFIED

        if unknown_rule_ids(receipt.rule_ids):
            reason_codes.append("receipt.unknown_rule_id")
            status = ObligationStatus.UNKNOWN
        if unknown_reason_codes(receipt.reason_codes):
            reason_codes.append("receipt.unknown_reason_code")
            status = ObligationStatus.UNKNOWN

        if candidate is None:
            reason_codes.append("conformance.obligation_missing")
            status = self._missing_status()
            return self._report(
                subject_type="promotion_receipt",
                subject_digest=receipt.receipt_digest,
                status=status,
                required_record_types=required,
                matched_record_digests=matched,
                reason_codes=reason_codes,
            )
        matched.append(sha256_digest(candidate))

        evidence = (
            index.evidence_by_digest.get(receipt.evidence_manifest_digest)
            if receipt.evidence_manifest_digest is not None
            else None
        )
        input_set = index.input_set_by_candidate.get(candidate.candidate_id)
        replay = (
            index.replay_by_input_digest.get(input_set.manifest_digest)
            if input_set is not None
            else None
        )
        shadow = index.shadow_by_candidate.get(candidate.candidate_id)
        active = index.active_by_candidate_and_receipt.get(
            (candidate.candidate_id, receipt.receipt_digest)
        )

        for item in [evidence, input_set, replay, shadow, active]:
            if item is not None:
                matched.append(sha256_digest(item))

        if receipt.decision == AdmissionDecision.ADMIT:
            metric = PromotionVerifier().verify(
                candidate,
                receipt,
                evidence_manifest=evidence,
                input_set_manifest=input_set,
                replay_evidence=replay,
                shadow_receipt=shadow,
                active_promotion_receipt=active,
                current_update_id=candidate.event.memory_update_id,
            )
            if metric.status != MetricStatus.VALID:
                reason_codes.extend(metric.reason_codes)
                if any(code.endswith("mismatch") for code in metric.reason_codes):
                    status = ObligationStatus.MISMATCHED
                elif status == ObligationStatus.SATISFIED:
                    status = self._missing_status()

            action = _PROTECTED_EVENT_ACTIONS.get(candidate.event.event_type)
            if action is not None:
                required.append("authority_bundle")
                if not index.has_authority_for(action, candidate.event.authority_scope):
                    reason_codes.append("authority.bundle_missing")
                    if status == ObligationStatus.SATISFIED:
                        status = self._missing_status()

        for challenge in index.open_challenges.get(candidate.event.memory_id, []):
            reason_codes.extend(challenge.reason_codes or ["challenge.open"])
            status = self._missing_status()
            matched.append(challenge.record_digest)
        for notice in index.absence_notices.get(candidate.event.memory_id, []):
            reason_codes.extend(notice.reason_codes)
            status = self._missing_status()
            matched.append(notice.notice_digest)

        return self._report(
            subject_type="promotion_receipt",
            subject_digest=receipt.receipt_digest,
            memory_id=candidate.event.memory_id,
            memory_update_id=candidate.event.memory_update_id,
            status=status,
            required_record_types=required,
            matched_record_digests=matched,
            reason_codes=sorted(set(reason_codes)),
        )

    def _missing_status(self) -> ObligationStatus:
        if self.profile == ConformanceProfile.STRICT:
            return ObligationStatus.MISSING
        if self.profile == ConformanceProfile.OPERATIONAL:
            return ObligationStatus.DEGRADED
        return ObligationStatus.DEGRADED

    def _graph_ok(self, reports: list[EvidenceBindingReport]) -> bool:
        if self.profile == ConformanceProfile.LEGACY:
            return True
        if self.profile == ConformanceProfile.OPERATIONAL:
            return all(
                report.status not in {ObligationStatus.MISMATCHED, ObligationStatus.UNKNOWN}
                for report in reports
            )
        return all(report.status == ObligationStatus.SATISFIED for report in reports)

    def _report(
        self,
        *,
        subject_type: str,
        subject_digest: str | None,
        status: ObligationStatus,
        required_record_types: list[str],
        matched_record_digests: list[str],
        reason_codes: list[str],
        memory_id: str | None = None,
        memory_update_id: str | None = None,
    ) -> EvidenceBindingReport:
        body = {
            "schema_version": "cmgl.evidence_binding_report.v1",
            "subject_type": subject_type,
            "subject_digest": subject_digest,
            "memory_id": memory_id,
            "memory_update_id": memory_update_id,
            "status": status,
            "required_record_types": required_record_types,
            "matched_record_digests": matched_record_digests,
            "reason_codes": reason_codes,
            "timestamp": now_utc(),
        }
        return EvidenceBindingReport(**body, report_digest=sha256_digest(body))


class _LedgerIndex:
    def __init__(self) -> None:
        self.promotion_receipts: list[PromotionReceipt] = []
        self.candidates: dict[str, MemoryCandidate] = {}
        self.evidence_by_digest: dict[str, EvidenceManifest] = {}
        self.input_set_by_candidate: dict[str, InputSetManifest] = {}
        self.replay_by_input_digest: dict[str, ReplayEvidence] = {}
        self.shadow_by_candidate: dict[str, ShadowTrialReceipt] = {}
        self.active_by_candidate_and_receipt: dict[tuple[str, str], ActivePromotionReceipt] = {}
        self.authority_bundles: list[AuthorityBundle] = []
        self.authority_evidence_bundles: list[AuthorityEvidenceBundle] = []
        self.open_challenges: dict[str, list[MemoryChallengeRecord]] = defaultdict(list)
        self.absence_notices: dict[str, list[RecordAbsenceNotice]] = defaultdict(list)

    @classmethod
    def from_records(cls, records: Sequence[object]) -> _LedgerIndex:
        index = cls()
        for record in records:
            record_type = getattr(record, "record_type", None)
            payload = getattr(record, "payload", None)
            try:
                if record_type == "promotion_receipt":
                    index.promotion_receipts.append(PromotionReceipt.model_validate(payload))
                elif record_type == "memory_candidate":
                    candidate = MemoryCandidate.model_validate(payload)
                    index.candidates[candidate.candidate_id] = candidate
                elif record_type == "evidence_manifest":
                    evidence = EvidenceManifest.model_validate(payload)
                    index.evidence_by_digest[evidence.manifest_digest] = evidence
                elif record_type == "input_set_manifest":
                    input_set = InputSetManifest.model_validate(payload)
                    index.input_set_by_candidate[input_set.candidate_id] = input_set
                elif record_type == "replay_evidence":
                    replay = ReplayEvidence.model_validate(payload)
                    index.replay_by_input_digest[replay.input_set_manifest_digest] = replay
                elif record_type == "shadow_trial_receipt":
                    shadow = ShadowTrialReceipt.model_validate(payload)
                    index.shadow_by_candidate[shadow.candidate_id] = shadow
                elif record_type == "active_promotion_receipt":
                    active = ActivePromotionReceipt.model_validate(payload)
                    index.active_by_candidate_and_receipt[
                        (active.candidate_id, active.source_receipt_digest)
                    ] = active
                elif record_type == "authority_bundle":
                    index.authority_bundles.append(AuthorityBundle.model_validate(payload))
                elif record_type == "authority_evidence_bundle":
                    index.authority_evidence_bundles.append(
                        AuthorityEvidenceBundle.model_validate(payload)
                    )
                elif record_type == "memory_challenge_record":
                    challenge = MemoryChallengeRecord.model_validate(payload)
                    if challenge.status.value == "open":
                        index.open_challenges[challenge.memory_id].append(challenge)
                elif record_type == "record_absence_notice":
                    notice = RecordAbsenceNotice.model_validate(payload)
                    if notice.memory_id is not None and notice.notice_type.value in {
                        "missing_source",
                        "missing_evidence",
                    }:
                        index.absence_notices[notice.memory_id].append(notice)
            except ValidationError:
                continue
        return index

    def has_authority_for(self, action: ProtectedAction, authority_scope: str) -> bool:
        for authority_bundle in self.authority_bundles:
            if (
                authority_bundle.receipt.action == action
                and authority_bundle.receipt.authority_scope == authority_scope
            ):
                return True
        for evidence_bundle in self.authority_evidence_bundles:
            if (
                evidence_bundle.receipt.action == action
                and evidence_bundle.receipt.authority_scope == authority_scope
                and not evidence_bundle.retained_channel_blocking
            ):
                return True
        return False
