from __future__ import annotations

from importlib import import_module
from inspect import isawaitable
from types import ModuleType
from typing import Any, Literal

from cmgl.adapters.binding import (
    append_adapter_receipt,
    bundle_with_adapter_receipt,
    external_ref_from_result,
    make_adapter_operation_receipt,
    success_reason,
)
from cmgl.adapters.common import normalize_records
from cmgl.admission import RetrievalFilterResult
from cmgl.exceptions import AdapterOperationError, OptionalDependencyError
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


def load_langmem() -> ModuleType:
    try:
        return import_module("langmem")
    except ImportError as exc:
        raise OptionalDependencyError("langmem", "langmem") from exc


class LangMemAdapter:
    """CMGL shim for LangMem tools and store-backed memory flows."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        layer: GovernanceLayer | None = None,
        lane: ContaminationLane = ContaminationLane.USER_CLAIM,
        authority_scope: str = "langmem:memory",
        agent_id: str = "langmem-adapter",
        run_id: str = "langmem-adapter",
        trace_id: str = "langmem-adapter",
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
    def from_client(cls, client: Any, **kwargs: Any) -> LangMemAdapter:
        return cls(client, **kwargs)

    @classmethod
    def require_dependency(cls) -> ModuleType:
        return load_langmem()

    @staticmethod
    def create_manage_memory_tool(*args: Any, **kwargs: Any) -> Any:
        return load_langmem().create_manage_memory_tool(*args, **kwargs)

    @staticmethod
    def create_search_memory_tool(*args: Any, **kwargs: Any) -> Any:
        return load_langmem().create_search_memory_tool(*args, **kwargs)

    def manage_memory(
        self,
        action: str,
        *,
        content: JsonContent = None,
        memory_id: str | None = None,
        manage_tool: Any | None = None,
        lane: ContaminationLane | None = None,
        authority_scope: str | None = None,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
        **kwargs: Any,
    ) -> GovernanceReceiptBundle:
        normalized = action.lower()
        if normalized in {"create", "add", "write"}:
            result = self.layer.write_memory(
                content,
                lane=lane or self.lane,
                authority_scope=authority_scope or self.authority_scope,
                metadata=metadata,
                authority_receipt=authority_receipt,
                authority_bundle=authority_bundle,
                authority_evidence_bundle=authority_evidence_bundle,
            )
        elif normalized in {"update", "patch"}:
            if memory_id is None:
                raise ValueError("memory_id is required for LangMem update actions")
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
        elif normalized in {"delete", "remove"}:
            if memory_id is None:
                raise ValueError("memory_id is required for LangMem delete actions")
            result = self.layer.delete_memory(
                memory_id,
                reason=str(kwargs.pop("reason", "langmem_delete")),
                authority_receipt=authority_receipt,
                authority_bundle=authority_bundle,
                authority_evidence_bundle=authority_evidence_bundle,
            )
        else:
            raise ValueError(f"unsupported LangMem memory action: {action}")

        payload = {
            "action": normalized,
            "content": content,
            "memory_id": memory_id,
            "metadata": metadata or {},
            **kwargs,
        }
        return self._call_tool_after_admit(
            result,
            operation=_operation_for_action(normalized),
            call=lambda: _invoke_tool(manage_tool or self.client, payload),
        )

    async def amanage_memory(
        self,
        action: str,
        *,
        content: JsonContent = None,
        memory_id: str | None = None,
        manage_tool: Any | None = None,
        lane: ContaminationLane | None = None,
        authority_scope: str | None = None,
        metadata: dict[str, object] | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
        **kwargs: Any,
    ) -> GovernanceReceiptBundle:
        normalized = action.lower()
        if normalized in {"create", "add", "write"}:
            result = self.layer.write_memory(
                content,
                lane=lane or self.lane,
                authority_scope=authority_scope or self.authority_scope,
                metadata=metadata,
                authority_receipt=authority_receipt,
                authority_bundle=authority_bundle,
                authority_evidence_bundle=authority_evidence_bundle,
            )
        elif normalized in {"update", "patch"}:
            if memory_id is None:
                raise ValueError("memory_id is required for LangMem update actions")
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
        elif normalized in {"delete", "remove"}:
            if memory_id is None:
                raise ValueError("memory_id is required for LangMem delete actions")
            result = self.layer.delete_memory(
                memory_id,
                reason=str(kwargs.pop("reason", "langmem_delete")),
                authority_receipt=authority_receipt,
                authority_bundle=authority_bundle,
                authority_evidence_bundle=authority_evidence_bundle,
            )
        else:
            raise ValueError(f"unsupported LangMem memory action: {action}")

        payload = {
            "action": normalized,
            "content": content,
            "memory_id": memory_id,
            "metadata": metadata or {},
            **kwargs,
        }
        return await self._call_tool_after_admit_async(
            result,
            operation=_operation_for_action(normalized),
            call=lambda: _invoke_tool_async(manage_tool or self.client, payload),
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        search_tool: Any | None = None,
        **kwargs: Any,
    ) -> list[MemoryEvent]:
        payload = {"query": query, "limit": limit, **kwargs}
        records = _invoke_tool(search_tool or self.client, payload)
        return self._normalize(records)

    def filter_search(
        self,
        query: str,
        *,
        limit: int = 10,
        search_tool: Any | None = None,
        **kwargs: Any,
    ) -> RetrievalFilterResult:
        events = self.search(query, limit=limit, search_tool=search_tool, **kwargs)
        return self.layer.filter_retrieval(query, events, limit=limit)

    def _normalize(self, records: Any) -> list[MemoryEvent]:
        return normalize_records(
            records,
            backend=BackendName.LANGMEM,
            event_type=MemoryEventType.MEMORY_RETRIEVE,
            lane=self.lane,
            authority_scope=self.authority_scope,
            agent_id=self.agent_id,
            run_id=self.run_id,
            trace_id=self.trace_id,
            trusted_results=self.trusted_results,
        )

    def _call_tool_after_admit(
        self,
        result: Any,
        *,
        operation: Literal["write", "update", "delete"],
        call: Any,
    ) -> GovernanceReceiptBundle:
        if result.promotion_receipt.decision != AdmissionDecision.ADMIT:
            receipt = make_adapter_operation_receipt(
                backend=BackendName.LANGMEM,
                operation=operation,
                event=result.event,
                status=AdapterOperationStatus.NOT_CALLED,
                decision=result.promotion_receipt.decision,
                reason_codes=["adapter.external_not_called"],
            )
            append_adapter_receipt(self.layer, receipt, quarantine_on_failure=False)
            return bundle_with_adapter_receipt(self.layer, result, adapter_receipt=receipt)
        try:
            backend_result = call()
        except Exception as exc:
            receipt = make_adapter_operation_receipt(
                backend=BackendName.LANGMEM,
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
        return self._success_bundle(result, operation=operation, backend_result=backend_result)

    async def _call_tool_after_admit_async(
        self,
        result: Any,
        *,
        operation: Literal["write", "update", "delete"],
        call: Any,
    ) -> GovernanceReceiptBundle:
        if result.promotion_receipt.decision != AdmissionDecision.ADMIT:
            receipt = make_adapter_operation_receipt(
                backend=BackendName.LANGMEM,
                operation=operation,
                event=result.event,
                status=AdapterOperationStatus.NOT_CALLED,
                decision=result.promotion_receipt.decision,
                reason_codes=["adapter.external_not_called"],
            )
            append_adapter_receipt(self.layer, receipt, quarantine_on_failure=False)
            return bundle_with_adapter_receipt(self.layer, result, adapter_receipt=receipt)
        try:
            backend_result = await call()
        except Exception as exc:
            receipt = make_adapter_operation_receipt(
                backend=BackendName.LANGMEM,
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
        return self._success_bundle(result, operation=operation, backend_result=backend_result)

    def _success_bundle(
        self,
        result: Any,
        *,
        operation: Literal["write", "update", "delete"],
        backend_result: Any,
    ) -> GovernanceReceiptBundle:
        external_ref = external_ref_from_result(
            backend_result,
            event=result.event,
            backend=BackendName.LANGMEM,
            namespace=result.event.authority_scope,
        )
        receipt = make_adapter_operation_receipt(
            backend=BackendName.LANGMEM,
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


def _invoke_tool(tool: Any, payload: dict[str, Any]) -> Any:
    if tool is None:
        raise ValueError("a LangMem tool, callable, or store client is required")
    if hasattr(tool, "invoke"):
        return tool.invoke(payload)
    if callable(tool):
        try:
            return tool(payload)
        except TypeError:
            return tool(**payload)
    if hasattr(tool, "search") and "query" in payload:
        return tool.search(payload["query"], limit=payload.get("limit", 10))
    if hasattr(tool, "put") and payload.get("action") in {"create", "add", "write"}:
        return tool.put(payload)
    raise TypeError("unsupported LangMem tool/store object")


async def _invoke_tool_async(tool: Any, payload: dict[str, Any]) -> Any:
    if tool is None:
        raise ValueError("a LangMem tool, callable, or store client is required")
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(payload)
    result = _invoke_tool(tool, payload)
    if isawaitable(result):
        return await result
    return result


def _operation_for_action(action: str) -> Literal["write", "update", "delete"]:
    if action in {"create", "add", "write"}:
        return "write"
    if action in {"update", "patch"}:
        return "update"
    return "delete"
