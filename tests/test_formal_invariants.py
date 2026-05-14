from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cmgl.absence import make_record_absence_notice
from cmgl.admission import candidate_from_event, filter_retrieval
from cmgl.authority import authorize_bundle, make_declared_scope, make_protected_action_request
from cmgl.canonical import canonical_json
from cmgl.challenge import make_memory_challenge_record
from cmgl.digest import sha256_digest
from cmgl.evidence import build_evidence_manifest
from cmgl.exceptions import LedgerError
from cmgl.guarded import GuardedMemoryBackend
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import (
    AbsenceNoticeType,
    AdmissionDecision,
    BackendName,
    ContaminationLane,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
    ProtectedAction,
)
from cmgl.policy import AdmissionPolicy
from cmgl.state import current_memory_view_from_events, current_memory_view_from_ledger
from cmgl.time import now_utc
from cmgl.validation import validate_record_file

JSON_SCALARS = st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=40))
JSON_VALUES = st.recursive(
    JSON_SCALARS,
    lambda children: (
        st.lists(children, max_size=4)
        | st.dictionaries(st.text(min_size=1, max_size=12), children, max_size=4)
    ),
    max_leaves=12,
)


def _event(
    *,
    memory_id: str = "memory-1",
    update_id: str | None = "update-1",
    status: MemoryStatus = MemoryStatus.CERTIFIED,
    lane: ContaminationLane = ContaminationLane.USER_CLAIM,
    event_type: MemoryEventType = MemoryEventType.MEMORY_WRITE,
    valid_from_offset: int | None = None,
    valid_to_offset: int | None = None,
    source_hashes: list[str] | None = None,
    content: str = "User prefers morning meetings.",
) -> MemoryEvent:
    now = now_utc()
    return MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent",
        backend=BackendName.INMEMORY,
        event_type=event_type,
        memory_id=memory_id,
        memory_update_id=update_id,
        content=content,
        content_digest=sha256_digest(content),
        source_event_hashes=source_hashes
        if source_hashes is not None
        else [sha256_digest("source")],
        lane=lane,
        provenance_depth=0,
        valid_from=None if valid_from_offset is None else now + timedelta(days=valid_from_offset),
        valid_to=None if valid_to_offset is None else now + timedelta(days=valid_to_offset),
        authority_scope="user:test",
        status=status,
        checker_version="test",
        created_at=now,
    )


@settings(max_examples=30, derandomize=True)
@given(JSON_VALUES)
def test_canonical_json_and_digest_are_stable(value: Any) -> None:
    assert canonical_json(value) == canonical_json(value)
    assert sha256_digest(value) == sha256_digest(value)


@settings(max_examples=30, derandomize=True)
@given(st.dictionaries(st.text(min_size=1, max_size=8), JSON_SCALARS, min_size=1, max_size=5))
def test_digest_changes_when_canonical_payload_changes(payload: dict[str, Any]) -> None:
    mutated = dict(payload)
    mutated["cmgl_mutation_marker"] = "changed"
    assert canonical_json(payload) != canonical_json(mutated)
    assert sha256_digest(payload) != sha256_digest(mutated)


def _write_raw_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(canonical_json(row) for row in rows) + "\n", encoding="utf-8")


