# API Stability

CMGL follows semantic versioning for documented stable APIs beginning with `1.1.0`.
CMGL v1.1.2 preserves all documented v1.1.1 stable top-level imports.

## Stable API

The following top-level imports from `cmgl` are stable for the v1 line:

- `__version__`
- `GovernanceLayer`
- `GuardedMemoryBackend`
- `AdmissionPolicy`
- `AppendOnlyLedger`
- `LedgerVerificationResult`
- `RetrievalFilterResult`
- `ContaminationLane`
- `MemoryEvent`
- `MemoryCandidate`
- `MemoryStatus`
- `MemoryEventType`
- `AdmissionDecision`
- `BackendName`
- `ProtectedAction`
- `AuthorityBundle`
- `AuthorityEvidenceBundle`
- `AuthorityReceipt`
- `DeclaredScope`
- `ProtectedActionRequest`
- `GovernanceReceiptBundle`
- `PromotionReceipt`
- `RetrievalDecision`
- `authorize_bundle`
- `authorize_request`
- `make_declared_scope`
- `make_protected_action_request`
- `filter_retrieval`
- `sha256_digest`

Stable means these symbols remain importable and retain compatible behavior within v1. Breaking changes require a v2 release unless a security fix makes compatibility impossible.

The machine-readable list in `src/cmgl/stable_api.py` is the test source of
truth for the stable top-level import set. `cmgl.__all__` is intentionally
wider than the stable list for compatibility with earlier v1.1 releases. Those
additional top-level exports are compatibility-retained but should be treated as
provisional unless they are listed above.

## Provisional API

The following are usable but may evolve in minor releases with deprecation notes:

- Optional adapter classes under `cmgl.adapters.*`
- Typed contract modules under `cmgl.contracts.*`
- Telemetry replay helpers
- Compression audit helpers
- Workflow and contamination diagnostics
- Ledger signing helpers

Provisional APIs should remain source-compatible when practical, but external SDK drift may require adapter changes.

## Internal API

The following are internal unless separately documented:

- `cmgl.commands.*`
- private helper functions
- implementation details in `cmgl.adapters.binding`
- test fixtures and conformance fixture generation details

Internal APIs may change in minor releases.

## Deprecation Policy

For stable APIs, CMGL should:

1. Keep the old symbol available for at least one minor release when feasible.
2. Document the replacement in changelog or release notes.
3. Avoid silent behavior changes in strict admission, authority, ledger verification, and retrieval filtering.

Security fixes may tighten behavior without a long deprecation window when fail-open behavior would be unsafe.

## Claim Boundary

CMGL proves procedural memory admissibility under declared records, policies, receipts, and ledger verification. It does not prove factual truth, legal compliance, user authentication, or external backend correctness.
