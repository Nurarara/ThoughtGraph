from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


VERIFICATION_STATUSES = {"unverified", "needs_review", "supported", "disputed", "refuted", "verified"}
EVIDENCE_STANCES = {"supporting", "refuting", "context"}
MODERATION_SUBJECT_TYPES = {"node", "claim", "source", "user", "media", "post"}
MODERATION_REPORT_STATUSES = {"open", "triaged", "actioned", "dismissed", "resolved"}
ENFORCEMENT_STATES = {"no_action", "limited", "blocked", "removed", "suspended", "appealed"}


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return value
    normalized = value.strip()
    return normalized or None


class TrustClaimCreate(BaseModel):
    claim_text: str = Field(min_length=3, max_length=4000)
    node_id: str | None = None
    verification_status: str = Field(default="unverified")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale_text: str | None = Field(default=None, max_length=4000)
    factors: dict = Field(default_factory=dict)
    metadata_json: dict = Field(default_factory=dict)

    @field_validator("verification_status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in VERIFICATION_STATUSES:
            raise ValueError("invalid verification_status")
        return value

    @field_validator("claim_text", "rationale_text")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return _normalize_text(value)


class TrustSourceCreate(BaseModel):
    source_type: str = Field(default="url", max_length=32)
    url: HttpUrl | None = None
    title: str | None = Field(default=None, max_length=300)
    author: str | None = Field(default=None, max_length=200)
    published_at: datetime | None = None
    credibility_score: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata_json: dict = Field(default_factory=dict)

    @field_validator("title", "author")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _normalize_text(value)


class ClaimEvidenceCreate(BaseModel):
    source_id: str | None = None
    node_id: str | None = None
    evidence_type: str = Field(default="source", max_length=32)
    stance: str = Field(default="context")
    summary: str = Field(min_length=3, max_length=4000)
    excerpt: str | None = Field(default=None, max_length=4000)
    url: HttpUrl | None = None
    weight: float = Field(default=0.0, ge=-1.0, le=1.0)
    metadata_json: dict = Field(default_factory=dict)

    @field_validator("stance")
    @classmethod
    def validate_stance(cls, value: str) -> str:
        if value not in EVIDENCE_STANCES:
            raise ValueError("invalid evidence stance")
        return value

    @field_validator("summary", "excerpt")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return _normalize_text(value)


class TrustRationaleCreate(BaseModel):
    verification_status: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    rationale_text: str = Field(min_length=3, max_length=4000)
    factors: dict = Field(default_factory=dict)
    metadata_json: dict = Field(default_factory=dict)

    @field_validator("verification_status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in VERIFICATION_STATUSES:
            raise ValueError("invalid verification_status")
        return value

    @field_validator("rationale_text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = _normalize_text(value)
        if normalized is None:
            raise ValueError("rationale_text cannot be empty")
        return normalized


class TrustSourceRead(BaseModel):
    id: str
    source_type: str
    url: str | None
    domain: str | None
    title: str | None
    author: str | None
    published_at: datetime | None
    credibility_score: float
    metadata_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ClaimEvidenceRead(BaseModel):
    id: str
    claim_id: str
    source_id: str | None
    node_id: str | None
    evidence_type: str
    stance: str
    summary: str
    excerpt: str | None
    url: str | None
    weight: float
    metadata_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class TrustRationaleRead(BaseModel):
    id: str
    claim_id: str
    version: int
    verification_status: str
    confidence_score: float
    rationale_text: str
    factors_json: dict
    created_by_user_id: str
    metadata_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class TrustClaimRead(BaseModel):
    id: str
    node_id: str | None
    created_by_user_id: str
    claim_text: str
    canonical_text: str
    verification_status: str
    confidence_score: float
    current_rationale_version: int
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProvenanceSnapshotRead(BaseModel):
    id: str
    claim_id: str | None
    node_id: str | None
    assembled_by_user_id: str
    summary: str
    graph_json: dict
    metadata_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ProvenanceRead(BaseModel):
    summary: str
    node_id: str | None
    claim: TrustClaimRead | None = None
    claims: list[TrustClaimRead] = Field(default_factory=list)
    evidence: list[ClaimEvidenceRead] = Field(default_factory=list)
    sources: list[TrustSourceRead] = Field(default_factory=list)
    rationales: list[TrustRationaleRead] = Field(default_factory=list)
    snapshot: ProvenanceSnapshotRead | None = None
    graph: dict = Field(default_factory=dict)


class ModerationReportCreate(BaseModel):
    subject_type: str
    subject_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=2, max_length=64)
    details: str | None = Field(default=None, max_length=4000)
    metadata_json: dict = Field(default_factory=dict)

    @field_validator("subject_type")
    @classmethod
    def validate_subject_type(cls, value: str) -> str:
        if value not in MODERATION_SUBJECT_TYPES:
            raise ValueError("invalid moderation subject_type")
        return value


class ModerationReportResolve(BaseModel):
    status: str
    resolution_note: str | None = Field(default=None, max_length=4000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in MODERATION_REPORT_STATUSES:
            raise ValueError("invalid moderation report status")
        return value


class ModerationEnforcementUpdate(BaseModel):
    subject_type: str
    subject_id: str = Field(min_length=1, max_length=64)
    state: str
    blocked_from_discovery: bool = False
    reason: str | None = Field(default=None, max_length=4000)
    expires_at: datetime | None = None
    metadata_json: dict = Field(default_factory=dict)
    report_id: str | None = None

    @field_validator("subject_type")
    @classmethod
    def validate_subject_type(cls, value: str) -> str:
        if value not in MODERATION_SUBJECT_TYPES:
            raise ValueError("invalid moderation subject_type")
        return value

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        if value not in ENFORCEMENT_STATES:
            raise ValueError("invalid enforcement state")
        return value


class ModerationEventRead(BaseModel):
    id: str
    report_id: str | None
    subject_type: str
    subject_id: str
    actor_id: str | None
    event_type: str
    from_state: str | None
    to_state: str | None
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ModerationReportRead(BaseModel):
    id: str
    reporter_id: str
    subject_type: str
    subject_id: str
    reason: str
    details: str
    status: str
    resolved_at: datetime | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModerationEnforcementRead(BaseModel):
    id: str
    subject_type: str
    subject_id: str
    state: str
    blocked_from_discovery: bool
    enforced_by_user_id: str | None
    reason: str
    expires_at: datetime | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
