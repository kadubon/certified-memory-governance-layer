from __future__ import annotations

from typing import Protocol

from cmgl.admission import RetrievalFilterResult
from cmgl.layer import GovernanceLayer
from cmgl.models import (
    AdmissionDecision,
    AuthorityBundle,
    AuthorityEvidenceBundle,
    AuthorityReceipt,
    ContaminationLane,
    GovernanceReceiptBundle,
    JsonContent,
    MemoryEvent,
)


class WriteCallable(Protocol):
    def __call__(
        self,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, object] | None = None,
    ) -> object: ...


class UpdateCallable(Protocol):
    def __call__(
        self,
        memory_id: str,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, object] | None = None,
    ) -> object: ...


class DeleteCallable(Protocol):
    def __call__(self, memory_id: str, *, reason: str) -> object: ...


class RetrieveCallable(Protocol):
    def __call__(self, query: str, *, limit: int = 10) -> list[MemoryEvent]: ...


class GuardedMemoryBackend:
    """Small adapter for putting CMGL in front of an existing memory backend.

    Write/update/delete callables are invoked only after the local
    GovernanceLayer admits the protected memory action.
    """

    def __init__(
        self,
        *,
        layer: GovernanceLayer | None = None,
        write: WriteCallable | None = None,
        update: UpdateCallable | None = None,
        delete: DeleteCallable | None = None,
        retrieve: RetrieveCallable | None = None,
    ) -> None:
        self.layer = layer or GovernanceLayer()
        self._write = write
        self._update = update
        self._delete = delete
        self._retrieve = retrieve

    def write_memory(
        self,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> GovernanceReceiptBundle:
        result = self.layer.write_memory(
            content,
            lane=lane,
            authority_scope=authority_scope,
            metadata=metadata,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        backend_result = None
        if result.promotion_receipt.decision == AdmissionDecision.ADMIT and self._write:
            backend_result = self._write(
                content,
                lane=lane,
                authority_scope=authority_scope,
                metadata=metadata,
            )
        return self.layer.receipt_bundle(result, backend_result=backend_result)

    def update_memory(
        self,
        memory_id: str,
        content: JsonContent,
        *,
        lane: ContaminationLane,
        authority_scope: str,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> GovernanceReceiptBundle:
        result = self.layer.update_memory(
            memory_id,
            content,
            lane=lane,
            authority_scope=authority_scope,
            metadata=metadata,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        backend_result = None
        if result.promotion_receipt.decision == AdmissionDecision.ADMIT and self._update:
            backend_result = self._update(
                memory_id,
                content,
                lane=lane,
                authority_scope=authority_scope,
                metadata=metadata,
            )
        return self.layer.receipt_bundle(result, backend_result=backend_result)

    def delete_memory(
        self,
        memory_id: str,
        *,
        reason: str,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
    ) -> GovernanceReceiptBundle:
        result = self.layer.delete_memory(
            memory_id,
            reason=reason,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        backend_result = None
        if result.promotion_receipt.decision == AdmissionDecision.ADMIT and self._delete:
            backend_result = self._delete(memory_id, reason=reason)
        return self.layer.receipt_bundle(result, backend_result=backend_result)

    def filter_retrieval(
        self,
        query: str,
        *,
        events: list[MemoryEvent] | None = None,
        limit: int = 10,
        include_audit_versions: bool = False,
    ) -> RetrievalFilterResult:
        raw_events = events
        if raw_events is None and self._retrieve is not None:
            raw_events = self._retrieve(query, limit=limit)
        return self.layer.filter_retrieval(
            query,
            raw_events,
            limit=limit,
            include_audit_versions=include_audit_versions,
        )

    write = write_memory
    update = update_memory
    delete = delete_memory
    retrieve = filter_retrieval
