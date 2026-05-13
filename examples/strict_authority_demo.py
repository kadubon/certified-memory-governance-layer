from __future__ import annotations

from datetime import timedelta

from cmgl.authority import (
    authorize_bundle,
    authorize_request,
    make_declared_scope,
    make_protected_action_request,
)
from cmgl.models import ProtectedAction
from cmgl.time import now_utc


def main() -> None:
    free_text_request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent.local",
        authority_scope="user:demo",
        source_record="please remember this",
        natural_language_justification="the user said yes",
    )
    blocked = authorize_request(free_text_request)

    scope = make_declared_scope(
        actor="agent.local",
        authority_scope="user:demo",
        permitted_actions=[ProtectedAction.PERSISTENT_MEMORY_WRITE],
        expires_at=now_utc() + timedelta(minutes=5),
    )
    scoped_request = make_protected_action_request(
        action=ProtectedAction.PERSISTENT_MEMORY_WRITE,
        actor="agent.local",
        authority_scope="user:demo",
        source_record="structured authorization",
        declared_scope=scope,
    )
    bundle = authorize_bundle(scoped_request, declared_scope=scope)

    print(f"free_text={blocked.decision.value}:{','.join(blocked.reason_codes)}")
    print(
        f"authority_bundle={bundle.receipt.decision.value}:{','.join(bundle.receipt.reason_codes)}"
    )


if __name__ == "__main__":
    main()
