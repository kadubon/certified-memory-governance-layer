# Proof Obligations

CMGL uses executable checks rather than a global theorem. The statements below describe the proof obligations an application must satisfy before treating a memory item as procedurally admissible.

## Strict Promotion Obligation

If:

- the ledger prefix verifies,
- the candidate, evidence manifest, replay evidence, and promotion receipt digests match,
- strict policy is used,
- the memory event has current `memory_id`, `memory_update_id`, and `content_digest` binding,
- no terminal status, open challenge, or blocking absence notice applies,
- blocked fact lanes are not being admitted as fact,
- the relevant rule IDs and reason codes are registered,
- protected writes have a valid `AuthorityBundle` or `AuthorityEvidenceBundle`,

then CMGL may call the memory procedurally admissible under that policy profile.

## Retrieval Obligation

If:

- each retrieved hit is normalized into a `MemoryEvent`,
- policy evaluation returns `admit` only for allowed statuses and lanes,
- every blocked hit carries reason codes,
- the admitted context digest is recomputed from admitted IDs and content digests,

then CMGL may construct a receipt-backed retrieval context for the agent runtime.

## Adapter Obligation

If:

- adapter modules import without optional SDKs,
- the user supplies the external client/tool/store object,
- protected operations are routed through `GovernanceLayer` or `GuardedMemoryBackend`,
- authority passes before the external callable is invoked,
- the adapter records success, not-called, failed, or compensated outcome,

then CMGL may bind a local memory event to an external backend reference. This does not prove the external backend stored, ranked, deleted, or served the record correctly beyond the returned client result.

## Non-Theorems

CMGL does not prove:

- factual truth,
- external backend correctness,
- prompt-injection immunity,
- distributed consensus,
- legal or compliance certification,
- future continued validity,
- universal compatibility with every version of an optional external SDK.
