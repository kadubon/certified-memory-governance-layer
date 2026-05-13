from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def canonical_datetime(value: datetime) -> str:
    """Serialize a datetime as stable UTC ISO-8601 with a trailing Z."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    text = value.isoformat(timespec="microseconds")
    return text.replace("+00:00", "Z")
