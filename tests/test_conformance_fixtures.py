from __future__ import annotations

import json
from pathlib import Path

from cmgl.adapters.common import record_to_memory_event
from cmgl.admission import candidate_from_event, filter_retrieval
from cmgl.models import BackendName, ContaminationLane, MemoryStatus
from cmgl.policy import AdmissionPolicy
from cmgl.validation import validate_record_file

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "conformance"


def test_valid_record_fixtures_validate_against_schemas() -> None:
    for name in [
        "admission.certified_user_claim.valid.json",
        "compression.summary_not_fact.valid.json",
        "memory_event.valid.json",
        "authority_bundle.valid.json",
    ]:
        assert validate_record_file(FIXTURES / name).status.value == "valid"


def test_invalid_admission_fixtures_fail_expected_policy_paths() -> None:
    cases = [
        ("admission.model_inference_fact.invalid.json", ContaminationLane.MODEL_INFERENCE),
        ("admission.summary_as_fact.invalid.json", ContaminationLane.SUMMARY),
    ]
    for filename, lane in cases:
        fixture = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
        event = record_to_memory_event(
            {"id": fixture["memory_id"], "content": "fixture", "status": "certified"},
            backend=BackendName.INMEMORY,
            lane=lane,
            authority_scope="user:fixture",
            trusted_result=True,
        )
        receipt = AdmissionPolicy().evaluate(candidate_from_event(event), as_fact=True)
        assert receipt.decision.value == "block"
        assert fixture["expected_reason_code"] in receipt.reason_codes


def test_retrieval_superseded_fixture_blocks_with_reason() -> None:
    fixture = json.loads(
        (FIXTURES / "retrieval.superseded_block.valid.json").read_text(encoding="utf-8")
    )
    event = record_to_memory_event(
        {
            "id": fixture["blocked_memory_id"],
            "content": "old preference",
            "status": MemoryStatus.SUPERSEDED.value,
        },
        backend=BackendName.INMEMORY,
        trusted_result=True,
    )
    result = filter_retrieval("preference", [event])
    assert result.decision.admitted_hits == 0
    assert fixture["expected_reason_code"] in result.decision.blocked_hits[0]["reason"]


def test_graphiti_temporal_fixture_normalizes_as_superseded() -> None:
    fixture = json.loads(
        (FIXTURES / "graphiti_temporal_supersession.valid.json").read_text(encoding="utf-8")
    )
    event = record_to_memory_event(
        fixture,
        backend=BackendName.GRAPHITI,
        lane=ContaminationLane.EXTERNAL_DOC,
        trusted_result=True,
    )
    assert event.memory_id == "graphiti-fixture-1"
    assert event.status == MemoryStatus.SUPERSEDED
    assert event.valid_from is not None
    assert event.valid_to is not None
    assert event.source_event_hashes


def test_mem0_add_only_correction_fixture_documents_non_mutating_correction() -> None:
    fixture = json.loads(
        (FIXTURES / "mem0_add_only_correction.valid.json").read_text(encoding="utf-8")
    )
    assert fixture["correction_model"] == "add-only"
    assert "supersession" in fixture
