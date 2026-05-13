from __future__ import annotations

import json
from datetime import timedelta

from cmgl.admission import candidate_from_event
from cmgl.audit import contamination_diagnostics, telemetry_audit_report
from cmgl.authority import (
    authorize_request,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.compression import make_compression_certificate
from cmgl.digest import sha256_digest
from cmgl.evidence import build_evidence_manifest, versioned_ref_from_event
from cmgl.exceptions import LedgerError
from cmgl.ledger import AppendOnlyLedger
from cmgl.lifecycle import (
    make_lease_receipt,
    make_quarantine_record,
    make_rollback_receipt,
    make_rollback_snapshot,
    make_shadow_trial_receipt,
)
from cmgl.models import (
    AdmissionDecision,
    BackendName,
    ContaminationLane,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
    ProtectedAction,
    TelemetryEventType,
    WorkflowLayer,
)
from cmgl.policy import AdmissionPolicy
from cmgl.receipt_verifier import verify_promotion_receipt
from cmgl.schemas import export_json_schemas
from cmgl.telemetry import make_telemetry_event
from cmgl.time import now_utc
from cmgl.transitions import transition_allowed, transition_reason
from cmgl.workflow import make_workflow_bottleneck_report


def _event(
    *,
    status: MemoryStatus = MemoryStatus.CERTIFIED,
    lane: ContaminationLane = ContaminationLane.USER_CLAIM,
    memory_id: str = "mem-1",
    update_id: str = "update-1",
) -> MemoryEvent:
    return MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent",
        backend=BackendName.INMEMORY,
        event_type=MemoryEventType.MEMORY_WRITE,
        memory_id=memory_id,
        memory_update_id=update_id,
        content="memory",
        content_digest=sha256_digest("memory"),
        lane=lane,
        provenance_depth=0,
        authority_scope="user:test",
        status=status,
        checker_version="test",
        created_at=now_utc(),
    )


def test_lifecycle_transition_table_blocks_terminal_states() -> None:
    assert transition_allowed(MemoryStatus.RAW, MemoryStatus.CANDIDATE)
    assert not transition_allowed(MemoryStatus.TOMBSTONED, MemoryStatus.CERTIFIED)
    assert transition_reason(MemoryStatus.TOMBSTONED, MemoryStatus.CERTIFIED) == (
        "transition.terminal.tombstoned"
    )


def test_receipt_verifier_detects_update_mismatch() -> None:
    candidate = candidate_from_event(_event())
    evidence = build_evidence_manifest(candidate)
    assert evidence is not None
    receipt = AdmissionPolicy().evaluate(candidate, evidence_manifest=evidence)
    tampered = receipt.model_copy(update={"memory_update_id": "wrong-update"})

    result = verify_promotion_receipt(candidate, tampered, evidence_manifest=evidence)
    assert result.status.value == "invalid"
    assert "receipt.memory_update_id_mismatch" in result.reason_codes


