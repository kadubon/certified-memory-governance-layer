# Schemas

Export schemas with:

```bash
uv run cmgl schema export ./schemas
```

Schema objects:

- `MemoryEvent`: normalized memory evidence from a backend or agent runtime.
- `MemoryCandidate`: a memory event prepared for policy admission.
- `PromotionReceipt`: deterministic policy result for a candidate.
- `RetrievalDecision`: admitted and blocked retrieval hits for a query.
- `AuthorityReceipt`: authorization record for protected actions.
- `AuthorityBundle`: strict protected-action bundle containing a request, declared scope, and receipt.
- `AuthorityEvidenceBundle`: authority bundle plus retained-channel assessment for strict memory actions.
- `CompressionCertificate`: compression-loss and recoverability record.
- `CompressionAuditReport`: declared-state, accountability-state, deployable recovery, and failure-class audit for a compression certificate.
- `CompressionBridgeProbe`, `CompressionGluingProbe`, and `CompressionDeploymentProbe`: typed pre-certificate probes for coverage, alias/uncertainty gluing, and deployability.
- `VersionedMemoryRef`: stable memory id plus update id plus content digest.
- `CurrentMemoryView` and `MemoryStateSnapshot`: current-version reconstruction from append-only memory events.
- `EvidenceManifest`: candidate-bound evidence used for promotion.
- `InputSetManifest`, `ReplayEvidence`, and `PromotionEvidenceBundle`: strict promotion inputs and bundled evidence for receipt-backed shadow and active promotion.
- `GovernanceReceiptBundle`: recommended high-level integration result containing the event, candidate, evidence, promotion receipt, append receipts, decision, and conformance status.
- `ExternalMemoryRef`: binding between a CMGL memory/update ID and an external backend record ID/update ID.
- `AdapterOperationReceipt`: external adapter operation evidence recording not-called, succeeded, failed, or compensated status.
- `MemoryRevision`: lifecycle transition record.
- `MemoryTelemetryEvent`: version-bound memory telemetry event.
- `TelemetryIngestResult`, `TelemetryLineDiagnostic`, and `TelemetryEventOutcome`: JSONL ingest diagnostics for duplicate IDs, order, skew, version binding, invalid lines, deduplication, rejection, and downgrade outcomes.
- `TelemetryWritePayload`, `TelemetryReplacePayload`, `TelemetryDeletePayload`, `TelemetryReadUsePayload`, `TelemetryVerifyPayload`, `TelemetryCorrectPayload`, and `TelemetryRetrievePayload`: typed MemoryFlow-style payload contracts for telemetry events.
- `TelemetryAuditReport`: typed telemetry audit output with stale, zombie, superseded, ordering, skew, correction-latency, deadline, and uptake metrics.
- `TelemetryReplayReport`: deterministic replay output over telemetry events and replay metrics.
- `TelemetryStateReplay` and `RationalValue`: MemoryFlow-style state replay with sorted deduplication, declaration/version checks, profile levels, and exact rational exposure metrics.
- `MetricResult`: audit metric with valid/degraded/not-computable style status.
- `LedgerAppendReceipt`, `LedgerIntegrityReceipt`, `LedgerLineStatus`, `SchemaMigrationRecord`, and `DuplicatePolicyReceipt`: append, verification, schema migration, duplicate policy, and typed line-status records.
- `DeclaredScope` and `ProtectedActionRequest`: structured authority inputs.
- `ShadowTrialReceipt`, `LeaseReceipt`, `ActivePromotionReceipt`, `RollbackSnapshot`, `RollbackReceipt`, `QuarantineRecord`: local lifecycle receipts.
- `WorkflowEvidenceSet`, `MemoryGovernanceEvidenceContract`, `VerificationWitness`, `ReportTermBinding`, and `WorkflowBottleneckReport`: evidence-bound lower-bound workflow report inputs and outputs.
- `ContaminationAuditReport`: lane risk, provenance discount, and cross-agent contamination report.
- `ContaminationStateReplay`: ordered contamination replay for contradiction reserve, positive excursion, low-reserve residence, fork count, and post-fork recovery quality.
- `EvidenceBindingReport`, `ObligationGraph`, `ConformanceFinding`, `ReceiptObligation`, and `ConformanceReport`: local reference-theory conformance and ledger-wide obligation audit objects.
- `MemoryChallengeRecord`: audit-only challenge record for disputed memory standing.
- `RecordAbsenceNotice`: audit/block evidence for missing source, missing evidence, or disclosure update.
- `SemanticRule`: fail-closed local rule descriptor.

Schemas are generated from Pydantic v2 models and are intended for tests, audits, and integration contracts.

The canonical contract modules live under `cmgl.contracts.*`. The historical
`cmgl.models` module remains as a compatibility facade for downstream users.
Configuration models live in `cmgl.config` because they describe local runtime
policy rather than ledger evidence.

The export command also writes:

- `schema_index.json`: stable index from schema names to exported files.
- `semantic_rules.json`: local fail-closed rule IDs from `cmgl.rules`, used by admission, receipt verification, telemetry, ledger, compression, and authority checks.

Portable validation commands:

```bash
uv run cmgl validate record examples/conformance/memory_event.valid.json
uv run cmgl validate ledger examples/conformance/ledger.valid.jsonl
uv run cmgl validate canonical
```

These files are generated locally. They are not copied from CAIT or other reference repositories.
