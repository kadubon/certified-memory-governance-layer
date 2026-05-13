from __future__ import annotations

import json
from datetime import timedelta

from typer.testing import CliRunner

from cmgl.absence import make_record_absence_notice
from cmgl.admission import candidate_from_event
from cmgl.audit import ContaminationPolicy, telemetry_audit_report
from cmgl.authority import (
    authorize_bundle,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.challenge import make_memory_challenge_record
from cmgl.cli import app
from cmgl.compression import CompressionProbeSuite, compression_metrics
from cmgl.digest import sha256_digest
from cmgl.evidence import (
    build_evidence_manifest,
    build_input_set_manifest,
    build_replay_evidence,
    versioned_ref_from_event,
)
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import (
    AbsenceNoticeType,
    AdmissionDecision,
    ChallengeStatus,
    ContaminationContext,
    ContaminationLane,
    GovernanceProfile,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
    MetricStatus,
    ProtectedAction,
    TelemetryEventType,
)
from cmgl.pipeline import PromotionPipeline
from cmgl.state import current_events_from_view, current_memory_view_from_events
from cmgl.telemetry import make_telemetry_event
from cmgl.telemetry_ingest import ingest_telemetry_jsonl
from cmgl.time import now_utc
from cmgl.validation import validate_record_file
from cmgl.workflow import (
    make_memory_governance_evidence_contract,
    make_workflow_evidence_set,
    workflow_report_from_evidence,
)

runner = CliRunner()


def _event(
    *,
    memory_id: str = "mem-1",
    update_id: str = "update-1",
    status: MemoryStatus = MemoryStatus.CERTIFIED,
    event_type: MemoryEventType = MemoryEventType.MEMORY_WRITE,
) -> MemoryEvent:
    return MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent.local",
        backend="inmemory",
        event_type=event_type,
        memory_id=memory_id,
        memory_update_id=update_id,
        content="memory",
        content_digest=sha256_digest("memory"),
        lane=ContaminationLane.USER_CLAIM,
        provenance_depth=0,
        authority_scope="user:test",
        status=status,
        checker_version="test",
        created_at=now_utc(),
    )


def _bundle(action: ProtectedAction = ProtectedAction.PERSISTENT_MEMORY_WRITE):
    scope = make_declared_scope(
        actor="agent.local",
        authority_scope="user:test",
        permitted_actions=[action],
        expires_at=now_utc() + timedelta(minutes=5),
    )
    request = make_protected_action_request(
        action=action,
        actor="agent.local",
        authority_scope="user:test",
        source_record="structured test scope",
        declared_scope=scope,
    )
    return authorize_bundle(request, declared_scope=scope)


def test_strict_promotion_pipeline_emits_shadow_and_active_receipts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    pipeline = PromotionPipeline(ledger=ledger)
    event = _event(status=MemoryStatus.CANDIDATE)
    certified_candidate = candidate_from_event(
        event.model_copy(update={"status": MemoryStatus.CERTIFIED})
    )
    evidence = build_evidence_manifest(certified_candidate)
    assert evidence is not None
    input_set = build_input_set_manifest(certified_candidate)
    replay = build_replay_evidence(input_set, checker_version=event.checker_version)
    result = pipeline.promote(
        event,
        authority_bundle=_bundle(),
        evidence_manifest=evidence,
        input_set_manifest=input_set,
        replay_evidence=replay,
        profile="strict",
    )

    assert result.shadow_receipt is not None
    assert result.promotion_receipt.decision == AdmissionDecision.ADMIT
    record_types = [record.record_type for record in ledger.iter_records()]
    assert "shadow_trial_receipt" in record_types
    assert "active_promotion_receipt" in record_types


def test_current_memory_view_reconstructs_latest_and_audit_history() -> None:
    old = _event(update_id="update-old", status=MemoryStatus.SUPERSEDED)
    new = _event(update_id="update-new", status=MemoryStatus.CERTIFIED)
    deleted = _event(
        memory_id="mem-2",
        update_id="update-dead",
        status=MemoryStatus.TOMBSTONED,
        event_type=MemoryEventType.MEMORY_TOMBSTONE,
    )

    view = current_memory_view_from_events([old, new, deleted])
    assert view.current_memory_ids == ["mem-1"]
    assert set(view.audit_memory_ids) == {"mem-1", "mem-2"}
    current = current_events_from_view([old, new, deleted], view)
    assert [event.memory_update_id for event in current] == ["update-new"]


def test_telemetry_jsonl_ingest_line_diagnostics(tmp_path) -> None:  # type: ignore[no-untyped-def]
    event = _event()
    ref = versioned_ref_from_event(event)
    assert ref is not None
    telemetry = make_telemetry_event(
        event_type=TelemetryEventType.MEM_USE,
        collector_id="collector",
        collector_seq=2,
        event_id="evt-1",
        memory_refs=[ref],
    )
    duplicate = telemetry.model_copy(update={"collector_seq": 1})
    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(telemetry.model_dump(mode="json")),
                json.dumps(duplicate.model_dump(mode="json")),
                '{"schema_version": "unknown"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = ingest_telemetry_jsonl(path, profile=GovernanceProfile.STRICT)
    reasons = [reason for item in result.diagnostics for reason in item.reason_codes]
    assert result.accepted_events == 1
    assert result.rejected_events == 2
    assert "telemetry.duplicate_event_id" in reasons
    assert "telemetry.ordering_violation" in reasons
    assert "telemetry.event_invalid" in reasons


