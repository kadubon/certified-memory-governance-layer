from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from cmgl.digest import sha256_digest
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import (
    ContaminationAuditReport,
    ContaminationContext,
    ContaminationLane,
    ContaminationStateReplay,
    GovernanceProfile,
    MemoryEvent,
    MemoryStatus,
    MemoryTelemetryEvent,
    MetricResult,
    MetricStatus,
    TelemetryAuditReport,
    TelemetryEventOutcome,
    TelemetryEventType,
    TelemetryOutcomeStatus,
    TelemetryReplayReport,
)
from cmgl.time import now_utc


class ContaminationPolicy:
    def __init__(self, *, require_explicit_shared_context: bool = True) -> None:
        self.require_explicit_shared_context = require_explicit_shared_context

    def evaluate(
        self,
        events: list[MemoryEvent],
        *,
        context: ContaminationContext | None = None,
    ) -> ContaminationAuditReport:
        active_context = context if context is not None else ContaminationContext()
        if self.require_explicit_shared_context and context is None:
            active_context = ContaminationContext()
        return contamination_diagnostics(events, context=active_context)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def stale_use_report(ledger: AppendOnlyLedger, *, now: datetime | None = None) -> dict[str, object]:
    check_time = _utc(now or now_utc())
    stale_ids: list[str] = []
    retrieval_blocks = 0
    for record in ledger.iter_records():
        if record.record_type == "memory_event":
            event = MemoryEvent.model_validate(record.payload)
            if event.valid_to is not None and _utc(event.valid_to) < check_time:
                stale_ids.append(event.memory_id)
        elif record.record_type == "retrieval_decision":
            blocked = record.payload.get("blocked_hits", [])
            if isinstance(blocked, list):
                retrieval_blocks += sum(
                    1
                    for item in blocked
                    if isinstance(item, dict) and "valid_to.expired" in str(item.get("reason", ""))
                )
    return {
        "stale_memory_ids": stale_ids,
        "stale_memory_count": len(stale_ids),
        "retrieval_blocks": retrieval_blocks,
    }


def contamination_report(ledger: AppendOnlyLedger) -> dict[str, object]:
    lane_counts: Counter[str] = Counter()
    blocked_fact_lanes = {
        ContaminationLane.MODEL_INFERENCE.value,
        ContaminationLane.REGENERATED_SUMMARY.value,
        ContaminationLane.SYNTHETIC_EVAL.value,
    }
    risky_ids: list[str] = []
    events: list[MemoryEvent] = []
    for record in ledger.iter_records():
        if record.record_type != "memory_event":
            continue
        event = MemoryEvent.model_validate(record.payload)
        events.append(event)
        lane_counts[event.lane.value] += 1
        if event.lane.value in blocked_fact_lanes:
            risky_ids.append(event.memory_id)
    diagnostics = contamination_diagnostics(events)
    return {
        "lane_counts": dict(lane_counts),
        "blocked_fact_lane_memory_ids": risky_ids,
        "discounted_risk_score": diagnostics.discounted_risk_score,
        "report_digest": diagnostics.report_digest,
    }


