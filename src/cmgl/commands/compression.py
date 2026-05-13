from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from cmgl.commands._common import print_obj
from cmgl.compression import audit_compression_certificate
from cmgl.models import CompressionCertificate

app = typer.Typer(no_args_is_help=True, help="Compression certificate audit commands.")


@app.command("audit")
def compression_audit(
    certificate_json: Annotated[Path, typer.Argument(help="Compression certificate JSON.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    certificate = CompressionCertificate.model_validate(
        json.loads(certificate_json.read_text(encoding="utf-8"))
    )
    report = audit_compression_certificate(certificate)
    print_obj(report, as_json=json_output)
    if not report.deployable_exact_recovery:
        raise typer.Exit(1)