def test_validate_record_cli_and_fail_closed_unknown_rule(tmp_path) -> None:  # type: ignore[no-untyped-def]
    valid = runner.invoke(
        app,
        ["validate", "record", "examples/conformance/memory_event.valid.json", "--json"],
    )
    assert valid.exit_code == 0

    bad_path = tmp_path / "metric.json"
    bad_path.write_text(
        json.dumps(
            {
                "schema_version": "cmgl.metric_result.v1",
                "metric_name": "bad",
                "status": "valid",
                "reason_codes": ["not_registered"],
                "timestamp": now_utc().isoformat(),
            }
        ),
        encoding="utf-8",
    )
    metric = validate_record_file(bad_path)
    assert metric.status == MetricStatus.INVALID
    assert "receipt.unknown_reason_code" in metric.reason_codes

    line_status = {
        "schema_version": "cmgl.ledger_line_status.v1",
        "line": 1,
        "statuses": ["not_a_registered_ledger_status"],
    }
    line_status_path = tmp_path / "line-status.json"
    line_status_path.write_text(json.dumps(line_status), encoding="utf-8")
    line_metric = validate_record_file(line_status_path)
    assert line_metric.status == MetricStatus.INVALID
    assert "receipt.unknown_reason_code" in line_metric.reason_codes


def test_validate_ledger_cli_fixture() -> None:
    result = runner.invoke(
        app,
        ["validate", "ledger", "examples/conformance/ledger.valid.jsonl", "--json"],
    )
    assert result.exit_code == 0


def test_compression_probe_suite_reject_metrics() -> None:
    suite = CompressionProbeSuite(
        source_digest_map={"mem-1": sha256_digest("source-1")},
        recoverability_probes={"recover-key-exception": False},
        alias_hazards=["morning/afternoon alias"],
        lost_uncertainties=["deadline qualifier"],
        lost_exceptions=[],
        lost_uncertainty_severity="high",
    )
    certificate = suite.make_certificate(
        compressed_memory_id="summary",
        source_memory_ids=["mem-1", "mem-2"],
        source_size=100,
        compressed_size=40,
        source_coverage=0.9,
    )
    metrics = {metric.metric_name: metric for metric in compression_metrics(certificate)}
    assert certificate.decision == "reject"
    assert metrics["compression_source_digest_coverage"].status == MetricStatus.INVALID
    assert metrics["compression_recoverability_probes"].status == MetricStatus.INVALID
    assert metrics["compression_alias_hazards"].status == MetricStatus.INVALID
    assert metrics["compression_uncertainty_loss"].status == MetricStatus.INVALID


def test_contamination_policy_requires_explicit_shared_context() -> None:
    event = _event(memory_id="shared-memory")
    policy = ContaminationPolicy()
    assert policy.evaluate([event]).cross_agent_shared_memory_ids == []
    report = policy.evaluate(
        [event],
        context=ContaminationContext(shared_memory_ids=["shared-memory"]),
    )
    assert report.cross_agent_shared_memory_ids == ["shared-memory"]


def test_workflow_contract_and_challenge_absence_records() -> None:
    evidence = make_workflow_evidence_set(
        workflow_id="wf",
        decisions=[AdmissionDecision.ADMIT, AdmissionDecision.BLOCK],
        audit_metrics=[],
    )
    contract = make_memory_governance_evidence_contract(evidence)
    report = workflow_report_from_evidence(evidence)
    challenge = make_memory_challenge_record(
        memory_id="mem-1",
        status=ChallengeStatus.OPEN,
        reason_codes=["challenge.open"],
    )
    absence = make_record_absence_notice(
        notice_type=AbsenceNoticeType.MISSING_EVIDENCE,
        memory_id="mem-1",
    )

    assert contract.workflow_id == "wf"
    assert report.lower_bound == 0.5
    assert challenge.status == ChallengeStatus.OPEN
    assert "absence.missing_evidence" in absence.reason_codes


def test_telemetry_report_profile_and_new_delay_metrics(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    stale = _event(status=MemoryStatus.SUPERSEDED)
    ref = versioned_ref_from_event(stale)
    assert ref is not None
    ledger.append("memory_event", stale)
    telemetry = make_telemetry_event(
        event_type=TelemetryEventType.MEM_USE,
        collector_id="collector",
        collector_seq=1,
        memory_refs=[ref],
    )
    ledger.append("telemetry_event", telemetry)
    report = telemetry_audit_report(ledger, profile=GovernanceProfile.OPERATIONAL)
    metrics = {metric.metric_name: metric for metric in report.metrics}
    assert report.profile == GovernanceProfile.OPERATIONAL
    assert metrics["supersedence_delay"].value == 1
