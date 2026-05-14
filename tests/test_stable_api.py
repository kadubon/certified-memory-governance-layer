from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import cmgl
from cmgl.time import now_utc


def test_stable_top_level_api_imports_and_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert cmgl.__version__ == "1.1.1"

    layer = cmgl.GovernanceLayer(ledger=tmp_path / "ledger.jsonl")
    assert isinstance(layer.policy, cmgl.AdmissionPolicy)

    declared_scope = cmgl.make_declared_scope(
        actor="agent.local",
        authority_scope="user:stable",
        permitted_actions=[cmgl.ProtectedAction.PERSISTENT_MEMORY_WRITE],
        expires_at=now_utc() + timedelta(minutes=10),
    )
    request = cmgl.make_protected_action_request(
        action=cmgl.ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent.local",
        authority_scope="user:stable",
        source_record="structured stable API test scope",
        declared_scope=declared_scope,
    )
    authority = cmgl.authorize_bundle(request, declared_scope=declared_scope)
    bundle = layer.write_memory_bundle(
        "Stable API memory.",
        lane=cmgl.ContaminationLane.USER_CLAIM,
        authority_scope="user:stable",
        authority_bundle=authority,
    )

    assert isinstance(bundle, cmgl.GovernanceReceiptBundle)
    assert bundle.decision == cmgl.AdmissionDecision.ADMIT
    assert isinstance(bundle.event, cmgl.MemoryEvent)
    assert isinstance(bundle.candidate, cmgl.MemoryCandidate)
    assert isinstance(bundle.promotion_receipt, cmgl.PromotionReceipt)
    assert layer.verify_ledger().ok

    guarded = cmgl.GuardedMemoryBackend(layer=layer)
    retrieval = guarded.filter_retrieval("Stable", events=[bundle.event])
    assert isinstance(retrieval, cmgl.RetrievalFilterResult)
    assert isinstance(retrieval.decision, cmgl.RetrievalDecision)

    digest = cmgl.sha256_digest({"memory_id": bundle.event.memory_id})
    assert digest.startswith("sha256:")


def test_api_stability_doc_names_core_symbols() -> None:
    text = (Path(__file__).resolve().parents[1] / "docs" / "api-stability.md").read_text(
        encoding="utf-8"
    )
    for symbol in [
        "GovernanceLayer",
        "GuardedMemoryBackend",
        "AdmissionPolicy",
        "MemoryEvent",
        "authorize_bundle",
        "filter_retrieval",
    ]:
        assert symbol in text
