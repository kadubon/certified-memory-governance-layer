from __future__ import annotations

import pytest
from pydantic import ValidationError

from cmgl.digest import sha256_digest
from cmgl.models import (
    BackendName,
    ContaminationLane,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
)
from cmgl.time import now_utc


def test_memory_event_validation() -> None:
    event = MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent",
        backend=BackendName.INMEMORY,
        event_type=MemoryEventType.MEMORY_WRITE,
        memory_id="mem-1",
        content="hello",
        content_digest=sha256_digest("hello"),
        lane=ContaminationLane.USER_CLAIM,
        provenance_depth=0,
        authority_scope="user:test",
        status=MemoryStatus.CERTIFIED,
        checker_version="test",
        created_at=now_utc(),
    )
    assert event.schema_version == "cmgl.memory_event.v1"


def test_memory_event_rejects_bad_digest() -> None:
    with pytest.raises(ValidationError):
        MemoryEvent(
            trace_id="trace",
            run_id="run",
            agent_id="agent",
            backend=BackendName.INMEMORY,
            event_type=MemoryEventType.MEMORY_WRITE,
            memory_id="mem-1",
            content="hello",
            content_digest="bad",
            lane=ContaminationLane.USER_CLAIM,
            provenance_depth=0,
            authority_scope="user:test",
            status=MemoryStatus.CERTIFIED,
            checker_version="test",
            created_at=now_utc(),
        )
