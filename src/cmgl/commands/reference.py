from __future__ import annotations

from typing import Annotated

import typer

from cmgl.commands._common import print_obj

app = typer.Typer(no_args_is_help=True, help="Reference mapping commands.")


@app.command("mapping")
def reference_mapping(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    mapping = [
        {"repo": "observable-agent-workflow-memory", "mapped_to": "lifecycle/evidence/admission"},
        {"repo": "memoryflow-agent-memory-auditor", "mapped_to": "telemetry/audit"},
        {"repo": "oasg", "mapped_to": "canonical ledger/prefix/lifecycle"},
        {"repo": "no-meta-authority-runtime", "mapped_to": "authority gates"},
        {"repo": "certified-workflow-conversion", "mapped_to": "workflow bottlenecks"},
        {"repo": "semantic-translation-contracts-poc", "mapped_to": "compression certificates"},
        {"repo": "sovereign-epistemic-commons-poc", "mapped_to": "contamination governance"},
    ]
    print_obj(mapping, as_json=json_output)
