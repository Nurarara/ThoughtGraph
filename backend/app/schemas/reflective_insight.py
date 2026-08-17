from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


ReflectiveInsightKind = Literal[
    "weekly_report",
    "attention_drift",
    "influence_summary",
    "cluster_growth_decay",
    "diversity_warning",
    "source_shaping_summary",
]

ReflectiveSeverity = Literal["info", "warning"]


class ReflectiveEvidenceRead(BaseModel):
    evidence_type: Literal["node", "cluster", "edge", "event", "source"]
    id: str
    label: str
    reason: str
    created_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class ReflectiveInsightRead(BaseModel):
    kind: ReflectiveInsightKind
    title: str
    summary: str
    severity: ReflectiveSeverity = "info"
    confidence: float = Field(ge=0.0, le=1.0)
    metrics: dict = Field(default_factory=dict)
    evidence: list[ReflectiveEvidenceRead] = Field(default_factory=list)
    action_hint: str | None = None


class ReflectiveWeeklyReportRead(BaseModel):
    id: str | None = None
    week_start: date
    week_end: date
    summary: str
    thought_count: int
    insight_count: int
    content: dict


class ReflectiveLoopRunRead(BaseModel):
    user_id: str
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    workflow_job_id: str | None = None
    workflow_status: str | None = None
    report: ReflectiveWeeklyReportRead
    insights: list[ReflectiveInsightRead]
    persisted_insight_ids: list[str] = Field(default_factory=list)
    event_id: str | None = None


class ReflectiveLoopRequest(BaseModel):
    reference_time: datetime | None = None
    run_inline: bool = True


class ReflectiveWindowRead(BaseModel):
    current_start: datetime
    current_end: datetime
    comparison_start: datetime
    comparison_end: datetime


class ReflectiveMetricRead(BaseModel):
    key: str
    label: str
    current: float
    previous: float
    delta: float
    unit: str
    method: str


class ReflectiveConfidenceRead(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    label: Literal["low", "medium", "high"]
    basis: str
    sample_size: int = Field(ge=0)
    minimum_sample_size: int = Field(ge=1)


class ReflectiveFeedbackRead(BaseModel):
    dismissed: bool = False
    correction: Literal["inaccurate", "wrong_evidence", "not_useful"] | None = None
    annotation: str | None = None
    updated_at: datetime | None = None


class ReflectiveFeedbackUpdate(BaseModel):
    dismissed: bool | None = None
    correction: Literal["inaccurate", "wrong_evidence", "not_useful"] | None = None
    annotation: str | None = Field(default=None, max_length=1000)


class PersistedReflectiveInsightRead(BaseModel):
    id: str
    kind: Literal["attention_drift"]
    contract_version: int
    title: str
    summary: str
    generated_at: datetime
    status: Literal["ready", "insufficient_data"]
    window: ReflectiveWindowRead
    metrics: list[ReflectiveMetricRead]
    evidence: list[ReflectiveEvidenceRead]
    confidence: ReflectiveConfidenceRead
    limitations: list[str]
    action_hint: str | None = None
    feedback: ReflectiveFeedbackRead
