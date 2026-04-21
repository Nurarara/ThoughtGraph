from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models.insight import Insight
from app.schemas.insight import InsightRead, InsightUpdate

router = APIRouter()


@router.get("/insights", response_model=list[InsightRead])
def list_insights(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[InsightRead]:
    insights = list(
        session.scalars(
            select(Insight)
            .where(Insight.user_id == current_user_id, Insight.dismissed.is_(False))
            .order_by(Insight.created_at.desc())
        )
    )
    return [InsightRead.model_validate(insight) for insight in insights]


@router.patch("/insights/{insight_id}", response_model=InsightRead)
def update_insight(
    insight_id: str,
    payload: InsightUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> InsightRead:
    insight = session.scalar(select(Insight).where(Insight.id == insight_id, Insight.user_id == current_user_id))
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    if payload.seen is not None:
        insight.seen = payload.seen
    if payload.dismissed is not None:
        insight.dismissed = payload.dismissed
    session.add(insight)
    session.commit()
    session.refresh(insight)
    return InsightRead.model_validate(insight)
