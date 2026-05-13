from __future__ import annotations

import json
from datetime import timedelta

from typer.testing import CliRunner

from cmgl.admission import candidate_from_event
from cmgl.audit import contamination_state_replay
from cmgl.authority import (
    authorize_bundle,
    make_authority_evidence_bundle,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.cli import app
from cmgl.compression import CompressionProbeSuite
from cmgl.digest import sha256_digest
from cmgl.layer import GovernanceLayer
from cmgl.ledger import AppendOnlyLedger, make_schema_migration_record
from cmgl.models import (
    AdmissionDecision,
    ContaminationContext,
    ContaminationLane,
    GovernanceProfile,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
    ObligationStatus,
    ProtectedAction,
    TelemetryEventType,
    TelemetryOutcomeStatus,
    WorkflowReportMode,
)
from cmgl.obligations import ObligationVerifier
from cmgl.pipeline import PromotionPipeline
from cmgl.policy import AdmissionPolicy
from cmgl.telemetry import make_telemetry_event
from cmgl.telemetry_replay import replay_telemetry_jsonl
from cmgl.time import now_utc
from cmgl.workflow import (
    certified_workflow_report_from_evidence,
    make_memory_governance_evidence_contract,
    make_report_term_binding,
    make_verification_witness,
    make_workflow_evidence_set,
)

runner = CliRunner()


def _event(
    *,
    memory_id: str = "mem-1",
    update_id: str = "update-1",
    status: MemoryStatus = MemoryStatus.CERTIFIED,
    event_type: MemoryEventType = MemoryEventType.MEMORY_WRITE,
) -> MemoryEvent:
    return MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent.local",
        backend="inmemory",
        event_type=event_type,
        memory_id=memory_id,
        memory_update_id=update_id,
        content="memory",
        content_digest=sha256_digest("memory"),
        lane=ContaminationLane.USER_CLAIM,
        provenance_depth=0,
        authority_scope="user:test",
        status=status,
        checker_version="test",
        created_at=now_utc(),
    )


def _bundle(action: ProtectedAction = ProtectedAction.PERSISTENT_MEMORY_WRITE):
    scope = make_declared_scope(
        actor="agent.local",
        authority_scope="user:test",
        permitted_actions=[action],
        expires_at=now_utc() + timedelta(minutes=5),
    )
    request = make_protected_action_request(
        action=action,
        actor="agent.local",
        authority_scope="user:test",
        source_record="structured scope",
        declared_scope=scope,
    )
    return authorize_bundle(request, declared_scope=scope)


