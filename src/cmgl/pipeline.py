from __future__ import annotations

from dataclasses import dataclass

from cmgl.admission import candidate_from_event
from cmgl.evidence import build_evidence_manifest, build_promotion_evidence_bundle
from cmgl.ledger import AppendOnlyLedger
from cmgl.lifecycle import (
    make_active_promotion_receipt,
    make_quarantine_record,
    make_shadow_trial_receipt,
)
from cmgl.models import (
    ActivePromotionReceipt,
    AdmissionDecision,
    AuthorityBundle,
    AuthorityEvidenceBundle,
    AuthorityReceipt,
    EvidenceManifest,
    InputSetManifest,
    LedgerAppendReceipt,
    MemoryCandidate,
    MemoryEvent,
    MemoryStatus,
    MetricResult,
    PromotionEvidenceBundle,
    PromotionReceipt,
    QuarantineRecord,
    ReplayEvidence,
    ShadowTrialReceipt,
)
from cmgl.policy import AdmissionPolicy, make_promotion_receipt
from cmgl.receipt_verifier import PromotionVerifier


@dataclass(frozen=True)
class PromotionPipelineResult:
    event: MemoryEvent
    candidate: MemoryCandidate
    evidence_manifest: EvidenceManifest | None
    promotion_receipt: PromotionReceipt
    append_receipts: list[LedgerAppendReceipt]
    shadow_receipt: ShadowTrialReceipt | None = None
    active_promotion_receipt: ActivePromotionReceipt | None = None
    quarantine_record: QuarantineRecord | None = None
    strict_verification: MetricResult | None = None


