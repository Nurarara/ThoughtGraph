from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models.trust_moderation  # noqa: F401 - registers new tables on Base metadata.
from app.core.config import get_settings
from app.db import session as db_session
from app.main import create_app
from app.models.domain_event import DomainEvent
from app.schemas.node import NodeCreate
from app.schemas.trust_moderation import (
    ClaimEvidenceCreate,
    ModerationEnforcementUpdate,
    ModerationReportCreate,
    ModerationReportResolve,
    TrustClaimCreate,
    TrustRationaleCreate,
    TrustSourceCreate,
)
from app.services.node_service import create_node
from app.services.trust_moderation_service import (
    add_claim_evidence,
    add_rationale_version,
    assemble_claim_provenance,
    create_claim,
    create_moderation_report,
    create_source,
    is_blocked_from_discovery,
    list_moderation_events,
    resolve_moderation_report,
    set_enforcement_state,
)


@pytest.fixture(autouse=True)
def reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def session(tmp_path: Path) -> Session:
    database_path = tmp_path / "trust_moderation.db"
    db_session.set_database_url(f"sqlite:///{database_path}")
    create_app()
    db_session.init_db()
    database_session = db_session.SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()


def test_trust_provenance_and_moderation_emit_domain_events(session: Session) -> None:
    node = create_node(
        session,
        "local-user",
        NodeCreate(
            kind="thought",
            title="Trust layer",
            content_text="Claims should include evidence, sources, and versioned rationales.",
            visibility="public",
        ),
    )
    claim = create_claim(
        session,
        "local-user",
        TrustClaimCreate(
            node_id=node.id,
            claim_text="ThoughtGraph claims can be traced to explicit evidence.",
            verification_status="needs_review",
            confidence_score=0.2,
            rationale_text="Initial moderator review is required.",
            factors={"initial": True},
        ),
    )
    source = create_source(
        session,
        "local-user",
        TrustSourceCreate(
            url="https://example.com/trust-spec",
            title="Trust Spec",
            credibility_score=0.7,
        ),
    )
    evidence = add_claim_evidence(
        session,
        "local-user",
        claim.id,
        ClaimEvidenceCreate(
            source_id=source.id,
            stance="supporting",
            summary="The source describes explicit provenance links.",
            weight=0.6,
        ),
    )
    rationale = add_rationale_version(
        session,
        "local-user",
        claim.id,
        TrustRationaleCreate(
            verification_status="supported",
            confidence_score=0.76,
            rationale_text="One supporting source is attached and inspectable.",
            factors={"supporting_evidence": 1},
        ),
    )
    provenance = assemble_claim_provenance(session, "local-user", claim.id)

    assert evidence.stance == "supporting"
    assert rationale.version == 2
    assert provenance.snapshot is not None
    assert provenance.claim is not None
    assert provenance.claim.verification_status == "supported"
    assert provenance.graph["claims"][0]["current_rationale_version"] == 2

    report = create_moderation_report(
        session,
        "local-user",
        ModerationReportCreate(subject_type="node", subject_id=node.id, reason="misleading", details="Needs review."),
    )
    enforcement = set_enforcement_state(
        session,
        "local-user",
        ModerationEnforcementUpdate(
            subject_type="node",
            subject_id=node.id,
            state="limited",
            blocked_from_discovery=True,
            reason="Temporarily hide while moderation review is active.",
            report_id=report.id,
        ),
    )
    resolved = resolve_moderation_report(
        session,
        "local-user",
        report.id,
        ModerationReportResolve(status="resolved", resolution_note="Temporary discovery block applied."),
    )

    assert enforcement.blocked_from_discovery is True
    assert is_blocked_from_discovery(session, "node", node.id) is True
    assert resolved.status == "resolved"
    assert len(list_moderation_events(session, subject_type="node", subject_id=node.id)) == 3

    emitted_types = set(session.scalars(select(DomainEvent.event_type)).all())
    assert {
        "trust_claim_created",
        "trust_source_created",
        "claim_evidence_added",
        "trust_rationale_version_created",
        "trust_claim_status_changed",
        "provenance_snapshot_assembled",
        "moderation_report_created",
        "moderation_enforcement_updated",
        "moderation_report_resolved",
    }.issubset(emitted_types)


def test_create_source_dedupes_same_user_url_without_extra_event(session: Session) -> None:
    first = create_source(
        session,
        "local-user",
        TrustSourceCreate(
            url="https://example.com/source",
            title="Original Source",
            credibility_score=0.7,
        ),
    )
    second = create_source(
        session,
        "local-user",
        TrustSourceCreate(
            url="https://EXAMPLE.com/source",
            title="Duplicate Source",
            credibility_score=0.2,
        ),
    )

    source_events = list(
        session.scalars(select(DomainEvent).where(DomainEvent.event_type == "trust_source_created"))
    )

    assert second.id == first.id
    assert len(source_events) == 1
