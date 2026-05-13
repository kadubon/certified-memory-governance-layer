from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from cmgl.admission import candidate_from_event
from cmgl.commands._common import print_obj
from cmgl.lifecycle import (
    make_active_promotion_receipt,
    make_lease_receipt,
    make_quarantine_record,
    make_rollback_receipt,
    make_rollback_snapshot,
    make_shadow_trial_receipt,
)
from cmgl.models import MemoryCandidate, MemoryEvent

app = typer.Typer(no_args_is_help=True, help="Shadow, lease, rollback, quarantine.")


def _candidate_from_event_json(path: Path) -> MemoryCandidate:
    event = MemoryEvent.model_validate(json.loads(path.read_text(encoding="utf-8")))
    return candidate_from_event(event)


@app.command("shadow")
def lifecycle_shadow(
    event_json: Annotated[Path, typer.Option("--event-json")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    print_obj(
        make_shadow_trial_receipt(_candidate_from_event_json(event_json), admitted=True),
        as_json=json_output,
    )


@app.command("lease")
def lifecycle_lease(
    event_json: Annotated[Path, typer.Option("--event-json")],
    lease_seconds: Annotated[int, typer.Option("--lease-seconds")] = 3600,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    receipt = make_lease_receipt(
        _candidate_from_event_json(event_json),
        lease_seconds=lease_seconds,
        admitted=True,
    )
    print_obj(receipt, as_json=json_output)


@app.command("promote")
def lifecycle_promote(
    event_json: Annotated[Path, typer.Option("--event-json")],
    source_receipt_digest: Annotated[str, typer.Option("--source-receipt-digest")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    receipt = make_active_promotion_receipt(
        _candidate_from_event_json(event_json),
        source_receipt_digest=source_receipt_digest,
        admitted=True,
    )
    print_obj(receipt, as_json=json_output)


@app.command("rollback")
def lifecycle_rollback(
    event_json: Annotated[Path, typer.Option("--event-json")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    event = MemoryEvent.model_validate(json.loads(event_json.read_text(encoding="utf-8")))
    snapshot = make_rollback_snapshot([event])
    receipt = make_rollback_receipt(snapshot, restored_memory_ids=[event.memory_id], admitted=True)
    print_obj({"snapshot": snapshot, "receipt": receipt}, as_json=json_output)


@app.command("quarantine")
def lifecycle_quarantine(
    target_json: Annotated[Path, typer.Option("--target-json")],
    target_type: Annotated[str, typer.Option("--target-type")] = "memory_event",
    reason: Annotated[str, typer.Option("--reason")] = "manual_quarantine",
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    target = json.loads(target_json.read_text(encoding="utf-8"))
    record = make_quarantine_record(target=target, target_type=target_type, reason_codes=[reason])
    print_obj(record, as_json=json_output)
