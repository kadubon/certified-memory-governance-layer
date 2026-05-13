from __future__ import annotations

from typing import Annotated, Literal, cast

import typer

from cmgl.commands._common import console, print_obj
from cmgl.live_smoke import adapter_doctor, run_live_smoke

app = typer.Typer(no_args_is_help=True, help="Optional adapter diagnostics and live smoke.")


@app.command("doctor")
def doctor(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    report = adapter_doctor()
    if json_output:
        print_obj(report, as_json=True)
        return
    status = "OK" if report["ok"] else "CHECK"
    console.print(f"CMGL adapters doctor: {status}")
    for check in report["checks"]:
        marker = "ok" if check["ok"] else "missing"
        console.print(f"- {marker}: {check['name']} ({check['detail']})")


@app.command("live-smoke")
def live_smoke(
    target: Annotated[
        str,
        typer.Option("--target", help="Adapter target: mem0, graphiti, langmem, langgraph, all."),
    ] = "all",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Validate live-smoke contract without provider calls."),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    if target not in {"mem0", "graphiti", "langmem", "langgraph", "all"}:
        raise typer.BadParameter("target must be one of: mem0, graphiti, langmem, langgraph, all")
    checked_target = cast(Literal["mem0", "graphiti", "langmem", "langgraph", "all"], target)
    report = run_live_smoke(target=checked_target, dry_run=dry_run)
    if json_output:
        print_obj(report, as_json=True)
    else:
        status = "OK" if report["ok"] else "FAILED"
        console.print(f"CMGL live adapter smoke: {status}")
        for check in report["checks"]:
            marker = "ok" if check["ok"] else "fail"
            console.print(f"- {marker}: {check['name']} ({check['detail']})")
    if not report["ok"]:
        raise typer.Exit(1)
