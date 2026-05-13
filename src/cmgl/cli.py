from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cmgl import __version__
from cmgl.commands import (
    adapters,
    audit,
    authority,
    compression,
    conformance,
    ledger,
    lifecycle,
    memory,
    promotion,
    receipt,
    reference,
    retrieve,
    schema,
    telemetry,
    validate,
    workflow,
)
from cmgl.commands._common import console, print_obj
from cmgl.config import write_default_config
from cmgl.doctor import run_doctor
from cmgl.schemas import export_json_schemas

app = typer.Typer(no_args_is_help=True, help="Certified Memory Governance Layer CLI.")


@app.command()
def version(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    payload = {"name": "cmgl", "version": __version__}
    if json_output:
        print_obj(payload, as_json=True)
    else:
        console.print(f"cmgl {__version__}")


@app.command()
def init(
    path: Annotated[Path, typer.Argument(help="Project directory to initialize.")] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    cmgl_dir = path / ".cmgl"
    ledger_path = cmgl_dir / "ledger.jsonl"
    config_path = cmgl_dir / "config.toml"
    schema_dir = cmgl_dir / "schemas"
    cmgl_dir.mkdir(parents=True, exist_ok=True)
    ledger_path.touch(exist_ok=True)
    write_default_config(config_path)
    schemas = export_json_schemas(schema_dir)
    payload = {
        "ledger": str(ledger_path),
        "config": str(config_path),
        "schema_dir": str(schema_dir),
        "schemas": [str(item) for item in schemas],
    }
    if json_output:
        print_obj(payload, as_json=True)
    else:
        console.print(f"Initialized CMGL ledger at {ledger_path}")
        console.print(f"Wrote local config to {config_path}")
        console.print(f"Exported schemas to {schema_dir}")


@app.command()
def doctor(
    ledger_path: Annotated[
        Path | None,
        typer.Option("--ledger", help="Ledger path to verify instead of local config/default."),
    ] = None,
    skip_ledger: Annotated[
        bool,
        typer.Option("--skip-ledger", help="Skip ledger verification for isolated smoke checks."),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    report = run_doctor(ledger=ledger_path, skip_ledger=skip_ledger)
    if json_output:
        print_obj(report, as_json=True)
    else:
        status = "OK" if report["ok"] else "FAILED"
        console.print(f"CMGL doctor: {status}")
        for check in report["checks"]:
            marker = "ok" if check["ok"] else "fail"
            console.print(f"- {marker}: {check['name']} ({check['detail']})")
    if not report["ok"]:
        raise typer.Exit(1)


app.add_typer(schema.app, name="schema")
app.add_typer(ledger.app, name="ledger")
app.add_typer(memory.app, name="memory")
app.add_typer(retrieve.app, name="retrieve")
app.add_typer(audit.app, name="audit")
app.add_typer(receipt.app, name="receipt")
app.add_typer(authority.app, name="authority")
app.add_typer(lifecycle.app, name="lifecycle")
app.add_typer(workflow.app, name="workflow")
app.add_typer(reference.app, name="reference")
app.add_typer(validate.app, name="validate")
app.add_typer(conformance.app, name="conformance")
app.add_typer(telemetry.app, name="telemetry")
app.add_typer(promotion.app, name="promotion")
app.add_typer(compression.app, name="compression")
app.add_typer(adapters.app, name="adapters")
