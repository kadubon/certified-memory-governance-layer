# CMGL

Certified Memory Governance Layer for long-running AI agents. Current public API status: `1.1.1`.

CMGL is a local Python governance layer that sits between an agent runtime and a memory backend. It is not a memory database. It decides whether a memory item is procedurally admissible, records evidence in an append-only ledger, and explains every admit/block decision with typed receipts.

The project is designed for agent systems that already use Mem0, Graphiti, LangMem, LangGraph, or a custom store and need a deterministic control point before memory is written or placed into model context.

## What CMGL Can Do

- Normalize backend-specific memory records into `MemoryEvent`.
- Guard persistent memory writes, updates, and deletes with structured authority bundles.
- Block stale, superseded, tombstoned, contradicted, quarantined, contaminated, or unauthorized memory.
- Keep model inference, regenerated summaries, and synthetic evaluation data out of factual memory by default.
- Record canonical JSON and `sha256:<hex>` digests in an append-only JSONL ledger.
- Emit receipts for promotion, authority, retrieval filtering, adapter operations, telemetry replay, ledger integrity, compression, and conformance.
- Run core checks locally without LLM calls, cloud services, hidden telemetry, or API keys.

CMGL proves procedural admissibility under declared policies, evidence, receipts, and ledger verification. It does not prove that a remembered statement is factually true.

## Install And Release Status

CMGL v1.1.1 is available on PyPI.

```bash
uv add cmgl
```

For development from GitHub source:

```bash
uv add "cmgl @ git+https://github.com/kadubon/certified-memory-governance-layer.git"
```

For local development from a clone:

```bash
uv sync --all-extras --dev
uv run cmgl version
uv run cmgl doctor --skip-ledger
```

Release checklist documents are retained as historical/internal maintenance records. See `docs/release-v1.1.0-checklist.md`.

## 10-Minute Offline Integration

Initialize a local ledger and schemas:

```bash
uv run cmgl init
```

Create structured authority and write memory through the strict path:

```bash
uv run cmgl authority bundle create \
  --action persistent_memory_write \
  --actor agent.local \
  --scope user:demo \
  --source-record "structured local scope" \
  --out /tmp/cmgl-authority.json

uv run cmgl memory write \
  --ledger .cmgl/ledger.jsonl \
  --content "User prefers morning meetings." \
  --lane user_claim \
  --scope user:demo \
  --authority-bundle-json /tmp/cmgl-authority.json \
  --json
```

Verify the result:

```bash
uv run cmgl ledger verify --ledger .cmgl/ledger.jsonl --receipt-json
uv run cmgl conformance audit --ledger .cmgl/ledger.jsonl --profile strict --json
```

For a local demo only, `cmgl memory write --demo-local-authority` creates short-lived synthetic authority evidence. Do not use that flag as production authorization.

## Python API

Use `GovernanceLayer` when you want typed local receipts and a stable integration surface.

```python
from datetime import timedelta

from cmgl import (
    ContaminationLane,
    GovernanceLayer,
    ProtectedAction,
    authorize_bundle,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.time import now_utc

layer = GovernanceLayer(ledger=".cmgl/ledger.jsonl", profile="strict")

scope = make_declared_scope(
    actor="agent.local",
    authority_scope="user:demo",
    permitted_actions=[ProtectedAction.PERSISTENT_MEMORY_WRITE],
    expires_at=now_utc() + timedelta(minutes=10),
)
request = make_protected_action_request(
    action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
    actor="agent.local",
    authority_scope="user:demo",
    source_record="structured local authority scope",
    declared_scope=scope,
)
authority = authorize_bundle(request, declared_scope=scope)

bundle = layer.write_memory_bundle(
    "User prefers morning meetings.",
    lane=ContaminationLane.USER_CLAIM,
    authority_scope="user:demo",
    authority_bundle=authority,
)

assert bundle.decision.value == "admit"
assert layer.verify_ledger().ok
```

`GovernanceReceiptBundle` is the recommended public result object. It contains the event, candidate, evidence, promotion receipt, ledger append receipts, optional adapter operation receipt, conformance status, and canonical digest.

