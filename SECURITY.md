# Security Policy

## Supported versions

CMGL v1.x is the supported stable line. Security fixes target the latest released v1 minor version unless otherwise stated. Users should upgrade to the newest v1 release before reporting a suspected fixed issue.

## Reporting vulnerabilities

Report suspected vulnerabilities privately to the maintainers. Do not post secrets, exploit details, private logs, private datasets, or credentials in public issues.

Include:

- affected version or commit
- minimal reproduction steps
- expected and observed behavior
- whether real private data or credentials may be involved

## Responsible disclosure

Maintainers will acknowledge reports when possible, investigate impact, prepare a fix, and coordinate public disclosure after a patch or mitigation is available.

## Governance limitations

CMGL does not guarantee factual truth. It provides procedural admissibility under declared policies, digests, evidence records, and receipts. A certified or admissible memory can still be factually wrong if the upstream evidence is wrong.

CMGL is not an authentication system, distributed ledger, malware scanner, or data-loss prevention product.

## Supply-chain policy

- Core tests must not require network services or API keys.
- Optional integrations must remain optional.
- Dependencies should be reviewed before release.
- PyPI publishing should use Trusted Publishing / OIDC rather than long-lived tokens.
- Examples use fake data only.

## Live adapter secrets

Live adapter CI must run only in a protected GitHub Environment. Provider keys and Neo4j credentials must be supplied as environment secrets and must never be committed to the repository.

Adapter receipts must not contain provider keys, cookies, private prompts, raw logs, or private datasets. Receipts may contain external backend IDs, source payload digests, authority scopes, and sanitized exception messages. Treat leaked receipts or logs as potentially sensitive if they reveal user IDs, backend IDs, or operational timing.

If a live smoke job leaks a secret or private receipt:

1. Revoke the affected provider key or credential.
2. Remove the leaked artifact or log according to the hosting platform process.
3. File a private security report with the affected version, workflow run, and exposure scope.
4. Rotate downstream secrets before re-running live smoke.

## Provider-key policy

CMGL does not need provider keys for core operation. Keys are required only by user-owned live integrations such as Mem0 or Graphiti when those frameworks call their configured LLM/embedder providers.

Use environment variables or a secret manager. Do not put provider keys in `cmgl.toml`, `.cmgl/ledger.jsonl`, examples, test fixtures, notebooks, issue reports, or documentation snippets.
