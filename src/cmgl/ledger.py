from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from cmgl.canonical import canonical_json
from cmgl.digest import sha256_digest
from cmgl.exceptions import LedgerError
from cmgl.lifecycle import make_quarantine_record
from cmgl.models import (
    CMGLModel,
    DuplicatePolicyReceipt,
    LedgerAppendReceipt,
    LedgerIntegrityReceipt,
    LedgerLineStatus,
    QuarantineRecord,
    SchemaMigrationRecord,
)
from cmgl.time import canonical_datetime, now_utc


class LedgerRecord(CMGLModel):
    append_index: int | None = None
    ledger_profile: str = "cmgl.ledger.v2"
    schema_epoch: str = "cmgl.schema.v1"
    policy_epoch: str = "cmgl.policy.v1"
    record_type: str
    payload: Any
    payload_digest: str
    previous_record_digest: str | None = None
    record_digest: str
    ledger_prefix_hash: str | None = None
    timestamp: str


class LedgerVerificationResult(CMGLModel):
    ok: bool
    records_checked: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
    last_record_digest: str | None = None
    ledger_prefix_hash: str | None = None
    line_statuses: list[LedgerLineStatus] = Field(default_factory=list)
    duplicate_count: int = Field(default=0, ge=0)


def _jsonable_payload(payload: Any) -> Any:
    return json.loads(canonical_json(payload))


def _record_digest(record_body: dict[str, Any]) -> str:
    body = dict(record_body)
    body.pop("record_digest", None)
    body.pop("ledger_prefix_hash", None)
    return sha256_digest(body)


def _ledger_prefix_hash(previous_prefix: str | None, record_digest: str) -> str:
    return sha256_digest(
        {
            "previous_ledger_prefix_hash": previous_prefix,
            "record_digest": record_digest,
        }
    )


def make_schema_migration_record(
    *,
    from_schema_epoch: str,
    to_schema_epoch: str,
    migration_id: str,
    reason_codes: list[str] | None = None,
) -> SchemaMigrationRecord:
    body = {
        "schema_version": "cmgl.schema_migration_record.v1",
        "from_schema_epoch": from_schema_epoch,
        "to_schema_epoch": to_schema_epoch,
        "migration_id": migration_id,
        "reason_codes": reason_codes or ["schema_migration_recorded"],
        "timestamp": now_utc(),
    }
    return SchemaMigrationRecord(**body, migration_digest=sha256_digest(body))


def make_duplicate_policy_receipt(
    *,
    duplicate_policy: Literal["allow", "reject", "quarantine"],
    record_type: str,
    payload_digest: str,
    duplicate: bool,
    reason_codes: list[str] | None = None,
) -> DuplicatePolicyReceipt:
    body = {
        "schema_version": "cmgl.duplicate_policy_receipt.v1",
        "duplicate_policy": duplicate_policy,
        "record_type": record_type,
        "payload_digest": payload_digest,
        "duplicate": duplicate,
        "reason_codes": reason_codes or ["duplicate_policy_recorded"],
        "timestamp": now_utc(),
    }
    return DuplicatePolicyReceipt(**body, receipt_digest=sha256_digest(body))