def contamination_diagnostics(
    events: list[MemoryEvent],
    *,
    context: ContaminationContext | None = None,
) -> ContaminationAuditReport:
    lane_counts: Counter[str] = Counter()
    broker_counts: Counter[str] = Counter()
    context = context or ContaminationContext()
    explicit_shared = set(context.shared_memory_ids) | set(context.cross_agent_memory_ids)
    shared: list[str] = []
    seen_shared: set[str] = set()
    contradiction_reserve = 0
    realized_fork_count = 0
    risk_weights = {
        ContaminationLane.USER_CLAIM.value: 0.2,
        ContaminationLane.TOOL_OBSERVATION.value: 0.1,
        ContaminationLane.EXTERNAL_DOC.value: 0.25,
        ContaminationLane.MODEL_INFERENCE.value: 0.9,
        ContaminationLane.SUMMARY.value: 0.6,
        ContaminationLane.REGENERATED_SUMMARY.value: 0.85,
        ContaminationLane.SYNTHETIC_EVAL.value: 0.8,
        ContaminationLane.POLICY_MEMORY.value: 0.4,
    }
    lane_scores: dict[str, float] = {lane: 0.0 for lane in risk_weights}
    total = 0.0
    for event in events:
        lane = event.lane.value
        lane_counts[lane] += 1
        broker_counts[event.agent_id] += 1
        if event.memory_id in explicit_shared and event.memory_id not in seen_shared:
            shared.append(event.memory_id)
            seen_shared.add(event.memory_id)
        if isinstance(event.content, dict) and "forked_from" in event.content:
            realized_fork_count += 1
        if event.status == MemoryStatus.CONTRADICTED:
            contradiction_reserve += 1
        depth_discount = 1.0 / (1.0 + float(event.provenance_depth))
        score = risk_weights.get(lane, 0.5) * depth_discount
        lane_scores[lane] = lane_scores.get(lane, 0.0) + score
        total += score
    body = {
        "schema_version": "cmgl.contamination_audit_report.v1",
        "lane_counts": dict(lane_counts),
        "lane_risk_scores": lane_scores,
        "discounted_risk_score": total,
        "broker_concentration": dict(broker_counts),
        "cross_agent_shared_memory_ids": shared,
        "contradiction_reserve": contradiction_reserve,
        "max_positive_excursion": max(lane_scores.values(), default=0.0),
        "realized_fork_count": realized_fork_count,
        "post_fork_recovery_quality": None if realized_fork_count == 0 else 1.0 / (1.0 + total),
        "timestamp": now_utc(),
    }
    return ContaminationAuditReport(**body, report_digest=sha256_digest(body))


def contamination_state_replay(
    events: list[MemoryEvent],
    *,
    context: ContaminationContext | None = None,
    reserve_floor: int = 1,
) -> ContaminationStateReplay:
    ordered = sorted(events, key=lambda event: event.created_at)
    report = contamination_diagnostics(ordered, context=context)
    reserve = 0
    low_reserve_residence = 0
    for event in ordered:
        if event.status == MemoryStatus.CONTRADICTED:
            reserve += 1
        elif reserve <= reserve_floor:
            low_reserve_residence += 1
    body = {
        "schema_version": "cmgl.contamination_state_replay.v1",
        "events_replayed": len(ordered),
        "contradiction_reserve": report.contradiction_reserve,
        "max_positive_excursion": report.max_positive_excursion,
        "low_reserve_residence": low_reserve_residence,
        "realized_fork_count": report.realized_fork_count,
        "post_fork_recovery_quality": report.post_fork_recovery_quality,
        "cross_agent_shared_memory_ids": report.cross_agent_shared_memory_ids,
        "timestamp": now_utc(),
    }
    return ContaminationStateReplay(**body, replay_digest=sha256_digest(body))


