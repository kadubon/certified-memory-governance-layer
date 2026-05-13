from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timezone
from fnmatch import fnmatch
from uuid import uuid4
from warnings import warn

from cmgl.digest import sha256_digest
from cmgl.models import (
    AdmissionDecision,
    AuthorityBundle,
    AuthorityEvidenceBundle,
    AuthorityReceipt,
    DeclaredScope,
    MetricResult,
    MetricStatus,
    ProtectedAction,
    ProtectedActionRequest,
)
from cmgl.receipt_verifier import verify_authority_receipt
from cmgl.time import now_utc


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def make_declared_scope(
    *,
    actor: str,
    authority_scope: str,
    permitted_actions: Collection[ProtectedAction],
    resource_patterns: list[str] | None = None,
    expires_at: datetime | None = None,
    scope_id: str | None = None,
    timestamp: datetime | None = None,
) -> DeclaredScope:
    created_at = timestamp or now_utc()
    body = {
        "schema_version": "cmgl.declared_scope.v1",
        "scope_id": scope_id or f"scope:{uuid4()}",
        "actor": actor,
        "authority_scope": authority_scope,
        "permitted_actions": list(permitted_actions),
        "resource_patterns": resource_patterns or [],
        "expires_at": expires_at,
        "created_at": created_at,
    }
    return DeclaredScope(**body, scope_digest=sha256_digest(body))


def make_protected_action_request(
    *,
    action: ProtectedAction,
    actor: str,
    authority_scope: str,
    source_record: str,
    natural_language_justification: str | None = None,
    declared_scope: DeclaredScope | None = None,
    resource: str | None = None,
    request_id: str | None = None,
    timestamp: datetime | None = None,
) -> ProtectedActionRequest:
    request_time = timestamp or now_utc()
    body = {
        "schema_version": "cmgl.protected_action_request.v1",
        "request_id": request_id or f"protected-action:{uuid4()}",
        "action": action,
        "actor": actor,
        "authority_scope": authority_scope,
        "source_record": source_record,
        "natural_language_justification": natural_language_justification,
        "declared_scope_digest": None if declared_scope is None else declared_scope.scope_digest,
        "resource": resource,
        "timestamp": request_time,
    }
    return ProtectedActionRequest(**body, request_digest=sha256_digest(body))


def authorize_request(
    request: ProtectedActionRequest,
    *,
    declared_scope: DeclaredScope | None = None,
    policy_version: str = "cmgl.authority_policy.v2",
    now: datetime | None = None,
) -> AuthorityReceipt:
    reason_codes: list[str] = []
    check_time = _utc(now or now_utc())

    if declared_scope is None:
        reason_codes.append("authority.declared_scope_missing")
        if request.natural_language_justification:
            reason_codes.append("authority.natural_language_not_authorization")
    else:
        if request.declared_scope_digest != declared_scope.scope_digest:
            reason_codes.append("authority.declared_scope_digest_mismatch")
        if request.actor != declared_scope.actor:
            reason_codes.append("authority.actor_mismatch")
        if request.authority_scope != declared_scope.authority_scope:
            reason_codes.append("authority.scope_mismatch")
        if request.action not in declared_scope.permitted_actions:
            reason_codes.append("authority.action_not_permitted")
        if declared_scope.resource_patterns and (
            request.resource is None
            or not any(
                fnmatch(request.resource, pattern) for pattern in declared_scope.resource_patterns
            )
        ):
            reason_codes.append("authority.resource_not_permitted")
        if declared_scope.expires_at is not None and _utc(declared_scope.expires_at) < check_time:
            reason_codes.append("authority.scope_expired")

    if not reason_codes:
        decision = AdmissionDecision.ADMIT
        reason_codes.append("authority.scoped_authorizing")
    else:
        decision = AdmissionDecision.BLOCK

    receipt_time = now_utc()
    source_record_digest = sha256_digest(request.source_record)
    body = {
        "schema_version": "cmgl.authority_receipt.v1",
        "action": request.action,
        "actor": request.actor,
        "authority_scope": request.authority_scope,
        "source_record": request.source_record,
        "policy_version": policy_version,
        "decision": decision,
        "reason_codes": reason_codes,
        "request_digest": request.request_digest,
        "declared_scope_digest": request.declared_scope_digest,
        "source_record_digest": source_record_digest,
        "rule_ids": [f"cmgl.rule.{code}" for code in reason_codes],
        "timestamp": receipt_time,
    }
    return AuthorityReceipt(**body, receipt_digest=sha256_digest(body))


def make_authority_bundle(
    *,
    request: ProtectedActionRequest,
    declared_scope: DeclaredScope,
    receipt: AuthorityReceipt,
) -> AuthorityBundle:
    body = {
        "schema_version": "cmgl.authority_bundle.v1",
        "request": request,
        "declared_scope": declared_scope,
        "receipt": receipt,
    }
    return AuthorityBundle(**body, bundle_digest=sha256_digest(body))


def make_authority_evidence_bundle(
    *,
    request: ProtectedActionRequest,
    declared_scope: DeclaredScope,
    receipt: AuthorityReceipt,
    retained_authority_channels: list[str] | None = None,
    retained_channel_blocking: bool = False,
    timestamp: datetime | None = None,
) -> AuthorityEvidenceBundle:
    body = {
        "schema_version": "cmgl.authority_evidence_bundle.v1",
        "request": request,
        "declared_scope": declared_scope,
        "receipt": receipt,
        "retained_authority_channels": retained_authority_channels or [],
        "retained_channel_blocking": retained_channel_blocking,
        "timestamp": timestamp or now_utc(),
    }
    return AuthorityEvidenceBundle(**body, bundle_digest=sha256_digest(body))


