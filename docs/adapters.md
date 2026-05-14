# Adapters

CMGL adapters are safe integration shims around user-owned framework clients. They do not create cloud clients, start databases, call LLMs, or hide framework-specific configuration. The application provides the client/tool/store object; CMGL provides deterministic governance before persistent writes and before retrieved memory enters agent context.

Adapter rules:

- Optional dependencies are never imported at module import time.
- Missing dependencies raise `OptionalDependencyError` with both `pip install "cmgl[...]"` and `uv add "cmgl[...]"` hints.
- Persistent writes, updates, and deletes are routed through `GovernanceLayer` or `GuardedMemoryBackend` before the external store is called.
- Retrieval results are normalized into `MemoryEvent` objects, then filtered by CMGL policy.
- External persistence produces `AdapterOperationReceipt`. The receipt records whether the external store was not called, succeeded, failed, or was compensated.
- Successful persistence binds CMGL `memory_id` / `memory_update_id` to the external backend ID/update ID, content digest, backend name, namespace/scope, and source payload digest.
- Failed persistence is not swallowed: CMGL records a failed adapter operation receipt and a quarantine record.
- Core tests use fake clients only. They do not require hosted services, Neo4j, LLM providers, API keys, or network access.
- CMGL does not vendor code from Mem0, Graphiti, LangMem, LangGraph, Letta, Cognee, or MemOS.

Install extras only when your application needs them:

```bash
uv add "cmgl[mem0]"
uv add "cmgl[graphiti]"
uv add "cmgl[langmem]"
uv add "cmgl[langgraph]"
```

## Compatibility Matrix

| Adapter | Optional extra | Tested mode | Live-smoke environment | Limitations | Missing dependency behavior |
| --- | --- | --- | --- | --- | --- |
| Mem0 | `cmgl[mem0]` | Fake `Memory` / `MemoryClient`-like client for add/search/get/get_all/update/delete; guarded writes; failed persistence receipt. | `OPENAI_API_KEY` or compatible Mem0 provider config; `MEM0_TEST_USER_PREFIX` recommended. | CMGL does not own Mem0 cloud/provider setup or guarantee every Mem0 SDK version. Update/delete require prior binding unless migration override is explicit. | Module imports without Mem0; `load_mem0()` / `require_dependency()` raise `OptionalDependencyError` with install hints. |
| Graphiti | `cmgl[graphiti]` | Fake async client for `add_episode`, `search`, and `search_`; guarded episode writes; retrieval filtering. | `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`. | CMGL does not own Neo4j, LLM, embedder, or Graphiti driver operations. | Module imports without Graphiti; `load_graphiti()` / `require_dependency()` raise `OptionalDependencyError` with install hints. |
| LangMem | `cmgl[langmem]` | Fake sync and async tools; `.invoke`, `.ainvoke`, callable, and store-like flows. | Local LangGraph `InMemoryStore` where possible; provider keys are application-owned if your LangMem setup needs them. | CMGL does not own long-term store choice or LangChain/LangMem runtime topology. | Module imports without LangMem; `load_langmem()` / `require_dependency()` raise `OptionalDependencyError` with install hints. |
| LangGraph | `cmgl[langgraph]` | Fake state/store items; retrieval filtering; context-node helper; store search normalization. | Local LangGraph `InMemoryStore`; no model calls. | CMGL does not assume a graph topology or manage graph execution. | Module imports without LangGraph; `load_langgraph()` / `require_dependency()` raise `OptionalDependencyError` with install hints. |

## Mem0

`Mem0Adapter` supports `Memory` and `MemoryClient`-like objects that expose common `add`, `search`, `get`, `get_all`, `update`, and `delete` methods.

```python
from cmgl.adapters.mem0 import Mem0Adapter

adapter = Mem0Adapter(mem0_client, authority_scope="user:demo")

write_bundle = adapter.add(
    "User prefers morning meetings.",
    authority_bundle=authority_bundle,
)

filtered = adapter.filter_search("meeting preference", limit=10)
admitted_ids = filtered.decision.admitted_memory_ids
```

`adapter.add`, `adapter.update`, and `adapter.delete` call Mem0 only after CMGL admits the protected action. Without a valid strict authority bundle, the external client is not called.

By default, Mem0 update/delete require a prior CMGL-to-external binding. For controlled migrations of an existing Mem0 store, pass `allow_unbound_external_ref=True` and keep a migration audit record in your own release notes.

## Graphiti

`GraphitiAdapter` is async and wraps user-supplied Graphiti clients with `add_episode`, `search`, and `search_` methods. Live Neo4j, LLM, embedder, and Graphiti driver setup remain application-owned.

```python
from cmgl.adapters.graphiti import GraphitiAdapter

adapter = GraphitiAdapter(graphiti_client, authority_scope="user:demo")

await adapter.add_episode(
    name="preference-correction",
    episode_body="User now prefers afternoon meetings.",
    source_description="user correction in run 42",
    authority_bundle=authority_bundle,
)

filtered = await adapter.filter_search("meeting preference")
```

