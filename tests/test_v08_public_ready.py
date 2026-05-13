from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from typer.testing import CliRunner

from cmgl import (
    AdmissionDecision,
    ContaminationLane,
    GovernanceLayer,
    GovernanceReceiptBundle,
    GuardedMemoryBackend,
    ProtectedAction,
    authorize_bundle,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.canonical import canonical_json
from cmgl.cli import app
from cmgl.digest import sha256_digest
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import MemoryEvent, MemoryEventType, MemoryStatus
from cmgl.time import now_utc

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]


def _authority_bundle(scope: str = "user:test"):
    declared_scope = make_declared_scope(
        actor="agent.local",
        authority_scope=scope,
        permitted_actions=[ProtectedAction.PERSISTENT_MEMORY_WRITE],
        expires_at=now_utc() + timedelta(minutes=5),
    )
    request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent.local",
        authority_scope=scope,
        source_record="structured local test scope",
        declared_scope=declared_scope,
    )
    return authorize_bundle(request, declared_scope=declared_scope)


def test_deleted_public_hygiene_files_are_absent_and_not_referenced() -> None:
    deleted = {
        f"{stem}{suffix}"
        for stem, suffix in [
            ("AGENTS", ".md"),
            ("CONTRIBUTING", ".md"),
            ("NOT" + "ICE", ""),
            ("PLAN", ".md"),
        ]
    }
    for name in deleted:
        assert not (ROOT / name).exists()

    checked_paths = [
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        ROOT / "CODE_OF_CONDUCT.md",
        ROOT / "DEPENDENCIES.md",
        ROOT / "THIRD_PARTY_NOTICES.md",
        ROOT / "pyproject.toml",
        *list((ROOT / "docs").glob("*.md")),
    ]
    for path in checked_paths:
        text = path.read_text(encoding="utf-8")
        for name in deleted - {"NOT" + "ICE"}:
            assert name not in text


def test_authority_bundle_cli_feeds_strict_memory_write(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = tmp_path / "ledger.jsonl"
    authority_path = tmp_path / "authority.json"
    create = runner.invoke(
        app,
        [
            "authority",
            "bundle",
            "create",
            "--action",
            "persistent_memory_write",
            "--actor",
            "agent.local",
            "--scope",
            "user:test",
            "--source-record",
            "structured local test scope",
            "--out",
            str(authority_path),
        ],
    )
    assert create.exit_code == 0

    write = runner.invoke(
        app,
        [
            "memory",
            "write",
            "--ledger",
            str(ledger),
            "--content",
            "User prefers morning meetings.",
            "--lane",
            "user_claim",
            "--scope",
            "user:test",
            "--authority-bundle-json",
            str(authority_path),
            "--json",
        ],
    )
    assert write.exit_code == 0, write.output
    payload = json.loads(write.output)
    assert payload["schema_version"] == "cmgl.governance_receipt_bundle.v1"
    assert payload["decision"] == "admit"
    assert payload["conformance_ok"] is True

    conformance = runner.invoke(
        app,
        ["conformance", "audit", "--ledger", str(ledger), "--profile", "strict", "--json"],
    )
    assert conformance.exit_code == 0
    assert json.loads(conformance.output)["ok"] is True


def test_demo_local_authority_is_explicit_demo_evidence(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = tmp_path / "ledger.jsonl"
    result = runner.invoke(
        app,
        [
            "memory",
            "write",
            "--ledger",
            str(ledger),
            "--content",
            "Local demo memory.",
            "--lane",
            "user_claim",
            "--scope",
            "user:demo",
            "--demo-local-authority",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["decision"] == "admit"
    authority_records = [
        record.payload
        for record in AppendOnlyLedger(ledger).iter_records()
        if record.record_type == "authority_evidence_bundle"
    ]
    assert authority_records
    assert "demo local authority" in authority_records[0]["request"]["source_record"]


def test_guarded_memory_backend_blocks_before_persistent_callable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    persisted: list[object] = []

    def persist_write(
        content: object,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, object] | None = None,
    ) -> object:
        del lane, metadata
        item = {"content": content, "scope": authority_scope}
        persisted.append(item)
        return item

    guarded = GuardedMemoryBackend(
        layer=GovernanceLayer(ledger=tmp_path / "ledger.jsonl"),
        write=persist_write,
    )
    blocked = guarded.write_memory(
        "blocked without authority",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:test",
    )
    assert blocked.decision == AdmissionDecision.BLOCK
    assert persisted == []

    admitted = guarded.write_memory(
        "admitted with authority",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:test",
        authority_bundle=_authority_bundle(),
    )
    assert admitted.decision == AdmissionDecision.ADMIT
    assert len(persisted) == 1
    assert admitted.backend_result_digest is not None


def test_governance_receipt_bundle_is_canonical_and_serializable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    layer = GovernanceLayer(ledger=tmp_path / "ledger.jsonl")
    bundle = layer.write_memory_bundle(
        "canonical bundle",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:test",
        authority_bundle=_authority_bundle(),
    )
    assert isinstance(bundle, GovernanceReceiptBundle)
    assert bundle.decision == AdmissionDecision.ADMIT
    assert canonical_json(bundle) == canonical_json(
        GovernanceReceiptBundle.model_validate_json(bundle.model_dump_json())
    )


def test_guarded_retrieval_filters_terminal_events(tmp_path) -> None:  # type: ignore[no-untyped-def]
    event = MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent.local",
        backend="custom",
        event_type=MemoryEventType.MEMORY_WRITE,
        memory_id="mem-1",
        memory_update_id="update-1",
        content="old memory",
        content_digest=sha256_digest("old memory"),
        lane=ContaminationLane.USER_CLAIM,
        provenance_depth=0,
        authority_scope="user:test",
        status=MemoryStatus.TOMBSTONED,
        checker_version="test",
        created_at=now_utc(),
    )
    guarded = GuardedMemoryBackend(
        layer=GovernanceLayer(ledger=tmp_path / "ledger.jsonl"),
        retrieve=lambda query, *, limit=10: [event],
    )
    result = guarded.filter_retrieval("old")
    assert result.decision.admitted_hits == 0
    assert result.decision.blocked_hits[0]["memory_id"] == "mem-1"
