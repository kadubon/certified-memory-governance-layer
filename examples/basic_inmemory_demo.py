from __future__ import annotations

from cmgl import AdmissionPolicy, ContaminationLane, filter_retrieval
from cmgl.backends import InMemoryBackend


def main() -> None:
    backend = InMemoryBackend()
    backend.write(
        "User prefers concise weekly planning updates.",
        lane=ContaminationLane.USER_CLAIM,
        authority_scope="user:demo",
    )
    raw_hits = backend.retrieve("planning")
    result = filter_retrieval("planning", raw_hits, policy=AdmissionPolicy())
    print("admitted_memory_ids=", result.decision.admitted_memory_ids)
    print("receipt_decisions=", [receipt.decision.value for receipt in result.receipts])


if __name__ == "__main__":
    main()