Graphiti episodes default to the `external_doc` contamination lane. The adapter binds `source_description`, `group_ids`, and `reference_time` into local evidence so strict policy has a source digest. Live Neo4j, LLM, and embedder configuration remains user-owned.

## LangMem

`LangMemAdapter` works with LangMem manage/search tools or compatible callables. It supports tools exposing `.invoke(payload)`, `.ainvoke(payload)`, sync callables, async callables, and store-like search/put objects.

```python
from cmgl.adapters.langmem import LangMemAdapter

adapter = LangMemAdapter(authority_scope="user:demo")

adapter.manage_memory(
    "create",
    content="User prefers concise summaries.",
    manage_tool=manage_memory_tool,
    authority_bundle=authority_bundle,
)

filtered = adapter.filter_search(
    "summary preference",
    search_tool=search_memory_tool,
)
```

Factory helpers are available when LangMem is installed:

```python
manage_tool = LangMemAdapter.create_manage_memory_tool(namespace=("memories",))
search_tool = LangMemAdapter.create_search_memory_tool(namespace=("memories",))
```

## LangGraph

`LangGraphAdapter` is a context-filter helper for state/store workflows. It does not assume a graph topology.

```python
from cmgl.adapters.langgraph import LangGraphAdapter

adapter = LangGraphAdapter(authority_scope="user:demo")

cmgl_node = adapter.as_node(
    query_key="query",
    memory_key="retrieved_memories",
    output_key="admitted_memories",
)

state = cmgl_node(state)
context = [event.content for event in state["admitted_memories"]]
```

You can also call `filter_events(query, events)` directly when your retrieval step already returns CMGL `MemoryEvent` objects. For LangGraph store-shaped items, use `search_store` or `filter_store_search`.

## Custom Backends

For most production systems, `GuardedMemoryBackend` is enough:

```python
from cmgl import ContaminationLane, GuardedMemoryBackend

guarded = GuardedMemoryBackend(
    write=my_store_write,
    update=my_store_update,
    delete=my_store_delete,
    retrieve=my_store_retrieve,
)

bundle = guarded.write_memory(
    "User prefers morning meetings.",
    lane=ContaminationLane.USER_CLAIM,
    authority_scope="user:demo",
    authority_bundle=authority_bundle,
)
```

The guarded backend is the lowest-friction integration path: your store keeps ownership of persistence, indexing, ranking, and hosting; CMGL owns governance decisions and receipts.

## Live Smoke

Offline CI must stay deterministic. Live smoke belongs on release/main branches with protected environment secrets:

```bash
uv run cmgl adapters doctor
uv run cmgl adapters live-smoke --target all --dry-run
uv run python scripts/live_adapter_smoke.py --target all
uv run python scripts/live_adapter_smoke.py --target all --require-live-env
```

Required environment:

| Target | Required live inputs |
| --- | --- |
| Mem0 | `OPENAI_API_KEY` or a Mem0-compatible provider configuration, plus `MEM0_TEST_USER_PREFIX` for isolated test users. |
| Graphiti | `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD`; Graphiti owns provider and graph setup. |
| LangMem | Installed `langmem` and `langgraph`; live smoke uses local `InMemoryStore` where possible. |
| LangGraph | Installed `langgraph`; live smoke uses local `InMemoryStore` and no model calls. |

Provider keys must come from the process environment or a secret manager. Do not put keys in `cmgl.toml`, ledgers, examples, fixtures, or issue reports.

Default behavior is skip-on-missing-provider-env. This keeps public release/main workflows usable before every optional live provider is configured. Use `--require-live-env` when your organization wants Mem0/Graphiti missing secrets to fail the live gate.

## Contract Guarantees

CMGL adapter shims guarantee only the local contract they implement:

- Core imports do not require optional adapter dependencies.
- Explicit dependency checks fail with `OptionalDependencyError` and both `pip` and `uv` install hints.
- Protected write/update/delete operations call external clients only after CMGL admits the local governance action.
- Missing authority produces a not-called adapter receipt or deterministic block.
- External persistence failure produces a failed adapter receipt and quarantine evidence, or raises `AdapterOperationError` when the caller opts into raising.
- Retrieval helpers normalize records into `MemoryEvent`, downgrade insufficiently sourced records unless `trusted_results=True`, and return reason-coded `RetrievalDecision` objects.

## Out Of Scope

CMGL does not provide cloud accounts, Neo4j instances, LLM providers, embedding providers, framework runtime orchestration, or external SDK compatibility certification. It does not guarantee that a backend has update/delete semantics; add-only backends can represent corrections through new records plus supersession or tombstone evidence.

## Version Drift Policy

The shims are tested against fake-client protocols and optional live-smoke workflows. External SDK minor releases may change method names, return shapes, or setup requirements. Run:

```bash
uv run cmgl adapters doctor --json
uv run cmgl adapters live-smoke --target all --dry-run --json
```

For production environments with configured secrets, run protected live smoke before release promotion. If an external SDK changes, prefer a small adapter compatibility patch rather than coupling CMGL core to that SDK.
