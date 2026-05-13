# Reference Mapping

CMGL is an independent Apache-2.0 memory governance package. It does not vendor,
import, or mechanically copy code from the author's prior repositories. The
mapping below states what CMGL implements, what remains a bounded executable
subset, and what is intentionally omitted so users do not mistake CMGL for a
merged research monolith.

| Reference | CMGL mapping | Status | Commercial implication |
| --- | --- | --- | --- |
| `observable-agent-workflow-memory` | Memory states, candidates, promotion receipts, admissible retrieval, supersession, tombstone, contradiction blocking, current update binding | Executable subset | CMGL governs whether memory may enter context. It does not create OAWM `WorkflowContract` capability memory or run the OAWM plugin/checker runtime. |
| `memoryflow-agent-memory-auditor` | Version-bound telemetry ingest/replay, stale/zombie/superseded use metrics, exact rational exposure metrics | Executable subset | CMGL can audit memory-use streams locally. Full MOS_DECLARE/read-cap/VUF/PUF compatibility remains future optional work. |
| `oasg` | Canonical JSON, SHA-256 digests, append-only JSONL ledger, prefix verification, schema migration records, duplicate-policy receipts, shadow/lease/rollback/quarantine concepts | Executable subset | CMGL gives local ledger evidence and conformance checks. It is not a distributed witness runner. |
| `no-meta-authority-runtime` | Protected-action requests, declared scopes, authority bundles, natural-language-is-not-authorization, retained-channel blocking | Executable subset | Strict protected memory writes require structured authority. CMGL does not provide a general-purpose authority runtime for non-memory actions. |
| `certified-workflow-conversion` | Evidence-bound workflow bottleneck reports and typed report-term witnesses | Executable subset | CMGL can produce diagnostic or certified lower-bound memory-governance reports when evidence bindings exist. It is not the full CWC claim compiler. |
| `semantic-translation-contracts-poc` | Compression certificates, summary-vs-fact separation, source coverage, alias hazard, bridge/gluing/deployment probes | Executable subset | CMGL can reject unsafe memory compression before promotion. It is not a complete semantic translation proof system. |
| `sovereign-epistemic-commons-poc` | Contamination lanes, provenance-depth discount, shared-memory explicit context, contradiction reserve, fork/recovery metrics | Executable subset | CMGL can diagnose shared-memory contamination when context is explicit. It is not a full multi-agent commons simulator. |
| `agent-lifecycle-certification-poc` | Drift/reset/fork stress ideas | Intentionally omitted | CMGL keeps only deterministic fixtures and metrics relevant to memory governance. |
| `search-stability-lab` | Finite-context stability and alias-hazard ideas | Bounded subset | Alias hazards are surfaced in compression and telemetry diagnostics; no search simulator is included. |
| `cimt-kernel` | Schema-first deterministic kernel, typed affordances, receipt obligations | Executable subset | CMGL exposes contracts under `cmgl.contracts.*` and keeps `cmgl.models` as a compatibility facade. |
| `cait-certificate-schema` | `schema_index.json`, `semantic_rules.json`, local fail-closed validation | Implemented | `cmgl schema export` and `cmgl validate` support portable local validation. |
| `no-meta-standing-ledger` | Challenge/standing concepts | Bounded audit object | `MemoryChallengeRecord` can block strict retrieval/admission, but CMGL is not a standing-ledger system. |
| `record-absence-poc` | Missing-record/disclosure governance | Bounded audit object | `RecordAbsenceNotice` can block strict admission when required evidence is absent. |

The required synthesis remains bounded:

OAWM admissibility + MemoryFlow telemetry audit + OASG ledger/trial/rollback +
no-meta-authority protected-action gates + CWC bottleneck reporting + semantic
compression certificates + SEC contamination lanes.

CMGL's public claim is procedural: the ledger and receipts satisfy CMGL's
declared evidence obligations under a selected profile. This is not a claim of
factual truth, complete reference-project equivalence, or legal certification.
