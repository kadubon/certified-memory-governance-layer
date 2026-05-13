from __future__ import annotations

from dataclasses import dataclass

from cmgl.digest import sha256_digest
from cmgl.models import (
    AdmissionDecision,
    MemoryCandidate,
    MemoryEvent,
    PromotionReceipt,
    RetrievalDecision,
)
from cmgl.policy import AdmissionPolicy
from cmgl.time import now_utc


def candidate_from_event(event: MemoryEvent) -> MemoryCandidate:
    normalized = event.content if event.content is not None else event.content_digest
    version = event.memory_update_id or "unversioned"
    return MemoryCandidate(
        candidate_id=f"candidate:{event.memory_id}:{version}",
        event=event,
        normalized_content_digest=sha256_digest(normalized),
    )


@dataclass(frozen=True)
class RetrievalFilterResult:
    decision: RetrievalDecision
    admitted_events: list[MemoryEvent]
    receipts: list[PromotionReceipt]


def filter_retrieval(
    query: str,
    events: list[MemoryEvent],
    *,
    policy: AdmissionPolicy | None = None,
    as_fact: bool = True,
) -> RetrievalFilterResult:
    active_policy = policy or AdmissionPolicy()
    receipts: list[PromotionReceipt] = []
    admitted: list[MemoryEvent] = []
    blocked_hits: list[dict[str, str]] = []

    for event in events:
        receipt = active_policy.evaluate(candidate_from_event(event), as_fact=as_fact)
        receipts.append(receipt)
        if receipt.decision == AdmissionDecision.ADMIT:
            admitted.append(event)
        else:
            blocked_hits.append(
                {
                    "memory_id": event.memory_id,
                    "memory_update_id": event.memory_update_id or "",
                    "reason": ",".join(receipt.reason_codes),
                }
            )

    context_digest = sha256_digest(
        [
            {
                "memory_id": event.memory_id,
                "content_digest": event.content_digest,
            }
            for event in admitted
        ]
    )
    decision = RetrievalDecision(
        query_digest=sha256_digest(query),
        raw_hits=len(events),
        admitted_hits=len(admitted),
        blocked_hits=blocked_hits,
        admitted_memory_ids=[event.memory_id for event in admitted],
        context_digest=context_digest,
        timestamp=now_utc(),
    )
    return RetrievalFilterResult(decision=decision, admitted_events=admitted, receipts=receipts)
