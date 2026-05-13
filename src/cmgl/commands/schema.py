from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cmgl.commands._common import print_obj
from cmgl.schemas import export_json_schemas

app = typer.Typer(no_args_is_help=True, help="JSON Schema commands.")


@app.command("export")
def schema_export(
    out_dir: Annotated[Path, typer.Argument(help="Directory for exported JSON Schemas.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    written = export_json_schemas(out_dir)
    payload = {"schemas": [str(path) for path in written]}
    if json_output:
        print_obj(payload, as_json=True)
    else:
        for path in written:
            print_obj(f"Wrote {path}", as_json=False)
