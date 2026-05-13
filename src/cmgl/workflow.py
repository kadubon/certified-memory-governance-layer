from __future__ import annotations

from datetime import datetime

from cmgl.digest import sha256_digest
from cmgl.models import (
    AdmissionDecision,
    MemoryGovernanceEvidenceContract,
    MetricResult,
    ReportTermBinding,
    VerificationWitness,
    WorkflowBottleneckReport,
    WorkflowEvidenceSet,
    WorkflowLayer,
    WorkflowReportMode,
)
from cmgl.time import now_utc


def make_workflow_bottleneck_report(
    *,
    workflow_id: str,
    layer_rates: dict[WorkflowLayer | str, float],
    evidence_ids: list[str] | None = None,
    limitations: list[str] | None = None,
    timestamp: datetime | None = None,
) -> WorkflowBottleneckReport:
    """Report the evidence-bound lower throughput for the memory-governance layer."""

    normalized: dict[str, float] = {
        (layer.value if isinstance(layer, WorkflowLayer) else str(layer)): max(rate, 0.0)
        for layer, rate in layer_rates.items()
    }
    if normalized:
        lower_bound = min(normalized.values())
        bottlenecks = [
            WorkflowLayer(layer)
            for layer, rate in normalized.items()
            if rate == lower_bound and layer in {item.value for item in WorkflowLayer}
        ]
    else:
        lower_bound = 0.0
        bottlenecks = [WorkflowLayer.MEMORY_GOVERNANCE]

    net_certified = normalized.get(WorkflowLayer.MEMORY_GOVERNANCE.value, lower_bound)
    body = {
        "schema_version": "cmgl.workflow_bottleneck_report.v1",
        "workflow_id": workflow_id,
        "layer": WorkflowLayer.MEMORY_GOVERNANCE,
        "mode": WorkflowReportMode.DIAGNOSTIC_ONLY,
        "lower_bound": lower_bound,
        "net_certified_throughput": net_certified,
        "bottleneck_layers": bottlenecks,
        "diagnostic_scores": normalized,
        "evidence_ids": evidence_ids or [],
        "limitations": limitations or ["procedural lower bound; not a factual-truth claim"],
        "timestamp": timestamp or now_utc(),
    }
    return WorkflowBottleneckReport(**body, report_digest=sha256_digest(body))


def make_workflow_evidence_set(
    *,
    workflow_id: str,
    decisions: list[AdmissionDecision],
    audit_metrics: list[MetricResult] | None = None,
    evidence_ids: list[str] | None = None,
) -> WorkflowEvidenceSet:
    counts = {decision: decisions.count(decision) for decision in AdmissionDecision}
    body = {
        "schema_version": "cmgl.workflow_evidence_set.v1",
        "workflow_id": workflow_id,
        "receipt_counts": counts,
        "audit_metrics": audit_metrics or [],
        "evidence_ids": evidence_ids or [],
        "timestamp": now_utc(),
    }
    return WorkflowEvidenceSet(**body, evidence_digest=sha256_digest(body))


def make_memory_governance_evidence_contract(
    evidence: WorkflowEvidenceSet,
    *,
    report_terms: list[str] | None = None,
) -> MemoryGovernanceEvidenceContract:
    terms = report_terms or [
        "receipt_counts.admit",
        "receipt_counts.block",
        "audit_metrics",
        "net_certified_throughput",
    ]
    body = {
        "schema_version": "cmgl.memory_governance_evidence_contract.v1",
        "contract_id": f"memory-governance:{evidence.workflow_id}",
        "workflow_id": evidence.workflow_id,
        "report_terms": terms,
        "evidence_ids": [evidence.evidence_digest, *evidence.evidence_ids],
        "witness_ids": [],
        "timestamp": now_utc(),
    }
    return MemoryGovernanceEvidenceContract(**body, contract_digest=sha256_digest(body))


def make_verification_witness(
    *,
    witness_id: str,
    accepted: bool,
    evidence_ids: list[str] | None = None,
    reason_codes: list[str] | None = None,
    timestamp: datetime | None = None,
) -> VerificationWitness:
    body = {
        "schema_version": "cmgl.verification_witness.v1",
        "witness_id": witness_id,
        "accepted": accepted,
        "evidence_ids": evidence_ids or [],
        "reason_codes": reason_codes or [],
        "timestamp": timestamp or now_utc(),
    }
    return VerificationWitness(**body, witness_digest=sha256_digest(body))


