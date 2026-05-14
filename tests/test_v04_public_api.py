from __future__ import annotations

import subprocess
import sys
from datetime import timedelta

import pytest
from typer.testing import CliRunner

from cmgl import __version__
from cmgl.authority import (
    authorize_bundle,
    make_authority_receipt,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.backends.inmemory import InMemoryBackend
from cmgl.cli import app
from cmgl.config import load_config, write_default_config
from cmgl.current import resolve_current_events
from cmgl.layer import GovernanceLayer
from cmgl.ledger import AppendOnlyLedger
from cmgl.ledger_signing import (
    generate_private_key_pem,
    public_key_pem_from_private_key,
    sign_record,
    verify_record_signature,
)
from cmgl.models import AdmissionDecision, ContaminationLane, ProtectedAction
from cmgl.pipeline import PromotionPipeline
from cmgl.stress import shared_memory_stress_fixture
from cmgl.time import now_utc

runner = CliRunner()


def _authority_bundle(
    *,
    action: ProtectedAction = ProtectedAction.PERSISTENT_MEMORY_WRITE,
    scope_name: str = "user:demo",
):
    scope = make_declared_scope(
        actor="agent.local",
        authority_scope=scope_name,
        permitted_actions=[action],
        expires_at=now_utc() + timedelta(days=1),
    )
    request = make_protected_action_request(
        action=action,
        actor="agent.local",
        authority_scope=scope_name,
        source_record="structured local test scope",
        declared_scope=scope,
    )
    return authorize_bundle(request, declared_scope=scope)


def test_version_bumped_for_v1() -> None:
    assert __version__ == "1.1.2"


def test_config_loading_defaults_and_invalid_rejection(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert load_config(cwd=tmp_path).policy.require_authority_for_persistent_writes

    config_path = write_default_config(tmp_path / ".cmgl" / "config.toml")
    loaded = load_config(cwd=tmp_path)
    assert loaded.ledger.persist_append_receipts
    assert loaded.policy.strict_authority_verification
    assert loaded.authority.reject_legacy_receipts
    assert config_path.exists()

    bad = tmp_path / "cmgl.toml"
    bad.write_text("[policy]\nunknown = true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid CMGL config"):
        load_config(cwd=tmp_path)


def test_governance_layer_write_update_delete_and_filter(tmp_path) -> None:  # type: ignore[no-untyped-def]
    layer = GovernanceLayer(ledger=tmp_path / "ledger.jsonl")

    write_result = layer.write_memory(
        "I prefer morning meetings",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:demo",
        authority_bundle=_authority_bundle(action=ProtectedAction.PERSISTENT_MEMORY_WRITE),
    )
    assert write_result.promotion_receipt.decision == AdmissionDecision.ADMIT
    memory_id = write_result.event.memory_id

    update_result = layer.update_memory(
        memory_id,
        "I prefer afternoon meetings",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:demo",
        authority_bundle=_authority_bundle(action=ProtectedAction.PERSISTENT_MEMORY_UPDATE),
    )
    assert update_result.promotion_receipt.decision == AdmissionDecision.ADMIT

    retrieval = layer.filter_retrieval("meetings")
    assert retrieval.decision.admitted_memory_ids == [memory_id]
    assert retrieval.admitted_events[0].content == "I prefer afternoon meetings"

    delete_result = layer.delete_memory(
        memory_id,
        reason="user requested deletion",
        authority_bundle=_authority_bundle(action=ProtectedAction.MEMORY_TOMBSTONE),
    )
    assert delete_result.promotion_receipt.decision == AdmissionDecision.BLOCK
    assert "status.tombstoned.blocked" in delete_result.promotion_receipt.reason_codes
    assert layer.verify_ledger().ok
    assert layer.audit().telemetry.telemetry_events == 0


def test_legacy_authority_receipt_fails_strict_protected_write(tmp_path) -> None:  # type: ignore[no-untyped-def]
    layer = GovernanceLayer(ledger=tmp_path / "ledger.jsonl")
    with pytest.warns(DeprecationWarning):
        legacy = make_authority_receipt(
            action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
            actor="agent.local",
            authority_scope="user:demo",
            source_record="legacy approval",
        )

    result = layer.write_memory(
        "legacy write attempt",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:demo",
        authority_receipt=legacy,
    )
    assert result.promotion_receipt.decision == AdmissionDecision.BLOCK
    assert "authority.strict_verification_failed" in result.promotion_receipt.reason_codes
    assert result.quarantine_record is not None


def test_promotion_pipeline_persists_append_receipts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    backend = InMemoryBackend()
    event = backend.write(
        "pipeline memory",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:demo",
    )
    pipeline = PromotionPipeline(
        ledger=AppendOnlyLedger(tmp_path / "ledger.jsonl"),
        persist_append_receipts=True,
    )
    result = pipeline.promote(event)
    assert result.evidence_manifest is not None
    assert result.append_receipts
    record_types = [record.record_type for record in pipeline.ledger.iter_records()]
    assert "ledger_append_receipt" in record_types


def test_current_resolver_filters_superseded_versions() -> None:
    backend = InMemoryBackend()
    first = backend.write(
        "morning",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:demo",
    )
    second = backend.update(
        first.memory_id,
        "afternoon",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:demo",
    )
    current = resolve_current_events(backend.retrieve("", limit=10))
    audit = resolve_current_events(backend.retrieve("", limit=10), include_audit=True)
    assert [event.memory_update_id for event in current] == [second.memory_update_id]
    assert len(audit) == 2


def test_ledger_append_receipt_cli_and_quarantine(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger_path = tmp_path / "ledger.jsonl"
    append_result = runner.invoke(
        app,
        [
            "ledger",
            "append",
            "--ledger",
            str(ledger_path),
            "--type",
            "test",
            "--json",
            '{"a": 1}',
            "--receipt-json",
        ],
    )
    assert append_result.exit_code == 0
    assert "ledger_append_receipt" in append_result.output

    ledger_path.write_text(
        ledger_path.read_text(encoding="utf-8").replace('"a":1', '"a":2'),
        encoding="utf-8",
    )
    quarantine = AppendOnlyLedger(ledger_path).quarantine_failed_verification()
    assert quarantine is not None
    assert quarantine.target_type == "ledger_verification"


def test_optional_ledger_signing_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("cryptography")
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    record = ledger.append("test", {"a": 1})
    private_key = generate_private_key_pem()
    public_key = public_key_pem_from_private_key(private_key)
    signature = sign_record(record, private_key)
    assert verify_record_signature(record, signature, public_key)
    tampered = record.model_copy(update={"payload": {"a": 2}})
    assert not verify_record_signature(tampered, signature, public_key)


def test_shared_memory_stress_fixture_is_explicit_context_only() -> None:
    fixture = shared_memory_stress_fixture()
    assert fixture.report.cross_agent_shared_memory_ids == ["shared-memory-0001"]
    assert fixture.report.discounted_risk_score > 0


def test_new_examples_run() -> None:
    for example in [
        "examples/governance_layer_demo.py",
        "examples/strict_authority_demo.py",
        "examples/ledger_receipt_demo.py",
    ]:
        result = subprocess.run(
            [sys.executable, example],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
