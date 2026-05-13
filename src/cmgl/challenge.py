from __future__ import annotations

from uuid import uuid4

from cmgl.digest import sha256_digest
from cmgl.models import ChallengeStatus, MemoryChallengeRecord
from cmgl.time import now_utc


def make_memory_challenge_record(
    *,
    memory_id: str,
    memory_update_id: str | None = None,
    status: ChallengeStatus = ChallengeStatus.OPEN,
    reason_codes: list[str] | None = None,
    evidence_ids: list[str] | None = None,
) -> MemoryChallengeRecord:
    body = {
        "schema_version": "cmgl.memory_challenge_record.v1",
        "challenge_id": f"challenge:{uuid4()}",
        "memory_id": memory_id,
        "memory_update_id": memory_update_id,
        "status": status,
        "reason_codes": list(reason_codes or [f"challenge.{status.value}"]),
        "evidence_ids": list(evidence_ids or []),
        "timestamp": now_utc(),
    }
    return MemoryChallengeRecord(**body, record_digest=sha256_digest(body))
