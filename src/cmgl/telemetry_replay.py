from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from cmgl.digest import sha256_digest
from cmgl.models import (
    GovernanceProfile,
    MemoryStatus,
    MemoryTelemetryEvent,
    MetricResult,
    MetricStatus,
    RationalValue,
    TelemetryCorrectPayload,
    TelemetryEventOutcome,
    TelemetryEventType,
    TelemetryOutcomeStatus,
    TelemetryStateReplay,
    VersionedMemoryRef,
)
from cmgl.telemetry import telemetry_order_key
from cmgl.time import now_utc


def replay_telemetry_jsonl(
    path: str | Path,
    *,
    profile: GovernanceProfile = GovernanceProfile.STRICT,
    now: datetime | None = None,
) -> TelemetryStateReplay:
    events: list[tuple[int, MemoryTelemetryEvent]] = []
    outcomes: list[TelemetryEventOutcome] = []
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            raw = json.loads(stripped)
            events.append((line_number, MemoryTelemetryEvent.model_validate(raw)))
        except (json.JSONDecodeError, ValidationError, ValueError):
            outcomes.append(
                TelemetryEventOutcome(
                    line=line_number,
                    event_id=None,
                    status=TelemetryOutcomeStatus.REJECTED,
                    reason_codes=["telemetry.event_invalid"],
                )
            )
    return replay_telemetry_events(events, profile=profile, initial_outcomes=outcomes, now=now)


