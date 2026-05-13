from __future__ import annotations

import json
from datetime import timedelta

from typer.testing import CliRunner

from cmgl.admission import candidate_from_event
from cmgl.audit import telemetry_replay_report
from cmgl.authority import authorize_bundle, make_declared_scope, make_protected_action_request
from cmgl.cli import app
from cmgl.compression import audit_compression_certificate, make_compression_certificate
from cmgl.digest import sha256_digest
from cmgl.evidence import (
    build_evidence_manifest,
    build_input_set_manifest,
    build_promotion_evidence_bundle,
    build_replay_evidence,
    versioned_ref_from_event,
)
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import (
    AdmissionDecision,
    AuthorityBundle,
    CompressionFailureClass,
    ConformanceProfile,
    ContaminationLane,
    GovernanceProfile,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
    ProtectedAction,
    TelemetryEventType,
    TelemetryOutcomeStatus,
    TelemetryReadUsePayload,
    WorkflowReportMode,
)
from cmgl.pipeline import PromotionPipeline
from cmgl.receipt_verifier import PromotionVerifier
from cmgl.telemetry import make_telemetry_event
from cmgl.telemetry_ingest import ingest_telemetry_jsonl
from cmgl.time import now_utc
from cmgl.validation import validate_ledger_file
from cmgl.workflow import (
    certified_workflow_report_from_evidence,
    make_memory_governance_evidence_contract,
    make_workflow_evidence_set,
)

runner = CliRunner()


def _event(
    *,
    status: MemoryStatus = MemoryStatus.CERTIFIED,
    event_type: MemoryEventType = MemoryEventType.MEMORY_WRITE,
) -> MemoryEvent:
    return MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent.local",
        backend="inmemory",
        event_type=event_type,
        memory_id="mem-1",
        memory_update_id="update-1",
        content="memory",
        content_digest=sha256_digest("memory"),
        lane=ContaminationLane.USER_CLAIM,
        provenance_depth=0,
        authority_scope="user:test",
        status=status,
        checker_version="test",
        created_at=now_utc(),
    )


def _bundle() -> AuthorityBundle:
    scope = make_declared_scope(
        actor="agent.local",
        authority_scope="user:test",
        permitted_actions=[ProtectedAction.PERSISTENT_MEMORY_WRITE],
        expires_at=now_utc() + timedelta(minutes=5),
    )
    request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent.local",
        authority_scope="user:test",
        source_record="structured scope",
        declared_scope=scope,
    )
    return authorize_bundle(request, declared_scope=scope)


def _strict_inputs(event: MemoryEvent):
    certified_candidate = candidate_from_event(
        event.model_copy(update={"status": MemoryStatus.CERTIFIED})
    )
    evidence = build_evidence_manifest(certified_candidate)
    assert evidence is not None
    input_set = build_input_set_manifest(certified_candidate)
    replay = build_replay_evidence(input_set, checker_version=event.checker_version)
    return certified_candidate, evidence, input_set, replay


def test_strict_promotion_blocks_missing_input_set_and_replay(tmp_path) -> None:  # type: ignore[no-untyped-def]
    event = _event(status=MemoryStatus.CANDIDATE)
    result = PromotionPipeline(ledger=AppendOnlyLedger(tmp_path / "ledger.jsonl")).promote(
        event,
        authority_bundle=_bundle(),
        profile="strict",
    )
    assert result.promotion_receipt.decision == AdmissionDecision.BLOCK
    assert "promotion.input_set_manifest_missing" in result.promotion_receipt.reason_codes
    assert result.quarantine_record is not None


def test_strict_promotion_verifier_accepts_complete_bundle(tmp_path) -> None:  # type: ignore[no-untyped-def]
    event = _event(status=MemoryStatus.CANDIDATE)
    _, evidence, input_set, replay = _strict_inputs(event)
    result = PromotionPipeline(ledger=AppendOnlyLedger(tmp_path / "ledger.jsonl")).promote(
        event,
        authority_bundle=_bundle(),
        evidence_manifest=evidence,
        input_set_manifest=input_set,
        replay_evidence=replay,
        profile="strict",
    )
    assert result.shadow_receipt is not None
    assert result.active_promotion_receipt is not None
    metric = PromotionVerifier().verify(
        result.candidate,
        result.promotion_receipt,
        evidence_manifest=result.evidence_manifest,
        input_set_manifest=input_set,
        replay_evidence=replay,
        shadow_receipt=result.shadow_receipt,
        active_promotion_receipt=result.active_promotion_receipt,
        current_update_id=result.event.memory_update_id,
    )
    assert metric.status.value == "valid"


