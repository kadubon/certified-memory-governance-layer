from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cmgl.commands._common import print_obj
from cmgl.validation import (
    validate_canonical_golden_vectors,
    validate_ledger_file,
    validate_record_file,
)

app = typer.Typer(no_args_is_help=True, help="Portable schema and rule validation.")


@app.command("record")
def validate_record(
    path: Annotated[Path, typer.Argument(help="Record JSON path.")],
    schema_name: Annotated[
        str | None, typer.Option("--schema", help="Schema name override.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    metric = validate_record_file(path, schema_name=schema_name)
    print_obj(metric, as_json=json_output)
    if metric.status.value != "valid":
        raise typer.Exit(1)


@app.command("canonical")
def validate_canonical(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    metric = validate_canonical_golden_vectors()
    print_obj(metric, as_json=json_output)
    if metric.status.value != "valid":
        raise typer.Exit(1)


@app.command("ledger")
def validate_ledger(
    path: Annotated[Path, typer.Argument(help="Ledger JSONL path.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    metric = validate_ledger_file(path)
    print_obj(metric, as_json=json_output)
    if metric.status.value != "valid":
        raise typer.Exit(1)
