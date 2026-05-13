from __future__ import annotations

from datetime import datetime
from importlib import import_module
from types import ModuleType
from typing import Any

from cmgl.adapters.binding import (
    append_adapter_receipt,
    bundle_with_adapter_receipt,
    external_ref_from_result,
    make_adapter_operation_receipt,
    success_reason,
)
from cmgl.adapters.common import normalize_records
from cmgl.admission import RetrievalFilterResult
from cmgl.digest import sha256_digest
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
    MemoryEvent,
    MemoryEventType,
)
from cmgl.time import now_utc


def load_graphiti() -> ModuleType:
    try:
        return import_module("graphiti_core")
    except ImportError as exc:
        raise OptionalDependencyError("graphiti-core", "graphiti") from exc


class GraphitiAdapter:
    """Async CMGL shim for user-supplied Graphiti clients."""

    def __init__(
        self,
        client: Any,
        *,
        layer: GovernanceLayer | None = None,
        lane: ContaminationLane = ContaminationLane.EXTERNAL_DOC,
        authority_scope: str = "graphiti:episode",
        agent_id: str = "graphiti-adapter",
        run_id: str = "graphiti-adapter",
        trace_id: str = "graphiti-adapter",
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
    def from_client(cls, client: Any, **kwargs: Any) -> GraphitiAdapter:
        return cls(client, **kwargs)

    @classmethod
    def require_dependency(cls) -> ModuleType:
        return load_graphiti()

    async def add_episode(
        self,
        *,
        name: str,
        episode_body: str,
        source_description: str,
        reference_time: datetime | None = None,
        lane: ContaminationLane | None = None,
        authority_scope: str | None = None,
        authority_receipt: AuthorityReceipt | None = None,
        authority_bundle: AuthorityBundle | None = None,
        authority_evidence_bundle: AuthorityEvidenceBundle | None = None,
        group_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> GovernanceReceiptBundle:
        result = self.layer.write_memory(
            episode_body,
            lane=lane or self.lane,
            authority_scope=authority_scope or self.authority_scope,
            metadata={
                "name": name,
                "source_description": source_description,
                "source_event_hashes": [
                    sha256_digest(
                        {
                            "episode_name": name,
                            "source_description": source_description,
                        }
                    )
                ],
                "group_ids": list(group_ids or []),
                "reference_time": (reference_time or now_utc()).isoformat(),
            },
            authority_receipt=authority_receipt,
            authority_bundle=authority_bundle,
            authority_evidence_bundle=authority_evidence_bundle,
        )
        if result.promotion_receipt.decision != AdmissionDecision.ADMIT:
            receipt = make_adapter_operation_receipt(
                backend=BackendName.GRAPHITI,
                operation="write",
                event=result.event,
                status=AdapterOperationStatus.NOT_CALLED,
                decision=result.promotion_receipt.decision,
                reason_codes=["adapter.external_not_called"],
            )
            append_adapter_receipt(self.layer, receipt, quarantine_on_failure=False)
            return bundle_with_adapter_receipt(self.layer, result, adapter_receipt=receipt)
        try:
            add_kwargs = dict(kwargs)
            if group_ids is not None:
                add_kwargs["group_ids"] = group_ids
            backend_result = await self.client.add_episode(
                name=name,
                episode_body=episode_body,
                source_description=source_description,
                reference_time=reference_time or now_utc(),
                **add_kwargs,
            )
        except Exception as exc:
            receipt = make_adapter_operation_receipt(
                backend=BackendName.GRAPHITI,
                operation="write",
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
            backend=BackendName.GRAPHITI,
            namespace=result.event.authority_scope,
            metadata={
                "source_description": source_description,
                "group_ids": list(group_ids or []),
                "reference_time": (reference_time or now_utc()).isoformat(),
            },
        )
        receipt = make_adapter_operation_receipt(
            backend=BackendName.GRAPHITI,
            operation="write",
            event=result.event,
            status=AdapterOperationStatus.SUCCEEDED,
            decision=AdmissionDecision.ADMIT,
            external_ref=external_ref,
            reason_codes=[success_reason("write")],
        )
        append_adapter_receipt(self.layer, receipt, quarantine_on_failure=False)
        return bundle_with_adapter_receipt(
            self.layer,
            result,
            adapter_receipt=receipt,
            backend_result=backend_result,
        )

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        group_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> list[MemoryEvent]:
        records = await self.client.search(
            query,
            group_ids=group_ids,
            num_results=limit,
            **kwargs,
        )
        return self._normalize(records)

    async def search_(
        self,
        query: str,
        *,
        group_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> list[MemoryEvent]:
        records = await self.client.search_(query, group_ids=group_ids, **kwargs)
        return self._normalize(records)

    async def filter_search(
        self,
        query: str,
        *,
        limit: int = 10,
        group_ids: list[str] | None = None,
        use_search_: bool = False,
        **kwargs: Any,
    ) -> RetrievalFilterResult:
        events = (
            await self.search_(query, group_ids=group_ids, **kwargs)
            if use_search_
            else await self.search(query, limit=limit, group_ids=group_ids, **kwargs)
        )
        return self.layer.filter_retrieval(query, events, limit=limit)

    def _normalize(self, records: Any) -> list[MemoryEvent]:
        return normalize_records(
            records,
            backend=BackendName.GRAPHITI,
            event_type=MemoryEventType.MEMORY_RETRIEVE,
            lane=self.lane,
            authority_scope=self.authority_scope,
            agent_id=self.agent_id,
            run_id=self.run_id,
            trace_id=self.trace_id,
            trusted_results=self.trusted_results,
        )
