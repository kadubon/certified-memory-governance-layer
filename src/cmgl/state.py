from __future__ import annotations

from collections import defaultdict

from cmgl.digest import sha256_digest
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import (
    CurrentMemoryView,
    MemoryEvent,
    MemoryStateSnapshot,
    MemoryStatus,
)
from cmgl.time import now_utc

CURRENT_STATUSES = {MemoryStatus.CERTIFIED, MemoryStatus.ADMISSIBLE}
TERMINAL_STATUSES = {
    MemoryStatus.SUPERSEDED,
    MemoryStatus.CONTRADICTED,
    MemoryStatus.TOMBSTONED,
    MemoryStatus.QUARANTINED,
}


def current_memory_view_from_events(events: list[MemoryEvent]) -> CurrentMemoryView:
    by_memory_id: dict[str, list[MemoryEvent]] = defaultdict(list)
    for event in events:
        by_memory_id[event.memory_id].append(event)

    snapshots: list[MemoryStateSnapshot] = []
    current_ids: list[str] = []
    audit_ids: list[str] = []
    timestamp = now_utc()
    for memory_id in sorted(by_memory_id):
        versions = by_memory_id[memory_id]
        latest = versions[-1]
        historical_update_ids = [
            event.memory_update_id for event in versions if event.memory_update_id is not None
        ]
        current_event = latest if latest.status in CURRENT_STATUSES else None
        if current_event is not None:
            current_ids.append(memory_id)
        if len(versions) > 1 or latest.status in TERMINAL_STATUSES:
            audit_ids.append(memory_id)
        body = {
            "schema_version": "cmgl.memory_state_snapshot.v1",
            "memory_id": memory_id,
            "current_update_id": None if current_event is None else current_event.memory_update_id,
            "current_status": None if current_event is None else current_event.status,
            "current_event_digest": None if current_event is None else sha256_digest(current_event),
            "historical_update_ids": historical_update_ids,
            "superseded_update_ids": [
                event.memory_update_id or ""
                for event in versions
                if event.status == MemoryStatus.SUPERSEDED
            ],
            "tombstoned_update_ids": [
                event.memory_update_id or ""
                for event in versions
                if event.status == MemoryStatus.TOMBSTONED
            ],
            "quarantined_update_ids": [
                event.memory_update_id or ""
                for event in versions
                if event.status == MemoryStatus.QUARANTINED
            ],
            "timestamp": timestamp,
        }
        snapshots.append(MemoryStateSnapshot(**body, snapshot_digest=sha256_digest(body)))

    view_body = {
        "schema_version": "cmgl.current_memory_view.v1",
        "snapshots": snapshots,
        "current_memory_ids": current_ids,
        "audit_memory_ids": audit_ids,
        "timestamp": timestamp,
    }
    return CurrentMemoryView(**view_body, view_digest=sha256_digest(view_body))


def current_memory_view_from_ledger(ledger: AppendOnlyLedger) -> CurrentMemoryView:
    events: list[MemoryEvent] = []
    for record in ledger.iter_records():
        if record.record_type == "memory_event":
            events.append(MemoryEvent.model_validate(record.payload))
    return current_memory_view_from_events(events)


def current_events_from_view(
    events: list[MemoryEvent], view: CurrentMemoryView
) -> list[MemoryEvent]:
    current_refs = {
        (snapshot.memory_id, snapshot.current_update_id)
        for snapshot in view.snapshots
        if snapshot.current_update_id is not None
    }
    return [event for event in events if (event.memory_id, event.memory_update_id) in current_refs]
