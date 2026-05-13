from __future__ import annotations

from typing import Literal

from pydantic import field_validator

from cmgl.contracts.base import CMGLModel, validate_digest


class SemanticRule(CMGLModel):
    schema_version: Literal["cmgl.semantic_rule.v1"] = "cmgl.semantic_rule.v1"
    rule_id: str
    description: str
    applies_to: str
    fail_closed: bool = True
    rule_digest: str

    @field_validator("rule_digest")
    @classmethod
    def validate_rule_digest(cls, value: str) -> str:
        return validate_digest(value)
