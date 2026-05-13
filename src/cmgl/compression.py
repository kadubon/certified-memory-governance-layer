from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cmgl.digest import sha256_digest
from cmgl.models import (
    CompressionAuditReport,
    CompressionBridgeProbe,
    CompressionCertificate,
    CompressionDeploymentProbe,
    CompressionFailureClass,
    CompressionGluingProbe,
    MetricResult,
    MetricStatus,
)
from cmgl.time import now_utc


@dataclass(frozen=True)
class CompressionProbeSuite:
    source_digest_map: dict[str, str]
    recoverability_probes: dict[str, bool]
    alias_hazards: list[str]
    lost_uncertainties: list[str]
    lost_exceptions: list[str]
    lost_uncertainty_severity: str = "none"

    def make_certificate(
        self,
        *,
        compressed_memory_id: str,
        source_memory_ids: list[str],
        source_size: int,
        compressed_size: int,
        source_coverage: float,
        recoverability_check: str = "pass",
    ) -> CompressionCertificate:
        return make_compression_certificate(
            compressed_memory_id=compressed_memory_id,
            source_memory_ids=source_memory_ids,
            source_size=source_size,
            compressed_size=compressed_size,
            recoverability_check=recoverability_check,
            source_coverage=source_coverage,
            lost_uncertainties=self.lost_uncertainties,
            lost_exceptions=self.lost_exceptions,
            source_digest_map=self.source_digest_map,
            recoverability_probes=self.recoverability_probes,
            lost_uncertainty_severity=self.lost_uncertainty_severity,
            alias_hazards=self.alias_hazards,
        )

    def bridge_probe(self, source_memory_ids: list[str]) -> CompressionBridgeProbe:
        missing = [
            memory_id for memory_id in source_memory_ids if memory_id not in self.source_digest_map
        ]
        body = {
            "schema_version": "cmgl.compression_bridge_probe.v1",
            "probe_id": "compression-bridge:source-coverage",
            "passed": not missing,
            "source_memory_ids": source_memory_ids,
            "reason_codes": [] if not missing else ["compression.bridge_failure"],
            "timestamp": now_utc(),
        }
        return CompressionBridgeProbe(**body, probe_digest=sha256_digest(body))

    def gluing_probe(self) -> CompressionGluingProbe:
        failed = bool(self.alias_hazards or self.lost_uncertainties)
        body = {
            "schema_version": "cmgl.compression_gluing_probe.v1",
            "probe_id": "compression-gluing:alias-uncertainty",
            "passed": not failed,
            "alias_hazards": self.alias_hazards,
            "lost_uncertainties": self.lost_uncertainties,
            "reason_codes": [] if not failed else ["compression.gluing_failure"],
            "timestamp": now_utc(),
        }
        return CompressionGluingProbe(**body, probe_digest=sha256_digest(body))

    def deployment_probe(self, *, recoverability_check: str = "pass") -> CompressionDeploymentProbe:
        probes_pass = (
            all(self.recoverability_probes.values()) if self.recoverability_probes else True
        )
        accountability_passed = not (self.alias_hazards or self.lost_exceptions)
        passed = probes_pass and accountability_passed and recoverability_check == "pass"
        body = {
            "schema_version": "cmgl.compression_deployment_probe.v1",
            "probe_id": "compression-deployment:recoverability-accountability",
            "passed": passed,
            "recoverability_check": recoverability_check,
            "accountability_passed": accountability_passed,
            "reason_codes": [] if passed else ["compression.deployment_failure"],
            "timestamp": now_utc(),
        }
        return CompressionDeploymentProbe(**body, probe_digest=sha256_digest(body))


