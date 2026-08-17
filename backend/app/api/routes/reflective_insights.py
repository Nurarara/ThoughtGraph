from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models.workflow_job import WorkflowJob
from app.schemas.reflective_insight import (
    PersistedReflectiveInsightRead,
    ReflectiveFeedbackUpdate,
    ReflectiveLoopRequest,
    ReflectiveLoopRunRead,
)
from app.services.reflective_insight_service import (
    enqueue_reflective_insight_loop,
    generate_reflective_insight_loop,
    list_persisted_reflective_insights,
    update_reflective_insight_feedback,
)

router = APIRouter(prefix="/reflective-insights")


@router.get("", response_model=list[PersistedReflectiveInsightRead])
def list_reflective_insights_route(
    include_dismissed: bool = False,
    kind: Literal["attention_drift", "source_shaping_summary"] | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[PersistedReflectiveInsightRead]:
    return list_persisted_reflective_insights(
        session, current_user_id, include_dismissed=include_dismissed, kind=kind, limit=limit
    )


@router.patch("/{insight_id}/feedback", response_model=PersistedReflectiveInsightRead)
def update_reflective_insight_feedback_route(
    insight_id: str,
    payload: ReflectiveFeedbackUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> PersistedReflectiveInsightRead:
    result = update_reflective_insight_feedback(session, current_user_id, insight_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="reflective insight not found")
    return result


@router.post("/run", response_model=ReflectiveLoopRunRead)
def run_reflective_insights_route(
    payload: ReflectiveLoopRequest,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> ReflectiveLoopRunRead:
    if payload.run_inline:
        return generate_reflective_insight_loop(
            session,
            current_user_id,
            reference_time=payload.reference_time,
        )
    job = enqueue_reflective_insight_loop(
        session,
        current_user_id,
        reference_time=payload.reference_time,
        run_inline=False,
    )
    assert isinstance(job, WorkflowJob)
    return ReflectiveLoopRunRead(
        user_id=current_user_id,
        generated_at=job.created_at,
        window_start=job.created_at,
        window_end=job.created_at,
        workflow_job_id=job.id,
        workflow_status=job.status,
        report={
            "id": None,
            "week_start": job.created_at.date(),
            "week_end": job.created_at.date(),
            "summary": "Reflective insight loop queued.",
            "thought_count": 0,
            "insight_count": 0,
            "content": {"queued": True, "job_type": job.job_type},
        },
        insights=[],
    )
