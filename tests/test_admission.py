from __future__ import annotations

from datetime import timedelta

from cmgl.admission import candidate_from_event
from cmgl.digest import sha256_digest
from cmgl.models import (
    AdmissionDecision,
    BackendName,
    ContaminationLane,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
)
from cmgl.policy import AdmissionPolicy
from cmgl.time import now_utc


def make_event(
    *,
    status: MemoryStatus = MemoryStatus.CERTIFIED,
    lane: ContaminationLane = ContaminationLane.USER_CLAIM,
    valid_to_offset_days: int | None = None,
    source_hashes: list[str] | None = None,
) -> MemoryEvent:
    valid_to = None
    if valid_to_offset_days is not None:
        valid_to = now_utc() + timedelta(days=valid_to_offset_days)
    return MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent",
        backend=BackendName.INMEMORY,
        event_type=MemoryEventType.MEMORY_WRITE,
        memory_id=f"mem-{status.value}-{lane.value}",
        memory_update_id=f"update-{status.value}-{lane.value}",
        content="memory",
        content_digest=sha256_digest("memory"),
        source_event_hashes=source_hashes or [],
        lane=lane,
        provenance_depth=0,
        valid_to=valid_to,
        authority_scope="user:test",
        status=status,
        checker_version="test",
        created_at=now_utc(),
    )


def test_policy_admits_certified_memory() -> None:
    receipt = AdmissionPolicy().evaluate(candidate_from_event(make_event()))
    assert receipt.decision == AdmissionDecision.ADMIT


def test_policy_blocks_disallowed_statuses() -> None:
    blocked = [
        MemoryStatus.RAW,
        MemoryStatus.CANDIDATE,
        MemoryStatus.SUPERSEDED,
        MemoryStatus.TOMBSTONED,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.QUARANTINED,
    ]
    for status in blocked:
        receipt = AdmissionPolicy().evaluate(candidate_from_event(make_event(status=status)))
        assert receipt.decision == AdmissionDecision.BLOCK
        assert f"status.{status.value}.blocked" in receipt.reason_codes


def test_policy_blocks_model_inference_as_fact() -> None:
    receipt = AdmissionPolicy().evaluate(
        candidate_from_event(
            make_event(
                lane=ContaminationLane.MODEL_INFERENCE,
                source_hashes=[sha256_digest("source")],
            )
        )
    )
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "lane.model_inference.blocked_as_fact" in receipt.reason_codes


def test_policy_blocks_expired_valid_to() -> None:
    receipt = AdmissionPolicy().evaluate(candidate_from_event(make_event(valid_to_offset_days=-1)))
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "valid_to.expired" in receipt.reason_codes


def test_policy_blocks_missing_source_for_tool_observation() -> None:
    receipt = AdmissionPolicy().evaluate(
        candidate_from_event(make_event(lane=ContaminationLane.TOOL_OBSERVATION))
    )
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "source_event_hashes.missing" in receipt.reason_codes
