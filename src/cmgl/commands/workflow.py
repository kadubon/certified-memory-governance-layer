from __future__ import annotations

import json
from typing import Annotated

import typer

from cmgl.commands._common import print_obj
from cmgl.workflow import make_workflow_bottleneck_report

app = typer.Typer(no_args_is_help=True, help="Workflow diagnostic commands.")


@app.command("bottleneck")
def workflow_bottleneck(
    workflow_id: Annotated[str, typer.Option("--workflow-id")],
    rates_json: Annotated[str, typer.Option("--rates-json", help="JSON object of layer rates.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    raw = json.loads(rates_json)
    if not isinstance(raw, dict):
        raise typer.BadParameter("rates JSON must be an object")
    rates = {str(key): float(value) for key, value in raw.items()}
    print_obj(
        make_workflow_bottleneck_report(workflow_id=workflow_id, layer_rates=rates),
        as_json=json_output,
    )