def _ledger_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_ledger_tamper_detection_variants(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = AppendOnlyLedger(path)
    ledger.append("memory_event", _event(memory_id="a"))
    ledger.append("memory_event", _event(memory_id="b"))
    ledger.append("memory_event", _event(memory_id="c"))
    rows = _ledger_rows(path)
    assert ledger.verify_prefix().ok

    variants: list[list[dict[str, Any]]] = []
    payload_mutation = [dict(row) for row in rows]
    payload_mutation[1]["payload"]["memory_id"] = "tampered"
    variants.append(payload_mutation)

    previous_mutation = [dict(row) for row in rows]
    previous_mutation[2]["previous_record_digest"] = sha256_digest("wrong")
    variants.append(previous_mutation)

    record_digest_mutation = [dict(row) for row in rows]
    record_digest_mutation[0]["record_digest"] = sha256_digest("wrong")
    variants.append(record_digest_mutation)

    variants.append([rows[0], rows[2]])
    variants.append([rows[1], rows[0], rows[2]])

    for index, variant in enumerate(variants):
        tampered = tmp_path / f"tampered-{index}.jsonl"
        _write_raw_ledger(tampered, variant)
        assert not AppendOnlyLedger(tampered).verify_prefix().ok


def test_expected_prefix_guard_rejects_stale_writer(tmp_path: Path) -> None:
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    first = ledger.append("memory_event", _event(memory_id="first"))
    ledger.append("memory_event", _event(memory_id="second"))
    with pytest.raises(LedgerError):
        ledger.append(
            "memory_event",
            _event(memory_id="forked"),
            expected_prefix=first.ledger_prefix_hash,
        )


@pytest.mark.parametrize(
    "status",
    [
        MemoryStatus.SUPERSEDED,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.TOMBSTONED,
        MemoryStatus.QUARANTINED,
    ],
)
def test_terminal_statuses_always_block_strict_policy(status: MemoryStatus) -> None:
    receipt = AdmissionPolicy().evaluate(candidate_from_event(_event(status=status)))
    assert receipt.decision == AdmissionDecision.BLOCK
    assert f"terminal_status.{status.value}" in receipt.reason_codes


@pytest.mark.parametrize(
    "lane",
    [
        ContaminationLane.MODEL_INFERENCE,
        ContaminationLane.REGENERATED_SUMMARY,
        ContaminationLane.SYNTHETIC_EVAL,
    ],
)
def test_blocked_fact_lanes_block_as_fact(lane: ContaminationLane) -> None:
    receipt = AdmissionPolicy().evaluate(candidate_from_event(_event(lane=lane)), as_fact=True)
    assert receipt.decision == AdmissionDecision.BLOCK
    assert f"lane.{lane.value}.blocked_as_fact" in receipt.reason_codes


def test_summary_is_not_promoted_to_fact_by_default() -> None:
    candidate = candidate_from_event(_event(lane=ContaminationLane.SUMMARY))
    fact_receipt = AdmissionPolicy().evaluate(candidate, as_fact=True)
    summary_receipt = AdmissionPolicy().evaluate(candidate, as_fact=False)
    assert fact_receipt.decision == AdmissionDecision.BLOCK
    assert "lane.summary.summary_not_fact" in fact_receipt.reason_codes
    assert summary_receipt.decision == AdmissionDecision.ADMIT


def test_temporal_and_version_binding_blockers() -> None:
    future = AdmissionPolicy().evaluate(
        candidate_from_event(_event(valid_from_offset=1)), as_fact=True
    )
    expired = AdmissionPolicy().evaluate(
        candidate_from_event(_event(valid_to_offset=-1)), as_fact=True
    )
    missing_update = AdmissionPolicy().evaluate(candidate_from_event(_event(update_id=None)))
    assert "valid_from.future" in future.reason_codes
    assert "valid_to.expired" in expired.reason_codes
    assert "version_binding.missing" in missing_update.reason_codes


def test_mismatched_evidence_manifest_blocks() -> None:
    event = _event()
    candidate = candidate_from_event(event)
    evidence = build_evidence_manifest(candidate).model_copy(
        update={"normalized_content_digest": sha256_digest("wrong")}
    )
    receipt = AdmissionPolicy().evaluate(candidate, evidence_manifest=evidence)
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "evidence_manifest.mismatch" in receipt.reason_codes


def test_mismatched_authority_scope_blocks_protected_event() -> None:
    scope = make_declared_scope(
        actor="agent.local",
        authority_scope="user:other",
        permitted_actions=[ProtectedAction.PERSISTENT_MEMORY_WRITE],
        expires_at=now_utc() + timedelta(minutes=10),
    )
    request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent.local",
        authority_scope="user:other",
        source_record="structured authority scope",
        declared_scope=scope,
    )
    event = _event(event_type=MemoryEventType.MEMORY_WRITE)
    receipt = AdmissionPolicy(
        require_authority_for_persistent_writes=True,
        require_authority_bundle=True,
    ).evaluate(
        candidate_from_event(event),
        authority_bundle=authorize_bundle(request, declared_scope=scope),
    )
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "authority.scope_mismatch" in receipt.reason_codes


