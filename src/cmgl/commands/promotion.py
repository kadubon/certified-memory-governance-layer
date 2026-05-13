from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from cmgl.commands._common import print_obj
from cmgl.models import PromotionEvidenceBundle, PromotionReceipt
from cmgl.receipt_verifier import PromotionVerifier

app = typer.Typer(no_args_is_help=True, help="Strict promotion verification commands.")


@app.command("verify")
def promotion_verify(
    receipt_json: Annotated[Path, typer.Argument(help="Promotion receipt JSON.")],
    evidence_bundle_json: Annotated[
        Path, typer.Option("--evidence-bundle", help="PromotionEvidenceBundle JSON.")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    receipt = PromotionReceipt.model_validate(json.loads(receipt_json.read_text(encoding="utf-8")))
    bundle = PromotionEvidenceBundle.model_validate(
        json.loads(evidence_bundle_json.read_text(encoding="utf-8"))
    )
    metric = PromotionVerifier().verify(
        bundle.candidate,
        receipt,
        evidence_manifest=bundle.evidence_manifest,
        input_set_manifest=bundle.input_set_manifest,
        replay_evidence=bundle.replay_evidence,
        shadow_receipt=bundle.shadow_receipt,
        active_promotion_receipt=bundle.active_promotion_receipt,
        current_update_id=bundle.candidate.event.memory_update_id,
    )
    print_obj(metric, as_json=json_output)
    if metric.status.value != "valid":
        raise typer.Exit(1)
