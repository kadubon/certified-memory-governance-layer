from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from types import ModuleType
from typing import Any

from pydantic import BaseModel

from cmgl.adapters.common import normalize_records
from cmgl.admission import RetrievalFilterResult
from cmgl.exceptions import OptionalDependencyError
from cmgl.layer import GovernanceLayer
from cmgl.models import ContaminationLane, MemoryEvent, MemoryEventType


def load_langgraph() -> ModuleType:
    try:
        return import_module("langgraph")
    except ImportError as exc:
        raise OptionalDependencyError("langgraph", "langgraph") from exc


class LangGraphAdapter:
    """CMGL context-filter helpers for LangGraph state and store workflows."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        layer: GovernanceLayer | None = None,
        lane: ContaminationLane = ContaminationLane.USER_CLAIM,
        authority_scope: str = "langgraph:store",
        agent_id: str = "langgraph-adapter",
        run_id: str = "langgraph-adapter",
        trace_id: str = "langgraph-adapter",
    ) -> None:
        self.client = client
        self.layer = layer or GovernanceLayer()
        self.lane = lane
        self.authority_scope = authority_scope
        self.agent_id = agent_id
        self.run_id = run_id
        self.trace_id = trace_id

    @classmethod
    def from_client(cls, client: Any, **kwargs: Any) -> LangGraphAdapter:
        return cls(client, **kwargs)

    @classmethod
    def require_dependency(cls) -> ModuleType:
        return load_langgraph()

    def filter_events(
        self,
        query: str,
        events: Sequence[MemoryEvent | Mapping[str, Any] | BaseModel],
        *,
        limit: int = 10,
    ) -> RetrievalFilterResult:
        return self.layer.filter_retrieval(query, self._coerce_events(events), limit=limit)

    def build_context(
        self,
        query: str,
        events: Sequence[MemoryEvent | Mapping[str, Any] | BaseModel],
        *,
        limit: int = 10,
    ) -> list[Any]:
        result = self.filter_events(query, events, limit=limit)
        return [event.content for event in result.admitted_events]

    def search_store(
        self,
        query: str,
        *,
        namespace: tuple[str, ...] | str | None = None,
        limit: int = 10,
        store: Any | None = None,
        **kwargs: Any,
    ) -> list[MemoryEvent]:
        """Read LangGraph store-shaped items and normalize them as memory events."""

        target = store or self.client
        if target is None or not hasattr(target, "search"):
            raise ValueError("a LangGraph store with a search method is required")
        if namespace is None:
            raw = target.search(query=query, limit=limit, **kwargs)
        else:
            raw = target.search(namespace, query=query, limit=limit, **kwargs)
        return self._coerce_events(list(raw) if isinstance(raw, Sequence) else [raw])

    def filter_store_search(
        self,
        query: str,
        *,
        namespace: tuple[str, ...] | str | None = None,
        limit: int = 10,
        store: Any | None = None,
        **kwargs: Any,
    ) -> RetrievalFilterResult:
        events = self.search_store(
            query,
            namespace=namespace,
            limit=limit,
            store=store,
            **kwargs,
        )
        return self.layer.filter_retrieval(query, events, limit=limit)

    def put_store_item(
        self,
        key: str,
        value: Mapping[str, Any],
        *,
        namespace: tuple[str, ...] | str | None = None,
        store: Any | None = None,
    ) -> Any:
        """Call a LangGraph store `put` method; caller owns authority gating for writes."""

        target = store or self.client
        if target is None or not hasattr(target, "put"):
            raise ValueError("a LangGraph store with a put method is required")
        if namespace is None:
            return target.put(key, value)
        return target.put(namespace, key, value)

    def filter_state(
        self,
        state: Mapping[str, Any],
        *,
        query_key: str = "query",
        memory_key: str = "memories",
        output_key: str | None = None,
        decision_key: str = "cmgl_retrieval_decision",
        limit: int = 10,
    ) -> dict[str, Any]:
        query = str(state.get(query_key, ""))
        raw_memories = state.get(memory_key, [])
        if not isinstance(raw_memories, Sequence) or isinstance(raw_memories, str | bytes):
            raw_memories = []
        result = self.filter_events(query, raw_memories, limit=limit)
        updated = dict(state)
        updated[output_key or memory_key] = result.admitted_events
        updated[decision_key] = result.decision.model_dump(mode="json")
        return updated

    def as_node(
        self,
        *,
        query_key: str = "query",
        memory_key: str = "memories",
        output_key: str | None = None,
        decision_key: str = "cmgl_retrieval_decision",
        limit: int = 10,
    ) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
        def node(state: Mapping[str, Any]) -> dict[str, Any]:
            return self.filter_state(
                state,
                query_key=query_key,
                memory_key=memory_key,
                output_key=output_key,
                decision_key=decision_key,
                limit=limit,
            )

        return node

    def _coerce_events(
        self, events: Sequence[MemoryEvent | Mapping[str, Any] | BaseModel]
    ) -> list[MemoryEvent]:
        if all(isinstance(event, MemoryEvent) for event in events):
            return [event for event in events if isinstance(event, MemoryEvent)]
        return normalize_records(
            list(events),
            backend="langgraph",
            event_type=MemoryEventType.MEMORY_RETRIEVE,
            lane=self.lane,
            authority_scope=self.authority_scope,
            agent_id=self.agent_id,
            run_id=self.run_id,
            trace_id=self.trace_id,
        )
