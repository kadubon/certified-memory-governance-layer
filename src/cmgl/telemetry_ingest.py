from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from cmgl.digest import sha256_digest
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import (
    GovernanceProfile,
    MemoryTelemetryEvent,
    MetricStatus,
    TelemetryEventOutcome,
    TelemetryIngestResult,
    TelemetryLineDiagnostic,
    TelemetryOutcomeStatus,
)
from cmgl.time import now_utc


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ingest_telemetry_jsonl(
    path: str | Path,
    *,
    ledger: AppendOnlyLedger | None = None,
    profile: GovernanceProfile = GovernanceProfile.STRICT,
    now: datetime | None = None,
) -> TelemetryIngestResult:
    check_time = _utc(now or now_utc())
    diagnostics: list[TelemetryLineDiagnostic] = []
    accepted = 0
    rejected = 0
    deduplicated = 0
    downgraded = 0
    event_ids: set[str] = set()
    last_seq_by_collector: dict[str, int] = {}
    outcomes: list[TelemetryEventOutcome] = []

    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            raw = json.loads(stripped)
            event = MemoryTelemetryEvent.model_validate(raw)
        except (json.JSONDecodeError, ValidationError, ValueError):
            rejected += 1
            diagnostics.append(
                TelemetryLineDiagnostic(
                    line=line_number,
                    event_id=None,
                    status=MetricStatus.INVALID.value,
                    reason_codes=["telemetry.event_invalid"],
                )
            )
            outcomes.append(
                TelemetryEventOutcome(
                    line=line_number,
                    event_id=None,
                    status=TelemetryOutcomeStatus.REJECTED,
                    reason_codes=["telemetry.event_invalid"],
                )
            )
            continue

        reason_codes: list[str] = []
        if event.event_id in event_ids:
            reason_codes.append("telemetry.duplicate_event_id")
            reason_codes.append("telemetry.event_deduplicated")
            deduplicated += 1
        event_ids.add(event.event_id)
        previous_seq = last_seq_by_collector.get(event.collector_id)
        if previous_seq is not None and event.collector_seq <= previous_seq:
            reason_codes.append("telemetry.ordering_violation")
        last_seq_by_collector[event.collector_id] = event.collector_seq
        skew_ms = abs((_utc(event.obs_time) - check_time).total_seconds() * 1000)
        if event.skew_budget_ms and skew_ms > event.skew_budget_ms:
            reason_codes.append("telemetry.skew_budget_exceeded")
        if any(ref.memory_update_id == "" for ref in event.memory_refs):
            reason_codes.append("telemetry.version_binding_missing")

        fail_closed = profile == GovernanceProfile.STRICT and bool(reason_codes)
        degraded = profile == GovernanceProfile.OPERATIONAL and bool(reason_codes)
        status = MetricStatus.INVALID if fail_closed else MetricStatus.VALID
        if fail_closed:
            rejected += 1
            outcome_status = TelemetryOutcomeStatus.REJECTED
        else:
            accepted += 1
            if degraded:
                downgraded += 1
                reason_codes.append("telemetry.event_downgraded")
                outcome_status = TelemetryOutcomeStatus.DOWNGRADED
            elif "telemetry.event_deduplicated" in reason_codes:
                outcome_status = TelemetryOutcomeStatus.DEDUPLICATED
            else:
                outcome_status = TelemetryOutcomeStatus.ACCEPTED
            if ledger is not None:
                ledger.append_with_receipt("telemetry_event", event)
        diagnostics.append(
            TelemetryLineDiagnostic(
                line=line_number,
                event_id=event.event_id,
                status=status.value,
                reason_codes=reason_codes,
            )
        )
        outcomes.append(
            TelemetryEventOutcome(
                line=line_number,
                event_id=event.event_id,
                status=outcome_status,
                reason_codes=reason_codes,
            )
        )

    body = {
        "schema_version": "cmgl.telemetry_ingest_result.v1",
        "profile": profile,
        "accepted_events": accepted,
        "rejected_events": rejected,
        "deduplicated_events": deduplicated,
        "downgraded_events": downgraded,
        "diagnostics": diagnostics,
        "outcomes": outcomes,
        "timestamp": now_utc(),
    }
    return TelemetryIngestResult(**body, result_digest=sha256_digest(body))
