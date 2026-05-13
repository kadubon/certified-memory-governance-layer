from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel

from cmgl.adapters.common import object_to_mapping
from cmgl.digest import sha256_digest
from cmgl.lifecycle import make_quarantine_record
from cmgl.models import (
    AdapterOperationReceipt,
    AdapterOperationStatus,
    AdmissionDecision,
    BackendName,
    ExternalMemoryRef,
    GovernanceReceiptBundle,
    MemoryEvent,
)
from cmgl.pipeline import PromotionPipelineResult
from cmgl.time import now_utc

_EXTERNAL_ID_KEYS = (
    "id",
    "memory_id",
    "uuid",
    "episode_uuid",
    "episode_id",
    "node_uuid",
    "edge_uuid",
    "source_node_uuid",
    "target_node_uuid",
)
_EXTERNAL_UPDATE_KEYS = (
    "memory_update_id",
    "update_id",
    "revision_id",
    "version",
    "updated_at",
    "created_at",
)


def external_ref_from_result(
    result: Any,
    *,
    event: MemoryEvent,
    backend: BackendName | str,
    namespace: str | None = None,
    external_id: str | None = None,
    external_update_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ExternalMemoryRef:
    """Create a stable CMGL-to-external-memory binding from an SDK result."""

    mapping = object_to_mapping(result)
    payload_digest = sha256_digest(_jsonable(result))
    resolved_external_id = external_id or _first_present(mapping, _EXTERNAL_ID_KEYS)
    resolved_update_id = external_update_id or _first_present(mapping, _EXTERNAL_UPDATE_KEYS)
    body = {
        "schema_version": "cmgl.external_memory_ref.v1",
        "backend": backend,
        "external_id": str(resolved_external_id or payload_digest),
        "external_update_id": None if resolved_update_id is None else str(resolved_update_id),
        "cmgl_memory_id": event.memory_id,
        "cmgl_memory_update_id": event.memory_update_id,
        "authority_scope": event.authority_scope,
        "content_digest": event.content_digest,
        "source_payload_digest": payload_digest,
        "namespace": namespace,
        "metadata": dict(metadata or {}),
        "timestamp": now_utc(),
    }
    return ExternalMemoryRef(**body)


def make_adapter_operation_receipt(
    *,
    backend: BackendName | str,
    operation: Literal["write", "update", "delete", "retrieve"],
    event: MemoryEvent | None = None,
    status: AdapterOperationStatus,
    decision: AdmissionDecision,
    external_ref: ExternalMemoryRef | None = None,
    reason_codes: list[str] | None = None,
    error: BaseException | None = None,
    timestamp: datetime | None = None,
) -> AdapterOperationReceipt:
    """Build a digest-bound adapter operation receipt."""

    body = {
        "schema_version": "cmgl.adapter_operation_receipt.v1",
        "operation_id": f"adapter-op:{uuid4()}",
        "backend": backend,
        "operation": operation,
        "status": status,
        "decision": decision,
        "cmgl_memory_id": None if event is None else event.memory_id,
        "cmgl_memory_update_id": None if event is None else event.memory_update_id,
        "external_ref": external_ref,
        "reason_codes": list(reason_codes or []),
        "error_type": None if error is None else type(error).__name__,
        "error_message": None if error is None else _safe_error_message(error),
        "timestamp": timestamp or now_utc(),
    }
    return AdapterOperationReceipt(**body, receipt_digest=sha256_digest(body))


def success_reason(operation: Literal["write", "update", "delete", "retrieve"]) -> str:
    return f"adapter.external_{operation}_succeeded"


def append_adapter_receipt(
    layer: Any,
    receipt: AdapterOperationReceipt,
    *,
    quarantine_on_failure: bool = True,
) -> str | None:
    """Append adapter operation evidence and optionally quarantine failures."""

    layer.ledger.append_with_receipt(
        "adapter_operation_receipt",
        receipt,
        persist_receipt=layer.config.ledger.persist_append_receipts,
    )
    if receipt.status != AdapterOperationStatus.FAILED or not quarantine_on_failure:
        return None
    quarantine = make_quarantine_record(
        target=receipt,
        target_type="adapter_operation_receipt",
        reason_codes=["adapter.external_persistence_failed"],
    )
    record, _ = layer.ledger.append_with_receipt(
        "quarantine_record",
        quarantine,
        persist_receipt=layer.config.ledger.persist_append_receipts,
    )
    return cast(str, record.record_digest)


def bundle_with_adapter_receipt(
    layer: Any,
    result: PromotionPipelineResult,
    *,
    adapter_receipt: AdapterOperationReceipt,
    backend_result: Any | None = None,
    quarantine_record_digest: str | None = None,
) -> GovernanceReceiptBundle:
    bundle = GovernanceReceiptBundle.model_validate(
        layer.receipt_bundle(
            result,
            backend_result=backend_result,
            adapter_operation_receipt=adapter_receipt,
        )
    )
    if quarantine_record_digest is None:
        return bundle
    body = bundle.model_dump()
    body["quarantine_record_digest"] = quarantine_record_digest
    body.pop("bundle_digest", None)
    return GovernanceReceiptBundle(**body, bundle_digest=sha256_digest(body))


def has_successful_binding(layer: Any, memory_id: str) -> bool:
    """Return true when the ledger has a prior succeeded external binding."""

    for record in layer.ledger.iter_records():
        if record.record_type != "adapter_operation_receipt":
            continue
        payload = record.payload
        if not isinstance(payload, Mapping):
            continue
        if payload.get("status") != AdapterOperationStatus.SUCCEEDED.value:
            continue
        external_ref = payload.get("external_ref")
        if isinstance(external_ref, Mapping) and external_ref.get("cmgl_memory_id") == memory_id:
            return True
    return False


def _first_present(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _safe_error_message(error: BaseException) -> str:
    message = str(error).replace("\n", " ").strip()
    if not message:
        return type(error).__name__
    return message[:240]
