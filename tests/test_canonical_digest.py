from __future__ import annotations

from datetime import datetime, timezone

from cmgl.canonical import canonical_json
from cmgl.digest import sha256_digest


def test_canonical_json_stable_ordering() -> None:
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_json(left) == '{"a":1,"b":2}'


def test_canonical_json_stable_datetime() -> None:
    value = {"time": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)}
    assert canonical_json(value) == '{"time":"2026-01-02T03:04:05.000000Z"}'


def test_digest_stable_and_changes() -> None:
    assert sha256_digest({"a": 1, "b": 2}) == sha256_digest({"b": 2, "a": 1})
    assert sha256_digest({"a": 1}) != sha256_digest({"a": 2})
    assert sha256_digest("hello").startswith("sha256:")
