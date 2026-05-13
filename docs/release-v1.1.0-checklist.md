# CMGL v1.1.0 Release Checklist

This checklist is retained as a historical/internal maintenance record for the v1.1.0 release. For future releases, adapt the same gates to the target version before tagging or publishing.

## Automated Local Gates

Run from a clean checkout:

```bash
uv lock --check
uv sync --locked --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
uv run pytest --cov=cmgl
uv run cmgl version
uv run cmgl doctor --skip-ledger
uv run cmgl validate canonical
uv run cmgl schema export /tmp/cmgl-schemas
uv build
uv run python scripts/check_publishability.py
uv run pip-audit
```

Wheel smoke:

```bash
python -m venv /tmp/cmgl-wheel-smoke
/tmp/cmgl-wheel-smoke/bin/python -m pip install dist/cmgl-1.1.0-py3-none-any.whl
/tmp/cmgl-wheel-smoke/bin/python -c "import cmgl; print(cmgl.__version__)"
/tmp/cmgl-wheel-smoke/bin/cmgl version
/tmp/cmgl-wheel-smoke/bin/cmgl doctor --skip-ledger
```

On Windows, use the corresponding `Scripts/python.exe` and `Scripts/cmgl.exe` paths.

## Automated CI Gates

- CI matrix passes on Python 3.10, 3.11, 3.12, and 3.13.
- Release CI builds package artifacts, runs examples, validates schemas, runs telemetry replay fixture, runs publishability, and runs `pip-audit`.
- Security workflow passes `pip-audit` and the high-confidence secret guard.
- CodeQL workflow is enabled.
- Dependency Review workflow is enabled.
- Live adapter workflow is enabled for main/release/tag/manual dispatch.

## PyPI Manual Gates

- Confirm `https://pypi.org/pypi/cmgl/json` is owned by this project before future publication.
- Configure PyPI Trusted Publisher:
  - owner/repository: `kadubon/certified-memory-governance-layer`
  - workflow: `.github/workflows/publish.yml`
  - environment: as configured in PyPI
  - project: `cmgl`
- Do not add long-lived PyPI API tokens to GitHub secrets.
- Optionally perform a TestPyPI publication rehearsal from a temporary test project name.

## GitHub Manual Gates

- Create a GitHub Release for `v1.1.0` using `docs/releases/v1.1.0.md` as the release note draft.
- Verify branch protection on `main`.
- Require CI before merge.
- Restrict who can publish releases.
- Enable secret scanning.
- Enable push protection.
- Enable Dependabot alerts.
- Enable Dependabot security updates.
- Enable CodeQL/code scanning.
- Enable dependency review.
- Fix repository topic typo `puthon` to `python`.
- Confirm repository description matches README purpose.

## Dependabot PRs

As of the release audit, 5 open Dependabot PRs exist for GitHub Actions:

- `actions/dependency-review-action` v4 to v5.
- `astral-sh/setup-uv` v5 to v7.
- `actions/checkout` v4 to v6.
- `github/codeql-action` v3 to v4.
- `actions/setup-python` v5 to v6.

Do not merge these automatically during the v1.1.0 stabilization. Review each PR separately and run the full gate before merging.

## Release Status

The v1.1.0 release was completed after PyPI Trusted Publishing was configured. Remaining items are repository maintenance tasks, not unresolved v1.1.0 code, test, packaging, or documentation defects.
