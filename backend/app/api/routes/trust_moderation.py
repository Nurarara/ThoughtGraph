from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, require_admin_user_id
from app.db.session import get_db
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
    TrustClaimCreate,
    TrustClaimRead,
    TrustRationaleCreate,
    TrustRationaleRead,
    TrustSourceCreate,
    TrustSourceRead,
)
from app.services.trust_moderation_service import (
    add_claim_evidence,
    add_rationale_version,
    assemble_claim_provenance,
    assemble_node_provenance,
    create_claim,
    create_moderation_report,
    create_source,
    get_enforcement_state,
    list_moderation_events,
    resolve_moderation_report,
    set_enforcement_state,
)

router = APIRouter()


@router.post("/trust/claims", response_model=TrustClaimRead)
def create_claim_route(
    payload: TrustClaimCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> TrustClaimRead:
    try:
        return create_claim(session, current_user_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/trust/sources", response_model=TrustSourceRead)
def create_source_route(
    payload: TrustSourceCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> TrustSourceRead:
    return create_source(session, current_user_id, payload)


@router.post("/trust/claims/{claim_id}/evidence", response_model=ClaimEvidenceRead)
def add_claim_evidence_route(
    claim_id: str,
    payload: ClaimEvidenceCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> ClaimEvidenceRead:
    try:
        return add_claim_evidence(session, current_user_id, claim_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/trust/claims/{claim_id}/rationales", response_model=TrustRationaleRead)
def add_rationale_version_route(
    claim_id: str,
    payload: TrustRationaleCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> TrustRationaleRead:
    try:
        return add_rationale_version(session, current_user_id, claim_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/trust/claims/{claim_id}/provenance", response_model=ProvenanceRead)
def claim_provenance_route(
    claim_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> ProvenanceRead:
    try:
        return assemble_claim_provenance(session, current_user_id, claim_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.get("/trust/nodes/{node_id}/provenance", response_model=ProvenanceRead)
def node_provenance_route(
    node_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> ProvenanceRead:
    try:
        return assemble_node_provenance(session, current_user_id, node_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post("/moderation/reports", response_model=ModerationReportRead)
def create_moderation_report_route(
    payload: ModerationReportCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> ModerationReportRead:
    try:
        return create_moderation_report(session, current_user_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/moderation/reports/{report_id}/resolve", response_model=ModerationReportRead)
def resolve_moderation_report_route(
    report_id: str,
    payload: ModerationReportResolve,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(require_admin_user_id),
) -> ModerationReportRead:
    try:
        return resolve_moderation_report(session, current_user_id, report_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.put("/moderation/enforcement", response_model=ModerationEnforcementRead)
def set_enforcement_state_route(
    payload: ModerationEnforcementUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(require_admin_user_id),
) -> ModerationEnforcementRead:
    try:
        return set_enforcement_state(session, current_user_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/moderation/enforcement/{subject_type}/{subject_id}", response_model=ModerationEnforcementRead | None)
def get_enforcement_state_route(
    subject_type: str,
    subject_id: str,
    session: Session = Depends(get_db),
    _: str = Depends(require_admin_user_id),
) -> ModerationEnforcementRead | None:
    return get_enforcement_state(session, subject_type, subject_id)


@router.get("/moderation/events", response_model=list[ModerationEventRead])
def list_moderation_events_route(
    subject_type: str | None = None,
    subject_id: str | None = None,
    report_id: str | None = None,
    session: Session = Depends(get_db),
    _: str = Depends(require_admin_user_id),
) -> list[ModerationEventRead]:
    return list_moderation_events(session, subject_type=subject_type, subject_id=subject_id, report_id=report_id)
