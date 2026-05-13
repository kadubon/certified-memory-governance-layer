from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from cmgl.contracts.base import CMGLModel, validate_digest


class ContaminationContext(CMGLModel):
    schema_version: Literal["cmgl.contamination_context.v1"] = "cmgl.contamination_context.v1"
    shared_memory_ids: list[str] = Field(default_factory=list)
    cross_agent_memory_ids: list[str] = Field(default_factory=list)
    broker_agent_ids: list[str] = Field(default_factory=list)


class ContaminationAuditReport(CMGLModel):
    schema_version: Literal["cmgl.contamination_audit_report.v1"] = (
        "cmgl.contamination_audit_report.v1"
    )
    lane_counts: dict[str, int]
    lane_risk_scores: dict[str, float]
    discounted_risk_score: float = Field(ge=0)
    broker_concentration: dict[str, int] = Field(default_factory=dict)
    cross_agent_shared_memory_ids: list[str] = Field(default_factory=list)
    contradiction_reserve: int = Field(default=0, ge=0)
    max_positive_excursion: float = Field(default=0.0, ge=0)
    realized_fork_count: int = Field(default=0, ge=0)
    post_fork_recovery_quality: float | None = Field(default=None, ge=0, le=1)
    report_digest: str
    timestamp: datetime

    @field_validator("report_digest")
    @classmethod
    def validate_contamination_report_digest(cls, value: str) -> str:
        return validate_digest(value)


class ContaminationStateReplay(CMGLModel):
    schema_version: Literal["cmgl.contamination_state_replay.v1"] = (
        "cmgl.contamination_state_replay.v1"
    )
    events_replayed: int = Field(ge=0)
    contradiction_reserve: int = Field(default=0, ge=0)
    max_positive_excursion: float = Field(default=0.0, ge=0)
    low_reserve_residence: int = Field(default=0, ge=0)
    realized_fork_count: int = Field(default=0, ge=0)
    post_fork_recovery_quality: float | None = Field(default=None, ge=0, le=1)
    cross_agent_shared_memory_ids: list[str] = Field(default_factory=list)
    replay_digest: str
    timestamp: datetime

    @field_validator("replay_digest")
    @classmethod
    def validate_state_replay_digest(cls, value: str) -> str:
        return validate_digest(value)
