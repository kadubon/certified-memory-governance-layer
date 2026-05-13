from __future__ import annotations

from cmgl.admission import candidate_from_event
from cmgl.compression import make_compression_certificate
from cmgl.digest import sha256_digest
from cmgl.models import (
    AdmissionDecision,
    BackendName,
    ContaminationLane,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
)
from cmgl.policy import AdmissionPolicy
from cmgl.time import now_utc


def test_compression_certificate_summary_not_promoted_as_fact() -> None:
    certificate = make_compression_certificate(
        compressed_memory_id="summary-1",
        source_memory_ids=["mem-1", "mem-2"],
        source_size=100,
        compressed_size=40,
        recoverability_check="pass",
        source_coverage=0.9,
    )
    assert certificate.decision == "admit_as_summary_not_fact"

    event = MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent",
        backend=BackendName.INMEMORY,
        event_type=MemoryEventType.MEMORY_WRITE,
        memory_id="summary-1",
        memory_update_id="summary-update-1",
        content="summary",
        content_digest=sha256_digest("summary"),
        source_event_hashes=[sha256_digest("source")],
        lane=ContaminationLane.SUMMARY,
        provenance_depth=1,
        authority_scope="user:test",
        status=MemoryStatus.CERTIFIED,
        checker_version="test",
        created_at=now_utc(),
    )
    receipt = AdmissionPolicy().evaluate(candidate_from_event(event), as_fact=True)
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "lane.summary.summary_not_fact" in receipt.reason_codes
