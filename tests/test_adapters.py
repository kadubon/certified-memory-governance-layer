from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from cmgl.adapters import graphiti, langgraph, langmem, mem0
from cmgl.authority import (
    authorize_bundle,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.exceptions import AdapterOperationError, OptionalDependencyError
from cmgl.models import AdapterOperationStatus, AdmissionDecision, ProtectedAction
from cmgl.time import now_utc


def _authority_bundle(
    *,
    scope: str = "user:adapter",
    action: ProtectedAction = ProtectedAction.PERSISTENT_MEMORY_WRITE,
):
    declared_scope = make_declared_scope(
        actor="agent.local",
        authority_scope=scope,
        permitted_actions=[action],
        expires_at=now_utc() + timedelta(minutes=10),
    )
    request = make_protected_action_request(
        action=action,
        actor="agent.local",
        authority_scope=scope,
        source_record="structured adapter test scope",
        declared_scope=declared_scope,
    )
    return authorize_bundle(request, declared_scope=declared_scope)


def test_optional_adapter_missing_dependency_message(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def missing(_: str) -> None:
        raise ImportError("missing")

    monkeypatch.setattr(mem0, "import_module", missing)
    with pytest.raises(OptionalDependencyError) as exc:
        mem0.load_mem0()
    assert 'pip install "cmgl[mem0]"' in str(exc.value)
    assert 'uv add "cmgl[mem0]"' in str(exc.value)


@pytest.mark.parametrize(
    ("module", "loader", "extra"),
    [
        (mem0, mem0.load_mem0, "cmgl[mem0]"),
        (graphiti, graphiti.load_graphiti, "cmgl[graphiti]"),
        (langmem, langmem.load_langmem, "cmgl[langmem]"),
        (langgraph, langgraph.load_langgraph, "cmgl[langgraph]"),
    ],
)
def test_optional_adapters_import_lazily(module, loader, extra, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def missing(_: str) -> None:
        raise ImportError("missing")

    monkeypatch.setattr(module, "import_module", missing)
    with pytest.raises(OptionalDependencyError) as exc:
        loader()
    assert extra in str(exc.value)
    assert "pip install" in str(exc.value)
    assert "uv add" in str(exc.value)


class FakeMem0Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.records = [
            {
                "id": "mem0-1",
                "memory": "User prefers morning meetings.",
                "status": "certified",
            },
            {
                "id": "mem0-2",
                "memory": "Old deleted preference.",
                "status": "tombstoned",
            },
        ]

    def add(self, content, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("add", content))
        return {"id": "mem0-created", "memory": content, "metadata": kwargs.get("metadata")}

    def search(self, query, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("search", query))
        return {"results": self.records[: kwargs.get("top_k", 10)]}

    def get(self, memory_id, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("get", memory_id))
        return {"id": memory_id, "memory": "lookup", "status": "certified"}

    def get_all(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("get_all", kwargs))
        return self.records

    def update(self, memory_id, content, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("update", memory_id))
        return {"id": memory_id, "memory": content}

    def delete(self, memory_id):  # type: ignore[no-untyped-def]
        self.calls.append(("delete", memory_id))
        return {"id": memory_id, "deleted": True}


def test_mem0_adapter_normalizes_and_guards_persistence() -> None:
    client = FakeMem0Client()
    adapter = mem0.Mem0Adapter(client, authority_scope="user:adapter")

    blocked = adapter.add("blocked")
    assert blocked.decision == AdmissionDecision.BLOCK
    assert blocked.adapter_operation_receipt is not None
    assert blocked.adapter_operation_receipt.status == AdapterOperationStatus.NOT_CALLED
    assert not any(call[0] == "add" for call in client.calls)

    admitted = adapter.add(
        "admitted",
        authority_bundle=_authority_bundle(scope="user:adapter"),
    )
    assert admitted.decision == AdmissionDecision.ADMIT
    assert admitted.adapter_operation_receipt is not None
    assert admitted.adapter_operation_receipt.status == AdapterOperationStatus.SUCCEEDED
    assert admitted.adapter_operation_receipt.external_ref is not None
    assert admitted.adapter_operation_receipt.external_ref.external_id == "mem0-created"
    assert ("add", "admitted") in client.calls

    filtered = adapter.filter_search("meetings")
    assert filtered.decision.raw_hits == 2
    assert filtered.decision.admitted_memory_ids == ["mem0-1"]
    assert filtered.admitted_events[0].backend == "mem0"
    assert adapter.get("mem0-1").memory_id == "mem0-1"
    assert len(adapter.get_all()) == 2
    untrusted = mem0.Mem0Adapter(client, authority_scope="user:adapter")
    assert untrusted.search("no explicit evidence")[0].status.value == "certified"
    client.records = [{"id": "mem0-unsourced", "memory": "unsourced"}]
    assert untrusted.search("unsourced")[0].status.value == "candidate"
    trusted = mem0.Mem0Adapter(client, authority_scope="user:adapter", trusted_results=True)
    assert trusted.search("unsourced")[0].status.value == "certified"

    with pytest.raises(AdapterOperationError):
        adapter.update("unbound", "new content")


def test_mem0_adapter_records_failed_external_write() -> None:
    class FailingMem0Client(FakeMem0Client):
        def add(self, content, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(("add", content))
            raise RuntimeError("provider failed")

    client = FailingMem0Client()
    adapter = mem0.Mem0Adapter(client, authority_scope="user:adapter")
    bundle = adapter.add(
        "admitted but backend fails",
        authority_bundle=_authority_bundle(scope="user:adapter"),
    )
    assert bundle.adapter_operation_receipt is not None
    assert bundle.adapter_operation_receipt.status == AdapterOperationStatus.FAILED
    assert bundle.adapter_operation_receipt.error_type == "RuntimeError"
    assert bundle.quarantine_record_digest is not None


class FakeGraphitiClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def add_episode(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append("add_episode")
        return {"uuid": "episode-created", "episode_body": kwargs["episode_body"]}

    async def search(self, query, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append("search")
        return [
            {"uuid": "episode-1", "fact": "Graphiti fact", "status": "certified"},
            {"uuid": "episode-2", "fact": "Quarantined fact", "status": "quarantined"},
        ]

    async def search_(self, query, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append("search_")
        return {"edges": [{"uuid": "edge-1", "fact": "Edge fact", "status": "certified"}]}


def test_graphiti_adapter_async_guard_and_filter() -> None:
    async def run() -> None:
        client = FakeGraphitiClient()
        adapter = graphiti.GraphitiAdapter(client, authority_scope="user:adapter")
        blocked = await adapter.add_episode(
            name="episode",
            episode_body="blocked body",
            source_description="test",
        )
        assert blocked.decision == AdmissionDecision.BLOCK
        assert "add_episode" not in client.calls

        admitted = await adapter.add_episode(
            name="episode",
            episode_body="admitted body",
            source_description="test",
            authority_bundle=_authority_bundle(scope="user:adapter"),
        )
        assert admitted.decision == AdmissionDecision.ADMIT
        assert admitted.adapter_operation_receipt is not None
        assert admitted.adapter_operation_receipt.status == AdapterOperationStatus.SUCCEEDED
        assert admitted.adapter_operation_receipt.external_ref is not None
        assert admitted.adapter_operation_receipt.external_ref.external_id == "episode-created"
        assert "add_episode" in client.calls

        filtered = await adapter.filter_search("fact")
        assert filtered.decision.raw_hits == 2
        assert filtered.decision.admitted_memory_ids == ["episode-1"]
        search_under = await adapter.search_("edge")
        assert search_under[0].memory_id == "edge-1"

    asyncio.run(run())


def test_graphiti_adapter_preserves_temporal_and_provenance_fields() -> None:
    async def run() -> None:
        class TemporalGraphitiClient(FakeGraphitiClient):
            async def search(self, query, **kwargs):  # type: ignore[no-untyped-def]
                return [
                    {
                        "uuid": "temporal-1",
                        "fact": "Temporal fact",
                        "status": "certified",
                        "source_description": "episode source",
                        "group_ids": ["group-a"],
                        "reference_time": "2026-05-14T00:00:00Z",
                        "valid_to": "2026-05-15T00:00:00Z",
                    }
                ]

        adapter = graphiti.GraphitiAdapter(TemporalGraphitiClient())
        event = (await adapter.search("temporal"))[0]
        assert event.memory_id == "temporal-1"
        assert event.valid_from is not None
        assert event.valid_to is not None
        assert event.metadata["source_description"] == "episode source"
        assert event.metadata["group_ids"] == ["group-a"]
        assert event.source_event_hashes

    asyncio.run(run())


class FakeTool:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def invoke(self, payload):  # type: ignore[no-untyped-def]
        self.calls.append(payload)
        return self.result


def test_langmem_adapter_guards_manage_tool_and_filters_search() -> None:
    manage_tool = FakeTool({"id": "lm-created", "content": "created"})
    search_tool = FakeTool(
        {
            "memories": [
                {"id": "lm-1", "content": "keep", "status": "certified"},
                {"id": "lm-2", "content": "drop", "status": "superseded"},
            ]
        }
    )
    adapter = langmem.LangMemAdapter(authority_scope="user:adapter")
    blocked = adapter.manage_memory("create", content="blocked", manage_tool=manage_tool)
    assert blocked.decision == AdmissionDecision.BLOCK
    assert manage_tool.calls == []

    admitted = adapter.manage_memory(
        "create",
        content="admitted",
        manage_tool=manage_tool,
        authority_bundle=_authority_bundle(scope="user:adapter"),
    )
    assert admitted.decision == AdmissionDecision.ADMIT
    assert admitted.adapter_operation_receipt is not None
    assert admitted.adapter_operation_receipt.status == AdapterOperationStatus.SUCCEEDED
    assert admitted.adapter_operation_receipt.external_ref is not None
    assert admitted.adapter_operation_receipt.external_ref.external_id == "lm-created"
    assert manage_tool.calls[0]["content"] == "admitted"

    filtered = adapter.filter_search("keep", search_tool=search_tool)
    assert filtered.decision.admitted_memory_ids == ["lm-1"]


def test_langmem_adapter_supports_async_tools() -> None:
    class AsyncTool:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def ainvoke(self, payload):  # type: ignore[no-untyped-def]
            self.calls.append(payload)
            return {"id": "async-memory", "content": payload["content"]}

    async def run() -> None:
        tool = AsyncTool()
        adapter = langmem.LangMemAdapter(authority_scope="user:adapter")
        bundle = await adapter.amanage_memory(
            "create",
            content="async admitted",
            manage_tool=tool,
            authority_bundle=_authority_bundle(scope="user:adapter"),
        )
        assert bundle.adapter_operation_receipt is not None
        assert bundle.adapter_operation_receipt.status == AdapterOperationStatus.SUCCEEDED
        assert tool.calls[0]["content"] == "async admitted"

    asyncio.run(run())


def test_langgraph_adapter_filters_state_and_preserves_order() -> None:
    adapter = langgraph.LangGraphAdapter(authority_scope="user:adapter")
    memories = [
        {"id": "lg-1", "content": "first", "status": "certified"},
        {"id": "lg-2", "content": "blocked", "status": "tombstoned"},
        {"id": "lg-3", "content": "second", "status": "admissible"},
    ]
    result = adapter.filter_events("query", memories)
    assert result.decision.admitted_memory_ids == ["lg-1", "lg-3"]
    assert [event.content for event in result.admitted_events] == ["first", "second"]

    node = adapter.as_node(output_key="admitted_memories")
    state = node({"query": "query", "memories": memories})
    assert [event.memory_id for event in state["admitted_memories"]] == ["lg-1", "lg-3"]
    assert state["cmgl_retrieval_decision"]["raw_hits"] == 3


def test_langgraph_adapter_normalizes_store_items() -> None:
    class FakeStore:
        def __init__(self) -> None:
            self.values = [
                {"id": "store-1", "content": "safe", "status": "certified"},
                {"id": "store-2", "content": "unsafe", "status": "quarantined"},
            ]

        def search(self, namespace, **kwargs):  # type: ignore[no-untyped-def]
            assert namespace == ("memories", "user")
            return self.values

    adapter = langgraph.LangGraphAdapter(authority_scope="user:adapter")
    result = adapter.filter_store_search(
        "safe",
        namespace=("memories", "user"),
        store=FakeStore(),
    )
    assert result.decision.admitted_memory_ids == ["store-1"]
