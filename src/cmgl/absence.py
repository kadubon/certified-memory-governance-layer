from __future__ import annotations

from uuid import uuid4

from cmgl.digest import sha256_digest
from cmgl.models import AbsenceNoticeType, RecordAbsenceNotice
from cmgl.time import now_utc


def make_record_absence_notice(
    *,
    notice_type: AbsenceNoticeType,
    memory_id: str | None = None,
    missing_record: object | None = None,
    disclosure: object | None = None,
    reason_codes: list[str] | None = None,
) -> RecordAbsenceNotice:
    default_code = f"absence.{notice_type.value}"
    body = {
        "schema_version": "cmgl.record_absence_notice.v1",
        "notice_id": f"absence:{uuid4()}",
        "notice_type": notice_type,
        "memory_id": memory_id,
        "missing_record_digest": None if missing_record is None else sha256_digest(missing_record),
        "disclosure_digest": None if disclosure is None else sha256_digest(disclosure),
        "reason_codes": list(reason_codes or [default_code]),
        "timestamp": now_utc(),
    }
    return RecordAbsenceNotice(**body, notice_digest=sha256_digest(body))