class PromotionPipeline:
    def __init__(
        self,
        *,
        ledger: AppendOnlyLedger,
        policy: AdmissionPolicy | None = None,
        persist_append_receipts: bool = True,
    ) -> None:
        self.ledger = ledger
        self.policy = policy or AdmissionPolicy()
        self.persist_append_receipts = persist_append_receipts

    def promote(
        self,
        event: MemoryEvent,
        *,
        as_fact: bool = True,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
        evidence_manifest: EvidenceManifest | None = None,
        input_set_manifest: InputSetManifest | None = None,
        replay_evidence: ReplayEvidence | None = None,
        promotion_evidence_bundle: PromotionEvidenceBundle | None = None,
        profile: str = "simple",
    ) -> PromotionPipelineResult:
        append_receipts: list[LedgerAppendReceipt] = []
        shadow = None
        active = None
        strict_verification = None

        if profile == "strict" and event.status in {
            MemoryStatus.RAW,
            MemoryStatus.CANDIDATE,
            MemoryStatus.VERIFIED_SHADOW,
        }:
            original_candidate = candidate_from_event(event)
            for record_type, original_payload in [
                ("memory_event", event),
                ("memory_candidate", original_candidate),
            ]:
                _, append_receipt = self.ledger.append_with_receipt(
                    record_type,
                    original_payload,
                    persist_receipt=self.persist_append_receipts,
                )
                append_receipts.append(append_receipt)

            strict_seed_event = event.model_copy(update={"status": MemoryStatus.CERTIFIED})
            strict_candidate = candidate_from_event(strict_seed_event)
            evidence = (
                promotion_evidence_bundle.evidence_manifest
                if promotion_evidence_bundle is not None
                else evidence_manifest
            )
            input_set = (
                promotion_evidence_bundle.input_set_manifest
                if promotion_evidence_bundle is not None
                else input_set_manifest
            )
            replay = (
                promotion_evidence_bundle.replay_evidence
                if promotion_evidence_bundle is not None
                else replay_evidence
            )
            preflight = PromotionVerifier().verify(
                strict_candidate,
                make_promotion_receipt(
                    candidate_id=strict_candidate.candidate_id,
                    decision=AdmissionDecision.ADMIT,
                    checks={},
                    reason_codes=[],
                    checker_version=strict_seed_event.checker_version,
                    policy_version=self.policy.policy_version,
                    memory_id=strict_seed_event.memory_id,
                    memory_update_id=strict_seed_event.memory_update_id,
                    content_digest=strict_seed_event.content_digest,
                    evidence_manifest_digest=None if evidence is None else evidence.manifest_digest,
                    rule_ids=["cmgl.rule.admission.passed"],
                ),
                evidence_manifest=evidence,
                input_set_manifest=input_set,
                replay_evidence=replay,
                shadow_receipt=promotion_evidence_bundle.shadow_receipt
                if promotion_evidence_bundle is not None
                else None,
                active_promotion_receipt=promotion_evidence_bundle.active_promotion_receipt
                if promotion_evidence_bundle is not None
                else None,
                current_update_id=strict_seed_event.memory_update_id,
            )
            strict_required_reasons = [
                reason
                for reason in preflight.reason_codes
                if reason
                in {
                    "evidence_manifest.missing",
                    "promotion.input_set_manifest_missing",
                    "promotion.replay_evidence_missing",
                    "promotion.input_set_candidate_mismatch",
                    "promotion.input_set_update_mismatch",
                    "promotion.input_set_content_digest_mismatch",
                    "promotion.input_set_candidate_digest_mismatch",
                    "promotion.replay_input_set_mismatch",
                    "promotion.replay_digest_mismatch",
                    "promotion.replay_rejected",
                }
            ]
            if strict_required_reasons:
                candidate = strict_candidate
                receipt = make_promotion_receipt(
                    candidate_id=candidate.candidate_id,
                    decision=AdmissionDecision.BLOCK,
                    checks={"strict_promotion_evidence_bound": False},
                    reason_codes=strict_required_reasons,
                    checker_version=event.checker_version,
                    policy_version=self.policy.policy_version,
                    memory_id=event.memory_id,
                    memory_update_id=event.memory_update_id,
                    content_digest=event.content_digest,
                    evidence_manifest_digest=None if evidence is None else evidence.manifest_digest,
                    rule_ids=[f"cmgl.rule.{code}" for code in strict_required_reasons],
                )
                for record_type, pipeline_payload in [
                    ("memory_event", strict_seed_event),
                    ("memory_candidate", candidate),
                    ("promotion_receipt", receipt),
                ]:
                    _, append_receipt = self.ledger.append_with_receipt(
                        record_type,
                        pipeline_payload,
                        persist_receipt=self.persist_append_receipts,
                    )
                    append_receipts.append(append_receipt)
                blocked_quarantine = make_quarantine_record(
                    target=receipt,
                    target_type="promotion_receipt",
                    reason_codes=receipt.reason_codes,
                )
                _, append_receipt = self.ledger.append_with_receipt(
                    "quarantine_record",
                    blocked_quarantine,
                    persist_receipt=self.persist_append_receipts,
                )
                append_receipts.append(append_receipt)
                return PromotionPipelineResult(
                    event=strict_seed_event,
                    candidate=candidate,
                    evidence_manifest=evidence,
                    promotion_receipt=receipt,
                    append_receipts=append_receipts,
                    quarantine_record=blocked_quarantine,
                    strict_verification=preflight,
                )

            shadow_event = event.model_copy(update={"status": MemoryStatus.VERIFIED_SHADOW})
            shadow_candidate = candidate_from_event(shadow_event)
            shadow = make_shadow_trial_receipt(shadow_candidate, admitted=True)
            for record_type, shadow_payload in [
                ("memory_event", shadow_event),
                ("memory_candidate", shadow_candidate),
                ("shadow_trial_receipt", shadow),
            ]:
                _, append_receipt = self.ledger.append_with_receipt(
                    record_type,
                    shadow_payload,
                    persist_receipt=self.persist_append_receipts,
                )
                append_receipts.append(append_receipt)
            pipeline_event = strict_seed_event
        else:
            pipeline_event = event

        candidate = candidate_from_event(pipeline_event)
        evidence = (
            promotion_evidence_bundle.evidence_manifest
            if promotion_evidence_bundle is not None
            else evidence_manifest
        ) or build_evidence_manifest(candidate)
        receipt = self.policy.evaluate(
            candidate,
            as_fact=as_fact,
            evidence_manifest=evidence,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        pipeline_input_set = (
            promotion_evidence_bundle.input_set_manifest
            if promotion_evidence_bundle is not None
            else input_set_manifest
        )
        pipeline_replay = (
            promotion_evidence_bundle.replay_evidence
            if promotion_evidence_bundle is not None
            else replay_evidence
        )
        pipeline_payloads: list[tuple[str, object | None]] = [
            ("memory_event", pipeline_event),
            ("memory_candidate", candidate),
            ("evidence_manifest", evidence),
            ("input_set_manifest", pipeline_input_set),
            ("replay_evidence", pipeline_replay),
            ("promotion_receipt", receipt),
        ]
        for record_type, payload_obj in pipeline_payloads:
            if payload_obj is None:
                continue
            _, append_receipt = self.ledger.append_with_receipt(
                record_type,
                payload_obj,
                persist_receipt=self.persist_append_receipts,
            )
            append_receipts.append(append_receipt)

        quarantine: QuarantineRecord | None = None
        if profile == "strict" and receipt.decision == AdmissionDecision.ADMIT:
            active = make_active_promotion_receipt(
                candidate,
                source_receipt_digest=receipt.receipt_digest,
                admitted=True,
            )
            _, append_receipt = self.ledger.append_with_receipt(
                "active_promotion_receipt",
                active,
                persist_receipt=self.persist_append_receipts,
            )
            append_receipts.append(append_receipt)
            if evidence is not None and shadow is not None:
                bundle_input_set = (
                    promotion_evidence_bundle.input_set_manifest
                    if promotion_evidence_bundle is not None
                    else input_set_manifest
                )
                bundle_replay = (
                    promotion_evidence_bundle.replay_evidence
                    if promotion_evidence_bundle is not None
                    else replay_evidence
                )
                if bundle_input_set is None or bundle_replay is None:
                    raise ValueError("strict promotion requires input set and replay evidence")
                bundle = build_promotion_evidence_bundle(
                    candidate,
                    evidence_manifest=evidence,
                    input_set_manifest=bundle_input_set,
                    replay_evidence=bundle_replay,
                    shadow_receipt=shadow,
                    active_promotion_receipt=active,
                )
                _, append_receipt = self.ledger.append_with_receipt(
                    "promotion_evidence_bundle",
                    bundle,
                    persist_receipt=self.persist_append_receipts,
                )
                append_receipts.append(append_receipt)
                strict_verification = PromotionVerifier().verify(
                    candidate,
                    receipt,
                    evidence_manifest=evidence,
                    input_set_manifest=bundle.input_set_manifest,
                    replay_evidence=bundle.replay_evidence,
                    shadow_receipt=shadow,
                    active_promotion_receipt=active,
                    current_update_id=candidate.event.memory_update_id,
                )
        elif receipt.decision == AdmissionDecision.SHADOW:
            shadow = make_shadow_trial_receipt(candidate, admitted=True)
            _, append_receipt = self.ledger.append_with_receipt(
                "shadow_trial_receipt",
                shadow,
                persist_receipt=self.persist_append_receipts,
            )
            append_receipts.append(append_receipt)
        elif receipt.decision in {AdmissionDecision.BLOCK, AdmissionDecision.QUARANTINE}:
            quarantine = make_quarantine_record(
                target=receipt,
                target_type="promotion_receipt",
                reason_codes=receipt.reason_codes or ["promotion.blocked"],
            )
            _, append_receipt = self.ledger.append_with_receipt(
                "quarantine_record",
                quarantine,
                persist_receipt=self.persist_append_receipts,
            )
            append_receipts.append(append_receipt)

        return PromotionPipelineResult(
            event=pipeline_event,
            candidate=candidate,
            evidence_manifest=evidence,
            promotion_receipt=receipt,
            append_receipts=append_receipts,
            shadow_receipt=shadow,
            active_promotion_receipt=active,
            quarantine_record=quarantine,
            strict_verification=strict_verification,
        )
