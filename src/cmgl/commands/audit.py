from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cmgl.audit import contamination_report, stale_use_report, telemetry_audit_report
from cmgl.commands._common import print_obj
from cmgl.ledger import AppendOnlyLedger

app = typer.Typer(no_args_is_help=True, help="Audit commands.")


@app.command("stale-use")
def audit_stale_use(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    print_obj(stale_use_report(AppendOnlyLedger(ledger)), as_json=json_output)


@app.command("contamination")
def audit_contamination(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    print_obj(contamination_report(AppendOnlyLedger(ledger)), as_json=json_output)


@app.command("telemetry")
def audit_telemetry(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    print_obj(telemetry_audit_report(AppendOnlyLedger(ledger)), as_json=json_output)
