from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

JsonContent = str | dict[str, Any] | list[Any] | None


class CMGLModel(BaseModel):
    """Base model for strict CMGL schema objects."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def validate_digest(value: str) -> str:
    if not value.startswith("sha256:"):
        raise ValueError("digest must start with 'sha256:'")
    hex_part = value.removeprefix("sha256:")
    if len(hex_part) != 64 or any(char not in "0123456789abcdef" for char in hex_part):
        raise ValueError("digest must be lowercase sha256:<64 hex chars>")
    return value
