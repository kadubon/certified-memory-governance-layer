from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest
from cmgl.contracts.enums import AdmissionDecision, ProtectedAction


class AuthorityReceipt(CMGLModel):
    schema_version: Literal["cmgl.authority_receipt.v1"] = "cmgl.authority_receipt.v1"
    action: ProtectedAction
    actor: str
    authority_scope: str
    source_record: str
    policy_version: str
    decision: AdmissionDecision
    reason_codes: list[str]
    request_digest: str | None = None
    declared_scope_digest: str | None = None
    source_record_digest: str | None = None
    rule_ids: list[str] = Field(default_factory=list)
    receipt_digest: str
    timestamp: datetime

    @field_validator(
        "receipt_digest", "request_digest", "declared_scope_digest", "source_record_digest"
    )
    @classmethod
    def validate_authority_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)


class DeclaredScope(CMGLModel):
    schema_version: Literal["cmgl.declared_scope.v1"] = "cmgl.declared_scope.v1"
    scope_id: str
    actor: str
    authority_scope: str
    permitted_actions: list[ProtectedAction]
    resource_patterns: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    scope_digest: str
    created_at: datetime

    @field_validator("scope_digest")
    @classmethod
    def validate_scope_digest(cls, value: str) -> str:
        return validate_digest(value)


class ProtectedActionRequest(CMGLModel):
    schema_version: Literal["cmgl.protected_action_request.v1"] = "cmgl.protected_action_request.v1"
    request_id: str
    action: ProtectedAction
    actor: str
    authority_scope: str
    source_record: str
    natural_language_justification: str | None = None
    declared_scope_digest: str | None = None
    resource: str | None = None
    request_digest: str
    timestamp: datetime

    @field_validator("declared_scope_digest", "request_digest")
    @classmethod
    def validate_request_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_digest(value)


class AuthorityBundle(CMGLModel):
    schema_version: Literal["cmgl.authority_bundle.v1"] = "cmgl.authority_bundle.v1"
    request: ProtectedActionRequest
    declared_scope: DeclaredScope
    receipt: AuthorityReceipt
    bundle_digest: str

    @field_validator("bundle_digest")
    @classmethod
    def validate_bundle_digest(cls, value: str) -> str:
        return validate_digest(value)


class AuthorityEvidenceBundle(CMGLModel):
    schema_version: Literal["cmgl.authority_evidence_bundle.v1"] = (
        "cmgl.authority_evidence_bundle.v1"
    )
    request: ProtectedActionRequest
    declared_scope: DeclaredScope
    receipt: AuthorityReceipt
    retained_authority_channels: list[str] = Field(default_factory=list)
    retained_channel_blocking: bool = False
    bundle_digest: str
    timestamp: datetime

    @field_validator("bundle_digest")
    @classmethod
    def validate_authority_evidence_digest(cls, value: str) -> str:
        return validate_digest(value)
