from __future__ import annotations

from dataclasses import dataclass

from cmgl.audit import contamination_diagnostics
from cmgl.digest import sha256_digest
from cmgl.models import (
    BackendName,
    ContaminationAuditReport,
    ContaminationContext,
    ContaminationLane,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
)
from cmgl.time import now_utc


@dataclass(frozen=True)
class SharedMemoryStressResult:
    events: list[MemoryEvent]
    context: ContaminationContext
    report: ContaminationAuditReport
    post_fork_recovery_summary: str


def shared_memory_stress_fixture() -> SharedMemoryStressResult:
    """Small deterministic SEC-style contamination fixture for local tests.

    The fixture models two agents writing to a shared memory id, then evaluates
    cross-agent contamination only through explicit context. It is intentionally
    not a simulation runner.
    """

    shared_id = "shared-memory-0001"
    timestamp = now_utc()
    user_event = MemoryEvent(
        trace_id="stress-trace",
        run_id="stress-run-a",
        agent_id="agent.alpha",
        backend=BackendName.INMEMORY,
        event_type=MemoryEventType.MEMORY_WRITE,
        memory_id=shared_id,
        memory_update_id="stress-update-0001",
        content="User prefers morning meetings.",
        content_digest=sha256_digest("User prefers morning meetings."),
        source_event_hashes=[],
        lane=ContaminationLane.USER_CLAIM,
        provenance_depth=0,
        authority_scope="user:stress",
        status=MemoryStatus.CERTIFIED,
        checker_version="cmgl.stress.v1",
        created_at=timestamp,
    )
    inference_event = MemoryEvent(
        trace_id="stress-trace",
        run_id="stress-run-b",
        agent_id="agent.beta",
        backend=BackendName.INMEMORY,
        event_type=MemoryEventType.MEMORY_UPDATE,
        memory_id=shared_id,
        memory_update_id="stress-update-0002",
        content="Model inferred the user always prefers mornings.",
        content_digest=sha256_digest("Model inferred the user always prefers mornings."),
        source_event_hashes=[sha256_digest(user_event)],
        lane=ContaminationLane.MODEL_INFERENCE,
        provenance_depth=1,
        authority_scope="user:stress",
        status=MemoryStatus.QUARANTINED,
        checker_version="cmgl.stress.v1",
        created_at=timestamp,
    )
    events = [user_event, inference_event]
    context = ContaminationContext(
        shared_memory_ids=[shared_id],
        cross_agent_memory_ids=[shared_id],
        broker_agent_ids=["agent.alpha", "agent.beta"],
    )
    return SharedMemoryStressResult(
        events=events,
        context=context,
        report=contamination_diagnostics(events, context=context),
        post_fork_recovery_summary=(
            "model_inference update remains quarantined; user_claim source remains auditable"
        ),
    )
