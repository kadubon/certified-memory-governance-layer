from __future__ import annotations

from cmgl.digest import sha256_digest
from cmgl.models import MemoryStatus, SemanticRule

STATIC_RULES: tuple[tuple[str, str, str], ...] = (
    ("cmgl.rule.admission.passed", "Admission checks passed.", "admission"),
    ("cmgl.rule.version_binding.missing", "Memory is not bound to an update id.", "admission"),
    ("cmgl.rule.evidence_manifest.missing", "Evidence manifest is missing.", "admission"),
    (
        "cmgl.rule.evidence_manifest.mismatch",
        "Evidence manifest does not bind candidate.",
        "admission",
    ),
    (
        "cmgl.rule.lane.model_inference.blocked_as_fact",
        "Model inference is blocked as fact.",
        "admission",
    ),
    (
        "cmgl.rule.lane.regenerated_summary.blocked_as_fact",
        "Regenerated summary is blocked as fact.",
        "admission",
    ),
    (
        "cmgl.rule.lane.synthetic_eval.blocked_as_fact",
        "Synthetic eval is blocked as fact.",
        "admission",
    ),
    (
        "cmgl.rule.lane.summary.summary_not_fact",
        "Summary lane may not be admitted as fact.",
        "admission",
    ),
    ("cmgl.rule.provenance_depth.exceeded", "Provenance depth exceeds policy limit.", "admission"),
    ("cmgl.rule.valid_from.future", "Memory is not valid yet.", "admission"),
    ("cmgl.rule.valid_to.expired", "Memory validity has expired.", "admission"),
    ("cmgl.rule.source_event_hashes.missing", "Source event hashes are missing.", "admission"),
    ("cmgl.rule.candidate.contradicted", "Candidate is contradicted.", "admission"),
    ("cmgl.rule.candidate.tombstone_marker", "Candidate is a tombstone marker.", "admission"),
    ("cmgl.rule.authority.missing", "Required authority receipt is missing.", "authority"),
    ("cmgl.rule.authority.blocked", "Authority receipt blocks the action.", "authority"),
    ("cmgl.rule.authority.scope_mismatch", "Authority scope does not match request.", "authority"),
    ("cmgl.rule.authority.action_mismatch", "Authority action does not match event.", "authority"),
    (
        "cmgl.rule.authority.strict_verification_failed",
        "Strict authority receipt verification failed.",
        "authority",
    ),
    ("cmgl.rule.authority.scope_allowed", "Legacy authority scope was allowed.", "authority"),
    ("cmgl.rule.authority.scope_denied", "Legacy authority scope was denied.", "authority"),
    ("cmgl.rule.authority.declared_scope_missing", "Declared scope is missing.", "authority"),
    (
        "cmgl.rule.authority.natural_language_not_authorization",
        "Free text is not authorization.",
        "authority",
    ),
    (
        "cmgl.rule.authority.declared_scope_digest_mismatch",
        "Declared scope digest mismatch.",
        "authority",
    ),
    ("cmgl.rule.authority.actor_mismatch", "Authority actor mismatch.", "authority"),
    (
        "cmgl.rule.authority.action_not_permitted",
        "Action is not permitted by declared scope.",
        "authority",
    ),
    ("cmgl.rule.authority.scope_expired", "Declared scope has expired.", "authority"),
    (
        "cmgl.rule.authority.resource_not_permitted",
        "Resource is outside declared scope.",
        "authority",
    ),
    (
        "cmgl.rule.authority.scoped_authorizing",
        "Structured scope authorizes the action.",
        "authority",
    ),
    (
        "cmgl.rule.authority.legacy_receipt_not_strict",
        "Legacy authority receipt is not strict.",
        "authority",
    ),
    (
        "cmgl.rule.authority.request_digest_missing",
        "Authority request digest is missing.",
        "authority",
    ),
    (
        "cmgl.rule.authority.request_digest_mismatch",
        "Authority receipt request digest does not match request.",
        "authority",
    ),
    (
        "cmgl.rule.authority.bundle_missing",
        "Strict authority profile requires an authority bundle.",
        "authority",
    ),
    (
        "cmgl.rule.authority.retained_channel_blocking",
        "Retained authority channel blocks a protected memory action.",
        "authority",
    ),
    ("cmgl.rule.receipt.candidate_id_mismatch", "Receipt candidate id mismatch.", "receipt"),
    ("cmgl.rule.receipt.memory_id_mismatch", "Receipt memory id mismatch.", "receipt"),
    ("cmgl.rule.receipt.memory_update_id_mismatch", "Receipt memory update mismatch.", "receipt"),
    ("cmgl.rule.receipt.not_current_update", "Receipt is not for current update.", "receipt"),
    ("cmgl.rule.receipt.content_digest_mismatch", "Receipt content digest mismatch.", "receipt"),
    ("cmgl.rule.receipt.evidence_manifest_digest_mismatch", "Evidence digest mismatch.", "receipt"),
    ("cmgl.rule.receipt.rule_ids_missing", "Receipt has no rule ids.", "receipt"),
    ("cmgl.rule.receipt.unknown_rule_id", "Receipt refers to an unknown rule id.", "receipt"),
    (
        "cmgl.rule.receipt.unknown_reason_code",
        "Receipt includes an unknown reason code.",
        "receipt",
    ),
    (
        "cmgl.rule.promotion.input_set_manifest_missing",
        "Strict promotion requires an input-set manifest.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.input_set_candidate_mismatch",
        "Input-set manifest candidate does not match promotion candidate.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.input_set_update_mismatch",
        "Input-set manifest update does not match promotion candidate.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.input_set_content_digest_mismatch",
        "Input-set manifest content digest does not match promotion candidate.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.input_set_candidate_digest_mismatch",
        "Input-set manifest candidate digest does not match.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.replay_evidence_missing",
        "Strict promotion requires replay evidence.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.replay_input_set_mismatch",
        "Replay evidence is not bound to the input-set manifest.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.replay_digest_mismatch",
        "Replay evidence digest does not match input-set replay digest.",
        "promotion",
    ),
    ("cmgl.rule.promotion.replay_rejected", "Replay evidence rejected promotion.", "promotion"),
    (
        "cmgl.rule.promotion.shadow_receipt_missing",
        "Strict promotion verification requires a shadow receipt.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.shadow_candidate_mismatch",
        "Shadow receipt candidate does not match promotion candidate.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.shadow_update_mismatch",
        "Shadow receipt update does not match promotion candidate.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.active_receipt_missing",
        "Strict promotion verification requires an active promotion receipt.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.active_candidate_mismatch",
        "Active promotion receipt candidate does not match promotion candidate.",
        "promotion",
    ),
    (
        "cmgl.rule.promotion.active_source_receipt_mismatch",
        "Active promotion receipt is not bound to the promotion receipt.",
        "promotion",
    ),
    ("cmgl.rule.telemetry.stale_use_detected", "Telemetry shows stale memory use.", "telemetry"),
    (
        "cmgl.rule.telemetry.zombie_use_detected",
        "Telemetry shows tombstoned memory use.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.superseded_use_detected",
        "Telemetry shows superseded memory use.",
        "telemetry",
    ),
    ("cmgl.rule.telemetry.duplicate_event_id", "Telemetry event id is duplicated.", "telemetry"),
    (
        "cmgl.rule.telemetry.ordering_violation",
        "Telemetry collector order is invalid.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.skew_budget_exceeded",
        "Telemetry skew budget was exceeded.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.correction_latency_observed",
        "Correction latency was measured.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.verify_deadline_missed",
        "Verification deadline was missed.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.event_invalid",
        "Telemetry event failed structural validation.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.version_binding_missing",
        "Telemetry reference is missing version binding.",
        "telemetry",
    ),
    ("cmgl.rule.telemetry.event_deduplicated", "Telemetry event was deduplicated.", "telemetry"),
    ("cmgl.rule.telemetry.event_downgraded", "Telemetry event was downgraded.", "telemetry"),
    (
        "cmgl.rule.telemetry.stale_exposure_detected",
        "Telemetry shows stale exposure.",
        "telemetry",
    ),
    ("cmgl.rule.telemetry.zombie_delay_detected", "Telemetry shows zombie delay.", "telemetry"),
    (
        "cmgl.rule.telemetry.supersedence_delay_detected",
        "Telemetry shows supersedence delay.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.verified_write_fraction_observed",
        "Verified write fraction was measured.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.missing_declaration",
        "Telemetry read/use/verify/correct/delete occurred before declaration or write.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.version_mismatch",
        "Telemetry reference does not match current declared memory version.",
        "telemetry",
    ),
    (
        "cmgl.rule.telemetry.risk_exposure_detected",
        "Telemetry replay measured risk exposure.",
        "telemetry",
    ),
    ("cmgl.rule.ledger_prefix_valid", "Ledger line prefix is valid.", "ledger"),
    ("cmgl.rule.legacy_prefix_unrecorded", "Ledger line predates explicit prefix hash.", "ledger"),
    ("cmgl.rule.rejected_payload_hash_mismatch", "Payload hash mismatch.", "ledger"),
    ("cmgl.rule.quarantined_hash_chain_mismatch", "Hash chain mismatch.", "ledger"),
    ("cmgl.rule.rejected_append_index_mismatch", "Append index mismatch.", "ledger"),
    ("cmgl.rule.rejected_canonical_hash_mismatch", "Canonical record hash mismatch.", "ledger"),
    ("cmgl.rule.rejected_ledger_profile_mismatch", "Ledger profile mismatch.", "ledger"),
    ("cmgl.rule.rejected_schema_epoch_mismatch", "Schema epoch mismatch.", "ledger"),
    ("cmgl.rule.rejected_policy_epoch_mismatch", "Policy epoch mismatch.", "ledger"),
    ("cmgl.rule.stale_or_forked_ledger_prefix", "Ledger prefix hash mismatch.", "ledger"),
    ("cmgl.rule.duplicate_payload", "Duplicate ledger payload identity.", "ledger"),
    (
        "cmgl.rule.schema_migration_recorded",
        "Ledger schema migration record is present.",
        "ledger",
    ),
    (
        "cmgl.rule.duplicate_policy_recorded",
        "Ledger duplicate policy receipt is present.",
        "ledger",
    ),
    ("cmgl.rule.validation.schema_missing", "Validation could not resolve schema.", "validation"),
    ("cmgl.rule.validation.schema_invalid", "Record failed schema validation.", "validation"),
    ("cmgl.rule.validation.rule_invalid", "Record failed semantic rule validation.", "validation"),
    ("cmgl.rule.validation.canonical_valid", "Canonical JSON golden vector passed.", "validation"),
    (
        "cmgl.rule.validation.canonical_mismatch",
        "Canonical JSON golden vector failed.",
        "validation",
    ),
    (
        "cmgl.rule.compression.source_digest_missing",
        "Source digest map does not cover all sources.",
        "compression",
    ),
    (
        "cmgl.rule.compression.probe_failed",
        "Compression recoverability probe failed.",
        "compression",
    ),
    ("cmgl.rule.compression.alias_hazard", "Compression has alias hazards.", "compression"),
    (
        "cmgl.rule.compression.high_uncertainty_loss",
        "Compression lost high-severity uncertainty.",
        "compression",
    ),
    (
        "cmgl.rule.compression.declared_state_failure",
        "Compression does not preserve declared state.",
        "compression",
    ),
    (
        "cmgl.rule.compression.accountability_state_failure",
        "Compression does not preserve accountability state.",
        "compression",
    ),
    ("cmgl.rule.compression.bridge_failure", "Compression bridge check failed.", "compression"),
    ("cmgl.rule.compression.gluing_failure", "Compression gluing check failed.", "compression"),
    (
        "cmgl.rule.compression.deployment_failure",
        "Compression is not deployable as exact recovery.",
        "compression",
    ),
    (
        "cmgl.rule.contamination.cross_agent_share",
        "Cross-agent shared memory was explicit.",
        "contamination",
    ),
    (
        "cmgl.rule.contamination.positive_excursion",
        "Contamination risk excursion was observed.",
        "contamination",
    ),
    (
        "cmgl.rule.contamination.low_reserve_residence",
        "Contamination replay spent time with low contradiction reserve.",
        "contamination",
    ),
    ("cmgl.rule.contamination.fork_count", "Contamination replay counted forks.", "contamination"),
    (
        "cmgl.rule.contamination.post_fork_recovery",
        "Contamination replay measured post-fork recovery quality.",
        "contamination",
    ),
    ("cmgl.rule.workflow.contract_missing", "Workflow evidence contract is missing.", "workflow"),
    (
        "cmgl.rule.workflow.report_terms_missing",
        "Workflow evidence contract does not bind required report terms.",
        "workflow",
    ),
    (
        "cmgl.rule.workflow.witness_missing",
        "Certified workflow lower-bound report requires accepted witnesses.",
        "workflow",
    ),
    (
        "cmgl.rule.workflow.report_term_binding_missing",
        "Certified workflow report requires accepted report-term bindings.",
        "workflow",
    ),
    (
        "cmgl.rule.workflow.witness_not_accepted",
        "Workflow witness was present but not accepted.",
        "workflow",
    ),
    ("cmgl.rule.conformance.ledger_invalid", "Ledger conformance check failed.", "conformance"),
    (
        "cmgl.rule.conformance.obligation_unsatisfied",
        "A conformance receipt obligation is unsatisfied.",
        "conformance",
    ),
    (
        "cmgl.rule.conformance.obligation_missing",
        "A required evidence obligation is missing.",
        "conformance",
    ),
    (
        "cmgl.rule.conformance.obligation_mismatched",
        "A required evidence obligation is mismatched.",
        "conformance",
    ),
    ("cmgl.rule.challenge.open", "Memory challenge remains open.", "challenge"),
    ("cmgl.rule.challenge.resolved", "Memory challenge is resolved.", "challenge"),
    ("cmgl.rule.absence.missing_source", "A required source record is absent.", "absence"),
    ("cmgl.rule.absence.missing_evidence", "A required evidence record is absent.", "absence"),
    ("cmgl.rule.absence.disclosure_update", "Later disclosure updated absence state.", "absence"),
    ("cmgl.rule.adapter.external_not_called", "External adapter store was not called.", "adapter"),
    (
        "cmgl.rule.adapter.external_write_succeeded",
        "External adapter write succeeded and was bound to CMGL memory.",
        "adapter",
    ),
    (
        "cmgl.rule.adapter.external_update_succeeded",
        "External adapter update succeeded and was bound to CMGL memory.",
        "adapter",
    ),
    (
        "cmgl.rule.adapter.external_delete_succeeded",
        "External adapter delete succeeded and was bound to CMGL memory.",
        "adapter",
    ),
    (
        "cmgl.rule.adapter.external_retrieve_succeeded",
        "External adapter retrieval succeeded and was normalized for policy filtering.",
        "adapter",
    ),
    (
        "cmgl.rule.adapter.external_persistence_failed",
        "External adapter persistence failed after CMGL admission.",
        "adapter",
    ),
    (
        "cmgl.rule.adapter.external_reference_unbound",
        "Adapter update/delete lacked a prior CMGL-to-external binding.",
        "adapter",
    ),
    (
        "cmgl.rule.adapter.external_reference_bound",
        "Adapter operation had a prior CMGL-to-external binding.",
        "adapter",
    ),
    (
        "cmgl.rule.adapter.external_compensated",
        "External adapter operation was compensated after failure.",
        "adapter",
    ),
)


