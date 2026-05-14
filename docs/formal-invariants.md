# Formal Invariants

CMGL is a local governance layer for procedural memory admissibility. The invariants below describe what the implementation checks under supported profiles. They are not claims of factual truth, legal certification, prompt-injection immunity, distributed consensus, or external backend correctness.

## 1. Canonicalization Determinism

For supported JSON-like values, Pydantic models, datetimes, enums, and nested containers, `canonical_json(x)` produces a deterministic UTF-8 JSON string with sorted keys and no insignificant whitespace. `sha256_digest(canonical_json(x))` is stable across calls for the same supported value. CMGL relies on normal SHA-256 collision-resistance assumptions; it does not prove collisions impossible.

## 2. Ledger Prefix Preservation

Append-only ledger records form a hash chain. Each record binds payload digest, previous record digest, append index, record digest, and ledger prefix metadata. Verification fails when a payload, previous digest, record digest, append index, schema/policy epoch, or prefix hash is tampered with. Expected-prefix guarded append rejects stale or forked writers when the supplied prefix differs from the current ledger prefix.

## 3. Terminal Status Absorption

`superseded`, `contradicted`, `tombstoned`, and `quarantined` records are never admitted into factual context under strict policy. Adding terminal evidence is monotonic with respect to blocking: terminal evidence must not turn a blocked factual record into an admitted one.

## 4. Version Binding

Strict admission requires candidate, receipt, and evidence paths to bind `memory_id`, `memory_update_id`, and `content_digest`. A receipt or evidence manifest for one update does not authorize a different update.

## 5. Authority Non-Bypass

Protected persistent writes, updates, deletes, tombstones, imports, exports, and related memory actions require structured authority. A free-text or natural-language approval field is not authorization. User-supplied persistence callables and external adapter clients must not be invoked before structured authority passes.

## 6. Fact-Lane Monotonicity

`model_inference`, `regenerated_summary`, and `synthetic_eval` lanes are blocked for fact admission by default. `summary` memory may be retrievable as summary evidence, but it is not promoted to fact merely because it is retrievable.

## 7. Retrieval Explainability

Every blocked retrieval hit includes at least one reason code. Every admitted retrieval context includes a `context_digest` bound to the admitted memory IDs and content digests.

## 8. Compression Non-Confusion

Compression certificates may support `admit_as_summary_not_fact`. They must not silently convert summary memory into factual memory. Lost uncertainty and lost exceptions remain auditable fields.

## 9. Adapter Isolation

Missing optional adapter dependencies do not break core imports. Missing dependencies raise `OptionalDependencyError` at explicit adapter dependency boundaries with install hints. Failed external persistence produces a failed adapter operation receipt or deterministic block; CMGL does not report silent success.

## 10. Drift And Continued-Validity Boundary

Admission is not permanent truth. Continued validity must be represented through `valid_to`, supersession, tombstone, telemetry, challenge, absence notice, or later lifecycle evidence. CMGL does not infer future validity without explicit records.
