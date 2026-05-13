# Dependencies

Runtime dependencies:

- Pydantic v2
- Typer
- Rich
- tomli on Python < 3.11, for TOML config loading

Development dependencies:

- pytest
- pytest-cov
- ruff
- mypy
- build
- pip-audit

Optional extras:

- `cmgl[mem0]`: Mem0 safe integration shim dependency.
- `cmgl[graphiti]`: Graphiti safe integration shim dependency.
- `cmgl[langmem]`: LangMem safe integration shim dependency.
- `cmgl[langgraph]`: LangGraph safe integration helper dependency.
- `cmgl[adapters]`: all supported adapter dependencies.
- `cmgl[signing]`: `cryptography` for optional local Ed25519 ledger signing.

Optional adapter and signing dependencies are not required for core tests or examples.
