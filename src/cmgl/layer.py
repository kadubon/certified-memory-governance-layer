from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from cmgl.admission import RetrievalFilterResult, filter_retrieval
from cmgl.audit import contamination_report, stale_use_report, telemetry_audit_report
from cmgl.backends.inmemory import InMemoryBackend
from cmgl.backends.protocol import MemoryBackend
from cmgl.checker import LocalDeterministicChecker, PromotionChecker
from cmgl.config import CMGLConfig, config_to_policy_kwargs
from cmgl.conformance import audit_ledger_conformance
from cmgl.current import resolve_current_events
from cmgl.digest import sha256_digest
from cmgl.ledger import AppendOnlyLedger, LedgerVerificationResult
from cmgl.models import (
    AdapterOperationReceipt,
    AuthorityBundle,
    AuthorityEvidenceBundle,
    AuthorityReceipt,
    ConformanceProfile,
    ConformanceReport,
    ContaminationLane,
    EvidenceBindingReport,
    GovernanceProfile,
    GovernanceReceiptBundle,
    JsonContent,
    MemoryEvent,
    MemoryStatus,
    MemoryTelemetryEvent,
    TelemetryAuditReport,
)
from cmgl.obligations import ObligationVerifier
from cmgl.pipeline import PromotionPipeline, PromotionPipelineResult
from cmgl.policy import AdmissionPolicy
from cmgl.time import now_utc


@dataclass(frozen=True)
class GovernanceAuditResult:
    stale: dict[str, object]
    contamination: dict[str, object]
    telemetry: TelemetryAuditReport


