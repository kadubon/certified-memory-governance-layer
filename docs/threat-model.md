# Threat Model

CMGL addresses procedural memory-governance failures in long-running agents.

## Covered risks

- Stale memory: records with expired `valid_to` are blocked.
- Contaminated summaries: summary and regenerated-summary lanes are separated from fact admission.
- Model inference stored as fact: model inference is blocked for fact admission by default.
- Malicious memory injection: strict default config requires authority bundles for protected persistent writes. Natural-language approval alone is blocked.
- Premature persistent writes: `GuardedMemoryBackend` invokes user-provided write/update/delete callables only after CMGL admits the protected memory action.
- Tombstoned memory reuse: tombstoned records are terminally blocked.
- Superseded or contradicted memory: terminal statuses block recall.
- Compression losing exceptions: compression certificates record coverage, recoverability, lost uncertainties, and lost exceptions.
- Ledger tampering: hash-chain verification detects payload or chain modification in local ledgers.
- Ledger anomaly response: failed prefix verification can be converted into a local quarantine record for audit.
- Stale/forked ledger writers: expected-prefix guarded append detects a writer that is not appending to the observed current prefix.
- Natural-language-only authorization: protected actions require a structured declared scope; free-text approval alone blocks.
- Receipt replay across versions: strict receipts are bound to `memory_update_id`, content digest, evidence manifest digest, and rule IDs.
- Superseded/deleted memory use after retrieval: version-bound telemetry can report stale, zombie, and superseded use.
- Shared-memory contamination: contamination audits apply lane risk weights and provenance-depth discounting.
- Supply-chain compromise: CI includes lint, tests, typing, pip-audit, CodeQL, and dependency review.
- Accidental secret publication: the security workflow and publishability script use high-confidence secret-shaped scans while excluding virtual environments, caches, build artifacts, and prose-heavy docs.

## Non-goals

CMGL does not prove factual truth, authenticate users, manage production signing keys, operate a distributed ledger, prevent all prompt injection, call LLMs, or replace backend access control. Optional local signing helpers are available through `cmgl[signing]`, but core governance does not depend on signatures. It does not run cloud services or hidden telemetry. Challenge and record-absence objects are audit records, not full standing-ledger or disclosure-governance subsystems. Drift certification remains future work rather than hidden behavior.
