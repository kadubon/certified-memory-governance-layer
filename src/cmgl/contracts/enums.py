from __future__ import annotations

from enum import Enum


class BackendName(str, Enum):
    INMEMORY = "inmemory"
    MEM0 = "mem0"
    GRAPHITI = "graphiti"
    LANGMEM = "langmem"
    LETTA = "letta"
    COGNEE = "cognee"
    MEMOS = "memos"
    CUSTOM = "custom"


class MemoryEventType(str, Enum):
    MEMORY_WRITE = "memory_write"
    MEMORY_READ = "memory_read"
    MEMORY_UPDATE = "memory_update"
    MEMORY_DELETE = "memory_delete"
    MEMORY_RETRIEVE = "memory_retrieve"
    MEMORY_SUPERSEDE = "memory_supersede"
    MEMORY_TOMBSTONE = "memory_tombstone"
    CORRECTION = "correction"


class ContaminationLane(str, Enum):
    USER_CLAIM = "user_claim"
    TOOL_OBSERVATION = "tool_observation"
    EXTERNAL_DOC = "external_doc"
    MODEL_INFERENCE = "model_inference"
    SUMMARY = "summary"
    REGENERATED_SUMMARY = "regenerated_summary"
    SYNTHETIC_EVAL = "synthetic_eval"
    POLICY_MEMORY = "policy_memory"


class MemoryStatus(str, Enum):
    RAW = "raw"
    CANDIDATE = "candidate"
    VERIFIED_SHADOW = "verified_shadow"
    CERTIFIED = "certified"
    ADMISSIBLE = "admissible"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"
    TOMBSTONED = "tombstoned"
    QUARANTINED = "quarantined"


class AdmissionDecision(str, Enum):
    ADMIT = "admit"
    BLOCK = "block"
    SHADOW = "shadow"
    QUARANTINE = "quarantine"


class AdapterOperationStatus(str, Enum):
    NOT_CALLED = "not_called"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    COMPENSATED = "compensated"


class ProtectedAction(str, Enum):
    PERSISTENT_MEMORY_WRITE = "persistent_memory_write"
    PERSISTENT_MEMORY_UPDATE = "persistent_memory_update"
    PERSISTENT_MEMORY_DELETE = "persistent_memory_delete"
    MEMORY_TOMBSTONE = "memory_tombstone"
    MEMORY_EXPORT = "memory_export"
    MEMORY_IMPORT = "memory_import"
    CROSS_AGENT_MEMORY_SHARE = "cross_agent_memory_share"
    TOOL_RESULT_TO_FACT_PROMOTION = "tool_result_to_fact_promotion"
    SUMMARY_TO_LONG_TERM_MEMORY_PROMOTION = "summary_to_long_term_memory_promotion"
    RETRIEVAL_POLICY_CHANGE = "retrieval_policy_change"
    COMPRESSION_POLICY_CHANGE = "compression_policy_change"
    CHECKER_POLICY_CHANGE = "checker_policy_change"
    EXTERNAL_EFFECT = "external_effect"
    DELEGATION_TO_SUBAGENT = "delegation_to_subagent"


class MetricStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    DEGRADED = "degraded"
    NONCOMPARABLE = "noncomparable"
    NOT_COMPUTABLE = "not_computable"
    BEST_EFFORT = "best_effort"


class GovernanceProfile(str, Enum):
    STRICT = "strict"
    OPERATIONAL = "operational"
    LEGACY = "legacy"


class ConformanceProfile(str, Enum):
    STRICT = "strict"
    OPERATIONAL = "operational"
    LEGACY = "legacy"


class ConformanceLevel(str, Enum):
    IMPLEMENTED = "implemented"
    EXECUTABLE_SUBSET = "executable_subset"
    SCHEMA_ONLY = "schema_only"
    NOT_IMPLEMENTED = "not_implemented"


class ConformanceSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class TelemetryOutcomeStatus(str, Enum):
    ACCEPTED = "accepted"
    DEDUPLICATED = "deduplicated"
    REJECTED = "rejected"
    DOWNGRADED = "downgraded"


class CompressionFailureClass(str, Enum):
    NONE = "none"
    DECLARED_STATE = "declared_state"
    ACCOUNTABILITY_STATE = "accountability_state"
    BRIDGE = "bridge"
    GLUING = "gluing"
    DEPLOYMENT = "deployment"


class WorkflowReportMode(str, Enum):
    CERTIFIED_LOWER_BOUND = "certified_lower_bound"
    DIAGNOSTIC_ONLY = "diagnostic_only"


class ObligationStatus(str, Enum):
    SATISFIED = "satisfied"
    MISSING = "missing"
    MISMATCHED = "mismatched"
    STALE = "stale"
    UNKNOWN = "unknown"
    DEGRADED = "degraded"


class ChallengeStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class AbsenceNoticeType(str, Enum):
    MISSING_SOURCE = "missing_source"
    MISSING_EVIDENCE = "missing_evidence"
    DISCLOSURE_UPDATE = "disclosure_update"


class TelemetryEventType(str, Enum):
    MEM_WRITE = "mem_write"
    MEM_REPLACE = "mem_replace"
    MEM_DELETE = "mem_delete"
    MEM_READ = "mem_read"
    MEM_USE = "mem_use"
    MEM_VERIFY = "mem_verify"
    MEM_CORRECT = "mem_correct"
    MEM_RETRIEVE = "mem_retrieve"


class LifecycleStage(str, Enum):
    SHADOW_TRIAL = "shadow_trial"
    LEASE_TRIAL = "lease_trial"
    ACTIVE_PROMOTION = "active_promotion"
    ROLLBACK = "rollback"
    QUARANTINE = "quarantine"


class WorkflowLayer(str, Enum):
    VALIDATION = "validation"
    REVIEW = "review"
    AUTHORIZATION = "authorization"
    MEMORY_GOVERNANCE = "memory_governance"
    RELEASE = "release"
    ROLLBACK = "rollback"
    INCIDENT_RESPONSE = "incident_response"