The stable public API is documented in `docs/api-stability.md`. Top-level imports from `cmgl` are stable when listed there; deeper modules under `cmgl.contracts.*`, `cmgl.commands.*`, and adapter implementation helpers are more specialized and may evolve with deprecation notes.

## Custom Backend Guard

Use `GuardedMemoryBackend` when you already have persistence callables.

```python
from cmgl import ContaminationLane, GuardedMemoryBackend

persisted = []

def persist_write(content, *, lane, authority_scope, metadata=None):
    persisted.append({"content": content, "scope": authority_scope})
    return persisted[-1]

guarded = GuardedMemoryBackend(write=persist_write)

result = guarded.write_memory(
    "User prefers morning meetings.",
    lane=ContaminationLane.USER_CLAIM,
    authority_scope="user:demo",
)

assert result.decision.value == "block"
assert persisted == []
```

## Adapter Status

Adapters are supported safe integration shims. They work with user-supplied clients, import optional dependencies lazily, and keep external framework setup application-owned.

| Target | Status | What CMGL owns |
| --- | --- | --- |
| Mem0 | Supported shim | Guard `add`/`update`/`delete`, bind returned IDs, normalize `search`/`get`/`get_all`, filter retrieval. |
| Graphiti | Supported async shim | Guard `add_episode`, bind episode/search IDs, normalize `search` and `search_`, filter graph results. |
| LangMem | Supported shim | Guard manage-memory tool calls, support sync and async tools, bind tool result IDs, filter search-memory output. |
| LangGraph | Supported helper | Filter retrieved `MemoryEvent` lists and store-shaped items before context construction. |
| Custom backend | Supported | Use `GovernanceLayer` or `GuardedMemoryBackend`. |

External records without explicit status or source evidence are downgraded before policy filtering unless you opt into `trusted_results=True`.

Adapter support means stable shim behavior, fake-client tests, optional dependency isolation, and optional live-smoke support. It does not mean CMGL owns cloud accounts, Neo4j, LLM providers, framework graph topology, or every external SDK version.

## Adapter Examples

Mem0:

```python
from cmgl.adapters.mem0 import Mem0Adapter

adapter = Mem0Adapter(mem0_client, authority_scope="user:demo")

bundle = adapter.add(
    "User prefers morning meetings.",
    authority_bundle=authority,
)

assert bundle.adapter_operation_receipt is not None
print(bundle.adapter_operation_receipt.external_ref.external_id)

filtered = adapter.filter_search("meeting preference", limit=10)
context_ids = filtered.decision.admitted_memory_ids
```

Graphiti:

```python
from cmgl.adapters.graphiti import GraphitiAdapter

adapter = GraphitiAdapter(graphiti_client, authority_scope="user:demo")

await adapter.add_episode(
    name="preference-update",
    episode_body="User now prefers afternoon meetings.",
    source_description="user correction in session 42",
    authority_bundle=authority,
)

filtered = await adapter.filter_search("meeting preference")
```

LangMem:

```python
from cmgl.adapters.langmem import LangMemAdapter

adapter = LangMemAdapter(authority_scope="user:demo")

adapter.manage_memory(
    "create",
    content="User prefers concise summaries.",
    manage_tool=manage_memory_tool,
    authority_bundle=authority,
)
filtered = adapter.filter_search("summary preference", search_tool=search_memory_tool)
```

LangGraph:

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

## Live Adapter Setup

Offline tests use fake clients. Release/main live smoke is separate and should run only in a protected GitHub Environment.

```bash
uv run cmgl adapters doctor
uv run cmgl adapters live-smoke --target all --dry-run
uv run python scripts/live_adapter_smoke.py --target all
```

Live smoke requirements:

