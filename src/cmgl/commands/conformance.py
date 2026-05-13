from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cmgl.commands._common import print_obj
from cmgl.conformance import audit_ledger_conformance
from cmgl.models import ConformanceProfile
from cmgl.obligations import ObligationVerifier

app = typer.Typer(no_args_is_help=True, help="Reference-theory conformance checks.")


@app.command("audit")
def conformance_audit(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    profile: Annotated[
        ConformanceProfile, typer.Option("--profile", help="strict, operational, or legacy.")
    ] = ConformanceProfile.STRICT,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    report = audit_ledger_conformance(ledger, profile=profile)
    print_obj(report, as_json=json_output)
    if not report.ok:
        raise typer.Exit(1)


@app.command("explain")
def conformance_explain(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    memory_id: Annotated[str, typer.Option("--memory-id", help="Memory id to explain.")],
    profile: Annotated[
        ConformanceProfile, typer.Option("--profile", help="strict, operational, or legacy.")
    ] = ConformanceProfile.STRICT,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    reports = ObligationVerifier(profile=profile).explain_memory(ledger, memory_id)
    print_obj(reports, as_json=json_output)