def test_simple_promotion_is_not_strict_conformant(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    result = PromotionPipeline(ledger=ledger).promote(_event(), profile="simple")
    assert result.promotion_receipt.decision == AdmissionDecision.ADMIT

    graph = ObligationVerifier().verify(ledger)
    assert not graph.ok
    assert graph.reports[0].status == ObligationStatus.MISSING
    assert "promotion.input_set_manifest_missing" in graph.reports[0].reason_codes


def test_governance_layer_strict_write_creates_full_obligation_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    layer = GovernanceLayer(ledger=tmp_path / "ledger.jsonl", profile=GovernanceProfile.STRICT)
    result = layer.write_memory(
        "strict path memory",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:test",
        authority_bundle=_bundle(),
    )
    assert result.promotion_receipt.decision == AdmissionDecision.ADMIT

    graph = ObligationVerifier().verify(layer.ledger)
    assert graph.ok
    assert {report.status for report in graph.reports} == {ObligationStatus.SATISFIED}
    assert layer.conformance_report().ok
    assert layer.explain_memory(result.event.memory_id)


def test_validate_canonical_cli_and_schema_migration_prefix(tmp_path) -> None:  # type: ignore[no-untyped-def]
    canonical = runner.invoke(app, ["validate", "canonical", "--json"])
    assert canonical.exit_code == 0
    assert "canonical_json_golden_vectors" in canonical.output

    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    migration = make_schema_migration_record(
        from_schema_epoch="cmgl.schema.v1",
        to_schema_epoch="cmgl.schema.v1",
        migration_id="noop",
    )
    ledger.append("schema_migration_record", migration)
    assert ledger.verify_prefix().ok


def test_telemetry_state_replay_sorts_deduplicates_and_requires_declaration(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ref = candidate_from_event(_event()).event
    version_ref = ref.model_dump()
    memory_ref = {
        "schema_version": "cmgl.versioned_memory_ref.v1",
        "memory_id": version_ref["memory_id"],
        "memory_update_id": version_ref["memory_update_id"],
        "content_digest": version_ref["content_digest"],
        "status": "certified",
    }
    use_before_write = make_telemetry_event(
        event_type=TelemetryEventType.MEM_USE,
        collector_id="collector",
        collector_seq=2,
        event_id="use-1",
        memory_refs=[],
    ).model_dump(mode="json")
    use_before_write["memory_refs"] = [memory_ref]
    write = make_telemetry_event(
        event_type=TelemetryEventType.MEM_WRITE,
        collector_id="collector",
        collector_seq=1,
        event_id="write-1",
        memory_refs=[],
    ).model_dump(mode="json")
    write["memory_refs"] = [memory_ref]
    duplicate = dict(write)
    duplicate["collector_seq"] = 3
    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        "\n".join(json.dumps(item) for item in [use_before_write, duplicate, write]) + "\n",
        encoding="utf-8",
    )

    replay = replay_telemetry_jsonl(path, profile=GovernanceProfile.STRICT)
    statuses = [outcome.status for outcome in replay.outcomes]
    assert TelemetryOutcomeStatus.DEDUPLICATED in statuses
    assert replay.rational_metrics["read_use_uptake"].numerator == 1
    assert replay.profile_level == "P0"


def test_authority_evidence_bundle_retained_channel_blocks_policy() -> None:
    bundle = _bundle()
    evidence_bundle = make_authority_evidence_bundle(
        request=bundle.request,
        declared_scope=bundle.declared_scope,
        receipt=bundle.receipt,
        retained_authority_channels=["chat.approval"],
        retained_channel_blocking=True,
    )
    policy = AdmissionPolicy(
        require_authority_for_persistent_writes=True,
        require_authority_bundle=True,
    )
    receipt = policy.evaluate(
        candidate_from_event(_event()),
        authority_evidence_bundle=evidence_bundle,
    )
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "authority.retained_channel_blocking" in receipt.reason_codes


def test_typed_workflow_witnesses_and_bindings_required() -> None:
    evidence = make_workflow_evidence_set(
        workflow_id="wf",
        decisions=[AdmissionDecision.ADMIT, AdmissionDecision.BLOCK],
    )
    contract = make_memory_governance_evidence_contract(evidence)
    witness = make_verification_witness(
        witness_id="witness:1",
        accepted=True,
        evidence_ids=[evidence.evidence_digest],
    )
    incomplete = certified_workflow_report_from_evidence(
        evidence,
        contract=contract,
        witnesses=[witness],
        report_term_bindings=[],
    )
    assert incomplete.mode == WorkflowReportMode.DIAGNOSTIC_ONLY

    bindings = [
        make_report_term_binding(term=term, witness=witness, evidence_id=evidence.evidence_digest)
        for term in contract.report_terms
    ]
    certified = certified_workflow_report_from_evidence(
        evidence,
        contract=contract,
        witnesses=[witness],
        report_term_bindings=bindings,
    )
    assert certified.mode == WorkflowReportMode.CERTIFIED_LOWER_BOUND


def test_compression_and_contamination_replay_probe_contracts() -> None:
    suite = CompressionProbeSuite(
        source_digest_map={"mem-1": sha256_digest("source")},
        recoverability_probes={"probe": False},
        alias_hazards=["alias"],
        lost_uncertainties=["uncertainty"],
        lost_exceptions=[],
        lost_uncertainty_severity="high",
    )
    assert not suite.bridge_probe(["mem-1", "mem-2"]).passed
    assert not suite.gluing_probe().passed
    assert not suite.deployment_probe(recoverability_check="fail").passed

    shared = _event(memory_id="shared", status=MemoryStatus.CONTRADICTED)
    forked = shared.model_copy(
        update={
            "memory_id": "fork",
            "status": MemoryStatus.CERTIFIED,
            "content": {"forked_from": "shared"},
        }
    )
    replay = contamination_state_replay(
        [shared, forked],
        context=ContaminationContext(shared_memory_ids=["shared"]),
    )
    assert replay.contradiction_reserve == 1
    assert replay.realized_fork_count == 1
    assert replay.cross_agent_shared_memory_ids == ["shared"]


def test_open_challenge_and_absence_notice_block_strict_policy() -> None:
    from cmgl.absence import make_record_absence_notice
    from cmgl.challenge import make_memory_challenge_record
    from cmgl.models import AbsenceNoticeType, ChallengeStatus

    event = _event()
    policy = AdmissionPolicy()
    challenge = make_memory_challenge_record(
        memory_id=event.memory_id,
        status=ChallengeStatus.OPEN,
        reason_codes=["challenge.open"],
    )
    absence = make_record_absence_notice(
        notice_type=AbsenceNoticeType.MISSING_EVIDENCE,
        memory_id=event.memory_id,
    )
    receipt = policy.evaluate(
        candidate_from_event(event),
        challenge_records=[challenge],
        absence_notices=[absence],
    )
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "challenge.open" in receipt.reason_codes
    assert "absence.missing_evidence" in receipt.reason_codes
