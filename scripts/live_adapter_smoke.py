from __future__ import annotations

import argparse
import json
import sys
import warnings

from cmgl.live_smoke import run_live_smoke

warnings.filterwarnings(
    "ignore",
    message=r"Support for class-based `config` is deprecated.*",
    category=Warning,
)
warnings.filterwarnings(
    "ignore",
    message=r"Importing Send from langgraph\.constants is deprecated.*",
    category=Warning,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CMGL adapter live smoke checks.")
    parser.add_argument(
        "--target",
        default="all",
        choices=["mem0", "graphiti", "langmem", "langgraph", "all"],
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--require-live-env",
        action="store_true",
        help="Fail when provider-backed targets are missing required environment.",
    )
    args = parser.parse_args()
    report = run_live_smoke(
        target=args.target,
        dry_run=args.dry_run,
        require_live_env=args.require_live_env,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