class AppendOnlyLedger:
    """Append-only JSONL ledger with hash-chained records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(
        self,
        record_type: str,
        payload: Any,
        *,
        expected_prefix: str | None = None,
        duplicate_policy: str = "allow",
    ) -> LedgerRecord:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload_json = _jsonable_payload(payload)
        state = self._last_state()
        if expected_prefix is not None and state["ledger_prefix_hash"] != expected_prefix:
            raise LedgerError("expected ledger prefix does not match current ledger prefix")
        payload_digest = sha256_digest(payload_json)
        duplicate = self._contains_identity(record_type, payload_digest)
        if duplicate and duplicate_policy == "reject":
            raise LedgerError("duplicate ledger payload rejected by duplicate_policy=reject")
        body = {
            "append_index": state["append_index"] + 1,
            "ledger_profile": "cmgl.ledger.v2",
            "schema_epoch": "cmgl.schema.v1",
            "policy_epoch": "cmgl.policy.v1",
            "record_type": record_type,
            "payload": payload_json,
            "payload_digest": payload_digest,
            "previous_record_digest": state["last_record_digest"],
            "timestamp": canonical_datetime(now_utc()),
        }
        body["record_digest"] = _record_digest(body)
        body["ledger_prefix_hash"] = _ledger_prefix_hash(
            state["ledger_prefix_hash"], body["record_digest"]
        )
        record = LedgerRecord.model_validate(body)
        with self.path.open("a", encoding="utf-8", newline="\n") as file:
            file.write(canonical_json(record) + "\n")
            file.flush()
        return record

    def append_receipt(
        self, record: LedgerRecord, *, duplicate: bool = False
    ) -> LedgerAppendReceipt:
        if record.append_index is None or record.ledger_prefix_hash is None:
            raise LedgerError(
                "ledger append receipt requires v2 append_index and ledger_prefix_hash"
            )
        timestamp = now_utc()
        body = {
            "schema_version": "cmgl.ledger_append_receipt.v1",
            "append_index": record.append_index,
            "record_digest": record.record_digest,
            "ledger_prefix_hash": record.ledger_prefix_hash,
            "payload_digest": record.payload_digest,
            "duplicate": duplicate,
            "timestamp": timestamp,
        }
        return LedgerAppendReceipt(**body, receipt_digest=sha256_digest(body))

    def append_with_receipt(
        self,
        record_type: str,
        payload: Any,
        *,
        expected_prefix: str | None = None,
        duplicate_policy: str = "allow",
        persist_receipt: bool = True,
    ) -> tuple[LedgerRecord, LedgerAppendReceipt]:
        record = self.append(
            record_type,
            payload,
            expected_prefix=expected_prefix,
            duplicate_policy=duplicate_policy,
        )
        receipt = self.append_receipt(record)
        if persist_receipt:
            self.append("ledger_append_receipt", receipt)
        return record, receipt

    def iter_records(self) -> Iterator[LedgerRecord]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    raw = json.loads(stripped)
                    yield LedgerRecord.model_validate(raw)
                except Exception as exc:
                    raise LedgerError(
                        f"invalid ledger record at line {line_number}: {exc}"
                    ) from exc

    def verify_prefix(self) -> LedgerVerificationResult:
        errors: list[str] = []
        previous_digest: str | None = None
        checked = 0
        last_digest: str | None = None
        previous_prefix: str | None = None
        line_statuses: list[LedgerLineStatus] = []
        seen_identities: set[tuple[str, str]] = set()
        duplicate_count = 0

        if not self.path.exists():
            return LedgerVerificationResult(ok=True, records_checked=0)

        try:
            raw_records = list(self._iter_raw_records())
        except LedgerError as exc:
            return LedgerVerificationResult(ok=False, records_checked=checked, errors=[str(exc)])

        for index, raw in enumerate(raw_records, start=1):
            checked += 1
            statuses: list[str] = []
            try:
                record = LedgerRecord.model_validate(raw)
            except Exception as exc:
                errors.append(f"line {index}: invalid record: {exc}")
                break

            if raw.get("ledger_profile") != "cmgl.ledger.v2":
                errors.append(f"line {index}: ledger profile mismatch")
                statuses.append("rejected_ledger_profile_mismatch")
            if raw.get("schema_epoch") != "cmgl.schema.v1":
                errors.append(f"line {index}: schema epoch mismatch")
                statuses.append("rejected_schema_epoch_mismatch")
            if raw.get("policy_epoch") != "cmgl.policy.v1":
                errors.append(f"line {index}: policy epoch mismatch")
                statuses.append("rejected_policy_epoch_mismatch")

            expected_payload_digest = sha256_digest(raw["payload"])
            if record.payload_digest != expected_payload_digest:
                errors.append(f"line {index}: payload digest mismatch")
                statuses.append("rejected_payload_hash_mismatch")

            if record.previous_record_digest != previous_digest:
                errors.append(f"line {index}: previous record digest mismatch")
                statuses.append("quarantined_hash_chain_mismatch")

            expected_append_index = index - 1
            if record.append_index is not None and record.append_index != expected_append_index:
                errors.append(f"line {index}: append index mismatch")
                statuses.append("rejected_append_index_mismatch")

            body = dict(raw)
            expected_record_digest = _record_digest(body)
            if record.record_digest != expected_record_digest:
                errors.append(f"line {index}: record digest mismatch")
                statuses.append("rejected_canonical_hash_mismatch")

            expected_prefix = _ledger_prefix_hash(previous_prefix, record.record_digest)
            if record.ledger_prefix_hash is None:
                statuses.append("legacy_prefix_unrecorded")
            elif record.ledger_prefix_hash != expected_prefix:
                errors.append(f"line {index}: ledger prefix hash mismatch")
                statuses.append("stale_or_forked_ledger_prefix")

            identity = (record.record_type, record.payload_digest)
            if identity in seen_identities:
                duplicate_count += 1
                statuses.append("duplicate_payload")
            seen_identities.add(identity)

            if not statuses:
                statuses.append("ledger_prefix_valid")
            line_statuses.append(
                LedgerLineStatus(
                    line=index,
                    statuses=statuses,
                    record_digest=record.record_digest,
                    payload_digest=record.payload_digest,
                )
            )

            previous_digest = record.record_digest
            last_digest = record.record_digest
            previous_prefix = record.ledger_prefix_hash or expected_prefix

        return LedgerVerificationResult(
            ok=not errors,
            records_checked=checked,
            errors=errors,
            last_record_digest=last_digest,
            ledger_prefix_hash=previous_prefix,
            line_statuses=line_statuses,
            duplicate_count=duplicate_count,
        )

    def integrity_receipt(self) -> LedgerIntegrityReceipt:
        verification = self.verify_prefix()
        timestamp = now_utc()
        body = {
            "schema_version": "cmgl.ledger_integrity_receipt.v1",
            "ok": verification.ok,
            "records_checked": verification.records_checked,
            "ledger_prefix_hash": verification.ledger_prefix_hash,
            "last_record_digest": verification.last_record_digest,
            "line_statuses": verification.line_statuses,
            "errors": verification.errors,
            "timestamp": timestamp,
        }
        return LedgerIntegrityReceipt(**body, receipt_digest=sha256_digest(body))

    def quarantine_failed_verification(self) -> QuarantineRecord | None:
        verification = self.verify_prefix()
        if verification.ok:
            return None
        reason_codes = [
            status
            for line in verification.line_statuses
            for status in line.statuses
            if isinstance(status, str) and status != "ledger_prefix_valid"
        ]
        if not reason_codes:
            reason_codes = ["stale_or_forked_ledger_prefix"]
        return make_quarantine_record(
            target=verification,
            target_type="ledger_verification",
            reason_codes=reason_codes,
        )

    def _last_record_digest(self) -> str | None:
        last: str | None = None
        for record in self.iter_records():
            last = record.record_digest
        return last

    def _last_state(self) -> dict[str, Any]:
        append_index = -1
        last_record_digest: str | None = None
        ledger_prefix_hash: str | None = None
        for index, record in enumerate(self.iter_records()):
            append_index = record.append_index if record.append_index is not None else index
            last_record_digest = record.record_digest
            ledger_prefix_hash = record.ledger_prefix_hash or _ledger_prefix_hash(
                ledger_prefix_hash, record.record_digest
            )
        return {
            "append_index": append_index,
            "last_record_digest": last_record_digest,
            "ledger_prefix_hash": ledger_prefix_hash,
        }

    def _contains_identity(self, record_type: str, payload_digest: str) -> bool:
        return any(
            record.record_type == record_type and record.payload_digest == payload_digest
            for record in self.iter_records()
        )

    def _iter_raw_records(self) -> Iterator[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    raw = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise LedgerError(f"line {line_number}: invalid JSON: {exc}") from exc
                if not isinstance(raw, dict):
                    raise LedgerError(f"line {line_number}: record must be a JSON object")
                yield raw