def test_ledger_prefix_expected_guard_and_duplicate_status(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    first = ledger.append("test", {"a": 1})
    assert first.append_index == 0
    assert first.ledger_prefix_hash is not None
    ledger.append("test", {"a": 1})
    result = ledger.verify_prefix()
    assert result.ok
    assert result.duplicate_count == 1
    assert any("duplicate_payload" in line.statuses for line in result.line_statuses)

    try:
        ledger.append("test", {"b": 2}, expected_prefix="sha256:" + "0" * 64)
    except LedgerError as exc:
        assert "expected ledger prefix" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected prefix guard to reject stale writer")


def test_telemetry_audit_counts_superseded_and_zombie_use(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    superseded = _event(status=MemoryStatus.SUPERSEDED, update_id="update-old")
    tombstoned = _event(status=MemoryStatus.TOMBSTONED, memory_id="mem-2", update_id="update-dead")
    ledger.append("memory_event", superseded)
    ledger.append("memory_event", tombstoned)

    refs = [versioned_ref_from_event(superseded), versioned_ref_from_event(tombstoned)]
    telemetry = make_telemetry_event(
        event_type=TelemetryEventType.MEM_USE,
        collector_id="collector",
        collector_seq=1,
        memory_refs=[ref for ref in refs if ref is not None],
    )
    ledger.append("telemetry_event", telemetry)

    report = telemetry_audit_report(ledger)
    metrics = {item.metric_name: item.value for item in report.metrics}
    assert metrics["superseded_use"] == 1
    assert metrics["zombie_use_after_tombstone"] == 1


def test_natural_language_alone_is_not_authorization() -> None:
    request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent",
        authority_scope="user:test",
        source_record="please write memory",
        natural_language_justification="the user said this is okay",
    )
    blocked = authorize_request(request)
    assert blocked.decision == AdmissionDecision.BLOCK
    assert "authority.natural_language_not_authorization" in blocked.reason_codes

    scope = make_declared_scope(
        actor="agent",
        authority_scope="user:test",
        permitted_actions=[ProtectedAction.PERSISTENT_MEMORY_WRITE],
        expires_at=now_utc() + timedelta(days=1),
    )
    allowed_request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent",
        authority_scope="user:test",
        source_record="structured scope",
        declared_scope=scope,
    )
    admitted = authorize_request(allowed_request, declared_scope=scope)
    assert admitted.decision == AdmissionDecision.ADMIT


def test_lifecycle_rollback_and_quarantine_records() -> None:
    candidate = candidate_from_event(_event(status=MemoryStatus.CANDIDATE))
    shadow = make_shadow_trial_receipt(candidate, admitted=True)
    lease = make_lease_receipt(candidate, lease_seconds=60, admitted=True)
    snapshot = make_rollback_snapshot([candidate.event])
    rollback = make_rollback_receipt(
        snapshot, restored_memory_ids=[candidate.event.memory_id], admitted=True
    )
    quarantine = make_quarantine_record(
        target=candidate, target_type="candidate", reason_codes=["test"]
    )

    assert shadow.decision == AdmissionDecision.SHADOW
    assert lease.decision == AdmissionDecision.SHADOW
    assert rollback.decision == AdmissionDecision.ADMIT
    assert quarantine.target_digest.startswith("sha256:")


def test_compression_rejects_alias_hazard_and_high_uncertainty() -> None:
    cert = make_compression_certificate(
        compressed_memory_id="summary",
        source_memory_ids=["mem-1"],
        source_size=100,
        compressed_size=50,
        recoverability_check="pass",
        source_coverage=1.0,
        lost_uncertainties=["deadline qualifier"],
        lost_uncertainty_severity="high",
        alias_hazards=["morning/afternoon preference alias"],
    )
    assert cert.decision == "reject"


def test_contamination_and_workflow_reports() -> None:
    report = contamination_diagnostics(
        [
            _event(lane=ContaminationLane.MODEL_INFERENCE),
            _event(lane=ContaminationLane.TOOL_OBSERVATION, update_id="update-2"),
        ]
    )
    assert report.discounted_risk_score > 0

    bottleneck = make_workflow_bottleneck_report(
        workflow_id="workflow",
        layer_rates={
            WorkflowLayer.MEMORY_GOVERNANCE: 3.0,
            WorkflowLayer.AUTHORIZATION: 5.0,
        },
    )
    assert bottleneck.lower_bound == 3.0
    assert WorkflowLayer.MEMORY_GOVERNANCE in bottleneck.bottleneck_layers


def test_schema_export_includes_index_and_semantic_rules(tmp_path) -> None:  # type: ignore[no-untyped-def]
    export_json_schemas(tmp_path)
    assert (tmp_path / "schema_index.json").exists()
    rules = json.loads((tmp_path / "semantic_rules.json").read_text(encoding="utf-8"))
    assert any(rule["rule_id"] == "cmgl.rule.version_binding.missing" for rule in rules)
