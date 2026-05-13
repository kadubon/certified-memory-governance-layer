# CMGL Conformance Fixtures

These local fixtures are intentionally small and synthetic. They exercise
portable CMGL invariants without external services:

- `memory_event.valid.json`: a structurally valid memory event.
- `ledger.valid.jsonl`: a one-record append-only ledger with matching payload,
  record, and prefix hashes.
- `authority_bundle.valid.json`: structured protected-action authority for a
  persistent memory write.
- `strict_ledger.valid.jsonl`: a strict ledger produced by `GovernanceLayer`
  with authority, evidence, shadow, active promotion, and append receipts.
- `simple_ledger.nonconformant.jsonl`: a deliberately simple ledger that
  remains readable but does not satisfy strict promotion obligations.
- `telemetry_replay.valid.jsonl`: deterministic telemetry replay fixture.

Smoke commands:

```bash
uv run cmgl validate record examples/conformance/memory_event.valid.json
uv run cmgl validate ledger examples/conformance/ledger.valid.jsonl
uv run cmgl validate ledger examples/conformance/strict_ledger.valid.jsonl
uv run cmgl conformance audit --ledger examples/conformance/strict_ledger.valid.jsonl --profile strict --json
uv run cmgl telemetry replay examples/conformance/telemetry_replay.valid.jsonl --profile strict --json
```
