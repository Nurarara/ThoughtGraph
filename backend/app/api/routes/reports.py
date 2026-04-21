from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.report import WeeklyReportRead
from app.services.report_service import generate_weekly_report, get_latest_report, get_report, list_reports

router = APIRouter(prefix="/reports")


@router.post("/generate", response_model=WeeklyReportRead)
async def generate_report_route(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> WeeklyReportRead:
    return await generate_weekly_report(session, current_user_id)


@router.get("", response_model=list[WeeklyReportRead])
def list_reports_route(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[WeeklyReportRead]:
    return list_reports(session, current_user_id)


@router.get("/latest", response_model=WeeklyReportRead)
def latest_report_route(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> WeeklyReportRead:
    report = get_latest_report(session, current_user_id)
    if not report:
        raise HTTPException(status_code=404, detail="No reports yet")
    return report


@router.get("/{report_id}", response_model=WeeklyReportRead)
def get_report_route(
    report_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> WeeklyReportRead:
    report = get_report(session, current_user_id, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
