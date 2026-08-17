from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content_node import ContentNode
from app.models.trust_moderation import (
    ClaimEvidence,
    ModerationEnforcementState,
    ModerationEventLog,
    ModerationReport,
    ProvenanceSnapshot,
    TrustClaim,
    TrustRationaleVersion,
    TrustSource,
)
from app.models.user import User
from app.schemas.trust_moderation import (
    ClaimEvidenceCreate,
    ClaimEvidenceRead,
    ModerationEnforcementRead,
    ModerationEnforcementUpdate,
    ModerationEventRead,
    ModerationReportCreate,
    ModerationReportRead,
    ModerationReportResolve,
    ProvenanceRead,
    ProvenanceSnapshotRead,
    TrustClaimCreate,
    TrustClaimRead,
    TrustRationaleCreate,
    TrustRationaleRead,
    TrustSourceCreate,
    TrustSourceRead,
)
from app.services.event_service import emit_event
from app.services.social_service import can_view_node
from app.services.user_service import ensure_user_exists


def create_claim(session: Session, user_id: str, payload: TrustClaimCreate) -> TrustClaimRead:
    ensure_user_exists(session, user_id)
    _ensure_node_is_visible(session, user_id, payload.node_id)
    claim = TrustClaim(
        node_id=payload.node_id,
        created_by_user_id=user_id,
        claim_text=payload.claim_text,
        canonical_text=_canonical_claim_text(payload.claim_text),
        verification_status=payload.verification_status,
        confidence_score=payload.confidence_score,
        metadata_json=payload.metadata_json,
    )
    session.add(claim)
    session.flush()

    rationale = TrustRationaleVersion(
        claim_id=claim.id,
        version=1,
        verification_status=payload.verification_status,
        confidence_score=payload.confidence_score,
        rationale_text=payload.rationale_text or "Claim recorded and awaiting verification.",
        factors_json=payload.factors,
        created_by_user_id=user_id,
        metadata_json={"source": "claim_create"},
    )
    session.add(rationale)
    session.flush()
    claim.current_rationale_version = rationale.version
    session.add(claim)

    emit_event(
        session,
        event_type="trust_claim_created",
        aggregate_type="trust_claim",
        aggregate_id=claim.id,
        actor_id=user_id,
        payload={
            "node_id": claim.node_id,
            "verification_status": claim.verification_status,
            "confidence_score": claim.confidence_score,
            "rationale_version": rationale.version,
        },
    )
    emit_event(
        session,
        event_type="trust_rationale_version_created",
        aggregate_type="trust_claim",
        aggregate_id=claim.id,
        actor_id=user_id,
        payload=_rationale_event_payload(rationale),
    )
    session.commit()
    session.refresh(claim)
    return TrustClaimRead.model_validate(claim)


def create_source(session: Session, user_id: str, payload: TrustSourceCreate) -> TrustSourceRead:
    ensure_user_exists(session, user_id)
    url = _normalize_url(str(payload.url)) if payload.url else None
    if url:
        existing = session.scalar(
            select(TrustSource).where(
                TrustSource.created_by_user_id == user_id,
                TrustSource.url == url,
            )
        )
        if existing is not None:
            return TrustSourceRead.model_validate(existing)
    source = TrustSource(
        created_by_user_id=user_id,
        source_type=payload.source_type,
        url=url,
        domain=_domain_for_url(url),
        title=payload.title,
        author=payload.author,
        published_at=payload.published_at,
        credibility_score=payload.credibility_score,
        metadata_json=payload.metadata_json,
    )
    session.add(source)
    session.flush()
    emit_event(
        session,
        event_type="trust_source_created",
        aggregate_type="trust_source",
        aggregate_id=source.id,
        actor_id=user_id,
        payload={
            "source_type": source.source_type,
            "domain": source.domain,
            "credibility_score": source.credibility_score,
        },
    )
    session.commit()
    session.refresh(source)
    return TrustSourceRead.model_validate(source)