def make_report_term_binding(
    *,
    term: str,
    witness: VerificationWitness,
    evidence_id: str,
    accepted: bool | None = None,
    timestamp: datetime | None = None,
) -> ReportTermBinding:
    body = {
        "schema_version": "cmgl.report_term_binding.v1",
        "term": term,
        "witness_id": witness.witness_id,
        "evidence_id": evidence_id,
        "accepted": witness.accepted if accepted is None else accepted,
        "timestamp": timestamp or now_utc(),
    }
    return ReportTermBinding(**body, binding_digest=sha256_digest(body))


def workflow_report_from_evidence(
    evidence: WorkflowEvidenceSet,
    *,
    limitations: list[str] | None = None,
) -> WorkflowBottleneckReport:
    admitted = evidence.receipt_counts.get(AdmissionDecision.ADMIT, 0)
    blocked = evidence.receipt_counts.get(AdmissionDecision.BLOCK, 0)
    shadow = evidence.receipt_counts.get(AdmissionDecision.SHADOW, 0)
    quarantine = evidence.receipt_counts.get(AdmissionDecision.QUARANTINE, 0)
    total = admitted + blocked + shadow + quarantine
    net = 0.0 if total == 0 else admitted / total
    return make_workflow_bottleneck_report(
        workflow_id=evidence.workflow_id,
        layer_rates={
            WorkflowLayer.MEMORY_GOVERNANCE: net,
            WorkflowLayer.VALIDATION: 1.0 if total else 0.0,
        },
        evidence_ids=[evidence.evidence_digest, *evidence.evidence_ids],
        limitations=limitations,
    )


def certified_workflow_report_from_evidence(
    evidence: WorkflowEvidenceSet,
    *,
    contract: MemoryGovernanceEvidenceContract | None,
    accepted_witness_ids: list[str] | None = None,
    witnesses: list[VerificationWitness] | None = None,
    report_term_bindings: list[ReportTermBinding] | None = None,
) -> WorkflowBottleneckReport:
    required_terms = {
        "receipt_counts.admit",
        "receipt_counts.block",
        "audit_metrics",
        "net_certified_throughput",
    }
    typed_witnesses = witnesses or []
    typed_bindings = report_term_bindings or []
    witness_ids = (
        [witness.witness_id for witness in typed_witnesses if witness.accepted]
        or accepted_witness_ids
        or []
    )
    limitations: list[str] = []
    certified = True
    if contract is None:
        certified = False
        limitations.append("workflow.contract_missing")
    elif not required_terms.issubset(set(contract.report_terms)):
        certified = False
        limitations.append("workflow.report_terms_missing")
    if not witness_ids:
        certified = False
        limitations.append("workflow.witness_missing")
    if typed_witnesses and any(not witness.accepted for witness in typed_witnesses):
        certified = False
        limitations.append("workflow.witness_not_accepted")
    if typed_bindings:
        accepted_terms = {
            binding.term for binding in typed_bindings if binding.accepted and binding.term
        }
        if not required_terms.issubset(accepted_terms):
            certified = False
            limitations.append("workflow.report_term_binding_missing")
    elif typed_witnesses:
        certified = False
        limitations.append("workflow.report_term_binding_missing")

    report = workflow_report_from_evidence(
        evidence,
        limitations=limitations
        or ["evidence-contract and witnesses present for procedural lower bound"],
    )
    updates = {
        "mode": WorkflowReportMode.CERTIFIED_LOWER_BOUND
        if certified
        else WorkflowReportMode.DIAGNOSTIC_ONLY,
        "evidence_ids": [
            *report.evidence_ids,
            *([] if contract is None else [contract.contract_digest]),
            *witness_ids,
            *[binding.binding_digest for binding in typed_bindings],
        ],
    }
    body = report.model_dump(mode="python", exclude={"report_digest"}) | updates
    return WorkflowBottleneckReport(**body, report_digest=sha256_digest(body))
