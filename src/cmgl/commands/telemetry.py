from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cmgl.commands._common import print_obj
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import GovernanceProfile
from cmgl.telemetry_ingest import ingest_telemetry_jsonl
from cmgl.telemetry_replay import replay_telemetry_jsonl

app = typer.Typer(no_args_is_help=True, help="Telemetry ingest and replay commands.")


@app.command("ingest")
def telemetry_ingest(
    path: Annotated[Path, typer.Argument(help="Telemetry JSONL path.")],
    ledger: Annotated[Path | None, typer.Option("--ledger", help="Optional ledger path.")] = None,
    profile: Annotated[
        GovernanceProfile, typer.Option("--profile", help="strict, operational, or legacy.")
    ] = GovernanceProfile.STRICT,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    active_ledger = None if ledger is None else AppendOnlyLedger(ledger)
    result = ingest_telemetry_jsonl(path, ledger=active_ledger, profile=profile)
    print_obj(result, as_json=json_output)
    if profile == GovernanceProfile.STRICT and result.rejected_events:
        raise typer.Exit(1)


@app.command("replay")
def telemetry_replay(
    path: Annotated[Path, typer.Argument(help="Telemetry JSONL path.")],
    profile: Annotated[
        GovernanceProfile, typer.Option("--profile", help="strict, operational, or legacy.")
    ] = GovernanceProfile.STRICT,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    result = replay_telemetry_jsonl(path, profile=profile)
    print_obj(result, as_json=json_output)
    if profile == GovernanceProfile.STRICT and any(
        outcome.status.value == "rejected" for outcome in result.outcomes
    ):
        raise typer.Exit(1)
