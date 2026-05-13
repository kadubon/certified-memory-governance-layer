# Changelog

All notable changes to CMGL are documented here.

## 1.1.0 - 2026-05-14

### Added

- Stable public API policy and smoke tests for the documented top-level API.
- Adapter operation evidence through `ExternalMemoryRef` and `AdapterOperationReceipt`.
- Safe adapter live-smoke entry point with skip-on-missing-provider-env default and strict `--require-live-env` mode.
- `cmgl adapters doctor` and `cmgl adapters live-smoke` CLI commands.
- Release documentation for PyPI Trusted Publishing, GitHub release creation, and manual repository metadata gates.
- Publishability checks for release docs, lockfile freshness, CLI smoke, built artifacts, wheel import, and manual release checklist output.

### Changed

- README install instructions now distinguish post-publication PyPI install, GitHub source install, and local development install.
- Adapter documentation now states the tested support level: stable shim, fake-client tested, optional live-smoke supported, and no cloud/provider dependency in core tests.
- Live adapter smoke no longer constructs Mem0 or Graphiti clients when required provider environment variables are absent, unless strict mode is requested.
- Publish workflow uses PyPI Trusted Publishing / OIDC with publish permissions scoped to the publish job.

### Security

- Release docs explicitly require PyPI Trusted Publisher setup and prohibit long-lived PyPI tokens.
- Security docs cover live adapter secrets, provider-key handling, and leaked receipt/log response.

### Known Manual Release Gates

- `cmgl` is not yet published on PyPI at the time of this preparation; the first upload must be performed through PyPI Trusted Publishing.
- GitHub Releases are currently empty and require a human-created `v1.1.0` release.
- Five Dependabot PRs for GitHub Actions updates are open and should be reviewed separately.
- GitHub repository topic `puthon` should be corrected manually to `python`.
