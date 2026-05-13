from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from cmgl import GovernanceLayer
from cmgl.authority import authorize_bundle, make_declared_scope, make_protected_action_request
from cmgl.models import ContaminationLane, ProtectedAction
from cmgl.time import now_utc


def authority_bundle_for_write(scope_name: str):
    scope = make_declared_scope(
        actor="agent.local",
        authority_scope=scope_name,
        permitted_actions=[ProtectedAction.PERSISTENT_MEMORY_WRITE],
        expires_at=now_utc() + timedelta(minutes=5),
    )
    request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent.local",
        authority_scope=scope_name,
        source_record="demo structured scope",
        declared_scope=scope,
    )
    return authorize_bundle(request, declared_scope=scope)


def main() -> None:
    with TemporaryDirectory() as tmp_dir:
        ledger_path = Path(tmp_dir) / "ledger.jsonl"
        layer = GovernanceLayer(ledger=ledger_path)
        result = layer.write_memory_bundle(
            "The demo user prefers morning meetings.",
            lane=ContaminationLane.USER_CLAIM,
            authority_scope="user:demo",
            authority_bundle=authority_bundle_for_write("user:demo"),
        )
        retrieval = layer.filter_retrieval("morning")
        print(f"promotion={result.decision.value}")
        print(f"admitted={retrieval.decision.admitted_memory_ids}")
        print(f"ledger_ok={layer.verify_ledger().ok}")


if __name__ == "__main__":
    main()
