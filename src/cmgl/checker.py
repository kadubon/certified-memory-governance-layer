from __future__ import annotations

from typing import Protocol

from cmgl.admission import candidate_from_event
from cmgl.evidence import build_evidence_manifest, build_input_set_manifest, build_replay_evidence
from cmgl.models import (
    EvidenceManifest,
    InputSetManifest,
    MemoryCandidate,
    MemoryEvent,
    MemoryStatus,
    ReplayEvidence,
)


class PromotionChecker(Protocol):
    """Local checker protocol used to construct strict promotion evidence."""

    checker_version: str

    def candidate_for_admission(self, event: MemoryEvent) -> MemoryCandidate:
        """Return the candidate that should be checked for admission."""

    def evidence_for(
        self,
        candidate: MemoryCandidate,
    ) -> tuple[EvidenceManifest, InputSetManifest, ReplayEvidence]:
        """Return evidence manifest, input-set manifest, and replay evidence."""


class LocalDeterministicChecker:
    """Dependency-free checker for local examples and tests.

    It makes no truth claim. It only binds the candidate, input set, and replay evidence
    deterministically so strict CMGL paths have concrete obligations to verify.
    """

    def __init__(self, *, checker_version: str = "cmgl.local_deterministic_checker.v1") -> None:
        self.checker_version = checker_version

    def candidate_for_admission(self, event: MemoryEvent) -> MemoryCandidate:
        certified = event.model_copy(
            update={
                "status": MemoryStatus.CERTIFIED,
                "checker_version": self.checker_version,
            }
        )
        return candidate_from_event(certified)

    def evidence_for(
        self,
        candidate: MemoryCandidate,
    ) -> tuple[EvidenceManifest, InputSetManifest, ReplayEvidence]:
        evidence = build_evidence_manifest(candidate)
        if evidence is None:
            raise ValueError("strict local checker requires memory_update_id")
        input_set = build_input_set_manifest(candidate)
        replay = build_replay_evidence(
            input_set,
            checker_version=candidate.event.checker_version,
            accepted=True,
        )
        return evidence, input_set, replay
