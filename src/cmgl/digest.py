from __future__ import annotations

from hashlib import sha256
from typing import Any

from cmgl.canonical import canonical_json_bytes


def sha256_digest(obj_or_text: Any) -> str:
    """Return a `sha256:<hex>` digest for text, bytes, or canonical JSON."""

    if isinstance(obj_or_text, bytes):
        data = obj_or_text
    elif isinstance(obj_or_text, str):
        data = obj_or_text.encode("utf-8")
    else:
        data = canonical_json_bytes(obj_or_text)
    return f"sha256:{sha256(data).hexdigest()}"