- Mem0: `cmgl[mem0]`, provider environment required by Mem0, and an isolated `MEM0_TEST_USER_PREFIX`.
- Graphiti: `cmgl[graphiti]`, Neo4j connection (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`), and provider environment required by Graphiti.
- LangMem: `cmgl[langmem]` and local LangGraph `InMemoryStore` for smoke.
- LangGraph: `cmgl[langgraph]` and local store/state helpers.

When provider secrets are absent, `scripts/live_adapter_smoke.py --target all` skips provider-backed Mem0/Graphiti calls and still runs local LangMem/LangGraph smoke. Add `--require-live-env` when a protected release gate must fail on missing provider configuration.

See `docs/adapters.md` and `docs/live-ci.md` for full live setup.

## Operational Commands

```bash
uv run cmgl validate canonical
uv run cmgl schema export /tmp/cmgl-schemas
uv run cmgl validate ledger examples/conformance/strict_ledger.valid.jsonl
uv run cmgl telemetry replay examples/conformance/telemetry_replay.valid.jsonl --profile strict --json
uv run python examples/governance_layer_demo.py
uv run python examples/strict_authority_demo.py
uv run python examples/ledger_receipt_demo.py
```

Useful commands:

- `cmgl init [path]`
- `cmgl memory write`
- `cmgl retrieve filter`
- `cmgl ledger verify`
- `cmgl validate record|ledger|canonical`
- `cmgl telemetry ingest|replay`
- `cmgl conformance audit|explain`
- `cmgl doctor --skip-ledger`
- `cmgl adapters doctor`
- `cmgl adapters live-smoke`

## Production Readiness Checklist

- Use strict `GovernanceLayer` defaults.
- Store authority as `AuthorityBundle` or `AuthorityEvidenceBundle`, not free text.
- Keep provider keys in environment variables or secret managers, never in ledgers, docs, fixtures, or issue reports.
- Run `cmgl ledger verify` and `cmgl conformance audit` in CI or deployment checks.
- Treat failed adapter operation receipts as incidents for the external memory backend.
- Quarantine broken ledgers before reusing them in agent context construction.
- Keep live adapter CI on protected release/main branches, not fork PRs.
- Review optional dependency licenses and external service terms before commercial deployment.

## Security Model

CMGL is local-first and deterministic. Core tests and examples do not use network services, paid APIs, LLM providers, private datasets, cookies, tokens, or hidden telemetry.

Controls include:

- Canonical JSON and SHA-256 digests.
- Append-only JSONL ledger with prefix verification.
- Structured authority bundles for protected actions.
- Natural-language-only authorization rejection.
- Fail-closed receipt and semantic-rule validation.
- Adapter operation receipts that record whether the external store was not called, succeeded, failed, or was compensated.
- Optional signing extra isolated from the core install.
- PyPI Trusted Publishing / OIDC in the publish workflow.

## Failure Modes

- Missing authority: protected writes block and external adapters are not called.
- External persistence failure: CMGL records a failed adapter operation receipt and a quarantine record.
- Unbound external update/delete: adapters block by default unless you explicitly allow migration mode.
- Broken ledger prefix: verification fails; do not use the ledger for context construction until investigated.
- Expired authority scope: strict protected actions block.
- Framework API drift: optional adapters isolate external API changes; core CMGL remains local and deterministic.

## Limits

CMGL does not provide:

- Factual-truth guarantees.
- A memory database, vector store, hosted service, dashboard, or LLM provider wrapper.
- Legal, compliance, or safety certification.
- Autonomous external actions.
- Deep ownership of Mem0, Graphiti, LangMem, LangGraph, Letta, Cognee, or MemOS deployment.
- A full implementation of the author's prior research repositories.

CMGL implements a bounded executable subset: OAWM-style admissibility, MemoryFlow-style telemetry replay, OASG-style ledgers, no-meta-authority protected-action gates, CWC-style lower-bound reporting, semantic compression certificates, and SEC-style contamination lanes. See `docs/reference-mapping.md`.

## CI Recipe

```bash
uv lock
uv sync --locked --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=cmgl
uv run cmgl doctor --skip-ledger
uv run cmgl adapters doctor
uv run cmgl adapters live-smoke --target all --dry-run
uv run cmgl validate canonical
uv run python -m build
uv run python scripts/check_publishability.py
uv run pip-audit
```

Release preparation also requires:

```bash
uv build
uv run python scripts/check_publishability.py
```

## License

Apache-2.0. Optional adapter targets are not vendored; review optional dependency licenses and service terms before deploying them.
