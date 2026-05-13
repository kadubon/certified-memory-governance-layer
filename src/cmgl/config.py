from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

if sys.version_info >= (3, 11):  # pragma: no cover - type checked for Python 3.10
    import tomllib
else:  # pragma: no cover - exercised on Python 3.10 only
    import tomli as tomllib


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_provenance_depth: int = Field(default=8, ge=0)
    allow_weak_personal_memory: bool = True
    require_version_binding: bool = True
    require_evidence_manifest: bool = True
    require_authority_for_persistent_writes: bool = True
    strict_authority_verification: bool = True
    summary_as_fact_allowed: bool = False


class LedgerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = ".cmgl/ledger.jsonl"
    persist_append_receipts: bool = True
    duplicate_policy: str = "allow"


class AuthorityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict: bool = True
    reject_legacy_receipts: bool = True
    require_bundle: bool = True


class CMGLConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    ledger: LedgerConfig = Field(default_factory=LedgerConfig)
    authority: AuthorityConfig = Field(default_factory=AuthorityConfig)


def default_config_text() -> str:
    return """# CMGL local configuration.
# Defaults are intentionally strict for public OSS use.

[policy]
max_provenance_depth = 8
allow_weak_personal_memory = true
require_version_binding = true
require_evidence_manifest = true
require_authority_for_persistent_writes = true
strict_authority_verification = true
summary_as_fact_allowed = false

[ledger]
path = ".cmgl/ledger.jsonl"
persist_append_receipts = true
duplicate_policy = "allow"

[authority]
strict = true
reject_legacy_receipts = true
require_bundle = true
"""


def load_config(path: str | Path | None = None, *, cwd: str | Path = ".") -> CMGLConfig:
    config_path = _resolve_config_path(path, cwd=Path(cwd))
    if config_path is None:
        return CMGLConfig()
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid CMGL TOML config at {config_path}: {exc}") from exc
    try:
        return CMGLConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid CMGL config at {config_path}: {exc}") from exc


def write_default_config(path: str | Path) -> Path:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(default_config_text(), encoding="utf-8")
    return config_path


def _resolve_config_path(path: str | Path | None, *, cwd: Path) -> Path | None:
    if path is not None:
        return Path(path)
    candidates = [cwd / "cmgl.toml", cwd / ".cmgl" / "config.toml"]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def config_to_policy_kwargs(config: CMGLConfig) -> dict[str, Any]:
    return {
        "max_provenance_depth": config.policy.max_provenance_depth,
        "allow_weak_personal_memory": config.policy.allow_weak_personal_memory,
        "require_version_binding": config.policy.require_version_binding,
        "require_explicit_evidence_manifest": config.policy.require_evidence_manifest,
        "require_authority_for_persistent_writes": (
            config.policy.require_authority_for_persistent_writes
        ),
        "strict_authority_verification": config.policy.strict_authority_verification,
        "require_authority_bundle": config.authority.require_bundle,
    }