def add_claim_evidence(
    session: Session,
    user_id: str,
    claim_id: str,
    payload: ClaimEvidenceCreate,
) -> ClaimEvidenceRead:
    ensure_user_exists(session, user_id)
    claim = _get_claim_or_raise(session, claim_id)
    _ensure_node_is_visible(session, user_id, payload.node_id)
    if payload.source_id and session.get(TrustSource, payload.source_id) is None:
        raise ValueError("source not found")

    evidence = ClaimEvidence(
        claim_id=claim.id,
        source_id=payload.source_id,
        node_id=payload.node_id,
        added_by_user_id=user_id,
        evidence_type=payload.evidence_type,
        stance=payload.stance,
        summary=payload.summary,
        excerpt=payload.excerpt,
        url=str(payload.url) if payload.url else None,
        weight=payload.weight,
        metadata_json=payload.metadata_json,
    )
    session.add(evidence)
    session.flush()
    emit_event(
        session,
        event_type="claim_evidence_added",
        aggregate_type="trust_claim",
        aggregate_id=claim.id,
        actor_id=user_id,
        payload={
            "evidence_id": evidence.id,
            "source_id": evidence.source_id,
            "node_id": evidence.node_id,
            "stance": evidence.stance,
            "weight": evidence.weight,
        },
    )
    session.commit()
    session.refresh(evidence)
    return ClaimEvidenceRead.model_validate(evidence)


def add_rationale_version(
    session: Session,
    user_id: str,
    claim_id: str,
    payload: TrustRationaleCreate,
) -> TrustRationaleRead:
    ensure_user_exists(session, user_id)
    claim = _get_claim_or_raise(session, claim_id)
    previous_status = claim.verification_status
    next_version = _next_rationale_version(session, claim.id)
    rationale = TrustRationaleVersion(
        claim_id=claim.id,
        version=next_version,
        verification_status=payload.verification_status,
        confidence_score=payload.confidence_score,
        rationale_text=payload.rationale_text,
        factors_json=payload.factors,
        created_by_user_id=user_id,
        metadata_json=payload.metadata_json,
    )
    session.add(rationale)
    session.flush()
    claim.verification_status = payload.verification_status
    claim.confidence_score = payload.confidence_score
    claim.current_rationale_version = next_version
    session.add(claim)

    emit_event(
        session,
        event_type="trust_rationale_version_created",
        aggregate_type="trust_claim",
        aggregate_id=claim.id,
        actor_id=user_id,
        payload=_rationale_event_payload(rationale),
    )
    emit_event(
        session,
        event_type="trust_claim_status_changed",
        aggregate_type="trust_claim",
        aggregate_id=claim.id,
        actor_id=user_id,
        payload={
            "from_status": previous_status,
            "to_status": claim.verification_status,
            "confidence_score": claim.confidence_score,
            "rationale_version": rationale.version,
        },
    )
    session.commit()
    session.refresh(rationale)
    return TrustRationaleRead.model_validate(rationale)


def assemble_claim_provenance(
    session: Session,
    user_id: str,
    claim_id: str,
    *,
    persist_snapshot: bool = True,
) -> ProvenanceRead:
    ensure_user_exists(session, user_id)
    claim = _get_claim_or_raise(session, claim_id)
    _ensure_node_is_visible(session, user_id, claim.node_id)
    return _assemble_provenance(session, user_id, claim=claim, node_id=claim.node_id, persist_snapshot=persist_snapshot)


def assemble_node_provenance(
    session: Session,
    user_id: str,
    node_id: str,
    *,
    persist_snapshot: bool = True,
) -> ProvenanceRead:
    ensure_user_exists(session, user_id)
    _ensure_node_is_visible(session, user_id, node_id)
    return _assemble_provenance(session, user_id, claim=None, node_id=node_id, persist_snapshot=persist_snapshot)


