from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import AdapterOperationStatus, AdmissionDecision, BackendName


class ExternalMemoryRef(CMGLModel):
    """Binding between a CMGL memory version and an external backend record."""

    schema_version: Literal["cmgl.external_memory_ref.v1"] = "cmgl.external_memory_ref.v1"
    backend: BackendName | str
    external_id: str
    external_update_id: str | None = None
    cmgl_memory_id: str
    cmgl_memory_update_id: str | None = None
    authority_scope: str
    content_digest: str
    source_payload_digest: str
    namespace: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime

    @field_validator("content_digest", "source_payload_digest")
    @classmethod
    def validate_ref_digest(cls, value: str) -> str:
        return validate_digest(value)


class AdapterOperationReceipt(CMGLModel):
    """Receipt for an external adapter persistence or retrieval operation."""

    schema_version: Literal["cmgl.adapter_operation_receipt.v1"] = (
        "cmgl.adapter_operation_receipt.v1"
    )
    operation_id: str
    backend: BackendName | str
    operation: Literal["write", "update", "delete", "retrieve"]
    status: AdapterOperationStatus
    decision: AdmissionDecision
    cmgl_memory_id: str | None = None
    cmgl_memory_update_id: str | None = None
    external_ref: ExternalMemoryRef | None = None
    reason_codes: list[str] = Field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None
    receipt_digest: str
    timestamp: datetime

    @field_validator("receipt_digest")
    @classmethod
    def validate_receipt_digest(cls, value: str) -> str:
        return validate_digest(value)
