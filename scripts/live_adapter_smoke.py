from __future__ import annotations

import argparse
import json
import sys

from cmgl.live_smoke import run_live_smoke


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CMGL adapter live smoke checks.")
    parser.add_argument(
        "--target",
        default="all",
        choices=["mem0", "graphiti", "langmem", "langgraph", "all"],
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = run_live_smoke(target=args.target, dry_run=args.dry_run)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
