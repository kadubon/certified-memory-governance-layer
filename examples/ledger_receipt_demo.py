from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from cmgl.ledger import AppendOnlyLedger


def main() -> None:
    with TemporaryDirectory() as tmp_dir:
        ledger = AppendOnlyLedger(Path(tmp_dir) / "ledger.jsonl")
        _, receipt = ledger.append_with_receipt("demo", {"message": "fake local data"})
        integrity = ledger.integrity_receipt()
        print(f"append_index={receipt.append_index}")
        print(f"append_prefix={receipt.ledger_prefix_hash}")
        print(f"integrity_ok={integrity.ok}")


if __name__ == "__main__":
    main()
