# CMGL v1.1.2 Release Checklist

This checklist prepares v1.1.2. It is not a record of completed publication until the manual gates are checked after release.

## Pre-Release Local Gates

- `uv lock --check`
- `uv sync --locked --all-extras --dev`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy src`
- `uv run pytest`
- `uv run pytest --cov=cmgl`
- `uv run cmgl version`
- `uv run cmgl doctor --skip-ledger`
- `uv run cmgl validate canonical`
- `uv run cmgl adapters doctor`
- `uv run cmgl adapters live-smoke --target all --dry-run`
- `uv build`
- `uv run python scripts/check_publishability.py`
- `uv run pip-audit`

## CI Gates

- Offline CI passes on supported Python versions.
- Release job builds sdist/wheel and runs publishability.
- Wheel smoke test imports `cmgl`, runs `cmgl version`, `cmgl doctor --skip-ledger`, and schema export.
- Optional adapter live smoke is protected and does not run on fork PRs.

## Manual Publishing Gates

- Configure or verify PyPI Trusted Publisher for this repository.
- Do not add long-lived PyPI tokens.
- Optionally run TestPyPI dry-run in an isolated environment.
- Create tag `v1.1.2` only after local and CI gates pass.
- Create a GitHub Release using `docs/releases/v1.1.2.md`.
- Confirm the publish workflow used OIDC.
- Run a post-release PyPI long-description check.
- Run release provenance check.

## Repository Maintenance Items

- Fix repository topic typo `puthon` to `python` if still present.
- Review Dependabot PRs separately; do not merge automatically.
- Verify secret scanning, push protection, Dependabot alerts, Dependabot security updates, CodeQL/code scanning, dependency review, main branch protection, required CI checks, release restrictions, and PyPI Trusted Publishing.

## Adapter Live-Smoke Gate

Adapter live smoke is optional and protected. Missing provider secrets must not affect core PR CI. Organizations that rely on Mem0 or Graphiti live environments should enable the `cmgl-live` GitHub Environment and run `scripts/live_adapter_smoke.py --target all --require-live-env`.
