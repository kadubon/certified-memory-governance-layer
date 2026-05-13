# Operations

This page describes the local operational checks a maintainer or application team should run before using CMGL in a production agent deployment.

## Authority Bundles

Strict protected memory writes require a structured `AuthorityBundle`. Natural-language approval alone is not authorization.

```bash
uv run cmgl authority bundle create \
  --action persistent_memory_write \
  --actor agent.local \
  --scope user:demo \
  --source-record "structured local scope" \
  --out /tmp/cmgl-authority.json
```

Use the bundle when writing memory:

```bash
uv run cmgl memory write \
  --ledger .cmgl/ledger.jsonl \
  --content "User prefers morning meetings." \
  --lane user_claim \
  --scope user:demo \
  --authority-bundle-json /tmp/cmgl-authority.json \
  --json
```

`--demo-local-authority` is only for local demos. It creates explicitly labeled synthetic evidence and should not be used as a production authorization source.

## Retrieval Filtering

Applications should retrieve raw hits from their memory backend, normalize them into `MemoryEvent` objects, and call `GovernanceLayer.filter_retrieval` before building agent context.

```python
filtered = layer.filter_retrieval("meeting preference", raw_memory_events)
context = [event.content for event in filtered.admitted_events]
```

Terminal, stale, unauthorized, contradicted, tombstoned, quarantined, and non-current memory versions are blocked with machine-readable reason codes.

## Telemetry Replay

MemoryFlow-style telemetry JSONL can be replayed locally:

```bash
uv run cmgl telemetry replay examples/conformance/telemetry_replay.valid.jsonl \
  --profile strict \
  --json
```

Strict replay checks duplicate event IDs, collector ordering, skew budget, version binding, declaration-before-use, stale exposure, zombie exposure, supersedence exposure, correction latency, and verified write fraction.

## Ledger Verification

Verify the ledger prefix before trusting receipts:

```bash
uv run cmgl ledger verify --ledger .cmgl/ledger.jsonl --receipt-json
uv run cmgl conformance audit --ledger .cmgl/ledger.jsonl --profile strict --json
```

Prefix integrity confirms append-only ordering and digest binding. Conformance audit checks whether the ledger contains the evidence obligations required for the selected profile.

If `cmgl doctor` fails because a developer has an ignored local `.cmgl/ledger.jsonl`, run one of:

```bash
uv run cmgl doctor --skip-ledger
uv run cmgl doctor --ledger /path/to/intended/ledger.jsonl
```

Use `--skip-ledger` only for package smoke checks. For an application deployment, verify the actual ledger path used by the agent.

## Adapter Operation Failures

Supported adapters emit `AdapterOperationReceipt` for write/update/delete paths:

- `not_called`: CMGL blocked the action before the external store was invoked.
- `succeeded`: the external store call completed and was bound to a CMGL memory/update ID.
- `failed`: CMGL admitted the action, but the external store raised an exception.
- `compensated`: reserved for applications that perform and record a compensating action.

On external failure, treat the quarantine record as an operational incident. The usual response is:

1. Stop using the affected memory ID for context construction.
2. Verify the CMGL ledger prefix.
3. Inspect the failed adapter receipt and external backend logs.
4. Retry through a new authority bundle if the original authority has expired.
5. Record a correction, tombstone, or migration note when the backend state diverged from CMGL evidence.

## Authority Expiry

Strict authority scopes may expire. If a write unexpectedly blocks:

```bash
uv run cmgl authority check \
  --action persistent_memory_write \
  --actor agent.local \
  --scope user:demo \
  --source-record "structured local scope" \
  --json
```

Create a new authority bundle rather than editing old receipts.

## Live Adapter Gate

PR CI should remain offline. Release/main live CI should run:

```bash
uv run cmgl adapters doctor
uv run python scripts/live_adapter_smoke.py --target all
```

Missing live secrets should fail the release/main live gate with actionable output. Fork PRs should not receive provider secrets.

## Release Smoke Testing

Before publishing a release:

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
uv run cmgl schema export /tmp/cmgl-schemas
uv run python -m build
uv run python scripts/check_publishability.py
uv run pip-audit
```

`scripts/check_publishability.py` verifies version consistency, deleted internal-file hygiene, secret-shaped values, workflow safety, build artifact versions, wheel import, doctor, and schema export.
