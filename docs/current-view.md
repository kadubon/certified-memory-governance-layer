# Current Memory View

`CurrentMemoryView` is a deterministic reconstruction over append-only memory events. It is a retrieval-governance helper, not a storage engine and not storage truth.

## Rules

- The latest certified/admissible update for a `memory_id` is the current retrievable update.
- Terminal statuses (`superseded`, `contradicted`, `tombstoned`, `quarantined`) block factual retrieval while remaining audit-visible.
- Older versions remain available for audit, explanation, and conformance review.
- Strict current-view construction from a ledger requires a verified ledger prefix. Broken or unverifiable ledgers should be treated as diagnostic input, not certified state.

## Why This Matters

Long-running agents often retrieve stale or superseded memory from backend search results. CMGL separates raw retrieval from admitted retrieval by reconstructing the current view and then applying admission policy with reason-coded receipts.
