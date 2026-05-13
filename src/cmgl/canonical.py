from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from cmgl.time import canonical_datetime


def _normalize(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return _normalize(obj.model_dump(mode="python"))
    if isinstance(obj, datetime):
        return canonical_datetime(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(key): _normalize(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_normalize(value) for value in obj]
    if isinstance(obj, tuple):
        return [_normalize(value) for value in obj]
    return obj


def canonical_json(obj: Any) -> str:
    """Return deterministic UTF-8 JSON text for a JSON-like object."""

    return json.dumps(
        _normalize(obj),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_json_bytes(obj: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes."""

    return canonical_json(obj).encode("utf-8")
