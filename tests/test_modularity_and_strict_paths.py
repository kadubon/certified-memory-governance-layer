from __future__ import annotations

import json
from datetime import timedelta

import pytest

from cmgl.admission import candidate_from_event
from cmgl.audit import contamination_diagnostics, telemetry_audit_report
from cmgl.authority import (
    authorize_request,
    make_authority_receipt,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.compression import compression_metrics, make_compression_certificate
from cmgl.contracts.memory import MemoryEvent as ContractMemoryEvent
from cmgl.digest import sha256_digest
from cmgl.evidence import build_evidence_manifest, versioned_ref_from_event
from cmgl.exceptions import LifecycleError
from cmgl.ledger import AppendOnlyLedger
from cmgl.lifecycle import make_shadow_trial_receipt
from cmgl.models import (
    AdmissionDecision,
    BackendName,
    ContaminationContext,
    ContaminationLane,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
    ProtectedAction,
    TelemetryEventType,
)
from cmgl.policy import AdmissionPolicy
from cmgl.receipt_verifier import (
    verify_authority_receipt,
    verify_ledger_integrity_receipt,
    verify_promotion_receipt,
)
from cmgl.rules import known_rule_ids
from cmgl.schemas import export_json_schemas
from cmgl.telemetry import make_telemetry_event
from cmgl.time import now_utc


def _event(
    *,
    memory_id: str = "mem-1",
    update_id: str = "update-1",
    status: MemoryStatus = MemoryStatus.CERTIFIED,
    lane: ContaminationLane = ContaminationLane.USER_CLAIM,
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


def test_contract_split_preserves_models_facade() -> None:
    assert MemoryEvent is ContractMemoryEvent


def test_schema_rules_export_matches_registry(tmp_path) -> None:  # type: ignore[no-untyped-def]
    export_json_schemas(tmp_path)
    exported = json.loads((tmp_path / "semantic_rules.json").read_text(encoding="utf-8"))
    assert {rule["rule_id"] for rule in exported} == known_rule_ids()


def test_unknown_receipt_rule_fails_closed() -> None:
    candidate = candidate_from_event(_event())
    evidence = build_evidence_manifest(candidate)
    assert evidence is not None
    receipt = AdmissionPolicy().evaluate(candidate, evidence_manifest=evidence)
    bad = receipt.model_copy(update={"rule_ids": ["cmgl.rule.not_registered"]})
    result = verify_promotion_receipt(candidate, bad, evidence_manifest=evidence)
    assert result.status.value == "invalid"
    assert "receipt.unknown_rule_id" in result.reason_codes


def test_strict_authority_rejects_legacy_and_resource_mismatch() -> None:
    with pytest.warns(DeprecationWarning):
        legacy = make_authority_receipt(
            action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
            actor="agent",
            authority_scope="user:test",
            source_record="legacy",
        )
    assert verify_authority_receipt(legacy).status.value == "invalid"

    scope = make_declared_scope(
        actor="agent",
        authority_scope="user:test",
        permitted_actions=[ProtectedAction.PERSISTENT_MEMORY_WRITE],
        resource_patterns=["memory:user:test:*"],
        expires_at=now_utc() + timedelta(days=1),
    )
    request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent",
        authority_scope="user:test",
        source_record="structured",
        declared_scope=scope,
        resource="memory:user:other:1",
    )
    receipt = authorize_request(request, declared_scope=scope)
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "authority.resource_not_permitted" in receipt.reason_codes


def test_lifecycle_receipt_rejects_illegal_transition() -> None:
    candidate = candidate_from_event(_event(status=MemoryStatus.TOMBSTONED))
    with pytest.raises(LifecycleError):
        make_shadow_trial_receipt(candidate, admitted=True)


def test_ledger_integrity_receipt_and_rule_validation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    ledger.append("test", {"a": 1})
    receipt = ledger.integrity_receipt()
    assert receipt.ok
    assert receipt.receipt_digest.startswith("sha256:")
    assert verify_ledger_integrity_receipt(receipt).status.value == "valid"


def test_telemetry_audit_detects_duplicate_order_skew_correction_deadline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    event = _event()
    ref = versioned_ref_from_event(event)
    assert ref is not None
    ledger.append("memory_event", event)
    first = make_telemetry_event(
        event_type=TelemetryEventType.MEM_READ,
        collector_id="collector",
        collector_seq=2,
        event_id="evt-1",
        obs_time=now_utc() - timedelta(days=1),
        skew_budget_ms=1,
        memory_refs=[ref],
    )
    duplicate_and_ordered_badly = make_telemetry_event(
        event_type=TelemetryEventType.MEM_USE,
        collector_id="collector",
        collector_seq=1,
        event_id="evt-1",
        memory_refs=[ref],
    )
    correction = make_telemetry_event(
        event_type=TelemetryEventType.MEM_CORRECT,
        collector_id="collector",
        collector_seq=3,
        metadata={"correction_of_event_id": "evt-1"},
    )
    verify = make_telemetry_event(
        event_type=TelemetryEventType.MEM_VERIFY,
        collector_id="collector",
        collector_seq=4,
        metadata={"verify_deadline": (now_utc() - timedelta(days=1)).isoformat()},
    )
    for telemetry in [first, duplicate_and_ordered_badly, correction, verify]:
        ledger.append("telemetry_event", telemetry)

    report = telemetry_audit_report(ledger)
    metrics = {item.metric_name: item for item in report.metrics}
    assert metrics["duplicate_event_id"].value == 1
    assert metrics["collector_ordering_violation"].value == 1
    assert metrics["skew_budget_violation"].value >= 1
    assert metrics["correction_latency_seconds"].status.value == "valid"
    assert metrics["verify_deadline_miss"].value == 1


def test_contamination_context_avoids_scope_false_positive() -> None:
    event = _event(memory_id="mem-safe")
    report = contamination_diagnostics([event])
    assert report.cross_agent_shared_memory_ids == []

    explicit = contamination_diagnostics(
        [event],
        context=ContaminationContext(shared_memory_ids=["mem-safe"]),
    )
    assert explicit.cross_agent_shared_memory_ids == ["mem-safe"]


def test_compression_source_digest_gap_rejects_and_metrics() -> None:
    certificate = make_compression_certificate(
        compressed_memory_id="summary",
        source_memory_ids=["mem-1", "mem-2"],
        source_size=100,
        compressed_size=40,
        recoverability_check="pass",
        source_coverage=1.0,
        source_digest_map={"mem-1": sha256_digest("source-1")},
    )
    assert certificate.decision == "reject"
    metrics = {metric.metric_name: metric for metric in compression_metrics(certificate)}
    assert metrics["compression_source_digest_coverage"].status.value == "invalid"