def create_moderation_report(
    session: Session,
    reporter_id: str,
    payload: ModerationReportCreate,
) -> ModerationReportRead:
    ensure_user_exists(session, reporter_id)
    _ensure_subject_exists(session, reporter_id, payload.subject_type, payload.subject_id)
    report = ModerationReport(
        reporter_id=reporter_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        reason=payload.reason,
        details=payload.details or "",
        metadata_json=payload.metadata_json,
    )
    session.add(report)
    session.flush()
    _log_moderation_event(
        session,
        actor_id=reporter_id,
        report_id=report.id,
        subject_type=report.subject_type,
        subject_id=report.subject_id,
        event_type="report_created",
        from_state=None,
        to_state=report.status,
        payload={"reason": report.reason, "details_present": bool(report.details)},
    )
    emit_event(
        session,
        event_type="moderation_report_created",
        aggregate_type="moderation_report",
        aggregate_id=report.id,
        actor_id=reporter_id,
        payload={
            "subject_type": report.subject_type,
            "subject_id": report.subject_id,
            "reason": report.reason,
            "status": report.status,
        },
    )
    session.commit()
    session.refresh(report)
    return ModerationReportRead.model_validate(report)


def resolve_moderation_report(
    session: Session,
    actor_id: str,
    report_id: str,
    payload: ModerationReportResolve,
) -> ModerationReportRead:
    ensure_user_exists(session, actor_id)
    report = session.get(ModerationReport, report_id)
    if report is None:
        raise ValueError("moderation report not found")
    previous_status = report.status
    report.status = payload.status
    report.resolved_at = datetime.now(timezone.utc)
    session.add(report)
    _log_moderation_event(
        session,
        actor_id=actor_id,
        report_id=report.id,
        subject_type=report.subject_type,
        subject_id=report.subject_id,
        event_type="report_resolved",
        from_state=previous_status,
        to_state=report.status,
        payload={"resolution_note": payload.resolution_note},
    )
    emit_event(
        session,
        event_type="moderation_report_resolved",
        aggregate_type="moderation_report",
        aggregate_id=report.id,
        actor_id=actor_id,
        payload={
            "from_status": previous_status,
            "to_status": report.status,
            "subject_type": report.subject_type,
            "subject_id": report.subject_id,
        },
    )
    session.commit()
    session.refresh(report)
    return ModerationReportRead.model_validate(report)


def set_enforcement_state(
    session: Session,
    actor_id: str,
    payload: ModerationEnforcementUpdate,
) -> ModerationEnforcementRead:
    ensure_user_exists(session, actor_id)
    _ensure_subject_exists(session, actor_id, payload.subject_type, payload.subject_id)
    enforcement = session.scalar(
        select(ModerationEnforcementState).where(
            ModerationEnforcementState.subject_type == payload.subject_type,
            ModerationEnforcementState.subject_id == payload.subject_id,
        )
    )
    previous_state = enforcement.state if enforcement else None
    previous_blocked = enforcement.blocked_from_discovery if enforcement else False
    if enforcement is None:
        enforcement = ModerationEnforcementState(
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
        )
    enforcement.state = payload.state
    enforcement.blocked_from_discovery = payload.blocked_from_discovery
    enforcement.enforced_by_user_id = actor_id
    enforcement.reason = payload.reason or ""
    enforcement.expires_at = payload.expires_at
    enforcement.metadata_json = payload.metadata_json
    session.add(enforcement)
    session.flush()

    _log_moderation_event(
        session,
        actor_id=actor_id,
        report_id=payload.report_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        event_type="enforcement_state_changed",
        from_state=previous_state,
        to_state=enforcement.state,
        payload={
            "blocked_from_discovery": enforcement.blocked_from_discovery,
            "previous_blocked_from_discovery": previous_blocked,
            "reason": enforcement.reason,
            "expires_at": enforcement.expires_at.isoformat() if enforcement.expires_at else None,
        },
    )
    emit_event(
        session,
        event_type="moderation_enforcement_updated",
        aggregate_type="moderation_enforcement_state",
        aggregate_id=enforcement.id,
        actor_id=actor_id,
        payload={
            "subject_type": enforcement.subject_type,
            "subject_id": enforcement.subject_id,
            "from_state": previous_state,
            "to_state": enforcement.state,
            "blocked_from_discovery": enforcement.blocked_from_discovery,
            "previous_blocked_from_discovery": previous_blocked,
        },
    )
    session.commit()
    session.refresh(enforcement)
    return ModerationEnforcementRead.model_validate(enforcement)


