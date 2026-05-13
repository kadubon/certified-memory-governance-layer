# GitHub Public Publication Checklist

Before public release, manually enable or verify:

- enable secret scanning
- enable push protection
- enable Dependabot alerts
- enable Dependabot security updates
- enable code scanning / CodeQL
- enable branch protection on main
- require PR review before merge
- require CI checks before merge
- require linear history if desired
- restrict who can publish releases
- use PyPI Trusted Publishing / OIDC, not long-lived PyPI tokens
- create a protected GitHub Environment named `cmgl-live` for release/main live adapter smoke
- store live provider keys only as GitHub Environment secrets
- never store OpenAI API keys or provider keys in repo
- use environment variables for local API keys
- verify no real `.env`, logs, notebooks, or private datasets are committed
- review `LICENSE` and `THIRD_PARTY_NOTICES.md` before release
- run `uv lock --check`
- run tests, lint, type check, and `pip-audit`
- run `uv run cmgl doctor --skip-ledger`, `uv run cmgl validate canonical`, and `uv run python scripts/check_publishability.py`
- run `uv run cmgl adapters live-smoke --target all --dry-run` locally
- create a clean clone and run the quickstart before tagging release
- create a clean virtual environment, install the built wheel, and run `cmgl version`
- test PyPI Trusted Publisher configuration against TestPyPI before the first real release
