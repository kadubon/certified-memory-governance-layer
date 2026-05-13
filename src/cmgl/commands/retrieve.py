from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from cmgl.admission import filter_retrieval
from cmgl.commands._common import console, print_obj
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import MemoryEvent

app = typer.Typer(no_args_is_help=True, help="Retrieval filtering commands.")


@app.command("filter")
def retrieve_filter(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    query: Annotated[str, typer.Option("--query", help="Retrieval query text.")],
    input_json: Annotated[Path, typer.Option("--input-json", help="List of MemoryEvent JSON.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    try:
        raw = json.loads(input_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"invalid input JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise typer.BadParameter("input JSON must be a list of memory event objects")
    events = [MemoryEvent.model_validate(item) for item in raw]
    result = filter_retrieval(query, events)
    AppendOnlyLedger(ledger).append("retrieval_decision", result.decision)
    if json_output:
        print_obj(result.decision, as_json=True)
    else:
        table = Table("Metric", "Value")
        table.add_row("Raw hits", str(result.decision.raw_hits))
        table.add_row("Admitted hits", str(result.decision.admitted_hits))
        table.add_row("Admitted IDs", ", ".join(result.decision.admitted_memory_ids))
        console.print(table)
        for blocked in result.decision.blocked_hits:
            console.print(f"Blocked {blocked['memory_id']}: {blocked['reason']}")
