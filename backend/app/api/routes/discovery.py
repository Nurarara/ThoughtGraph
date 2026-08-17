from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.discovery import AdjacentPeopleResponse, DiscoveryExploreResponse, DiscoveryFilters, RelatedIdeasResponse
from app.services.discovery_service import adjacent_people, explore_discovery, related_ideas

router = APIRouter(prefix="/discovery")


@router.get("/explore", response_model=DiscoveryExploreResponse)
def explore_route(
    q: str | None = None,
    close_to_me: bool = False,
    outside_my_bubble: bool = False,
    high_evidence: bool = False,
    new_low_spread: bool = False,
    trusted_only: bool = False,
    limit: int = Query(default=10, ge=1, le=25),
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> DiscoveryExploreResponse:
    filters = DiscoveryFilters(
        q=q,
        close_to_me=close_to_me,
        outside_my_bubble=outside_my_bubble,
        high_evidence=high_evidence,
        new_low_spread=new_low_spread,
        trusted_only=trusted_only,
        limit=limit,
    )
    return explore_discovery(session, current_user_id, filters)


@router.get("/related/{node_id}", response_model=RelatedIdeasResponse)
def related_route(
    node_id: str,
    limit: int = Query(default=8, ge=1, le=20),
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> RelatedIdeasResponse:
    try:
        return related_ideas(session, current_user_id, node_id, limit=limit)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.get("/people-adjacent", response_model=AdjacentPeopleResponse)
def people_adjacent_route(
    limit: int = Query(default=8, ge=1, le=20),
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> AdjacentPeopleResponse:
    return adjacent_people(session, current_user_id, limit=limit)
