from __future__ import annotations

from cmgl.models import MemoryEvent
from cmgl.state import current_memory_view_from_events


def resolve_current_events(
    events: list[MemoryEvent],
    *,
    include_audit: bool = False,
) -> list[MemoryEvent]:
    if include_audit:
        return list(events)
    view = current_memory_view_from_events(events)
    current_refs = {
        (snapshot.memory_id, snapshot.current_update_id)
        for snapshot in view.snapshots
        if snapshot.current_update_id is not None
    }
    return [event for event in events if (event.memory_id, event.memory_update_id) in current_refs]