def telemetry_audit_report(
    ledger: AppendOnlyLedger,
    *,
    now: datetime | None = None,
    profile: GovernanceProfile = GovernanceProfile.STRICT,
) -> TelemetryAuditReport:
    check_time = _utc(now or now_utc())
    status_by_ref: dict[tuple[str, str], MemoryEvent] = {}
    telemetry_events: list[MemoryTelemetryEvent] = []

    for record in ledger.iter_records():
        if record.record_type == "memory_event":
            event = MemoryEvent.model_validate(record.payload)
            if event.memory_update_id is not None:
                status_by_ref[(event.memory_id, event.memory_update_id)] = event
        elif record.record_type == "telemetry_event":
            telemetry_events.append(MemoryTelemetryEvent.model_validate(record.payload))

    event_ids: set[str] = set()
    duplicate_event_ids = 0
    ordering_violations = 0
    skew_budget_violations = 0
    correction_latencies: list[float] = []
    verify_deadline_misses = 0
    by_collector: dict[str, MemoryTelemetryEvent] = {}
    by_event_id: dict[str, MemoryTelemetryEvent] = {}

    for telemetry in sorted(telemetry_events, key=lambda item: item.obs_time):
        if telemetry.event_id in event_ids:
            duplicate_event_ids += 1
        event_ids.add(telemetry.event_id)
        previous = by_collector.get(telemetry.collector_id)
        if previous is not None and telemetry.collector_seq <= previous.collector_seq:
            ordering_violations += 1
        by_collector[telemetry.collector_id] = telemetry
        by_event_id[telemetry.event_id] = telemetry
        skew_ms = abs((_utc(telemetry.obs_time) - check_time).total_seconds() * 1000)
        if telemetry.skew_budget_ms and skew_ms > telemetry.skew_budget_ms:
            skew_budget_violations += 1

    stale_use = 0
    zombie_use = 0
    superseded_use = 0
    read_count = 0
    use_count = 0
    write_count = 0
    verified_write_count = 0
    for telemetry in telemetry_events:
        if telemetry.event_type == TelemetryEventType.MEM_WRITE:
            write_count += 1
            for ref in telemetry.memory_refs:
                written_event = status_by_ref.get((ref.memory_id, ref.memory_update_id))
                if written_event is not None and written_event.status in {
                    MemoryStatus.CERTIFIED,
                    MemoryStatus.ADMISSIBLE,
                }:
                    verified_write_count += 1
        if telemetry.event_type not in {TelemetryEventType.MEM_USE, TelemetryEventType.MEM_READ}:
            if telemetry.event_type == TelemetryEventType.MEM_CORRECT:
                correction_of = telemetry.metadata.get("correction_of_event_id")
                if isinstance(correction_of, str) and correction_of in by_event_id:
                    delta = _utc(telemetry.obs_time) - _utc(by_event_id[correction_of].obs_time)
                    correction_latencies.append(max(delta.total_seconds(), 0.0))
            if telemetry.event_type == TelemetryEventType.MEM_VERIFY:
                deadline = telemetry.metadata.get("verify_deadline")
                if isinstance(deadline, str):
                    try:
                        deadline_time = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                    except ValueError:
                        deadline_time = None
                    if deadline_time is not None and _utc(telemetry.obs_time) > _utc(deadline_time):
                        verify_deadline_misses += 1
            continue
        if telemetry.event_type == TelemetryEventType.MEM_READ:
            read_count += 1
        if telemetry.event_type == TelemetryEventType.MEM_USE:
            use_count += 1
        for ref in telemetry.memory_refs:
            used_event = status_by_ref.get((ref.memory_id, ref.memory_update_id))
            if used_event is None:
                continue
            if used_event.valid_to is not None and _utc(used_event.valid_to) < check_time:
                stale_use += 1
            if used_event.status == MemoryStatus.TOMBSTONED:
                zombie_use += 1
            if used_event.status == MemoryStatus.SUPERSEDED:
                superseded_use += 1

    timestamp = now_utc()
    total_reads_and_uses = read_count + use_count
    uptake = 0.0 if read_count == 0 else use_count / read_count
    max_correction_latency = max(correction_latencies, default=0.0)
    metrics = [
        MetricResult(
            metric_name="memory_read_events",
            status=MetricStatus.VALID,
            value=read_count,
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="memory_use_events",
            status=MetricStatus.VALID,
            value=use_count,
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="read_use_uptake",
            status=MetricStatus.NOT_COMPUTABLE if read_count == 0 else MetricStatus.VALID,
            value=uptake,
            numerator=use_count,
            denominator=read_count,
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="stale_use",
            status=MetricStatus.VALID,
            value=stale_use,
            reason_codes=[] if stale_use == 0 else ["telemetry.stale_use_detected"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="zombie_use_after_tombstone",
            status=MetricStatus.VALID,
            value=zombie_use,
            reason_codes=[] if zombie_use == 0 else ["telemetry.zombie_use_detected"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="superseded_use",
            status=MetricStatus.VALID,
            value=superseded_use,
            reason_codes=[] if superseded_use == 0 else ["telemetry.superseded_use_detected"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="duplicate_event_id",
            status=MetricStatus.VALID,
            value=duplicate_event_ids,
            reason_codes=[] if duplicate_event_ids == 0 else ["telemetry.duplicate_event_id"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="collector_ordering_violation",
            status=MetricStatus.VALID,
            value=ordering_violations,
            reason_codes=[] if ordering_violations == 0 else ["telemetry.ordering_violation"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="skew_budget_violation",
            status=MetricStatus.VALID,
            value=skew_budget_violations,
            reason_codes=[] if skew_budget_violations == 0 else ["telemetry.skew_budget_exceeded"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="correction_latency_seconds",
            status=MetricStatus.NOT_COMPUTABLE if not correction_latencies else MetricStatus.VALID,
            value=max_correction_latency,
            reason_codes=[]
            if not correction_latencies
            else ["telemetry.correction_latency_observed"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="verify_deadline_miss",
            status=MetricStatus.VALID,
            value=verify_deadline_misses,
            reason_codes=[]
            if verify_deadline_misses == 0
            else ["telemetry.verify_deadline_missed"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="stale_exposure",
            status=MetricStatus.VALID,
            value=stale_use,
            reason_codes=[] if stale_use == 0 else ["telemetry.stale_exposure_detected"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="zombie_delay",
            status=MetricStatus.VALID,
            value=zombie_use,
            reason_codes=[] if zombie_use == 0 else ["telemetry.zombie_delay_detected"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="supersedence_delay",
            status=MetricStatus.VALID,
            value=superseded_use,
            reason_codes=[] if superseded_use == 0 else ["telemetry.supersedence_delay_detected"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="verified_write_fraction",
            status=MetricStatus.NOT_COMPUTABLE if write_count == 0 else MetricStatus.VALID,
            value=None if write_count == 0 else verified_write_count / write_count,
            numerator=verified_write_count,
            denominator=write_count,
            reason_codes=[] if write_count == 0 else ["telemetry.verified_write_fraction_observed"],
            timestamp=timestamp,
        ),
    ]
    body = {
        "schema_version": "cmgl.telemetry_audit_report.v1",
        "profile": profile,
        "metrics": metrics,
        "telemetry_events": len(telemetry_events),
        "read_use_events": total_reads_and_uses,
        "timestamp": now_utc(),
    }
    return TelemetryAuditReport(**body, report_digest=sha256_digest(body))


def telemetry_replay_report(
    ledger: AppendOnlyLedger,
    *,
    now: datetime | None = None,
    profile: GovernanceProfile = GovernanceProfile.STRICT,
) -> TelemetryReplayReport:
    audit = telemetry_audit_report(ledger, now=now, profile=profile)
    telemetry_events: list[MemoryTelemetryEvent] = []
    for record in ledger.iter_records():
        if record.record_type == "telemetry_event":
            telemetry_events.append(MemoryTelemetryEvent.model_validate(record.payload))
    seen: set[str] = set()
    outcomes: list[TelemetryEventOutcome] = []
    for line, telemetry in enumerate(
        sorted(telemetry_events, key=lambda item: item.obs_time), start=1
    ):
        if telemetry.event_id in seen:
            outcomes.append(
                TelemetryEventOutcome(
                    line=line,
                    event_id=telemetry.event_id,
                    status=TelemetryOutcomeStatus.DEDUPLICATED,
                    reason_codes=["telemetry.event_deduplicated"],
                )
            )
        else:
            outcomes.append(
                TelemetryEventOutcome(
                    line=line,
                    event_id=telemetry.event_id,
                    status=TelemetryOutcomeStatus.ACCEPTED,
                    reason_codes=[],
                )
            )
        seen.add(telemetry.event_id)
    body = {
        "schema_version": "cmgl.telemetry_replay_report.v1",
        "profile": profile,
        "metrics": audit.metrics,
        "outcomes": outcomes,
        "timestamp": now_utc(),
    }
    return TelemetryReplayReport(**body, replay_digest=sha256_digest(body))