def get_enforcement_state(
    session: Session,
    subject_type: str,
    subject_id: str,
) -> ModerationEnforcementRead | None:
    enforcement = session.scalar(
        select(ModerationEnforcementState).where(
            ModerationEnforcementState.subject_type == subject_type,
            ModerationEnforcementState.subject_id == subject_id,
        )
    )
    if enforcement is None:
        return None
    return ModerationEnforcementRead.model_validate(enforcement)


def is_blocked_from_discovery(session: Session, subject_type: str, subject_id: str) -> bool:
    enforcement = session.scalar(
        select(ModerationEnforcementState).where(
            ModerationEnforcementState.subject_type == subject_type,
            ModerationEnforcementState.subject_id == subject_id,
            ModerationEnforcementState.blocked_from_discovery.is_(True),
        )
    )
    if enforcement is None:
        return False
    return enforcement.expires_at is None or enforcement.expires_at > datetime.now(timezone.utc)


def list_moderation_events(
    session: Session,
    *,
    subject_type: str | None = None,
    subject_id: str | None = None,
    report_id: str | None = None,
) -> list[ModerationEventRead]:
    statement = select(ModerationEventLog).order_by(ModerationEventLog.created_at.asc())
    if subject_type:
        statement = statement.where(ModerationEventLog.subject_type == subject_type)
    if subject_id:
        statement = statement.where(ModerationEventLog.subject_id == subject_id)
    if report_id:
        statement = statement.where(ModerationEventLog.report_id == report_id)
    return [ModerationEventRead.model_validate(event) for event in session.scalars(statement)]


def _assemble_provenance(
    session: Session,
    user_id: str,
    *,
    claim: TrustClaim | None,
    node_id: str | None,
    persist_snapshot: bool,
) -> ProvenanceRead:
    claims = [claim] if claim else list(
        session.scalars(select(TrustClaim).where(TrustClaim.node_id == node_id).order_by(TrustClaim.created_at.asc()))
    )
    claim_ids = [item.id for item in claims]
    evidence = list(
        session.scalars(
            select(ClaimEvidence)
            .where(ClaimEvidence.claim_id.in_(claim_ids))
            .order_by(ClaimEvidence.created_at.asc())
        )
    ) if claim_ids else []
    source_ids = {item.source_id for item in evidence if item.source_id}
    sources = list(session.scalars(select(TrustSource).where(TrustSource.id.in_(source_ids)))) if source_ids else []
    rationales = list(
        session.scalars(
            select(TrustRationaleVersion)
            .where(TrustRationaleVersion.claim_id.in_(claim_ids))
            .order_by(TrustRationaleVersion.claim_id.asc(), TrustRationaleVersion.version.asc())
        )
    ) if claim_ids else []
    graph = {
        "node_id": node_id,
        "claims": [
            {
                "id": item.id,
                "verification_status": item.verification_status,
                "confidence_score": item.confidence_score,
                "current_rationale_version": item.current_rationale_version,
            }
            for item in claims
        ],
        "evidence": [
            {
                "id": item.id,
                "claim_id": item.claim_id,
                "source_id": item.source_id,
                "node_id": item.node_id,
                "stance": item.stance,
                "weight": item.weight,
            }
            for item in evidence
        ],
        "sources": [
            {
                "id": item.id,
                "source_type": item.source_type,
                "domain": item.domain,
                "credibility_score": item.credibility_score,
            }
            for item in sources
        ],
        "rationale_versions": [
            {
                "id": item.id,
                "claim_id": item.claim_id,
                "version": item.version,
                "verification_status": item.verification_status,
                "confidence_score": item.confidence_score,
            }
            for item in rationales
        ],
    }
    summary = _provenance_summary(claims, evidence, sources)
    snapshot_read = None
    if persist_snapshot:
        snapshot = ProvenanceSnapshot(
            claim_id=claim.id if claim else None,
            node_id=node_id,
            assembled_by_user_id=user_id,
            summary=summary,
            graph_json=graph,
            metadata_json={"claim_count": len(claims), "evidence_count": len(evidence), "source_count": len(sources)},
        )
        session.add(snapshot)
        session.flush()
        emit_event(
            session,
            event_type="provenance_snapshot_assembled",
            aggregate_type="provenance_snapshot",
            aggregate_id=snapshot.id,
            actor_id=user_id,
            payload={
                "claim_id": snapshot.claim_id,
                "node_id": snapshot.node_id,
                "claim_count": len(claims),
                "evidence_count": len(evidence),
                "source_count": len(sources),
            },
        )
        session.commit()
        session.refresh(snapshot)
        snapshot_read = ProvenanceSnapshotRead.model_validate(snapshot)

    return ProvenanceRead(
        summary=summary,
        node_id=node_id,
        claim=TrustClaimRead.model_validate(claim) if claim else None,
        claims=[TrustClaimRead.model_validate(item) for item in claims],
        evidence=[ClaimEvidenceRead.model_validate(item) for item in evidence],
        sources=[TrustSourceRead.model_validate(item) for item in sources],
        rationales=[TrustRationaleRead.model_validate(item) for item in rationales],
        snapshot=snapshot_read,
        graph=graph,
    )