def test_promotion_verify_cli_uses_evidence_bundle(tmp_path) -> None:  # type: ignore[no-untyped-def]
    event = _event(status=MemoryStatus.CANDIDATE)
    _, evidence, input_set, replay = _strict_inputs(event)
    result = PromotionPipeline(ledger=AppendOnlyLedger(tmp_path / "ledger.jsonl")).promote(
        event,
        authority_bundle=_bundle(),
        evidence_manifest=evidence,
        input_set_manifest=input_set,
        replay_evidence=replay,
        profile="strict",
    )
    assert result.evidence_manifest is not None
    assert result.shadow_receipt is not None
    assert result.active_promotion_receipt is not None
    bundle = build_promotion_evidence_bundle(
        result.candidate,
        evidence_manifest=result.evidence_manifest,
        input_set_manifest=input_set,
        replay_evidence=replay,
        shadow_receipt=result.shadow_receipt,
        active_promotion_receipt=result.active_promotion_receipt,
    )
    receipt_path = tmp_path / "receipt.json"
    bundle_path = tmp_path / "bundle.json"
    receipt_path.write_text(
        json.dumps(result.promotion_receipt.model_dump(mode="json")),
        encoding="utf-8",
    )
    bundle_path.write_text(json.dumps(bundle.model_dump(mode="json")), encoding="utf-8")
    cli_result = runner.invoke(
        app,
        [
            "promotion",
            "verify",
            str(receipt_path),
            "--evidence-bundle",
            str(bundle_path),
            "--json",
        ],
    )
    assert cli_result.exit_code == 0


def test_telemetry_typed_payload_ingest_and_replay(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    event = _event()
    ref = versioned_ref_from_event(event)
    assert ref is not None
    ledger.append("memory_event", event)
    telemetry = make_telemetry_event(
        event_type=TelemetryEventType.MEM_USE,
        collector_id="collector",
        collector_seq=1,
        event_id="evt-typed",
        memory_refs=[ref],
        payload=TelemetryReadUsePayload(
            memory_refs=[ref],
            query_digest=sha256_digest("memory"),
        ),
    )
    duplicate = telemetry.model_copy(update={"collector_seq": 2})
    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(telemetry.model_dump(mode="json")),
                json.dumps(duplicate.model_dump(mode="json")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ingest = ingest_telemetry_jsonl(
        path,
        ledger=ledger,
        profile=GovernanceProfile.OPERATIONAL,
    )
    assert ingest.accepted_events == 2
    assert ingest.deduplicated_events == 1
    assert ingest.outcomes[-1].status == TelemetryOutcomeStatus.DOWNGRADED
    replay = telemetry_replay_report(ledger)
    assert any(metric.metric_name == "read_use_uptake" for metric in replay.metrics)


def test_ledger_schema_epoch_validation_fails_closed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = AppendOnlyLedger(ledger_path)
    ledger.append("test", {"a": 1})
    ledger_path.write_text(
        ledger_path.read_text(encoding="utf-8").replace("cmgl.schema.v1", "unknown.schema"),
        encoding="utf-8",
    )
    metric = validate_ledger_file(ledger_path)
    assert metric.status.value == "invalid"


def test_conformance_cli_reports_empty_valid_ledger(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text("", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "conformance",
            "audit",
            "--ledger",
            str(ledger_path),
            "--profile",
            ConformanceProfile.STRICT.value,
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert "conformance_report" in result.output


def test_compression_audit_report_failure_classes() -> None:
    certificate = make_compression_certificate(
        compressed_memory_id="summary",
        source_memory_ids=["mem-1", "mem-2"],
        source_size=100,
        compressed_size=40,
        recoverability_check="fail",
        source_coverage=0.9,
        source_digest_map={"mem-1": sha256_digest("source-1")},
        alias_hazards=["preference alias"],
    )
    report = audit_compression_certificate(certificate)
    assert not report.deployable_exact_recovery
    assert CompressionFailureClass.BRIDGE in report.failure_classes
    assert CompressionFailureClass.GLUING in report.failure_classes


def test_workflow_certified_report_requires_contract_and_witnesses() -> None:
    evidence = make_workflow_evidence_set(
        workflow_id="wf",
        decisions=[AdmissionDecision.ADMIT, AdmissionDecision.BLOCK],
    )
    diagnostic = certified_workflow_report_from_evidence(
        evidence,
        contract=None,
        accepted_witness_ids=[],
    )
    assert diagnostic.mode == WorkflowReportMode.DIAGNOSTIC_ONLY
    contract = make_memory_governance_evidence_contract(evidence)
    certified = certified_workflow_report_from_evidence(
        evidence,
        contract=contract,
        accepted_witness_ids=["witness:1"],
    )
    assert certified.mode == WorkflowReportMode.CERTIFIED_LOWER_BOUND
