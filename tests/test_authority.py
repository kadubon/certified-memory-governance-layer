from __future__ import annotations

import pytest

from cmgl.admission import candidate_from_event
from cmgl.authority import make_authority_receipt
from cmgl.digest import sha256_digest
from cmgl.models import (
    AdmissionDecision,
    BackendName,
    ContaminationLane,
    MemoryEvent,
    MemoryEventType,
    MemoryStatus,
    ProtectedAction,
)
from cmgl.policy import AdmissionPolicy
from cmgl.time import now_utc


def test_authority_receipt_required_for_persistent_write_policy_path() -> None:
    event = MemoryEvent(
        trace_id="trace",
        run_id="run",
        agent_id="agent",
        backend=BackendName.INMEMORY,
        event_type=MemoryEventType.MEMORY_WRITE,
        memory_id="mem-authority",
        memory_update_id="update-authority",
        content="memory",
        content_digest=sha256_digest("memory"),
        lane=ContaminationLane.USER_CLAIM,
        provenance_depth=0,
        authority_scope="user:allowed",
        status=MemoryStatus.CERTIFIED,
        checker_version="test",
        created_at=now_utc(),
    )
    policy = AdmissionPolicy(require_authority_for_persistent_writes=True)

    missing = policy.evaluate(candidate_from_event(event))
    assert missing.decision == AdmissionDecision.BLOCK
    assert "authority.missing" in missing.reason_codes

    with pytest.warns(DeprecationWarning):
        authority = make_authority_receipt(
            action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
            actor="agent",
            authority_scope="user:allowed",
            source_record="local-test",
            allowed_scopes={"user:allowed"},
        )
    admitted = policy.evaluate(candidate_from_event(event), authority_receipt=authority)
    assert admitted.decision == AdmissionDecision.BLOCK
    assert "authority.strict_verification_failed" in admitted.reason_codes

    legacy_compat_policy = AdmissionPolicy(
        require_authority_for_persistent_writes=True,
        strict_authority_verification=False,
    )
    admitted = legacy_compat_policy.evaluate(
        candidate_from_event(event), authority_receipt=authority
    )
    assert admitted.decision == AdmissionDecision.ADMIT
