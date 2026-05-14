"""Shared utilities for safe optional memory-backend adapters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel

from cmgl.digest import sha256_digest
from cmgl.models import (
    BackendName,
    ContaminationLane,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
)
from cmgl.time import now_utc

_RESULT_KEYS = (
    "results",
    "memories",
    "data",
    "items",
    "episodes",
    "edges",
    "nodes",
    "facts",
)
_ID_KEYS = (
    "memory_id",
    "id",
    "uuid",
    "episode_uuid",
    "episode_id",
    "node_uuid",
    "edge_uuid",
    "source_node_uuid",
    "target_node_uuid",
)
_UPDATE_ID_KEYS = (
    "memory_update_id",
    "update_id",
    "revision_id",
    "version",
    "updated_at",
    "created_at",
)
_CONTENT_KEYS = (
    "content",
    "memory",
    "text",
    "fact",
    "episode_body",
    "body",
    "summary",
    "name",
)


def object_to_mapping(record: Any) -> Mapping[str, Any]:
    """Return a best-effort mapping view for common SDK result objects."""

    if isinstance(record, Mapping):
        return record
    if isinstance(record, BaseModel):
        return record.model_dump(mode="json")
    if is_dataclass(record):
        dataclass_values = {
            field: getattr(record, field) for field in getattr(record, "__dataclass_fields__", {})
        }
        return dataclass_values
    if hasattr(record, "_asdict"):
        value = record._asdict()
        if isinstance(value, Mapping):
            return value
    values: dict[str, Any] = {}
    for key in (*_ID_KEYS, *_UPDATE_ID_KEYS, *_CONTENT_KEYS, "metadata", "properties"):
        if hasattr(record, key):
            values[key] = getattr(record, key)
    return values


def extract_records(value: Any) -> list[Any]:
    """Flatten common SDK response wrappers into a list of result records."""

    if value is None:
        return []
    if isinstance(value, str | bytes):
        return [value]
    if isinstance(value, Sequence):
        if (
            len(value) == 2
            and isinstance(value[0], Sequence)
            and not isinstance(value[0], str | bytes)
        ):
            return list(value[0])
        return list(value)
    mapping = object_to_mapping(value)
    for key in _RESULT_KEYS:
        if key in mapping:
            nested = mapping[key]
            if isinstance(nested, Sequence) and not isinstance(nested, str | bytes):
                return list(nested)
            if nested is not None:
                return [nested]
    collected: list[Any] = []
    for key in ("episodes", "edges", "nodes", "communities"):
        nested = getattr(value, key, None)
        if isinstance(nested, Sequence) and not isinstance(nested, str | bytes):
            collected.extend(nested)
    if collected:
        return collected
    return [value]


def normalize_records(
    records: Any,
    *,
    backend: BackendName | str,
    event_type: MemoryEventType = MemoryEventType.MEMORY_RETRIEVE,
    lane: ContaminationLane = ContaminationLane.USER_CLAIM,
    authority_scope: str = "adapter:default",
    status: MemoryStatus = MemoryStatus.CERTIFIED,
    agent_id: str = "adapter",
    run_id: str = "adapter",
    trace_id: str = "adapter",
    checker_version: str = "cmgl.adapter.v1",
    trusted_results: bool = False,
) -> list[MemoryEvent]:
    """Normalize one SDK response or many records into CMGL memory events."""

    events: list[MemoryEvent] = []
    for index, record in enumerate(extract_records(records)):
        events.append(
            record_to_memory_event(
                record,
                backend=backend,
                event_type=event_type,
                lane=lane,
                authority_scope=authority_scope,
                status=status,
                agent_id=agent_id,
                run_id=run_id,
                trace_id=trace_id,
                checker_version=checker_version,
                fallback_index=index,
                trusted_result=trusted_results,
            )
        )
    return events


def record_to_memory_event(
    record: Any,
    *,
    backend: BackendName | str,
    event_type: MemoryEventType = MemoryEventType.MEMORY_RETRIEVE,
    lane: ContaminationLane = ContaminationLane.USER_CLAIM,
    authority_scope: str = "adapter:default",
    status: MemoryStatus = MemoryStatus.CERTIFIED,
    agent_id: str = "adapter",
    run_id: str = "adapter",
    trace_id: str = "adapter",
    checker_version: str = "cmgl.adapter.v1",
    fallback_index: int = 0,
    trusted_result: bool = False,
) -> MemoryEvent:
    """Create a deterministic `MemoryEvent` from a framework result record."""

    mapping = object_to_mapping(record)
    metadata = _coerce_mapping(_first_present(mapping, ("metadata", "payload", "properties")))
    for metadata_key in ("source_description", "group_ids", "reference_time"):
        if metadata_key in mapping and metadata_key not in metadata:
            metadata[metadata_key] = _jsonable(mapping[metadata_key])
    content = _extract_content(record, mapping)
    content_digest = str(mapping.get("content_digest") or sha256_digest(content))
    memory_id = str(_first_present(mapping, _ID_KEYS) or _stable_record_id(record, fallback_index))
    update_id = _first_present(mapping, _UPDATE_ID_KEYS)
    memory_update_id = str(update_id) if update_id is not None else f"{memory_id}:adapter"
    event_lane = _coerce_enum(mapping.get("lane"), ContaminationLane, lane)
    explicit_status = mapping.get("status") is not None
    explicit_source = _has_explicit_source_evidence(mapping, metadata)
    event_status = _coerce_enum(mapping.get("status"), MemoryStatus, status)
    if (
        not trusted_result
        and not explicit_status
        and not explicit_source
        and event_status
        not in {
            MemoryStatus.SUPERSEDED,
            MemoryStatus.CONTRADICTED,
            MemoryStatus.TOMBSTONED,
            MemoryStatus.QUARANTINED,
        }
    ):
        event_status = MemoryStatus.CANDIDATE
    event_time = _coerce_datetime(mapping.get("created_at") or mapping.get("timestamp"))
    source_hashes = _coerce_source_hashes(mapping, metadata, record)

    return MemoryEvent(
        trace_id=str(mapping.get("trace_id") or trace_id),
        run_id=str(mapping.get("run_id") or run_id),
        agent_id=str(mapping.get("agent_id") or agent_id),
        backend=backend,
        event_type=_coerce_enum(mapping.get("event_type"), MemoryEventType, event_type),
        memory_id=memory_id,
        memory_update_id=memory_update_id,
        content=content,
        content_digest=content_digest,
        source_event_hashes=source_hashes,
        lane=event_lane,
        provenance_depth=int(mapping.get("provenance_depth") or 0),
        valid_from=_coerce_datetime(mapping.get("valid_from") or mapping.get("reference_time")),
        valid_to=_coerce_datetime(mapping.get("valid_to")),
        authority_scope=str(mapping.get("authority_scope") or authority_scope),
        status=event_status,
        checker_version=str(mapping.get("checker_version") or checker_version),
        created_at=event_time or now_utc(),
        metadata=metadata,
    )


def _stable_record_id(record: Any, fallback_index: int) -> str:
    return sha256_digest({"record": _jsonable(record), "index": fallback_index})


def _extract_content(
    record: Any, mapping: Mapping[str, Any]
) -> str | dict[str, Any] | list[Any] | None:
    if isinstance(record, str):
        return record
    value = _first_present(mapping, _CONTENT_KEYS)
    if isinstance(value, str | list):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    if value is not None:
        return str(value)
    if mapping:
        return dict(mapping)
    return str(record)


def _first_present(mapping: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return {"value": _jsonable(value)}


def _coerce_enum(value: Any, enum_type: type[Enum], default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value))
    except ValueError:
        return default


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _coerce_source_hashes(
    mapping: Mapping[str, Any], metadata: Mapping[str, Any], record: Any
) -> list[str]:
    for source in (mapping, metadata):
        value = source.get("source_event_hashes")
        if isinstance(value, list):
            return [str(item) for item in value]
        digest = source.get("source_digest") or source.get("digest")
        if digest:
            return [_valid_digest_or_hash(str(digest))]
    return [sha256_digest(_jsonable(record))]


def _has_explicit_source_evidence(mapping: Mapping[str, Any], metadata: Mapping[str, Any]) -> bool:
    for source in (mapping, metadata):
        if source.get("source_event_hashes"):
            return True
        if source.get("source_digest") or source.get("digest"):
            return True
    return False


def _valid_digest_or_hash(value: str) -> str:
    if value.startswith("sha256:") and len(value.removeprefix("sha256:")) == 64:
        return value
    return sha256_digest(value)


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
