from __future__ import annotations

from cmgl import ContaminationLane, MemoryStatus
from cmgl.backends import InMemoryBackend


def test_inmemory_backend_write_retrieve_update_delete() -> None:
    backend = InMemoryBackend()
    old = backend.write(
        "User prefers morning meetings.",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:test",
    )
    assert old.status == MemoryStatus.CERTIFIED
    assert old.memory_update_id is not None
    assert backend.retrieve("morning")[0].memory_id == old.memory_id

    new = backend.update(
        old.memory_id,
        "User prefers afternoon meetings.",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:test",
    )
    hits = backend.retrieve("meetings")
    assert new.memory_id == old.memory_id
    statuses = {event.memory_update_id: event.status for event in hits}
    assert statuses[old.memory_update_id] == MemoryStatus.SUPERSEDED
    assert statuses[new.memory_update_id] == MemoryStatus.CERTIFIED

    tombstone = backend.delete(new.memory_id, reason="test cleanup")
    assert tombstone.status == MemoryStatus.TOMBSTONED
    assert tombstone.memory_id == old.memory_id
    assert backend.retrieve("afternoon")[0].status == MemoryStatus.TOMBSTONED
