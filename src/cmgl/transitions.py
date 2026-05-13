from __future__ import annotations

from dataclasses import dataclass

from cmgl.digest import sha256_digest
from cmgl.exceptions import LifecycleError
from cmgl.models import MemoryRevision, MemoryStatus
from cmgl.time import now_utc

TERMINAL_STATUSES = {
    MemoryStatus.SUPERSEDED,
    MemoryStatus.CONTRADICTED,
    MemoryStatus.TOMBSTONED,
    MemoryStatus.QUARANTINED,
}

ALLOWED_TRANSITIONS: dict[MemoryStatus, set[MemoryStatus]] = {
    MemoryStatus.RAW: {MemoryStatus.CANDIDATE, MemoryStatus.QUARANTINED},
    MemoryStatus.CANDIDATE: {
        MemoryStatus.VERIFIED_SHADOW,
        MemoryStatus.QUARANTINED,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.TOMBSTONED,
    },
    MemoryStatus.VERIFIED_SHADOW: {
        MemoryStatus.CERTIFIED,
        MemoryStatus.ADMISSIBLE,
        MemoryStatus.QUARANTINED,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.SUPERSEDED,
    },
    MemoryStatus.CERTIFIED: {
        MemoryStatus.ADMISSIBLE,
        MemoryStatus.SUPERSEDED,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.TOMBSTONED,
        MemoryStatus.QUARANTINED,
    },
    MemoryStatus.ADMISSIBLE: {
        MemoryStatus.SUPERSEDED,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.TOMBSTONED,
        MemoryStatus.QUARANTINED,
    },
    MemoryStatus.SUPERSEDED: set(),
    MemoryStatus.CONTRADICTED: set(),
    MemoryStatus.TOMBSTONED: set(),
    MemoryStatus.QUARANTINED: set(),
}


def transition_allowed(from_status: MemoryStatus, to_status: MemoryStatus) -> bool:
    """Return whether a memory lifecycle transition is allowed."""

    return to_status in ALLOWED_TRANSITIONS[from_status]


def transition_reason(from_status: MemoryStatus, to_status: MemoryStatus) -> str | None:
    if from_status in TERMINAL_STATUSES:
        return f"transition.terminal.{from_status.value}"
    if not transition_allowed(from_status, to_status):
        return f"transition.{from_status.value}_to_{to_status.value}.blocked"
    return None


@dataclass(frozen=True)
class LifecyclePolicy:
    """Shared memory lifecycle transition policy."""

    allow_noop: bool = False

    def validate_transition(
        self,
        from_status: MemoryStatus,
        to_status: MemoryStatus,
    ) -> list[str]:
        if self.allow_noop and from_status == to_status:
            return []
        reason = transition_reason(from_status, to_status)
        return [] if reason is None else [reason]

    def require_transition(
        self,
        from_status: MemoryStatus,
        to_status: MemoryStatus,
    ) -> None:
        reasons = self.validate_transition(from_status, to_status)
        if reasons:
            raise LifecycleError(";".join(reasons))


def make_memory_revision(
    *,
    revision_id: str,
    memory_id: str,
    from_update_id: str | None,
    to_update_id: str | None,
    from_status: MemoryStatus,
    to_status: MemoryStatus,
    reason_codes: list[str] | None = None,
) -> MemoryRevision:
    reasons = list(reason_codes or [])
    blocked_reason = transition_reason(from_status, to_status)
    if blocked_reason is not None:
        reasons.append(blocked_reason)
    timestamp = now_utc()
    body = {
        "schema_version": "cmgl.memory_revision.v1",
        "revision_id": revision_id,
        "memory_id": memory_id,
        "from_update_id": from_update_id,
        "to_update_id": to_update_id,
        "from_status": from_status,
        "to_status": to_status,
        "reason_codes": reasons,
        "timestamp": timestamp,
    }
    return MemoryRevision(**body, revision_digest=sha256_digest(body))
