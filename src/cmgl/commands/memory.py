from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Annotated

import typer

from cmgl.authority import (
    authorize_bundle,
    make_authority_evidence_bundle,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.commands._common import print_obj
from cmgl.layer import GovernanceLayer
from cmgl.models import (
    AuthorityBundle,
    AuthorityEvidenceBundle,
    ContaminationLane,
    ProtectedAction,
)
from cmgl.time import now_utc

app = typer.Typer(no_args_is_help=True, help="Memory event commands.")


@app.command("write")
def memory_write(
    ledger: Annotated[Path, typer.Option("--ledger", help="Ledger JSONL path.")],
    content: Annotated[str, typer.Option("--content", help="Memory text content.")],
    lane: Annotated[ContaminationLane, typer.Option("--lane", help="Contamination lane.")],
    scope: Annotated[str, typer.Option("--scope", help="Authority scope.")],
    authority_bundle_json: Annotated[
        Path | None,
        typer.Option(
            "--authority-bundle-json",
            help="AuthorityBundle or AuthorityEvidenceBundle JSON for strict writes.",
        ),
    ] = None,
    demo_local_authority: Annotated[
        bool,
        typer.Option(
            "--demo-local-authority",
            help="Create short-lived synthetic demo authority. Do not use for production.",
        ),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    authority_bundle: AuthorityBundle | None = None
    authority_evidence_bundle: AuthorityEvidenceBundle | None = None
    if authority_bundle_json is not None:
        authority_bundle, authority_evidence_bundle = _load_authority_bundle(authority_bundle_json)
    elif demo_local_authority:
        authority_evidence_bundle = _demo_authority_evidence_bundle(scope=scope)

    layer = GovernanceLayer(ledger=ledger)
    result = layer.write_memory(
        content,
        lane=lane,
        authority_scope=scope,
        authority_bundle=authority_bundle,
        authority_evidence_bundle=authority_evidence_bundle,
    )
    bundle = layer.receipt_bundle(result)
    if json_output:
        print_obj(bundle, as_json=True)
    else:
        print_obj(f"{bundle.decision.value}: {bundle.event.memory_id}", as_json=False)
        if bundle.promotion_receipt.reason_codes:
            print_obj(", ".join(bundle.promotion_receipt.reason_codes), as_json=False)


def _load_authority_bundle(
    path: Path,
) -> tuple[AuthorityBundle | None, AuthorityEvidenceBundle | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise typer.BadParameter("authority bundle JSON must be an object")
    schema_version = raw.get("schema_version")
    if schema_version == "cmgl.authority_bundle.v1":
        return AuthorityBundle.model_validate(raw), None
    if schema_version == "cmgl.authority_evidence_bundle.v1":
        return None, AuthorityEvidenceBundle.model_validate(raw)
    raise typer.BadParameter(
        "authority bundle JSON must have schema_version "
        "cmgl.authority_bundle.v1 or cmgl.authority_evidence_bundle.v1"
    )


def _demo_authority_evidence_bundle(*, scope: str) -> AuthorityEvidenceBundle:
    declared_scope = make_declared_scope(
        actor="cmgl-cli",
        authority_scope=scope,
        permitted_actions=[ProtectedAction.PERSISTENT_MEMORY_WRITE],
        expires_at=now_utc() + timedelta(minutes=10),
    )
    request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="cmgl-cli",
        authority_scope=scope,
        source_record=("cmgl demo local authority; synthetic structured scope for local demo only"),
        declared_scope=declared_scope,
        resource=f"memory:{scope}:demo",
    )
    bundle = authorize_bundle(request, declared_scope=declared_scope)
    return make_authority_evidence_bundle(
        request=bundle.request,
        declared_scope=bundle.declared_scope,
        receipt=bundle.receipt,
        retained_authority_channels=["cmgl.demo_local_authority"],
        retained_channel_blocking=False,
    )
