from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from cmgl.contracts.telemetry import TelemetryPayload
from cmgl.digest import sha256_digest
from cmgl.evidence import versioned_ref_from_event
from cmgl.models import MemoryEvent, MemoryTelemetryEvent, TelemetryEventType, VersionedMemoryRef
from cmgl.time import now_utc


def make_telemetry_event(
    *,
    event_type: TelemetryEventType,
    collector_id: str,
    collector_seq: int,
    memory_refs: list[VersionedMemoryRef] | None = None,
    event_id: str | None = None,
    obs_time: datetime | None = None,
    skew_budget_ms: int = 0,
    trace_id: str | None = None,
    run_id: str | None = None,
    agent_id: str | None = None,
    metadata: dict[str, object] | None = None,
    payload: TelemetryPayload | None = None,
) -> MemoryTelemetryEvent:
    timestamp = obs_time or now_utc()
    body = {
        "schema_version": "cmgl.memory_telemetry_event.v1",
        "event_type": event_type,
        "collector_id": collector_id,
        "collector_seq": collector_seq,
        "event_id": event_id or f"telemetry:{uuid4()}",
        "obs_time": timestamp,
        "skew_budget_ms": skew_budget_ms,
        "memory_refs": memory_refs or [],
        "trace_id": trace_id,
        "run_id": run_id,
        "agent_id": agent_id,
        "metadata": metadata or {},
        "payload": payload,
    }
    return MemoryTelemetryEvent(**body, event_digest=sha256_digest(body))


def telemetry_from_memory_event(
    event: MemoryEvent,
    *,
    event_type: TelemetryEventType,
    collector_id: str = "cmgl",
    collector_seq: int = 0,
    metadata: dict[str, object] | None = None,
) -> MemoryTelemetryEvent:
    ref = versioned_ref_from_event(event)
    refs = [] if ref is None else [ref]
    return make_telemetry_event(
        event_type=event_type,
        collector_id=collector_id,
        collector_seq=collector_seq,
        memory_refs=refs,
        trace_id=event.trace_id,
        run_id=event.run_id,
        agent_id=event.agent_id,
        metadata=metadata,
    )


def telemetry_order_key(event: MemoryTelemetryEvent) -> tuple[datetime, str, int, str]:
    return (event.obs_time, event.collector_id, event.collector_seq, event.event_id)
