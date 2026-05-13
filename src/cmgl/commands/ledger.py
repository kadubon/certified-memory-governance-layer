from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from cmgl.commands._common import print_obj
from cmgl.ledger import AppendOnlyLedger

app = typer.Typer(no_args_is_help=True, help="Append-only ledger commands.")


@app.command("append")
def ledger_append(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    record_type: Annotated[str, typer.Option("--type", help="Ledger record type.")],
    payload_json: Annotated[str, typer.Option("--json", help="Record payload JSON.")],
    expected_prefix: Annotated[
        str | None, typer.Option("--expected-prefix", help="Expected current ledger prefix hash.")
    ] = None,
    duplicate_policy: Annotated[
        str, typer.Option("--duplicate-policy", help="allow or reject duplicate payload identity.")
    ] = "allow",
    receipt_json: Annotated[
        bool, typer.Option("--receipt-json", help="Persist and emit a LedgerAppendReceipt.")
    ] = False,
) -> None:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"invalid JSON payload: {exc}") from exc
    active_ledger = AppendOnlyLedger(ledger)
    if receipt_json:
        _, receipt = active_ledger.append_with_receipt(
            record_type,
            payload,
            expected_prefix=expected_prefix,
            duplicate_policy=duplicate_policy,
            persist_receipt=True,
        )
        print_obj(receipt, as_json=True)
    else:
        record = active_ledger.append(
            record_type,
            payload,
            expected_prefix=expected_prefix,
            duplicate_policy=duplicate_policy,
        )
        print_obj(record, as_json=True)


@app.command("verify")
def ledger_verify(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
    receipt_json: Annotated[
        bool, typer.Option("--receipt-json", help="Emit a LedgerIntegrityReceipt as JSON.")
    ] = False,
) -> None:
    active_ledger = AppendOnlyLedger(ledger)
    if receipt_json:
        print_obj(active_ledger.integrity_receipt(), as_json=True)
        return

    result = active_ledger.verify_prefix()
    if json_output:
        print_obj(result, as_json=True)
    elif result.ok:
        print_obj(f"OK: verified {result.records_checked} records", as_json=False)
        if result.ledger_prefix_hash is not None:
            print_obj(f"Prefix: {result.ledger_prefix_hash}", as_json=False)
    else:
        print_obj(f"FAILED: verified {result.records_checked} records", as_json=False)
        for error in result.errors:
            print_obj(f"- {error}", as_json=False)
        raise typer.Exit(1)
