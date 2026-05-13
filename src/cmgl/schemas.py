from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from cmgl.models import (
    ActivePromotionReceipt,
    AdapterOperationReceipt,
    AuthorityBundle,
    AuthorityEvidenceBundle,
    AuthorityReceipt,
    CompressionAuditReport,
    CompressionBridgeProbe,
    CompressionCertificate,
    CompressionDeploymentProbe,
    CompressionGluingProbe,
    ConformanceFinding,
    ConformanceReport,
    ContaminationAuditReport,
    ContaminationContext,
    ContaminationStateReplay,
    CurrentMemoryView,
    DeclaredScope,
    DuplicatePolicyReceipt,
    EvidenceBindingReport,
    EvidenceManifest,
    ExternalMemoryRef,
    GovernanceReceiptBundle,
    InputSetManifest,
    LeaseReceipt,
    LedgerAppendReceipt,
    LedgerIntegrityReceipt,
    LedgerLineStatus,
    MemoryCandidate,
    MemoryChallengeRecord,
    MemoryEvent,
    MemoryGovernanceEvidenceContract,
    MemoryRevision,
    MemoryStateSnapshot,
    MemoryTelemetryEvent,
    MetricResult,
    ObligationGraph,
    PromotionEvidenceBundle,
    PromotionReceipt,
    ProtectedActionRequest,
    QuarantineRecord,
    RationalValue,
    ReceiptObligation,
    RecordAbsenceNotice,
    ReplayEvidence,
    ReportTermBinding,
    RetrievalDecision,
    RollbackReceipt,
    RollbackSnapshot,
    SchemaMigrationRecord,
    SemanticRule,
    ShadowTrialReceipt,
    TelemetryAuditReport,
    TelemetryCorrectPayload,
    TelemetryDeletePayload,
    TelemetryEventOutcome,
    TelemetryIngestResult,
    TelemetryLineDiagnostic,
    TelemetryReadUsePayload,
    TelemetryReplacePayload,
    TelemetryReplayReport,
    TelemetryRetrievePayload,
    TelemetryStateReplay,
    TelemetryVerifyPayload,
    TelemetryWritePayload,
    VerificationWitness,
    VersionedMemoryRef,
    WorkflowBottleneckReport,
    WorkflowEvidenceSet,
)
from cmgl.rules import semantic_rules

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "memory_event": MemoryEvent,
    "memory_candidate": MemoryCandidate,
    "promotion_receipt": PromotionReceipt,
    "retrieval_decision": RetrievalDecision,
    "authority_receipt": AuthorityReceipt,
    "authority_bundle": AuthorityBundle,
    "authority_evidence_bundle": AuthorityEvidenceBundle,
    "compression_certificate": CompressionCertificate,
    "compression_audit_report": CompressionAuditReport,
    "compression_bridge_probe": CompressionBridgeProbe,
    "compression_gluing_probe": CompressionGluingProbe,
    "compression_deployment_probe": CompressionDeploymentProbe,
    "conformance_finding": ConformanceFinding,
    "conformance_report": ConformanceReport,
    "receipt_obligation": ReceiptObligation,
    "evidence_binding_report": EvidenceBindingReport,
    "obligation_graph": ObligationGraph,
    "contamination_context": ContaminationContext,
    "contamination_state_replay": ContaminationStateReplay,
    "versioned_memory_ref": VersionedMemoryRef,
    "current_memory_view": CurrentMemoryView,
    "memory_state_snapshot": MemoryStateSnapshot,
    "evidence_manifest": EvidenceManifest,
    "input_set_manifest": InputSetManifest,
    "replay_evidence": ReplayEvidence,
    "promotion_evidence_bundle": PromotionEvidenceBundle,
    "governance_receipt_bundle": GovernanceReceiptBundle,
    "memory_revision": MemoryRevision,
    "memory_challenge_record": MemoryChallengeRecord,
    "record_absence_notice": RecordAbsenceNotice,
    "semantic_rule": SemanticRule,
    "metric_result": MetricResult,
    "ledger_append_receipt": LedgerAppendReceipt,
    "ledger_integrity_receipt": LedgerIntegrityReceipt,
    "ledger_line_status": LedgerLineStatus,
    "schema_migration_record": SchemaMigrationRecord,
    "duplicate_policy_receipt": DuplicatePolicyReceipt,
    "declared_scope": DeclaredScope,
    "protected_action_request": ProtectedActionRequest,
    "shadow_trial_receipt": ShadowTrialReceipt,
    "lease_receipt": LeaseReceipt,
    "active_promotion_receipt": ActivePromotionReceipt,
    "external_memory_ref": ExternalMemoryRef,
    "adapter_operation_receipt": AdapterOperationReceipt,
    "rollback_snapshot": RollbackSnapshot,
    "rollback_receipt": RollbackReceipt,
    "quarantine_record": QuarantineRecord,
    "memory_telemetry_event": MemoryTelemetryEvent,
    "telemetry_audit_report": TelemetryAuditReport,
    "telemetry_ingest_result": TelemetryIngestResult,
    "telemetry_line_diagnostic": TelemetryLineDiagnostic,
    "telemetry_event_outcome": TelemetryEventOutcome,
    "telemetry_replay_report": TelemetryReplayReport,
    "telemetry_state_replay": TelemetryStateReplay,
    "rational_value": RationalValue,
    "telemetry_write_payload": TelemetryWritePayload,
    "telemetry_replace_payload": TelemetryReplacePayload,
    "telemetry_delete_payload": TelemetryDeletePayload,
    "telemetry_read_use_payload": TelemetryReadUsePayload,
    "telemetry_verify_payload": TelemetryVerifyPayload,
    "telemetry_correct_payload": TelemetryCorrectPayload,
    "telemetry_retrieve_payload": TelemetryRetrievePayload,
    "workflow_bottleneck_report": WorkflowBottleneckReport,
    "workflow_evidence_set": WorkflowEvidenceSet,
    "memory_governance_evidence_contract": MemoryGovernanceEvidenceContract,
    "verification_witness": VerificationWitness,
    "report_term_binding": ReportTermBinding,
    "contamination_audit_report": ContaminationAuditReport,
}


def default_semantic_rules() -> list[SemanticRule]:
    return semantic_rules()


def export_json_schemas(out_dir: str | Path) -> list[Path]:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in SCHEMA_MODELS.items():
        path = output / f"{name}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    schema_index = {
        "schema_version": "cmgl.schema_index.v1",
        "schemas": {
            name: {
                "file": f"{name}.schema.json",
                "title": model.model_json_schema().get("title", name),
            }
            for name, model in SCHEMA_MODELS.items()
        },
    }
    schema_index_path = output / "schema_index.json"
    schema_index_path.write_text(
        json.dumps(schema_index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(schema_index_path)

    semantic_rules_path = output / "semantic_rules.json"
    semantic_rules_path.write_text(
        json.dumps(
            [rule.model_dump(mode="json") for rule in default_semantic_rules()],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(semantic_rules_path)
    return written
