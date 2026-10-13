---
name: certified-memory-governance-layer
description: "Govern persistent and retrieved AI-agent memory with CMGL authority bundles, contamination lanes, typed receipts, append-only ledgers, retrieval filtering, and Mem0/Graphiti/LangMem/LangGraph/custom adapters. Use for memory writes, updates, deletes, stale or contradicted retrieval, memory provenance, and memory authority. Do not use as a memory database, generic RAG/vector-search guide, or to claim stored content is factually true."
license: Apache-2.0
metadata:
  author: K. Takahashi
  repository: https://github.com/kadubon/certified-memory-governance-layer
  version: "1.0"
---

# Certified Memory Governance Layer

Separate procedural admission from factual truth at the boundary between an agent and its memory backend.

## Fast path

1. Identify backend, action (`write`, `update`, `delete`, or `retrieve`), actor, and scope.
2. Classify source status and contamination lane; retain stale, contradicted, and quarantined states.
3. Create or inspect an authority bundle for protected mutation.
4. Use the strict CMGL path and inspect its typed receipt.
5. Verify the append-only ledger and run strict conformance when the decision matters.
6. Report admit/block separately from any factual claim.

## When to use

Use for governed persistent memory or memory placed into agent context, including Mem0,
Graphiti, LangMem, LangGraph, and custom backends. For general verification evidence use
Verification Ecology Kit; for adaptive research systems use Audit-Closed AI Scientist; for
general agent-result checks use PIC; for benchmark fixtures use ATRB.

## Do not use

- Ordinary database design, generic vector search, generic RAG, or memory summarization.
- To explain a third-party memory framework without a governance task.
- To prove that a remembered statement is true, safe, or permissioned outside the declared scope.

## Workflow

Initialize and diagnose locally:

```text
uv run cmgl doctor --skip-ledger
uv run cmgl init
```

For a real persistent-memory mutation, build declared authority, then use `cmgl memory write`,
update, or delete with `--authority-bundle-json`; verify with `cmgl ledger verify` and
`cmgl conformance audit --profile strict --json`. Never use `--demo-local-authority` as production
authorization: it creates short-lived synthetic demo evidence only.

Use `GovernanceLayer` for typed local governance receipts. Use `GuardedMemoryBackend` to wrap
existing persistence callables. For an external backend, read
[backend routing](references/backend-routing.md) before selecting its adapter. On retrieval,
normalize/filter before constructing model context; never treat a retrieved record as factual merely
because it survived filtering.

## Evidence and result semantics

A receipt shows CMGL's declared procedure and decision. Ledger verification establishes the
checked ledger properties. `admit` is scope- and policy-relative procedural admissibility, not
truth, universal authority, or backend correctness. Read
[governance boundary](references/governance-boundary.md) for reporting language.

## Retrieve only what is needed

- Read `docs/api-stability.md` for supported public imports.
- Read `docs/backend-semantics.md` only for backend mutation/retrieval semantics.
- Read [backend routing](references/backend-routing.md) only for an external adapter.
- Read [governance boundary](references/governance-boundary.md) for claims or authority decisions.

## Validate

```text
uv run pytest
uv run cmgl doctor --skip-ledger
```

For an integration, retain the receipt and run the matching ledger/conformance command.

## Report

State outcome; action/backend; receipt and ledger evidence; remaining contamination, expiry, or
authority residuals; scope; non-claims; and the next safe action. Keep `admit`/`block` distinct
from factual truth.

## Required non-claims

- CMGL is not a memory database and does not own external framework accounts or topology.
- Procedural admissibility does not establish factual truth.
- A demo authority flag is never production authorization.