def _dynamic_rules() -> list[tuple[str, str, str]]:
    from cmgl.transitions import ALLOWED_TRANSITIONS

    rules: list[tuple[str, str, str]] = []
    for status in MemoryStatus:
        rules.append(
            (
                f"cmgl.rule.status.{status.value}.blocked",
                f"Memory status {status.value!r} is blocked by policy.",
                "admission",
            )
        )
        rules.append(
            (
                f"cmgl.rule.terminal_status.{status.value}",
                f"Memory status {status.value!r} is terminal.",
                "admission",
            )
        )
        rules.append(
            (
                f"cmgl.rule.transition.terminal.{status.value}",
                f"Cannot transition from terminal status {status.value!r}.",
                "lifecycle",
            )
        )
    for from_status in MemoryStatus:
        for to_status in MemoryStatus:
            if to_status not in ALLOWED_TRANSITIONS[from_status]:
                rules.append(
                    (
                        f"cmgl.rule.transition.{from_status.value}_to_{to_status.value}.blocked",
                        f"Transition from {from_status.value!r} to {to_status.value!r} is blocked.",
                        "lifecycle",
                    )
                )
    return rules


def semantic_rules() -> list[SemanticRule]:
    result: list[SemanticRule] = []
    for rule_id, description, applies_to in [*STATIC_RULES, *_dynamic_rules()]:
        body = {
            "schema_version": "cmgl.semantic_rule.v1",
            "rule_id": rule_id,
            "description": description,
            "applies_to": applies_to,
            "fail_closed": True,
        }
        result.append(SemanticRule(**body, rule_digest=sha256_digest(body)))
    return result


def rule_id_for_code(code: str) -> str:
    return code if code.startswith("cmgl.rule.") else f"cmgl.rule.{code}"


def known_rule_ids() -> set[str]:
    return {rule.rule_id for rule in semantic_rules()}


def unknown_rule_ids(rule_ids: list[str]) -> list[str]:
    known = known_rule_ids()
    return sorted(rule_id for rule_id in rule_ids if rule_id not in known)


def unknown_reason_codes(reason_codes: list[str]) -> list[str]:
    known = known_rule_ids()
    return sorted(code for code in reason_codes if rule_id_for_code(code) not in known)