class GovernanceLayer:
    """High-level local governance facade for immediately usable CMGL integrations."""

    def __init__(
        self,
        *,
        ledger: str | Path | AppendOnlyLedger | None = None,
        policy: AdmissionPolicy | None = None,
        backend: MemoryBackend | None = None,
        config: CMGLConfig | None = None,
        profile: GovernanceProfile | str = GovernanceProfile.STRICT,
        checker: PromotionChecker | None = None,
    ) -> None:
        self.config = config or CMGLConfig()
        self.profile = GovernanceProfile(profile)
        self.ledger = (
            ledger
            if isinstance(ledger, AppendOnlyLedger)
            else AppendOnlyLedger(ledger or self.config.ledger.path)
        )
        self.policy = policy or AdmissionPolicy(**config_to_policy_kwargs(self.config))
        self.backend = backend or InMemoryBackend()
        self.checker = checker or LocalDeterministicChecker()
        self.pipeline = PromotionPipeline(
            ledger=self.ledger,
            policy=self.policy,
            persist_append_receipts=self.config.ledger.persist_append_receipts,
        )

    def write_memory(
        self,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> PromotionPipelineResult:
        event = self.backend.write(
            content,
            lane=lane,
            authority_scope=authority_scope,
            metadata=dict(metadata or {}),
        )
        return self._promote_event(
            event,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )

    def write_memory_bundle(
        self,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> GovernanceReceiptBundle:
        result = self.write_memory(
            content,
            lane=lane,
            authority_scope=authority_scope,
            metadata=metadata,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        return self.receipt_bundle(result)

    def update_memory(
        self,
        memory_id: str,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> PromotionPipelineResult:
        event = self.backend.update(
            memory_id,
            content,
            lane=lane,
            authority_scope=authority_scope,
            metadata=dict(metadata or {}),
        )
        return self._promote_event(
            event,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )

    def update_memory_bundle(
        self,
        memory_id: str,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> GovernanceReceiptBundle:
        result = self.update_memory(
            memory_id,
            content,
            lane=lane,
            authority_scope=authority_scope,
            metadata=metadata,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        return self.receipt_bundle(result)

    def delete_memory(
        self,
        memory_id: str,
        *,
        reason: str,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> PromotionPipelineResult:
        event = self.backend.delete(memory_id, reason=reason)
        return self._promote_event(
            event,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )

    def delete_memory_bundle(
        self,
        memory_id: str,
        *,
        reason: str,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> GovernanceReceiptBundle:
        result = self.delete_memory(
            memory_id,
            reason=reason,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        return self.receipt_bundle(result)

    def filter_retrieval(
        self,
        query: str,
        events: list[MemoryEvent] | None = None,
        *,
        limit: int = 10,
        include_audit_versions: bool = False,
    ) -> RetrievalFilterResult:
        raw_events = events if events is not None else self.backend.retrieve(query, limit=limit)
        current_events = resolve_current_events(raw_events, include_audit=include_audit_versions)
        if include_audit_versions:
            events_for_policy = current_events
        else:
            current_keys = {(event.memory_id, event.memory_update_id) for event in current_events}
            events_for_policy = [
                event
                if (event.memory_id, event.memory_update_id) in current_keys
                else event.model_copy(update={"status": MemoryStatus.SUPERSEDED})
                if event.status
                in {
                    MemoryStatus.CERTIFIED,
                    MemoryStatus.ADMISSIBLE,
                    MemoryStatus.RAW,
                    MemoryStatus.CANDIDATE,
                    MemoryStatus.VERIFIED_SHADOW,
                }
                else event
                for event in raw_events
            ]
        retrieval_policy = replace(
            self.policy,
            require_authority_for_persistent_writes=False,
            require_explicit_evidence_manifest=False,
        )
        result = filter_retrieval(query, events_for_policy, policy=retrieval_policy)
        self.ledger.append_with_receipt(
            "retrieval_decision",
            result.decision,
            persist_receipt=self.config.ledger.persist_append_receipts,
        )
        return result

    def record_telemetry(self, event: MemoryTelemetryEvent) -> None:
        self.ledger.append_with_receipt(
            "telemetry_event",
            event,
            persist_receipt=self.config.ledger.persist_append_receipts,
        )

    def verify_ledger(self) -> LedgerVerificationResult:
        return self.ledger.verify_prefix()

    def audit(self) -> GovernanceAuditResult:
        return GovernanceAuditResult(
            stale=stale_use_report(self.ledger),
            contamination=contamination_report(self.ledger),
            telemetry=telemetry_audit_report(self.ledger),
        )

    def explain_memory(self, memory_id: str) -> list[EvidenceBindingReport]:
        profile = ConformanceProfile(self.profile.value)
        return ObligationVerifier(profile=profile).explain_memory(self.ledger, memory_id)

    def conformance_report(self) -> ConformanceReport:
        return audit_ledger_conformance(
            self.ledger,
            profile=ConformanceProfile(self.profile.value),
        )

    def receipt_bundle(
        self,
        result: PromotionPipelineResult,
        *,
        adapter_operation_receipt: AdapterOperationReceipt | None = None,
        backend_result: object | None = None,
    ) -> GovernanceReceiptBundle:
        conformance = self.conformance_report()
        body = {
            "schema_version": "cmgl.governance_receipt_bundle.v1",
            "event": result.event,
            "candidate": result.candidate,
            "evidence_manifest": result.evidence_manifest,
            "promotion_receipt": result.promotion_receipt,
            "append_receipts": result.append_receipts,
            "shadow_receipt": result.shadow_receipt,
            "active_promotion_receipt": result.active_promotion_receipt,
            "adapter_operation_receipt": adapter_operation_receipt,
            "quarantine_record_digest": None
            if result.quarantine_record is None
            else result.quarantine_record.record_digest,
            "strict_verification_status": None
            if result.strict_verification is None
            else result.strict_verification.status,
            "decision": result.promotion_receipt.decision,
            "conformance_ok": conformance.ok,
            "backend_result_digest": None
            if backend_result is None
            else sha256_digest(backend_result),
            "timestamp": now_utc(),
        }
        return GovernanceReceiptBundle(**body, bundle_digest=sha256_digest(body))

    def _promote_event(
        self,
        event: MemoryEvent,
        *,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> PromotionPipelineResult:
        if authority_bundle is not None:
            self.ledger.append_with_receipt(
                "authority_bundle",
                authority_bundle,
                persist_receipt=self.config.ledger.persist_append_receipts,
            )
        if authority_evidence_bundle is not None:
            self.ledger.append_with_receipt(
                "authority_evidence_bundle",
                authority_evidence_bundle,
                persist_receipt=self.config.ledger.persist_append_receipts,
            )
        if self.profile == GovernanceProfile.STRICT and event.status in {
            MemoryStatus.CERTIFIED,
            MemoryStatus.ADMISSIBLE,
            MemoryStatus.RAW,
            MemoryStatus.CANDIDATE,
            MemoryStatus.VERIFIED_SHADOW,
        }:
            checked_event = event.model_copy(
                update={
                    "status": MemoryStatus.CANDIDATE,
                    "checker_version": self.checker.checker_version,
                }
            )
            checked_candidate = self.checker.candidate_for_admission(checked_event)
            evidence, input_set, replay = self.checker.evidence_for(checked_candidate)
            return self.pipeline.promote(
                checked_event,
                authority_receipt=authority_receipt,
                authority_bundle=authority_bundle,
                authority_evidence_bundle=authority_evidence_bundle,
                evidence_manifest=evidence,
                input_set_manifest=input_set,
                replay_evidence=replay,
                profile="strict",
            )
        return self.pipeline.promote(
            event,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
            profile="strict" if self.profile == GovernanceProfile.STRICT else "simple",
        )
