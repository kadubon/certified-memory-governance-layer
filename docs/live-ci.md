# Live Adapter CI

CMGL keeps pull-request CI deterministic and offline. Live adapter smoke is a release/main gate because it may call provider APIs, Neo4j, or framework code that depends on environment-specific setup.

## GitHub Environment

Create a GitHub Environment named `cmgl-live` and restrict who can approve jobs that use it. Store provider credentials only as environment secrets.

Recommended secrets:

- `OPENAI_API_KEY`: provider key used by Mem0 and Graphiti defaults.
- `NEO4J_URI`: Neo4j URI for Graphiti.
- `NEO4J_USER`: Neo4j user.
- `NEO4J_PASSWORD`: Neo4j password.
- `MEM0_TEST_USER_PREFIX`: isolated Mem0 test user prefix.

Never store provider keys in repository files, examples, fixtures, ledgers, issue reports, or workflow logs.

## Workflow Scope

`.github/workflows/live-adapters.yml` runs on:

- push to `main`
- push to `release/**`
- tags matching `v*`
- manual dispatch

Fork PRs do not run this workflow and should not receive live secrets. Ordinary PRs use offline fake-client tests.

## Local Dry Run

Use dry-run before enabling the environment:

```bash
uv run cmgl adapters doctor
uv run cmgl adapters live-smoke --target all --dry-run
```

Dry-run checks command wiring and required environment contracts without provider calls.

## Release/Main Gate

Protected release/main jobs should run:

```bash
uv run python scripts/live_adapter_smoke.py --target all
```

Missing required live secrets must fail the job. A provider failure should be treated as a release blocker unless it is clearly unrelated to CMGL adapter behavior.

## What The Gate Proves

The live gate proves that:

- optional adapter dependencies import in the release environment
- required provider environment is present
- Mem0 add/search can complete against the configured provider
- Graphiti can add/search an episode against configured Neo4j/provider setup
- LangMem tools work with a local LangGraph store
- LangGraph store helpers work without model calls

The live gate does not prove factual truth, production authorization policy correctness, provider availability outside the test window, or legal compliance.
