from __future__ import annotations

from datetime import datetime

from cmgl.digest import sha256_digest
from cmgl.evidence import build_evidence_manifest
from cmgl.models import (
    ActivePromotionReceipt,
    AuthorityReceipt,
    EvidenceManifest,
    InputSetManifest,
    LedgerIntegrityReceipt,
    MemoryCandidate,
    MetricResult,
    MetricStatus,
    PromotionReceipt,
    ReplayEvidence,
    ShadowTrialReceipt,
)
from cmgl.rules import unknown_reason_codes, unknown_rule_ids
from cmgl.time import now_utc


def verify_promotion_receipt(
    candidate: MemoryCandidate,
    receipt: PromotionReceipt,
    *,
    evidence_manifest: EvidenceManifest | None = None,
    current_update_id: str | None = None,
    timestamp: datetime | None = None,
) -> MetricResult:
    """Verify that a promotion receipt is bound to the current candidate version."""

    evidence = evidence_manifest or build_evidence_manifest(candidate)
    reason_codes: list[str] = []

    if receipt.candidate_id != candidate.candidate_id:
        reason_codes.append("receipt.candidate_id_mismatch")
    if receipt.memory_id != candidate.event.memory_id:
        reason_codes.append("receipt.memory_id_mismatch")
    if receipt.memory_update_id != candidate.event.memory_update_id:
        reason_codes.append("receipt.memory_update_id_mismatch")
    if current_update_id is not None and receipt.memory_update_id != current_update_id:
        reason_codes.append("receipt.not_current_update")
    if receipt.content_digest != candidate.event.content_digest:
        reason_codes.append("receipt.content_digest_mismatch")
    if evidence is None:
        reason_codes.append("evidence_manifest.missing")
    elif receipt.evidence_manifest_digest != evidence.manifest_digest:
        reason_codes.append("receipt.evidence_manifest_digest_mismatch")
    if not receipt.rule_ids:
        reason_codes.append("receipt.rule_ids_missing")
    if unknown := unknown_rule_ids(receipt.rule_ids):
        reason_codes.append("receipt.unknown_rule_id")
        reason_codes.extend([f"unknown_rule_id:{rule_id}" for rule_id in unknown])
    if unknown_codes := unknown_reason_codes(receipt.reason_codes):
        reason_codes.append("receipt.unknown_reason_code")
        reason_codes.extend([f"unknown_reason_code:{code}" for code in unknown_codes])

    status = MetricStatus.VALID if not reason_codes else MetricStatus.INVALID
    return MetricResult(
        metric_name="promotion_receipt_binding",
        status=status,
        value=0 if reason_codes else 1,
        reason_codes=reason_codes,
        evidence_ids=[] if evidence is None else [evidence.manifest_digest],
        timestamp=timestamp or now_utc(),
    )


