from __future__ import annotations

from cmgl.ledger import AppendOnlyLedger


def test_ledger_append_and_verify_success(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    first = ledger.append("test", {"a": 1})
    second = ledger.append("test", {"b": 2})

    assert second.previous_record_digest == first.record_digest
    result = ledger.verify_prefix()
    assert result.ok
    assert result.records_checked == 2


def test_ledger_detects_tampering(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "ledger.jsonl"
    ledger = AppendOnlyLedger(path)
    ledger.append("test", {"a": 1})
    path.write_text(path.read_text(encoding="utf-8").replace('"a":1', '"a":2'), encoding="utf-8")

    result = ledger.verify_prefix()
    assert not result.ok
    assert any("digest mismatch" in error for error in result.errors)
