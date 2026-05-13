from __future__ import annotations

from pathlib import Path

from cmgl.digest import sha256_digest
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import (
    ConformanceFinding,
    ConformanceLevel,
    ConformanceProfile,
    ConformanceReport,
    ConformanceSeverity,
    ObligationStatus,
    ReceiptObligation,
)
from cmgl.obligations import ObligationVerifier
from cmgl.receipt_verifier import verify_ledger_integrity_receipt
from cmgl.time import now_utc


def audit_ledger_conformance(
    ledger: str | Path | AppendOnlyLedger,
    *,
    profile: ConformanceProfile = ConformanceProfile.STRICT,
) -> ConformanceReport:
    active_ledger = ledger if isinstance(ledger, AppendOnlyLedger) else AppendOnlyLedger(ledger)
    receipt = active_ledger.integrity_receipt()
    ledger_metric = verify_ledger_integrity_receipt(receipt)
    obligation_graph = ObligationVerifier(profile=profile).verify(active_ledger)
    findings: list[ConformanceFinding] = [
        ConformanceFinding(
            reference="oasg",
            level=ConformanceLevel.EXECUTABLE_SUBSET,
            severity=ConformanceSeverity.INFO if receipt.ok else ConformanceSeverity.ERROR,
            summary="Append-only JSONL ledger prefix verification is executable locally.",
            reason_codes=[] if receipt.ok else ["conformance.ledger_invalid"],
            evidence_ids=[] if receipt.ledger_prefix_hash is None else [receipt.ledger_prefix_hash],
        ),
        ConformanceFinding(
            reference="oawm",
            level=ConformanceLevel.EXECUTABLE_SUBSET,
            severity=ConformanceSeverity.INFO,
            summary="Promotion receipts and current-update binding are present as a CMGL subset.",
            reason_codes=[],
            evidence_ids=[],
        ),
        ConformanceFinding(
            reference="memoryflow",
            level=ConformanceLevel.EXECUTABLE_SUBSET,
            severity=ConformanceSeverity.INFO,
            summary="Telemetry ingest and replay metrics are local deterministic subsets.",
            reason_codes=[],
            evidence_ids=[],
        ),
    ]
    obligation = ReceiptObligation(
        obligation_id="ledger-integrity-receipt-valid",
        subject_digest=receipt.receipt_digest,
        required_rule_ids=["cmgl.rule.ledger_prefix_valid"],
        satisfied=ledger_metric.status.value == "valid" and receipt.ok,
        reason_codes=[] if receipt.ok else ["conformance.obligation_unsatisfied"],
        timestamp=now_utc(),
        obligation_digest=sha256_digest(
            {
                "obligation_id": "ledger-integrity-receipt-valid",
                "subject_digest": receipt.receipt_digest,
                "satisfied": ledger_metric.status.value == "valid" and receipt.ok,
            }
        ),
    )
    receipt_obligations = [obligation]
    for index, evidence_report in enumerate(obligation_graph.reports, start=1):
        satisfied = evidence_report.status == ObligationStatus.SATISFIED
        receipt_obligations.append(
            ReceiptObligation(
                obligation_id=f"evidence-binding-{index}",
                subject_digest=evidence_report.subject_digest,
                required_rule_ids=["cmgl.rule.conformance.obligation_unsatisfied"],
                satisfied=satisfied,
                reason_codes=[]
                if satisfied
                else [
                    *evidence_report.reason_codes,
                    "conformance.obligation_unsatisfied",
                ],
                timestamp=now_utc(),
                obligation_digest=sha256_digest(
                    {
                        "obligation_id": f"evidence-binding-{index}",
                        "subject_digest": evidence_report.subject_digest,
                        "satisfied": satisfied,
                        "status": evidence_report.status,
                    }
                ),
            )
        )
    if not obligation_graph.ok:
        findings.append(
            ConformanceFinding(
                reference="cmgl-obligations",
                level=ConformanceLevel.EXECUTABLE_SUBSET,
                severity=ConformanceSeverity.ERROR
                if profile == ConformanceProfile.STRICT
                else ConformanceSeverity.WARNING,
                summary="Ledger-wide promotion evidence obligations were not fully satisfied.",
                reason_codes=["conformance.obligation_unsatisfied"],
                evidence_ids=[obligation_graph.graph_digest],
            )
        )
    ok = receipt.ok and obligation.satisfied and obligation_graph.ok
    body = {
        "schema_version": "cmgl.conformance_report.v1",
        "profile": profile,
        "ok": ok,
        "findings": findings,
        "obligations": receipt_obligations,
        "timestamp": now_utc(),
    }
    return ConformanceReport(**body, report_digest=sha256_digest(body))
