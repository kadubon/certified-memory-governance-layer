# Architecture

CMGL sits between an agent runtime and one or more memory backends.

```text
Agent runtime
  |
  | memory write/read/update/retrieve
  v
CMGL governance layer
  |-- normalize MemoryEvent
  |-- append evidence to JSONL ledger
  |-- evaluate MemoryCandidate
  |-- emit PromotionReceipt / RetrievalDecision / AdapterOperationReceipt
  |-- block stale, contaminated, unauthorized, or terminal records
  v
Memory backend
  |-- InMemory for local tests
  |-- optional adapters for Mem0, Graphiti, LangMem, LangGraph
```

CMGL does not replace memory storage. It provides a deterministic admission and retrieval filter that can be placed before persistent writes and before retrieved records are inserted into an agent context.

The core is local and infrastructure-free. It uses canonical JSON, SHA-256 digests, append-only JSONL records, evidence manifests, version-bound receipts, and deterministic policy checks. Optional framework integrations are protocol-oriented safe shims around user-supplied clients. They fail clearly when dependencies are not installed and keep external service setup outside CMGL. When an adapter calls an external store, CMGL records whether the call was skipped, succeeded, failed, or compensated and binds successful external IDs back to CMGL memory/update IDs.

Most integrations should start with `cmgl.layer.GovernanceLayer`. It is a
small facade over the lower-level modules: backend normalization, promotion
pipeline, strict policy, append-only ledger, current-version retrieval, and
audit helpers remain separately importable and replaceable.

For existing stores, `cmgl.guarded.GuardedMemoryBackend` wraps user-provided
write, update, delete, and retrieve callables. Persistent write/update/delete
callables are invoked only after CMGL admits the protected action, so the common
integration path does not require implementing a full backend class first.

Public schemas are organized under `cmgl.contracts.*`. The older `cmgl.models`
import path is kept as a facade so downstream code can migrate gradually. CLI
subcommands are similarly split under `cmgl.commands.*`, with `cmgl.cli:app`
remaining the installed entry point.

Local configuration is loaded with `cmgl.config`. `cmgl init` creates
`.cmgl/config.toml`; the default profile is strict and requires structured
authority bundles for protected persistent writes. A bundle is a
`ProtectedActionRequest`, `DeclaredScope`, and `AuthorityReceipt` bound by
digests. This keeps the public API usable without hiding the underlying receipt
and policy objects.

## Strict admission flow

```text
MemoryEvent
  -> VersionedMemoryRef(memory_id, memory_update_id, content_digest)
  -> MemoryCandidate
  -> EvidenceManifest
  -> InputSetManifest + ReplayEvidence
  -> ShadowTrialReceipt
  -> ActivePromotionReceipt
  -> AuthorityBundle for protected persistent writes
  -> AdmissionPolicy
  -> PromotionReceipt(bound to update id, content digest, evidence digest, rule ids)
  -> PromotionVerifier before context admission
```

New CMGL-generated memory writes include `memory_update_id`. Strict policy paths block candidates that are not bound to a concrete memory update or evidence manifest. This binding is procedural: it proves the receipt applies to the current record version, not that the memory content is true.

`CurrentMemoryView` reconstructs the latest retrievable update from append-only
events while preserving superseded, tombstoned, contradicted, and quarantined
versions for audit. This is the OAWM-style current-state view without turning
CMGL into a memory database.

## Ledger profile

The JSONL ledger keeps the simple local storage model but records OASG-inspired fields:

- `append_index`
- `ledger_profile`
- `schema_epoch`
- `policy_epoch`
- `ledger_prefix_hash`
- line-level verification statuses
- duplicate payload detection
- expected-prefix guarded append for stale/forked writers

Older ledger records remain readable; missing prefix fields are reported as legacy prefix metadata.

`append_with_receipt` can persist `LedgerAppendReceipt` records beside payload
records. `integrity_receipt` emits a `LedgerIntegrityReceipt`, and failed prefix
verification can be converted into a local `QuarantineRecord`. Optional Ed25519
signing helpers live in `cmgl.ledger_signing` and require `cmgl[signing]`; core
tests and runtime do not require cryptography.

## Related author projects

CMGL extracts design patterns from the author's prior repositories without vendoring code:

- [observable-agent-workflow-memory](https://github.com/kadubon/observable-agent-workflow-memory): admissibility lifecycle, promotion receipts, admissible retrieval, supersession, tombstone, contradiction handling.
- [memoryflow-agent-memory-auditor](https://github.com/kadubon/memoryflow-agent-memory-auditor): version-bound telemetry and stale/deleted/superseded memory-use audits.
- [oasg](https://github.com/kadubon/oasg): canonical JSON, SHA-256 records, append-only ledgers, prefix verification, shadow/lease/rollback/quarantine concepts.
- [no-meta-authority-runtime](https://github.com/kadubon/no-meta-authority-runtime): protected-action gates, declared scopes, and the rule that natural language alone is not authorization.
- [certified-workflow-conversion](https://github.com/kadubon/certified-workflow-conversion): workflow bottleneck diagnostics and evidence-bound lower-bound reporting.
- [semantic-translation-contracts-poc](https://github.com/kadubon/semantic-translation-contracts-poc): compression certificates, summary-vs-fact separation, recoverability and accountability checks.
- [sovereign-epistemic-commons-poc](https://github.com/kadubon/sovereign-epistemic-commons-poc): contamination lanes, provenance-depth discount, and shared-memory contamination governance.

See `docs/reference-mapping.md` for the detailed mapping matrix.

`cmgl conformance audit` reports CMGL's executable subset against these
lineages. A passing conformance report means the local CMGL ledger and receipts
meet CMGL's declared procedural rules; it is not a claim of full equivalence to
the referenced systems.

## Ledger-wide obligations

The obligation verifier runs over the JSONL ledger. It scans actual records,
not only ledger integrity, and checks whether admitted promotion receipts have
the expected candidate, evidence manifest, input-set manifest, replay evidence,
shadow receipt, active-promotion receipt, current update binding, known rules,
and structured authority bundle when the action is protected.

Profiles are explicit:

- `strict`: missing, stale, mismatched, or unknown obligations fail closed.
- `operational`: deterministic but incomplete evidence can be downgraded.
- `legacy`: best-effort reporting for older ledgers.

Use:

```bash
uv run cmgl conformance audit --ledger .cmgl/ledger.jsonl --profile strict --json
uv run cmgl conformance explain --ledger .cmgl/ledger.jsonl --memory-id mem-0001 --json
uv run cmgl receipt obligations --ledger .cmgl/ledger.jsonl --receipt-digest sha256:...
```
