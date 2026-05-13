from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from cmgl.canonical import canonical_json
from cmgl.digest import sha256_digest
from cmgl.ledger import AppendOnlyLedger
from cmgl.models import (
    AuthorityReceipt,
    LedgerIntegrityReceipt,
    LedgerLineStatus,
    MetricResult,
    MetricStatus,
)
from cmgl.obligations import ObligationVerifier
from cmgl.receipt_verifier import (
    verify_authority_receipt,
    verify_ledger_integrity_receipt,
    verify_metric_result,
)
from cmgl.rules import unknown_reason_codes, unknown_rule_ids
from cmgl.schemas import SCHEMA_MODELS
from cmgl.time import now_utc

SCHEMA_VERSION_TO_NAME = {
    model.model_fields["schema_version"].default: name
    for name, model in SCHEMA_MODELS.items()
    if "schema_version" in model.model_fields
}


def validate_record_object(raw: dict[str, Any], *, schema_name: str | None = None) -> MetricResult:
    resolved_schema = schema_name or SCHEMA_VERSION_TO_NAME.get(str(raw.get("schema_version")))
    reason_codes: list[str] = []
    if resolved_schema is None or resolved_schema not in SCHEMA_MODELS:
        reason_codes.append("validation.schema_missing")
        return _validation_metric(reason_codes)
    model = SCHEMA_MODELS[resolved_schema]
    try:
        record = model.model_validate(raw)
    except ValidationError:
        reason_codes.append("validation.schema_invalid")
        return _validation_metric(reason_codes)

    reason_codes.extend(_unknown_rule_reasons(record))
    metric = _validation_metric(reason_codes)
    if isinstance(record, AuthorityReceipt):
        authority_metric = verify_authority_receipt(record)
        reason_codes.extend(authority_metric.reason_codes)
        metric = _validation_metric(reason_codes)
    if isinstance(record, LedgerIntegrityReceipt):
        ledger_metric = verify_ledger_integrity_receipt(record)
        reason_codes.extend(ledger_metric.reason_codes)
        metric = _validation_metric(reason_codes)
    if isinstance(record, LedgerLineStatus):
        unknown = unknown_reason_codes(record.statuses)
        if unknown:
            reason_codes.append("receipt.unknown_reason_code")
            reason_codes.extend([f"unknown_reason_code:{code}" for code in unknown])
            metric = _validation_metric(reason_codes)
    if isinstance(record, MetricResult):
        rule_metric = verify_metric_result(record)
        reason_codes.extend(rule_metric.reason_codes)
        metric = _validation_metric(reason_codes)
    return metric


def validate_record_file(path: str | Path, *, schema_name: str | None = None) -> MetricResult:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return _validation_metric(["validation.schema_invalid"])
    return validate_record_object(raw, schema_name=schema_name)


def validate_ledger_file(path: str | Path) -> MetricResult:
    receipt = AppendOnlyLedger(path).integrity_receipt()
    metric = verify_ledger_integrity_receipt(receipt)
    if not receipt.ok:
        return metric.model_copy(
            update={
                "status": MetricStatus.INVALID,
                "reason_codes": [*metric.reason_codes, "validation.rule_invalid"],
            }
        )
    obligations = ObligationVerifier().verify(AppendOnlyLedger(path))
    if not obligations.ok:
        return metric.model_copy(
            update={
                "status": MetricStatus.INVALID,
                "reason_codes": [
                    *metric.reason_codes,
                    "conformance.obligation_unsatisfied",
                    "validation.rule_invalid",
                ],
                "evidence_ids": [*metric.evidence_ids, obligations.graph_digest],
            }
        )
    return metric


def validate_canonical_golden_vectors() -> MetricResult:
    vectors = [
        (
            {"b": 2, "a": 1},
            {"a": 1, "b": 2},
            '{"a":1,"b":2}',
        ),
        (
            {"outer": {"z": [3, 2, 1], "a": "x"}},
            {"outer": {"a": "x", "z": [3, 2, 1]}},
            '{"outer":{"a":"x","z":[3,2,1]}}',
        ),
    ]
    reason_codes: list[str] = []
    evidence_ids: list[str] = []
    for left, right, expected in vectors:
        left_json = canonical_json(left)
        right_json = canonical_json(right)
        if left_json != expected or right_json != expected:
            reason_codes.append("validation.canonical_mismatch")
        evidence_ids.append(sha256_digest(left_json))
    return MetricResult(
        metric_name="canonical_json_golden_vectors",
        status=MetricStatus.VALID if not reason_codes else MetricStatus.INVALID,
        value=1 if not reason_codes else 0,
        reason_codes=reason_codes or ["validation.canonical_valid"],
        evidence_ids=evidence_ids,
        timestamp=now_utc(),
    )


def _unknown_rule_reasons(record: Any) -> list[str]:
    reason_codes: list[str] = []
    raw_reason_codes = getattr(record, "reason_codes", None)
    if isinstance(raw_reason_codes, list):
        unknown = unknown_reason_codes([str(item) for item in raw_reason_codes])
        if unknown:
            reason_codes.append("receipt.unknown_reason_code")
            reason_codes.extend([f"unknown_reason_code:{code}" for code in unknown])
    raw_rule_ids = getattr(record, "rule_ids", None)
    if isinstance(raw_rule_ids, list):
        unknown = unknown_rule_ids([str(item) for item in raw_rule_ids])
        if unknown:
            reason_codes.append("receipt.unknown_rule_id")
            reason_codes.extend([f"unknown_rule_id:{rule_id}" for rule_id in unknown])
    return reason_codes


def _validation_metric(reason_codes: list[str]) -> MetricResult:
    return MetricResult(
        metric_name="record_validation",
        status=MetricStatus.VALID if not reason_codes else MetricStatus.INVALID,
        value=0 if reason_codes else 1,
        reason_codes=reason_codes,
        timestamp=now_utc(),
    )
