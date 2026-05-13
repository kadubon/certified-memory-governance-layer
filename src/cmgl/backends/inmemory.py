from __future__ import annotations

import json
from typing import Any

from cmgl.digest import sha256_digest
from cmgl.models import (
    BackendName,
    ContaminationLane,
    JsonContent,
    MemoryEvent,
    MemoryEventType,
    MemoryRevision,
    MemoryStatus,
)
from cmgl.time import now_utc
from cmgl.transitions import LifecyclePolicy, make_memory_revision


class InMemoryBackend:
    """Small deterministic backend for tests and local examples."""

    def __init__(
        self,
        *,
        agent_id: str = "agent.local",
        run_id: str = "run.local",
        trace_id: str = "trace.local",
        checker_version: str = "cmgl.checker.v1",
    ) -> None:
        self.agent_id = agent_id
        self.run_id = run_id
        self.trace_id = trace_id
        self.checker_version = checker_version
        self._memory_counter = 0
        self._update_counter = 0
        self._events: dict[str, MemoryEvent] = {}
        self._revisions: list[MemoryRevision] = []
        self._lifecycle_policy = LifecyclePolicy()

    def write(
        self,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEvent:
        metadata = metadata or {}
        status = MemoryStatus(metadata.get("status", MemoryStatus.CERTIFIED.value))
        event = self._make_event(
            event_type=MemoryEventType.MEMORY_WRITE,
            content=content,
            lane=lane,
            authority_scope=authority_scope,
            status=status,
            source_event_hashes=list(metadata.get("source_event_hashes", [])),
            valid_from=metadata.get("valid_from"),
            valid_to=metadata.get("valid_to"),
            provenance_depth=int(metadata.get("provenance_depth", 0)),
        )
        self._events[_event_key(event)] = event
        return event

    def retrieve(self, query: str, *, limit: int = 10) -> list[MemoryEvent]:
        query_text = query.lower()
        results: list[MemoryEvent] = []
        for stored_event in self._events.values():
            event = self._materialize_status(stored_event)
            haystack = _content_text(event.content).lower()
            if not query_text or query_text in haystack:
                results.append(event)
            if len(results) >= limit:
                break
        return results

    def update(
        self,
        memory_id: str,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEvent:
        metadata = metadata or {}
        old_event = self._latest_event(memory_id)
        self._lifecycle_policy.require_transition(old_event.status, MemoryStatus.SUPERSEDED)
        event = self._make_event(
            event_type=MemoryEventType.MEMORY_UPDATE,
            content=content,
            lane=lane,
            authority_scope=authority_scope,
            status=MemoryStatus(metadata.get("status", MemoryStatus.CERTIFIED.value)),
            source_event_hashes=[sha256_digest(old_event)],
            memory_id=memory_id,
            valid_from=metadata.get("valid_from"),
            valid_to=metadata.get("valid_to"),
            provenance_depth=int(metadata.get("provenance_depth", old_event.provenance_depth + 1)),
        )
        self._revisions.append(
            make_memory_revision(
                revision_id=f"revision-{len(self._revisions) + 1:04d}",
                memory_id=memory_id,
                from_update_id=old_event.memory_update_id,
                to_update_id=event.memory_update_id,
                from_status=old_event.status,
                to_status=MemoryStatus.SUPERSEDED,
                reason_codes=["memory.superseded_by_update"],
            )
        )
        self._events[_event_key(event)] = event
        return event

    def delete(self, memory_id: str, *, reason: str) -> MemoryEvent:
        old_event = self._latest_event(memory_id)
        self._lifecycle_policy.require_transition(old_event.status, MemoryStatus.TOMBSTONED)
        event = self._make_event(
            event_type=MemoryEventType.MEMORY_TOMBSTONE,
            content={"reason": reason, "tombstone_of": memory_id},
            lane=old_event.lane,
            authority_scope=old_event.authority_scope,
            status=MemoryStatus.TOMBSTONED,
            source_event_hashes=[sha256_digest(old_event)],
            memory_id=memory_id,
        )
        self._revisions.append(
            make_memory_revision(
                revision_id=f"revision-{len(self._revisions) + 1:04d}",
                memory_id=memory_id,
                from_update_id=old_event.memory_update_id,
                to_update_id=event.memory_update_id,
                from_status=old_event.status,
                to_status=MemoryStatus.TOMBSTONED,
                reason_codes=[reason],
            )
        )
        self._events[_event_key(event)] = event
        return event

    def revisions(self) -> list[MemoryRevision]:
        return list(self._revisions)

    def _make_event(
        self,
        *,
        event_type: MemoryEventType,
        content: JsonContent,
        lane: ContaminationLane,
        authority_scope: str,
        status: MemoryStatus,
        source_event_hashes: list[str],
        provenance_depth: int = 0,
        memory_id: str | None = None,
        valid_from: Any = None,
        valid_to: Any = None,
    ) -> MemoryEvent:
        if memory_id is None:
            self._memory_counter += 1
            memory_id = f"mem-{self._memory_counter:04d}"
        self._update_counter += 1
        memory_update_id = f"update-{self._update_counter:04d}"
        return MemoryEvent(
            trace_id=self.trace_id,
            run_id=self.run_id,
            agent_id=self.agent_id,
            backend=BackendName.INMEMORY,
            event_type=event_type,
            memory_id=memory_id,
            memory_update_id=memory_update_id,
            content=content,
            content_digest=sha256_digest(content if content is not None else ""),
            source_event_hashes=source_event_hashes,
            lane=lane,
            provenance_depth=provenance_depth,
            valid_from=valid_from,
            valid_to=valid_to,
            authority_scope=authority_scope,
            status=status,
            checker_version=self.checker_version,
            created_at=now_utc(),
        )

    def _latest_event(self, memory_id: str) -> MemoryEvent:
        matches = [
            self._materialize_status(event)
            for event in self._events.values()
            if event.memory_id == memory_id
        ]
        if not matches:
            raise KeyError(memory_id)
        return matches[-1]

    def _materialize_status(self, event: MemoryEvent) -> MemoryEvent:
        status = event.status
        for revision in self._revisions:
            if (
                revision.memory_id == event.memory_id
                and revision.from_update_id == event.memory_update_id
            ):
                status = revision.to_status
        if status == event.status:
            return event
        return event.model_copy(update={"status": status})


def _content_text(content: JsonContent) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return json.dumps(content, sort_keys=True)


def _event_key(event: MemoryEvent) -> str:
    return f"{event.memory_id}:{event.memory_update_id or 'unversioned'}"