def make_compression_certificate(
    *,
    compressed_memory_id: str,
    source_memory_ids: list[str],
    source_size: int,
    compressed_size: int,
    recoverability_check: str = "not_checked",
    source_coverage: float,
    lost_uncertainties: list[str] | None = None,
    lost_exceptions: list[str] | None = None,
    source_digest_map: dict[str, str] | None = None,
    recoverability_probes: dict[str, bool] | None = None,
    lost_uncertainty_severity: str = "none",
    accountability_budget: int = 0,
    collapse_budget: int = 0,
    alias_hazards: list[str] | None = None,
    timestamp: datetime | None = None,
) -> CompressionCertificate:
    compression_ratio = 0.0 if source_size <= 0 else compressed_size / source_size

    uncertainties = list(lost_uncertainties or [])
    exceptions = list(lost_exceptions or [])
    probes = dict(recoverability_probes or {})
    aliases = list(alias_hazards or [])
    provided_digest_map = dict(source_digest_map or {})
    missing_source_digests = bool(source_digest_map is not None) and any(
        memory_id not in provided_digest_map for memory_id in source_memory_ids
    )
    probes_pass = all(probes.values()) if probes else True
    has_high_uncertainty_loss = lost_uncertainty_severity == "high" and bool(uncertainties)
    if (
        exceptions
        or has_high_uncertainty_loss
        or aliases
        or not probes_pass
        or missing_source_digests
    ):
        decision = "reject"
    elif recoverability_check == "pass" and source_coverage >= 0.8:
        decision = "admit_as_summary_not_fact"
    elif recoverability_check == "not_checked" and source_coverage >= 0.8:
        decision = "shadow"
    else:
        decision = "reject"

    certificate_time = timestamp or now_utc()
    body = {
        "schema_version": "cmgl.compression_certificate.v1",
        "compressed_memory_id": compressed_memory_id,
        "source_memory_ids": source_memory_ids,
        "compression_ratio": compression_ratio,
        "recoverability_check": recoverability_check,
        "source_coverage": source_coverage,
        "lost_uncertainties": uncertainties,
        "lost_exceptions": exceptions,
        "source_digest_map": provided_digest_map,
        "recoverability_probes": probes,
        "lost_uncertainty_severity": lost_uncertainty_severity,
        "accountability_budget": accountability_budget,
        "collapse_budget": collapse_budget,
        "alias_hazards": aliases,
        "decision": decision,
        "timestamp": certificate_time,
    }
    return CompressionCertificate(**body, certificate_digest=sha256_digest(body))


def compression_metrics(certificate: CompressionCertificate) -> list[MetricResult]:
    timestamp = now_utc()
    source_ids = set(certificate.source_memory_ids)
    covered = set(certificate.source_digest_map)
    missing = sorted(source_ids - covered)
    failed_probes = sorted(
        probe for probe, passed in certificate.recoverability_probes.items() if not passed
    )
    return [
        MetricResult(
            metric_name="compression_source_digest_coverage",
            status=MetricStatus.VALID if not missing else MetricStatus.INVALID,
            value=0 if missing else 1,
            numerator=len(covered & source_ids),
            denominator=len(source_ids),
            reason_codes=[] if not missing else ["compression.source_digest_missing"],
            evidence_ids=list(certificate.source_digest_map.values()),
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="compression_recoverability_probes",
            status=MetricStatus.VALID if not failed_probes else MetricStatus.INVALID,
            value=len(failed_probes),
            reason_codes=[] if not failed_probes else ["compression.probe_failed"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="compression_alias_hazards",
            status=MetricStatus.VALID if not certificate.alias_hazards else MetricStatus.INVALID,
            value=len(certificate.alias_hazards),
            reason_codes=[] if not certificate.alias_hazards else ["compression.alias_hazard"],
            timestamp=timestamp,
        ),
        MetricResult(
            metric_name="compression_uncertainty_loss",
            status=MetricStatus.VALID
            if certificate.lost_uncertainty_severity != "high"
            else MetricStatus.INVALID,
            value=certificate.lost_uncertainty_severity,
            reason_codes=[]
            if certificate.lost_uncertainty_severity != "high"
            else ["compression.high_uncertainty_loss"],
            timestamp=timestamp,
        ),
    ]


def audit_compression_certificate(
    certificate: CompressionCertificate,
) -> CompressionAuditReport:
    metrics = compression_metrics(certificate)
    failure_classes: list[CompressionFailureClass] = []
    metric_by_name = {metric.metric_name: metric for metric in metrics}
    exact_declared = certificate.decision != "reject"
    exact_accountability = (
        metric_by_name["compression_source_digest_coverage"].status == MetricStatus.VALID
        and metric_by_name["compression_alias_hazards"].status == MetricStatus.VALID
        and metric_by_name["compression_uncertainty_loss"].status == MetricStatus.VALID
    )
    deployable = (
        exact_declared
        and exact_accountability
        and metric_by_name["compression_recoverability_probes"].status == MetricStatus.VALID
    )
    if not exact_declared:
        failure_classes.append(CompressionFailureClass.DECLARED_STATE)
    if not exact_accountability:
        failure_classes.append(CompressionFailureClass.ACCOUNTABILITY_STATE)
    if metric_by_name["compression_source_digest_coverage"].status != MetricStatus.VALID:
        failure_classes.append(CompressionFailureClass.BRIDGE)
    if metric_by_name["compression_alias_hazards"].status != MetricStatus.VALID:
        failure_classes.append(CompressionFailureClass.GLUING)
    if not deployable:
        failure_classes.append(CompressionFailureClass.DEPLOYMENT)
    body = {
        "schema_version": "cmgl.compression_audit_report.v1",
        "certificate_digest": certificate.certificate_digest,
        "exact_declared_state": exact_declared,
        "exact_accountability_state": exact_accountability,
        "deployable_exact_recovery": deployable,
        "failure_classes": failure_classes or [CompressionFailureClass.NONE],
        "metrics": metrics,
        "timestamp": now_utc(),
    }
    return CompressionAuditReport(**body, report_digest=sha256_digest(body))