def replay_telemetry_events(
    events: list[tuple[int, MemoryTelemetryEvent]],
    *,
    profile: GovernanceProfile = GovernanceProfile.STRICT,
    initial_outcomes: list[TelemetryEventOutcome] | None = None,
    now: datetime | None = None,
) -> TelemetryStateReplay:
    check_time = _utc(now or now_utc())
    sorted_events = sorted(events, key=lambda item: telemetry_order_key(item[1]))
    outcomes: list[TelemetryEventOutcome] = list(initial_outcomes or [])
    seen_event_ids: set[str] = set()
    current: dict[str, VersionedMemoryRef] = {}
    declared_ids: set[str] = set()
    by_event_id: dict[str, MemoryTelemetryEvent] = {}
    duplicate_count = 0
    missing_declaration = 0
    version_mismatch = 0
    read_count = 0
    use_count = 0
    stale_exposure = 0
    zombie_exposure = 0
    supersedence_exposure = 0
    risk_exposure = 0
    correction_latencies: list[float] = []

    for line, event in sorted_events:
        if event.event_id in seen_event_ids:
            duplicate_count += 1
            outcomes.append(
                TelemetryEventOutcome(
                    line=line,
                    event_id=event.event_id,
                    status=TelemetryOutcomeStatus.DEDUPLICATED,
                    reason_codes=["telemetry.event_deduplicated"],
                )
            )
            continue
        seen_event_ids.add(event.event_id)
        reason_codes: list[str] = []
        refs = _event_refs(event)

        if (
            event.event_type == TelemetryEventType.MEM_WRITE
            or event.event_type == TelemetryEventType.MEM_REPLACE
        ):
            for ref in refs:
                current[ref.memory_id] = ref
                declared_ids.add(ref.memory_id)
        elif event.event_type == TelemetryEventType.MEM_DELETE:
            for ref in refs:
                reason_codes.extend(_check_declared(ref, current))
                current.pop(ref.memory_id, None)
        elif event.event_type in {
            TelemetryEventType.MEM_READ,
            TelemetryEventType.MEM_USE,
            TelemetryEventType.MEM_VERIFY,
            TelemetryEventType.MEM_CORRECT,
            TelemetryEventType.MEM_RETRIEVE,
        }:
            if event.event_type == TelemetryEventType.MEM_READ:
                read_count += 1
            if event.event_type == TelemetryEventType.MEM_USE:
                use_count += 1
            for ref in refs:
                ref_reasons = _check_declared(ref, current)
                reason_codes.extend(ref_reasons)
                if "telemetry.missing_declaration" in ref_reasons:
                    missing_declaration += 1
                if "telemetry.version_mismatch" in ref_reasons:
                    version_mismatch += 1
                if ref.status == MemoryStatus.TOMBSTONED:
                    zombie_exposure += 1
                if ref.status == MemoryStatus.SUPERSEDED:
                    supersedence_exposure += 1
                if ref.status in {
                    MemoryStatus.SUPERSEDED,
                    MemoryStatus.CONTRADICTED,
                    MemoryStatus.TOMBSTONED,
                    MemoryStatus.QUARANTINED,
                }:
                    stale_exposure += 1
                if ref.status not in {MemoryStatus.CERTIFIED, MemoryStatus.ADMISSIBLE, None}:
                    risk_exposure += 1
            correction_of = _correction_of(event)
            if correction_of is not None and correction_of in by_event_id:
                delta = _utc(event.obs_time) - _utc(by_event_id[correction_of].obs_time)
                correction_latencies.append(max(delta.total_seconds(), 0.0))

        skew_ms = abs((_utc(event.obs_time) - check_time).total_seconds() * 1000)
        if event.skew_budget_ms and skew_ms > event.skew_budget_ms:
            reason_codes.append("telemetry.skew_budget_exceeded")

        outcome_status = _outcome_status(profile, reason_codes)
        outcomes.append(
            TelemetryEventOutcome(
                line=line,
                event_id=event.event_id,
                status=outcome_status,
                reason_codes=sorted(set(reason_codes)),
            )
        )
        by_event_id[event.event_id] = event

    timestamp = now_utc()
    rational_metrics = {
        "read_use_uptake": _ratio(use_count, read_count),
        "stale_exposure": _ratio(stale_exposure, len(seen_event_ids)),
        "risk_exposure": _ratio(risk_exposure, len(seen_event_ids)),
        "zombie_exposure": _ratio(zombie_exposure, len(seen_event_ids)),
        "supersedence_exposure": _ratio(supersedence_exposure, len(seen_event_ids)),
    }
    metrics = [
        _metric("duplicate_event_id", duplicate_count, "telemetry.duplicate_event_id", timestamp),
        _metric(
            "missing_declaration",
            missing_declaration,
            "telemetry.missing_declaration",
            timestamp,
        ),
        _metric("version_mismatch", version_mismatch, "telemetry.version_mismatch", timestamp),
        _metric("stale_exposure", stale_exposure, "telemetry.stale_exposure_detected", timestamp),
        _metric("risk_exposure", risk_exposure, "telemetry.risk_exposure_detected", timestamp),
        _metric("zombie_exposure", zombie_exposure, "telemetry.zombie_delay_detected", timestamp),
        _metric(
            "supersedence_exposure",
            supersedence_exposure,
            "telemetry.supersedence_delay_detected",
            timestamp,
        ),
        MetricResult(
            metric_name="correction_latency_seconds",
            status=MetricStatus.NOT_COMPUTABLE if not correction_latencies else MetricStatus.VALID,
            value=max(correction_latencies, default=0.0),
            reason_codes=[]
            if not correction_latencies
            else ["telemetry.correction_latency_observed"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="read_use_uptake",
            status=MetricStatus.NOT_COMPUTABLE if read_count == 0 else MetricStatus.VALID,
            value=None if read_count == 0 else rational_metrics["read_use_uptake"].value,
            numerator=use_count,
            denominator=read_count,
            timestamp=timestamp,
        ),
    ]
    body = {
        "schema_version": "cmgl.telemetry_state_replay.v1",
        "profile": profile,
        "profile_level": _profile_level(profile),
        "metrics": metrics,
        "rational_metrics": rational_metrics,
        "outcomes": outcomes,
        "declared_memory_ids": sorted(declared_ids),
        "current_memory_ids": sorted(current),
        "timestamp": timestamp,
    }
    return TelemetryStateReplay(**body, replay_digest=sha256_digest(body))


def _event_refs(event: MemoryTelemetryEvent) -> list[VersionedMemoryRef]:
    if event.memory_refs:
        return event.memory_refs
    payload = event.payload
    refs = getattr(payload, "memory_refs", None)
    if isinstance(refs, list):
        return refs
    ref = getattr(payload, "memory_ref", None)
    if isinstance(ref, VersionedMemoryRef):
        return [ref]
    new_ref = getattr(payload, "new_ref", None)
    if isinstance(new_ref, VersionedMemoryRef):
        return [new_ref]
    old_ref = getattr(payload, "old_ref", None)
    if isinstance(old_ref, VersionedMemoryRef):
        return [old_ref]
    return []


def _check_declared(
    ref: VersionedMemoryRef,
    current: dict[str, VersionedMemoryRef],
) -> list[str]:
    known = current.get(ref.memory_id)
    if known is None:
        return ["telemetry.missing_declaration"]
    if known.memory_update_id != ref.memory_update_id:
        return ["telemetry.version_mismatch"]
    return []


def _correction_of(event: MemoryTelemetryEvent) -> str | None:
    if isinstance(event.payload, TelemetryCorrectPayload):
        return event.payload.correction_of_event_id
    value = event.metadata.get("correction_of_event_id")
    return value if isinstance(value, str) else None


def _outcome_status(
    profile: GovernanceProfile,
    reason_codes: list[str],
) -> TelemetryOutcomeStatus:
    if not reason_codes:
        return TelemetryOutcomeStatus.ACCEPTED
    if profile == GovernanceProfile.STRICT:
        return TelemetryOutcomeStatus.REJECTED
    if profile == GovernanceProfile.OPERATIONAL:
        return TelemetryOutcomeStatus.DOWNGRADED
    return TelemetryOutcomeStatus.ACCEPTED


def _metric(
    name: str,
    value: int,
    reason_code: str,
    timestamp: datetime,
) -> MetricResult:
    return MetricResult(
        metric_name=name,
        status=MetricStatus.VALID,
        value=value,
        reason_codes=[] if value == 0 else [reason_code],
        timestamp=timestamp,
    )


def _ratio(numerator: int, denominator: int) -> RationalValue:
    return RationalValue(numerator=numerator, denominator=max(denominator, 1))


def _profile_level(profile: GovernanceProfile) -> str:
    return {
        GovernanceProfile.STRICT: "P0",
        GovernanceProfile.OPERATIONAL: "P1",
        GovernanceProfile.LEGACY: "P2",
    }[profile]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
