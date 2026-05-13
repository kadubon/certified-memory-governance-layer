from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any, Literal

from cmgl.adapters.binding import (
    append_adapter_receipt,
    bundle_with_adapter_receipt,
    external_ref_from_result,
    has_successful_binding,
    make_adapter_operation_receipt,
    success_reason,
)
from cmgl.adapters.common import normalize_records, record_to_memory_event
from cmgl.admission import RetrievalFilterResult
from cmgl.exceptions import AdapterOperationError, OptionalDependencyError
from cmgl.guarded import GuardedMemoryBackend
from cmgl.layer import GovernanceLayer
from cmgl.models import (
    AdapterOperationStatus,
    AdmissionDecision,
    AuthorityBundle,
    AuthorityEvidenceBundle,
    AuthorityReceipt,
    BackendName,
    ContaminationLane,
    GovernanceReceiptBundle,
    JsonContent,
    MemoryEvent,
    MemoryEventType,
)


def load_mem0() -> ModuleType:
    try:
        return import_module("mem0")
    except ImportError as exc:
        raise OptionalDependencyError("mem0ai", "mem0") from exc


class Mem0Adapter:
    """Safe CMGL shim for user-supplied Mem0 `Memory` or `MemoryClient` objects."""

    def __init__(
        self,
        client: Any,
        *,
        layer: GovernanceLayer | None = None,
        lane: ContaminationLane = ContaminationLane.USER_CLAIM,
        authority_scope: str = "mem0:memory",
        agent_id: str = "mem0-adapter",
        run_id: str = "mem0-adapter",
        trace_id: str = "mem0-adapter",
        trusted_results: bool = False,
        raise_on_external_error: bool = False,
    ) -> None:
        self.client = client
        self.layer = layer or GovernanceLayer()
        self.lane = lane
        self.authority_scope = authority_scope
        self.agent_id = agent_id
        self.run_id = run_id
        self.trace_id = trace_id
        self.trusted_results = trusted_results
        self.raise_on_external_error = raise_on_external_error

    @classmethod
    def from_client(cls, client: Any, **kwargs: Any) -> Mem0Adapter:
        return cls(client, **kwargs)

    @classmethod
    def require_dependency(cls) -> ModuleType:
        return load_mem0()

    def guarded_backend(
        self,
        *,
        add_kwargs: dict[str, Any] | None = None,
        update_kwargs: dict[str, Any] | None = None,
    ) -> GuardedMemoryBackend:
        """Return a guarded backend that only calls Mem0 after CMGL admission."""

        return GuardedMemoryBackend(
            layer=self.layer,
            write=lambda content, lane, authority_scope, metadata=None: self._add_raw(
                content, metadata=metadata, **dict(add_kwargs or {})
            ),
            update=lambda memory_id, content, lane, authority_scope, metadata=None: (
                self._update_raw(memory_id, content, metadata=metadata, **dict(update_kwargs or {}))
            ),
            delete=lambda memory_id, reason: self._delete_raw(memory_id),
            retrieve=lambda query, limit=10: self.search(query, limit=limit),
        )

    def add(
        self,
        content: JsonContent,
        *,
        lane: ContaminationLane | None = None,
        authority_scope: str | None = None,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
        **kwargs: Any,
    ) -> GovernanceReceiptBundle:
        result = self.layer.write_memory(
            content,
            lane=lane or self.lane,
            authority_scope=authority_scope or self.authority_scope,
            metadata=metadata,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        return self._call_external_after_admit(
            result,
            operation="write",
            call=lambda: self._add_raw(content, metadata=metadata, **kwargs),
        )

    write = add

    def update(
        self,
        memory_id: str,
        content: JsonContent,
        *,
        lane: ContaminationLane | None = None,
        authority_scope: str | None = None,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
        allow_unbound_external_ref: bool = False,
        **kwargs: Any,
    ) -> GovernanceReceiptBundle:
        if not allow_unbound_external_ref and not has_successful_binding(self.layer, memory_id):
            raise AdapterOperationError(
                "Mem0 update requires a prior CMGL external binding; pass "
                "allow_unbound_external_ref=True only for controlled migrations."
            )
        result = self.layer.update_memory(
            memory_id,
            content,
            lane=lane or self.lane,
            authority_scope=authority_scope or self.authority_scope,
            metadata=metadata,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        return self._call_external_after_admit(
            result,
            operation="update",
            call=lambda: self._update_raw(memory_id, content, metadata=metadata, **kwargs),
        )

    def delete(
        self,
        memory_id: str,
        *,
        reason: str = "cmgl_adapter_delete",
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
        allow_unbound_external_ref: bool = False,
    ) -> GovernanceReceiptBundle:
        if not allow_unbound_external_ref and not has_successful_binding(self.layer, memory_id):
            raise AdapterOperationError(
                "Mem0 delete requires a prior CMGL external binding; pass "
                "allow_unbound_external_ref=True only for controlled migrations."
            )
        result = self.layer.delete_memory(
            memory_id,
            reason=reason,
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        return self._call_external_after_admit(
            result,
            operation="delete",
            call=lambda: self._delete_raw(memory_id),
        )

    def get(self, memory_id: str, **kwargs: Any) -> MemoryEvent:
        record = self.client.get(memory_id, **kwargs)
        return record_to_memory_event(
            record,
            backend=BackendName.MEM0,
            event_type=MemoryEventType.MEMORY_READ,
            lane=self.lane,
            authority_scope=self.authority_scope,
            agent_id=self.agent_id,
            run_id=self.run_id,
            trace_id=self.trace_id,
            trusted_result=self.trusted_results,
        )

    def get_all(
        self,
        *,
        limit: int = 20,
        filters: dict[str, object] | None = None,
        **kwargs: Any,
    ) -> list[MemoryEvent]:
        method = self.client.get_all
        records = method(filters=filters, top_k=limit, **kwargs)
        return self._normalize(records, event_type=MemoryEventType.MEMORY_READ)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, object] | None = None,
        **kwargs: Any,
    ) -> list[MemoryEvent]:
        records = self.client.search(query, top_k=limit, filters=filters, **kwargs)
        return self._normalize(records, event_type=MemoryEventType.MEMORY_RETRIEVE)

    def filter_search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, object] | None = None,
        **kwargs: Any,
    ) -> RetrievalFilterResult:
        events = self.search(query, limit=limit, filters=filters, **kwargs)
        return self.layer.filter_retrieval(query, events, limit=limit)

    def _add_raw(
        self,
        content: JsonContent,
        *,
        metadata: dict[str, object] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self.client.add(content, metadata=metadata, **kwargs)

    def _update_raw(
        self,
        memory_id: str,
        content: JsonContent,
        *,
        metadata: dict[str, object] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self.client.update(memory_id, content, metadata=metadata, **kwargs)

    def _delete_raw(self, memory_id: str) -> Any:
        return self.client.delete(memory_id)

    def _normalize(
        self,
        records: Any,
        *,
        event_type: MemoryEventType,
    ) -> list[MemoryEvent]:
        return normalize_records(
            records,
            backend=BackendName.MEM0,
            event_type=event_type,
            lane=self.lane,
            authority_scope=self.authority_scope,
            agent_id=self.agent_id,
            run_id=self.run_id,
            trace_id=self.trace_id,
            trusted_results=self.trusted_results,
        )

    def _call_external_after_admit(
        self,
        result: Any,
        *,
        operation: Literal["write", "update", "delete"],
        call: Any,
    ) -> GovernanceReceiptBundle:
        if result.promotion_receipt.decision != AdmissionDecision.ADMIT:
            receipt = make_adapter_operation_receipt(
                backend=BackendName.MEM0,
                operation=operation,
                event=result.event,
                status=AdapterOperationStatus.NOT_CALLED,
                decision=result.promotion_receipt.decision,
                reason_codes=["adapter.external_not_called"],
            )
            append_adapter_receipt(self.layer, receipt, quarantine_on_failure=False)
            return bundle_with_adapter_receipt(
                self.layer,
                result,
                adapter_receipt=receipt,
            )
        try:
            backend_result = call()
        except Exception as exc:
            receipt = make_adapter_operation_receipt(
                backend=BackendName.MEM0,
                operation=operation,
                event=result.event,
                status=AdapterOperationStatus.FAILED,
                decision=AdmissionDecision.BLOCK,
                reason_codes=["adapter.external_persistence_failed"],
                error=exc,
            )
            quarantine_digest = append_adapter_receipt(self.layer, receipt)
            if self.raise_on_external_error:
                raise AdapterOperationError(str(exc)) from exc
            return bundle_with_adapter_receipt(
                self.layer,
                result,
                adapter_receipt=receipt,
                quarantine_record_digest=quarantine_digest,
            )
        external_ref = external_ref_from_result(
            backend_result,
            event=result.event,
            backend=BackendName.MEM0,
            namespace=result.event.authority_scope,
        )
        receipt = make_adapter_operation_receipt(
            backend=BackendName.MEM0,
            operation=operation,
            event=result.event,
            status=AdapterOperationStatus.SUCCEEDED,
            decision=AdmissionDecision.ADMIT,
            external_ref=external_ref,
            reason_codes=[success_reason(operation)],
        )
        append_adapter_receipt(self.layer, receipt, quarantine_on_failure=False)
        return bundle_with_adapter_receipt(
            self.layer,
            result,
            adapter_receipt=receipt,
            backend_result=backend_result,
        )
