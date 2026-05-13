from __future__ import annotations

from typing import Any, Protocol

from cmgl.models import ContaminationLane, JsonContent, MemoryEvent


class MemoryBackend(Protocol):
    def write(
        self,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEvent:
        """Write content and return the normalized memory event."""

    def retrieve(self, query: str, *, limit: int = 10) -> list[MemoryEvent]:
        """Retrieve raw backend hits."""

    def update(
        self,
        memory_id: str,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEvent:
        """Create an update event without rewriting ledger evidence."""

    def delete(self, memory_id: str, *, reason: str) -> MemoryEvent:
        """Create a delete/tombstone event."""
