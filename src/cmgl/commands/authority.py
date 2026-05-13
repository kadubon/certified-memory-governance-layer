from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from cmgl.authority import (
    authorize_bundle,
    authorize_request,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.canonical import canonical_json
from cmgl.commands._common import print_obj
from cmgl.models import DeclaredScope, ProtectedAction

app = typer.Typer(no_args_is_help=True, help="Protected-action authority commands.")


@app.command("check")
def authority_check(
    action: Annotated[ProtectedAction, typer.Option("--action")],
    actor: Annotated[str, typer.Option("--actor")],
    scope: Annotated[str, typer.Option("--scope")],
    source_record: Annotated[str, typer.Option("--source-record")],
    declared_scope_json: Annotated[Path | None, typer.Option("--declared-scope-json")] = None,
    natural_language: Annotated[str | None, typer.Option("--natural-language")] = None,
    resource: Annotated[str | None, typer.Option("--resource")] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    declared_scope = None
    if declared_scope_json is not None:
        declared_scope = DeclaredScope.model_validate(
            json.loads(declared_scope_json.read_text(encoding="utf-8"))
        )
    request = make_protected_action_request(
        action=action,
        actor=actor,
        authority_scope=scope,
        source_record=source_record,
        natural_language_justification=natural_language,
        declared_scope=declared_scope,
        resource=resource,
    )
    print_obj(authorize_request(request, declared_scope=declared_scope), as_json=json_output)


bundle_app = typer.Typer(no_args_is_help=True, help="Authority bundle commands.")


@bundle_app.command("create")
def authority_bundle_create(
    action: Annotated[ProtectedAction, typer.Option("--action")],
    actor: Annotated[str, typer.Option("--actor")],
    scope: Annotated[str, typer.Option("--scope")],
    source_record: Annotated[str, typer.Option("--source-record")],
    out: Annotated[Path | None, typer.Option("--out", help="Write bundle JSON to path.")] = None,
    resource: Annotated[str | None, typer.Option("--resource")] = None,
    permitted_actions: Annotated[
        list[ProtectedAction] | None,
        typer.Option("--permitted-action", help="Permitted action; repeatable."),
    ] = None,
    expires_at: Annotated[
        str | None,
        typer.Option("--expires-at", help="ISO-8601 UTC expiration timestamp."),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    expiration = _parse_expires_at(expires_at)
    declared_scope = make_declared_scope(
        actor=actor,
        authority_scope=scope,
        permitted_actions=permitted_actions or [action],
        resource_patterns=[] if resource is None else [resource],
        expires_at=expiration,
    )
    request = make_protected_action_request(
        action=action,
        actor=actor,
        authority_scope=scope,
        source_record=source_record,
        declared_scope=declared_scope,
        resource=resource,
    )
    bundle = authorize_bundle(request, declared_scope=declared_scope)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(canonical_json(bundle) + "\n", encoding="utf-8")
    if json_output or out is None:
        print_obj(bundle, as_json=True)
    else:
        print_obj(f"Wrote authority bundle to {out}", as_json=False)


def _parse_expires_at(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


app.add_typer(bundle_app, name="bundle")
