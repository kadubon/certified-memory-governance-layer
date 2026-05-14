# Backend Semantics

CMGL is not a memory database. It models memory governance over events and receipts, then lets applications choose the storage backend. Different backends expose different mutation semantics; CMGL represents those differences without requiring a common database model.

| Backend class | Representation |
| --- | --- |
| Append-only / add-only backend | A correction is a new `memory_update_id` and a supersession or tombstone record. The old record remains audit-visible. |
| Update-capable backend | CMGL still records a new update event and binds it to the backend update result. In-place mutation is treated as an external storage detail. |
| Delete-capable backend | Delete calls are protected actions. CMGL records a tombstone/delete event and adapter operation receipt before relying on backend behavior. |
| Tombstone-only backend | Deletion is represented as a terminal `tombstoned` event. Retrieval policy blocks it while retaining audit evidence. |
| Temporal graph backend | Validity windows map to `valid_from` / `valid_to`; episodes and facts map to source evidence and provenance metadata. |
| Tool/store-shaped backend | Tool or store outputs are normalized into `MemoryEvent` objects before filtering. CMGL does not own graph topology or runtime execution. |

## Field Mapping

- `memory_id`: stable application or backend identity when available; otherwise a deterministic local digest-based identity.
- `memory_update_id`: update/revision/version identity when available; add-only corrections create a new update ID.
- `supersession`: represented by terminal status, candidate metadata, or revision records; older updates remain audit-visible.
- `tombstone`: represented by terminal `tombstoned` status and protected-action authority.
- `valid_from` / `valid_to`: temporal validity boundaries when supplied by the backend or source evidence.
- `source_event_hashes`: source payload, episode, tool, or observation digests used for procedural evidence.
- `external backend ref`: recorded through `ExternalMemoryRef` and `AdapterOperationReceipt` after successful external persistence.
- `retrieval normalization`: external records without explicit status or source evidence are downgraded before policy filtering unless `trusted_results=True` is explicitly selected.

## Mem0 ADD-Only Compatibility

CMGL does not require overwrite semantics. For accumulation-oriented memory stores, represent a correction as a new certified memory plus supersession or tombstone metadata for the older update. Retrieval filtering then admits only the current certified update and blocks the older update for factual context.