def authorize_bundle(
    request: ProtectedActionRequest,
    *,
    declared_scope: DeclaredScope,
) -> AuthorityBundle:
    return make_authority_bundle(
        request=request,
        declared_scope=declared_scope,
        receipt=authorize_request(request, declared_scope=declared_scope),
    )


def make_authority_receipt(
    *,
    action: ProtectedAction,
    actor: str,
    authority_scope: str,
    source_record: str,
    policy_version: str = "cmgl.authority_policy.v1",
    allowed_scopes: Collection[str] | None = None,
    timestamp: datetime | None = None,
) -> AuthorityReceipt:
    warn(
        "make_authority_receipt is a legacy compatibility helper; use "
        "make_protected_action_request + authorize_request for strict authority.",
        DeprecationWarning,
        stacklevel=2,
    )
    allowed = set(allowed_scopes or {authority_scope})
    if authority_scope in allowed:
        decision = AdmissionDecision.ADMIT
        reason_codes = ["authority.scope_allowed"]
    else:
        decision = AdmissionDecision.BLOCK
        reason_codes = ["authority.scope_denied"]

    receipt_time = timestamp or now_utc()
    body = {
        "schema_version": "cmgl.authority_receipt.v1",
        "action": action,
        "actor": actor,
        "authority_scope": authority_scope,
        "source_record": source_record,
        "policy_version": policy_version,
        "decision": decision,
        "reason_codes": reason_codes,
        "request_digest": None,
        "declared_scope_digest": None,
        "source_record_digest": sha256_digest(source_record),
        "rule_ids": [f"cmgl.rule.{code}" for code in reason_codes],
        "timestamp": receipt_time,
    }
    return AuthorityReceipt(**body, receipt_digest=sha256_digest(body))


class StrictAuthorityVerifier:
    """Fail-closed verifier for protected actions."""

    def verify_bundle(self, bundle: AuthorityBundle) -> MetricResult:
        reason_codes: list[str] = []
        if bundle.request.declared_scope_digest != bundle.declared_scope.scope_digest:
            reason_codes.append("authority.declared_scope_digest_mismatch")
        if bundle.receipt.request_digest != bundle.request.request_digest:
            reason_codes.append("authority.request_digest_mismatch")
        if bundle.receipt.declared_scope_digest != bundle.declared_scope.scope_digest:
            reason_codes.append("authority.declared_scope_digest_mismatch")
        if bundle.receipt.action != bundle.request.action:
            reason_codes.append("authority.action_mismatch")
        if bundle.receipt.actor != bundle.request.actor:
            reason_codes.append("authority.actor_mismatch")
        if bundle.receipt.authority_scope != bundle.request.authority_scope:
            reason_codes.append("authority.scope_mismatch")
        receipt_result = self.verify(bundle.receipt)
        reason_codes.extend(receipt_result.reason_codes)
        return MetricResult(
            metric_name="authority_bundle_binding",
            status=MetricStatus.VALID if not reason_codes else MetricStatus.INVALID,
            value=0 if reason_codes else 1,
            reason_codes=reason_codes,
            evidence_ids=[
                bundle.request.request_digest,
                bundle.declared_scope.scope_digest,
                bundle.receipt.receipt_digest,
            ],
            timestamp=now_utc(),
        )

    def verify_evidence_bundle(self, bundle: AuthorityEvidenceBundle) -> MetricResult:
        base = self.verify_bundle(
            AuthorityBundle(
                request=bundle.request,
                declared_scope=bundle.declared_scope,
                receipt=bundle.receipt,
                bundle_digest=make_authority_bundle(
                    request=bundle.request,
                    declared_scope=bundle.declared_scope,
                    receipt=bundle.receipt,
                ).bundle_digest,
            )
        )
        reason_codes = list(base.reason_codes)
        if bundle.retained_channel_blocking:
            reason_codes.append("authority.retained_channel_blocking")
        return MetricResult(
            metric_name="authority_evidence_bundle_binding",
            status=MetricStatus.VALID if not reason_codes else MetricStatus.INVALID,
            value=0 if reason_codes else 1,
            reason_codes=reason_codes,
            evidence_ids=[
                bundle.request.request_digest,
                bundle.declared_scope.scope_digest,
                bundle.receipt.receipt_digest,
                bundle.bundle_digest,
            ],
            timestamp=now_utc(),
        )

    def verify(self, receipt: AuthorityReceipt) -> MetricResult:
        result = verify_authority_receipt(receipt)
        if receipt.decision != AdmissionDecision.ADMIT:
            return result.model_copy(
                update={
                    "status": MetricStatus.INVALID,
                    "reason_codes": [*result.reason_codes, "authority.blocked"],
                }
            )
        return result

    def allows(self, receipt: AuthorityReceipt) -> bool:
        return self.verify(receipt).status == MetricStatus.VALID

    def allows_bundle(self, bundle: AuthorityBundle) -> bool:
        return self.verify_bundle(bundle).status == MetricStatus.VALID
