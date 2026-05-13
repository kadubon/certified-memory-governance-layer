from __future__ import annotations

from cmgl import AdmissionPolicy, ContaminationLane, filter_retrieval
from cmgl.backends import InMemoryBackend


def main() -> None:
    backend = InMemoryBackend()
    old = backend.write(
        "User prefers morning meetings.",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:demo",
    )
    new = backend.update(
        old.memory_id,
        "User now prefers afternoon meetings.",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:demo",
    )

    raw_hits = backend.retrieve("meetings")
    print(
        "raw_retrieval=",
        [(event.memory_id, event.memory_update_id, event.status.value) for event in raw_hits],
    )

    result = filter_retrieval("meetings", raw_hits, policy=AdmissionPolicy())
    print("admitted_memory_ids=", result.decision.admitted_memory_ids)
    print("new_version=", (new.memory_id, new.memory_update_id))
    print("blocked_hits=", result.decision.blocked_hits)


if __name__ == "__main__":
    main()
