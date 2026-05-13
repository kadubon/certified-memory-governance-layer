from __future__ import annotations

from typer.testing import CliRunner

from cmgl.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "cmgl" in result.output


def test_cli_init_schema_export_and_ledger_verify(tmp_path) -> None:  # type: ignore[no-untyped-def]
    init_result = runner.invoke(app, ["init", str(tmp_path)])
    assert init_result.exit_code == 0
    ledger = tmp_path / ".cmgl" / "ledger.jsonl"
    assert ledger.exists()

    schema_dir = tmp_path / "schemas"
    schema_result = runner.invoke(app, ["schema", "export", str(schema_dir)])
    assert schema_result.exit_code == 0
    assert (schema_dir / "memory_event.schema.json").exists()
    assert (schema_dir / "schema_index.json").exists()
    assert (schema_dir / "semantic_rules.json").exists()

    verify_result = runner.invoke(app, ["ledger", "verify", "--ledger", str(ledger)])
    assert verify_result.exit_code == 0
    assert "OK" in verify_result.output


def test_cli_new_reference_alignment_commands(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = tmp_path / "ledger.jsonl"
    audit_result = runner.invoke(app, ["audit", "telemetry", "--ledger", str(ledger), "--json"])
    assert audit_result.exit_code == 0

    authority_result = runner.invoke(
        app,
        [
            "authority",
            "check",
            "--action",
            "persistent_memory_write",
            "--actor",
            "agent",
            "--scope",
            "user:test",
            "--source-record",
            "free text",
            "--natural-language",
            "please do it",
            "--json",
        ],
    )
    assert authority_result.exit_code == 0
    assert "natural_language_not_authorization" in authority_result.output

    workflow_result = runner.invoke(
        app,
        [
            "workflow",
            "bottleneck",
            "--workflow-id",
            "wf",
            "--rates-json",
            '{"memory_governance": 2, "authorization": 3}',
            "--json",
        ],
    )
    assert workflow_result.exit_code == 0

    mapping_result = runner.invoke(app, ["reference", "mapping", "--json"])
    assert mapping_result.exit_code == 0
    assert "observable-agent-workflow-memory" in mapping_result.output


def test_cli_doctor_ledger_controls(tmp_path) -> None:  # type: ignore[no-untyped-def]
    broken = tmp_path / "broken.jsonl"
    broken.write_text("{not json}\n", encoding="utf-8")

    skipped = runner.invoke(app, ["doctor", "--skip-ledger", "--json"])
    assert skipped.exit_code == 0
    assert "skipped by request" in skipped.output

    explicit = runner.invoke(app, ["doctor", "--ledger", str(broken), "--json"])
    assert explicit.exit_code == 1
    assert "ledger_verify" in explicit.output


def test_cli_adapter_diagnostics_are_offline() -> None:
    doctor_result = runner.invoke(app, ["adapters", "doctor", "--json"])
    assert doctor_result.exit_code == 0
    assert "cmgl.adapters_doctor_report.v1" in doctor_result.output

    smoke_result = runner.invoke(
        app,
        ["adapters", "live-smoke", "--target", "all", "--dry-run", "--json"],
    )
    assert smoke_result.exit_code == 0
    assert '"dry_run":true' in smoke_result.output