class PromotionVerifier:
    """Strict verifier for OAWM/OASG-style receipt-backed promotion bundles."""

    def verify(
        self,
        candidate: MemoryCandidate,
        receipt: PromotionReceipt,
        *,
        evidence_manifest: EvidenceManifest | None,
        input_set_manifest: InputSetManifest | None,
        replay_evidence: ReplayEvidence | None,
        shadow_receipt: ShadowTrialReceipt | None,
        active_promotion_receipt: ActivePromotionReceipt | None,
        current_update_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> MetricResult:
        base = verify_promotion_receipt(
            candidate,
            receipt,
            evidence_manifest=evidence_manifest,
            current_update_id=current_update_id,
            timestamp=timestamp,
        )
        reason_codes = list(base.reason_codes)
        if evidence_manifest is None and "evidence_manifest.missing" not in reason_codes:
            reason_codes.append("evidence_manifest.missing")

        candidate_digest = sha256_digest(candidate)
        if input_set_manifest is None:
            reason_codes.append("promotion.input_set_manifest_missing")
        else:
            if input_set_manifest.candidate_id != candidate.candidate_id:
                reason_codes.append("promotion.input_set_candidate_mismatch")
            if input_set_manifest.memory_update_id != candidate.event.memory_update_id:
                reason_codes.append("promotion.input_set_update_mismatch")
            if input_set_manifest.content_digest != candidate.event.content_digest:
                reason_codes.append("promotion.input_set_content_digest_mismatch")
            if input_set_manifest.candidate_digest != candidate_digest:
                reason_codes.append("promotion.input_set_candidate_digest_mismatch")

        if replay_evidence is None:
            reason_codes.append("promotion.replay_evidence_missing")
        elif input_set_manifest is not None:
            if replay_evidence.input_set_manifest_digest != input_set_manifest.manifest_digest:
                reason_codes.append("promotion.replay_input_set_mismatch")
            if replay_evidence.replay_digest != input_set_manifest.replay_digest:
                reason_codes.append("promotion.replay_digest_mismatch")
            if not replay_evidence.accepted:
                reason_codes.append("promotion.replay_rejected")

        if shadow_receipt is None:
            reason_codes.append("promotion.shadow_receipt_missing")
        else:
            if shadow_receipt.candidate_id != candidate.candidate_id:
                reason_codes.append("promotion.shadow_candidate_mismatch")
            if shadow_receipt.memory_ref.memory_update_id != candidate.event.memory_update_id:
                reason_codes.append("promotion.shadow_update_mismatch")

        if active_promotion_receipt is None:
            reason_codes.append("promotion.active_receipt_missing")
        else:
            if active_promotion_receipt.candidate_id != candidate.candidate_id:
                reason_codes.append("promotion.active_candidate_mismatch")
            if active_promotion_receipt.source_receipt_digest != receipt.receipt_digest:
                reason_codes.append("promotion.active_source_receipt_mismatch")

        if unknown_codes := unknown_reason_codes(reason_codes):
            missing = [code for code in unknown_codes if not code.startswith("unknown_")]
            if missing:
                reason_codes.append("receipt.unknown_reason_code")
                reason_codes.extend([f"unknown_reason_code:{code}" for code in missing])

        return MetricResult(
            metric_name="strict_promotion_bundle",
            status=MetricStatus.VALID if not reason_codes else MetricStatus.INVALID,
            value=0 if reason_codes else 1,
            reason_codes=reason_codes,
            evidence_ids=[
                item
                for item in [
                    None if evidence_manifest is None else evidence_manifest.manifest_digest,
                    None if input_set_manifest is None else input_set_manifest.manifest_digest,
                    None if replay_evidence is None else replay_evidence.evidence_digest,
                    None if shadow_receipt is None else shadow_receipt.receipt_digest,
                    None
                    if active_promotion_receipt is None
                    else active_promotion_receipt.receipt_digest,
                ]
                if item is not None
            ],
            timestamp=timestamp or now_utc(),
        )


def verify_authority_receipt(
    receipt: AuthorityReceipt,
    *,
    timestamp: datetime | None = None,
) -> MetricResult:
    reason_codes: list[str] = []
    if receipt.policy_version == "cmgl.authority_policy.v1":
        reason_codes.append("authority.legacy_receipt_not_strict")
    if receipt.request_digest is None:
        reason_codes.append("authority.request_digest_missing")
    if receipt.declared_scope_digest is None:
        reason_codes.append("authority.declared_scope_missing")
    if not receipt.rule_ids:
        reason_codes.append("receipt.rule_ids_missing")
    if unknown := unknown_rule_ids(receipt.rule_ids):
        reason_codes.append("receipt.unknown_rule_id")
        reason_codes.extend([f"unknown_rule_id:{rule_id}" for rule_id in unknown])
    if unknown_codes := unknown_reason_codes(receipt.reason_codes):
        reason_codes.append("receipt.unknown_reason_code")
        reason_codes.extend([f"unknown_reason_code:{code}" for code in unknown_codes])
    return MetricResult(
        metric_name="authority_receipt_binding",
        status=MetricStatus.VALID if not reason_codes else MetricStatus.INVALID,
        value=0 if reason_codes else 1,
        reason_codes=reason_codes,
        evidence_ids=[
            item for item in [receipt.request_digest, receipt.declared_scope_digest] if item
        ],
        timestamp=timestamp or now_utc(),
    )


def verify_metric_result(
    metric: MetricResult,
    *,
    timestamp: datetime | None = None,
) -> MetricResult:
    reason_codes: list[str] = []
    if unknown_codes := unknown_reason_codes(metric.reason_codes):
        reason_codes.append("receipt.unknown_reason_code")
        reason_codes.extend([f"unknown_reason_code:{code}" for code in unknown_codes])
    return MetricResult(
        metric_name=f"{metric.metric_name}.rule_validation",
        status=MetricStatus.VALID if not reason_codes else MetricStatus.INVALID,
        value=0 if reason_codes else 1,
        reason_codes=reason_codes,
        evidence_ids=metric.evidence_ids,
        timestamp=timestamp or now_utc(),
    )


def verify_ledger_integrity_receipt(
    receipt: LedgerIntegrityReceipt,
    *,
    timestamp: datetime | None = None,
) -> MetricResult:
    reason_codes: list[str] = []
    statuses: list[str] = []
    for line in receipt.line_statuses:
        statuses.extend(str(status) for status in line.statuses)
    if unknown_codes := unknown_reason_codes(statuses):
        reason_codes.append("receipt.unknown_reason_code")
        reason_codes.extend([f"unknown_reason_code:{code}" for code in unknown_codes])
    return MetricResult(
        metric_name="ledger_integrity_rule_validation",
        status=MetricStatus.VALID if not reason_codes else MetricStatus.INVALID,
        value=0 if reason_codes else 1,
        reason_codes=reason_codes,
        evidence_ids=[] if receipt.ledger_prefix_hash is None else [receipt.ledger_prefix_hash],
        timestamp=timestamp or now_utc(),
    )
