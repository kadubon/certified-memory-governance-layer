from __future__ import annotations

from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from cmgl import __version__
from cmgl.config import load_config
from cmgl.ledger import AppendOnlyLedger
from cmgl.schemas import export_json_schemas
from cmgl.validation import validate_canonical_golden_vectors


def run_doctor(
    *,
    cwd: str | Path = ".",
    ledger: str | Path | None = None,
    skip_ledger: bool = False,
) -> dict[str, Any]:
    """Run deterministic local readiness checks without network access."""

    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str | None = None) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("import", True, "cmgl imported")
    add("version", True, __version__)

    try:
        config = load_config(cwd=cwd)
        add("config", True, "loaded default or local config")
    except Exception as exc:
        config = None
        add("config", False, str(exc))

    canonical = validate_canonical_golden_vectors()
    add("canonical", canonical.status.value == "valid", ",".join(canonical.reason_codes))

    with TemporaryDirectory() as tmp:
        try:
            schemas = export_json_schemas(Path(tmp) / "schemas")
            add("schema_export", bool(schemas), f"{len(schemas)} files")
        except Exception as exc:
            add("schema_export", False, str(exc))

    if skip_ledger:
        add("ledger_verify", True, "skipped by request")
    else:
        ledger_path = (
            Path(ledger)
            if ledger is not None
            else (Path(".cmgl/ledger.jsonl") if config is None else Path(config.ledger.path))
        )
        if not ledger_path.is_absolute():
            ledger_path = Path(cwd) / ledger_path
        verification = AppendOnlyLedger(ledger_path).verify_prefix()
        add(
            "ledger_verify",
            verification.ok,
            f"{verification.records_checked} records checked at {ledger_path}",
        )

    for module_name in [
        "cmgl.adapters.mem0",
        "cmgl.adapters.graphiti",
        "cmgl.adapters.langmem",
        "cmgl.adapters.langgraph",
    ]:
        try:
            import_module(module_name)
            add(f"adapter_module:{module_name.rsplit('.', maxsplit=1)[-1]}", True, "lazy import ok")
        except Exception as exc:
            add(f"adapter_module:{module_name.rsplit('.', maxsplit=1)[-1]}", False, str(exc))

    add("network", True, "doctor performs no network calls")
    return {
        "schema_version": "cmgl.doctor_report.v1",
        "ok": all(bool(item["ok"]) for item in checks),
        "version": __version__,
        "checks": checks,
    }