def test_blocked_authority_does_not_invoke_external_write_callable() -> None:
    calls: list[str] = []

    def write(content, *, lane, authority_scope, metadata=None):  # type: ignore[no-untyped-def]
        calls.append(str(content))
        return {"id": "should-not-exist"}

    guarded = GuardedMemoryBackend(write=write)
    result = guarded.write_memory(
        "blocked",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:test",
    )
    assert result.decision == AdmissionDecision.BLOCK
    assert calls == []


def test_retrieval_filter_is_stable_and_reason_coded() -> None:
    events = [
        _event(memory_id="admit", content="current"),
        _event(memory_id="blocked", status=MemoryStatus.TOMBSTONED, content="old"),
    ]
    first = filter_retrieval("query", events)
    second = filter_retrieval("query", list(events))
    assert first.decision.admitted_memory_ids == second.decision.admitted_memory_ids == ["admit"]
    assert first.decision.context_digest == second.decision.context_digest
    assert first.decision.blocked_hits[0]["reason"]


def test_open_challenge_and_absence_notice_block_strict_admission() -> None:
    event = _event()
    candidate = candidate_from_event(event)
    challenge = make_memory_challenge_record(
        memory_id=event.memory_id,
        memory_update_id=event.memory_update_id,
        reason_codes=["challenge.open"],
    )
    absence = make_record_absence_notice(
        notice_type=AbsenceNoticeType.MISSING_EVIDENCE,
        memory_id=event.memory_id,
    )
    receipt = AdmissionPolicy().evaluate(
        candidate,
        challenge_records=[challenge],
        absence_notices=[absence],
    )
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "challenge.open" in receipt.reason_codes
    assert "absence.missing_evidence" in receipt.reason_codes


def test_current_view_terminal_states_and_broken_ledger(tmp_path: Path) -> None:
    current = _event(memory_id="same", update_id="u2", content="new")
    old = _event(memory_id="same", update_id="u1", status=MemoryStatus.SUPERSEDED, content="old")
    view = current_memory_view_from_events([old, current])
    assert view.current_memory_ids == ["same"]
    assert view.snapshots[0].current_update_id == "u2"

    for terminal in [
        MemoryStatus.TOMBSTONED,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.QUARANTINED,
    ]:
        terminal_view = current_memory_view_from_events(
            [
                current,
                _event(memory_id="same", update_id=f"terminal-{terminal.value}", status=terminal),
            ]
        )
        assert terminal_view.current_memory_ids == []
        assert terminal_view.audit_memory_ids == ["same"]

    ledger_path = tmp_path / "broken.jsonl"
    ledger = AppendOnlyLedger(ledger_path)
    ledger.append("memory_event", current)
    rows = _ledger_rows(ledger_path)
    rows[0]["payload"]["memory_id"] = "tampered"
    _write_raw_ledger(ledger_path, rows)
    with pytest.raises(LedgerError):
        current_memory_view_from_ledger(AppendOnlyLedger(ledger_path))
    legacy_view = current_memory_view_from_ledger(AppendOnlyLedger(ledger_path), strict=False)
    assert legacy_view.current_memory_ids == ["tampered"]


@pytest.mark.parametrize(
    "fixture_name",
    [
        "admission.certified_user_claim.valid.json",
        "compression.summary_not_fact.valid.json",
    ],
)
def test_valid_conformance_fixtures_validate(fixture_name: str) -> None:
    path = Path("examples/conformance") / fixture_name
    assert validate_record_file(path).status.value == "valid"
