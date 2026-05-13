from __future__ import annotations

from typing import Any

from rich.console import Console

from cmgl.canonical import canonical_json

console = Console()


def print_obj(obj: Any, *, as_json: bool) -> None:
    if as_json:
        console.out(canonical_json(obj))
    else:
        console.print(obj)
