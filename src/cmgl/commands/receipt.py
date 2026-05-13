from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from cmgl.commands._common import print_obj
from cmgl.models import EvidenceManifest, MemoryCandidate, PromotionReceipt
from cmgl.obligations import ObligationVerifier
from cmgl.receipt_verifier import verify_promotion_receipt

app = typer.Typer(no_args_is_help=True, help="Receipt verification commands.")


@app.command("verify")
def receipt_verify(
    candidate_json: Annotated[Path, typer.Option("--candidate-json")],
    receipt_json: Annotated[Path, typer.Option("--receipt-json")],
    evidence_json: Annotated[Path | None, typer.Option("--evidence-json")] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    candidate = MemoryCandidate.model_validate(
        json.loads(candidate_json.read_text(encoding="utf-8"))
    )
    receipt = PromotionReceipt.model_validate(json.loads(receipt_json.read_text(encoding="utf-8")))
    evidence = None
    if evidence_json is not None:
        evidence = EvidenceManifest.model_validate(
            json.loads(evidence_json.read_text(encoding="utf-8"))
        )
    print_obj(
        verify_promotion_receipt(candidate, receipt, evidence_manifest=evidence),
        as_json=json_output,
    )


@app.command("obligations")
def receipt_obligations(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    receipt_digest: Annotated[
        str, typer.Option("--receipt-digest", help="Promotion receipt digest.")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    graph = ObligationVerifier().verify(ledger)
    reports = [report for report in graph.reports if report.subject_digest == receipt_digest]
    print_obj(reports, as_json=json_output)
    if not reports:
        raise typer.Exit(1)
