from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest


class LedgerAppendReceipt(CMGLModel):
    schema_version: Literal["cmgl.ledger_append_receipt.v1"] = "cmgl.ledger_append_receipt.v1"
    append_index: int = Field(ge=0)
    record_digest: str
    ledger_prefix_hash: str
    payload_digest: str
    duplicate: bool = False
    receipt_digest: str
    timestamp: datetime

    @field_validator("record_digest", "ledger_prefix_hash", "payload_digest", "receipt_digest")
    @classmethod
    def validate_ledger_append_digest(cls, value: str) -> str:
        return validate_digest(value)


class LedgerLineStatus(CMGLModel):
    schema_version: Literal["cmgl.ledger_line_status.v1"] = "cmgl.ledger_line_status.v1"
    line: int = Field(ge=1)
    statuses: list[str] = Field(default_factory=list)
    record_digest: str | None = None
    payload_digest: str | None = None

    @field_validator("record_digest", "payload_digest")
    @classmethod
    def validate_line_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)


class LedgerIntegrityReceipt(CMGLModel):
    schema_version: Literal["cmgl.ledger_integrity_receipt.v1"] = "cmgl.ledger_integrity_receipt.v1"
    ok: bool
    records_checked: int = Field(ge=0)
    ledger_prefix_hash: str | None = None
    last_record_digest: str | None = None
    line_statuses: list[LedgerLineStatus] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    receipt_digest: str
    timestamp: datetime

    @field_validator("ledger_prefix_hash", "last_record_digest", "receipt_digest")
    @classmethod
    def validate_integrity_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)


class SchemaMigrationRecord(CMGLModel):
    schema_version: Literal["cmgl.schema_migration_record.v1"] = "cmgl.schema_migration_record.v1"
    from_schema_epoch: str
    to_schema_epoch: str
    migration_id: str
    reason_codes: list[str] = Field(default_factory=list)
    migration_digest: str
    timestamp: datetime

    @field_validator("migration_digest")
    @classmethod
    def validate_migration_digest(cls, value: str) -> str:
        return validate_digest(value)


class DuplicatePolicyReceipt(CMGLModel):
    schema_version: Literal["cmgl.duplicate_policy_receipt.v1"] = "cmgl.duplicate_policy_receipt.v1"
    duplicate_policy: Literal["allow", "reject", "quarantine"]
    record_type: str
    payload_digest: str
    duplicate: bool
    reason_codes: list[str] = Field(default_factory=list)
    receipt_digest: str
    timestamp: datetime

    @field_validator("payload_digest", "receipt_digest")
    @classmethod
    def validate_duplicate_policy_digest(cls, value: str) -> str:
        return validate_digest(value)