def _log_moderation_event(
    session: Session,
    *,
    actor_id: str | None,
    report_id: str | None,
    subject_type: str,
    subject_id: str,
    event_type: str,
    from_state: str | None,
    to_state: str | None,
    payload: dict,
) -> ModerationEventLog:
    event = ModerationEventLog(
        actor_id=actor_id,
        report_id=report_id,
        subject_type=subject_type,
        subject_id=subject_id,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        payload=payload,
    )
    session.add(event)
    session.flush()
    return event


def _get_claim_or_raise(session: Session, claim_id: str) -> TrustClaim:
    claim = session.get(TrustClaim, claim_id)
    if claim is None:
        raise ValueError("claim not found")
    return claim


def _ensure_node_is_visible(session: Session, user_id: str, node_id: str | None) -> None:
    if node_id is None:
        return
    node = session.get(ContentNode, node_id)
    if node is None or not can_view_node(session, user_id, node):
        raise ValueError("node not found")


def _ensure_subject_exists(session: Session, actor_id: str, subject_type: str, subject_id: str) -> None:
    if subject_type == "node":
        _ensure_node_is_visible(session, actor_id, subject_id)
        return
    if subject_type == "claim" and session.get(TrustClaim, subject_id) is None:
        raise ValueError("claim not found")
    if subject_type == "source" and session.get(TrustSource, subject_id) is None:
        raise ValueError("source not found")
    if subject_type == "user" and session.get(User, subject_id) is None:
        raise ValueError("user not found")


def _canonical_claim_text(value: str) -> str:
    return " ".join(value.lower().split())


def _domain_for_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc.lower() or None


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{netloc}{path}{query}"


def _next_rationale_version(session: Session, claim_id: str) -> int:
    current = session.scalar(
        select(func.max(TrustRationaleVersion.version)).where(TrustRationaleVersion.claim_id == claim_id)
    )
    return int(current or 0) + 1


def _rationale_event_payload(rationale: TrustRationaleVersion) -> dict:
    return {
        "rationale_id": rationale.id,
        "version": rationale.version,
        "verification_status": rationale.verification_status,
        "confidence_score": rationale.confidence_score,
        "factors": rationale.factors_json,
    }


def _provenance_summary(claims: list[TrustClaim], evidence: list[ClaimEvidence], sources: list[TrustSource]) -> str:
    if not claims:
        return "No trust claims are attached to this provenance target yet."
    statuses = sorted({claim.verification_status for claim in claims})
    source_domains = sorted({source.domain for source in sources if source.domain})
    source_part = f" across {len(source_domains)} source domains" if source_domains else ""
    return (
        f"{len(claims)} claim(s) with statuses {', '.join(statuses)} have "
        f"{len(evidence)} evidence item(s){source_part}."
    )
