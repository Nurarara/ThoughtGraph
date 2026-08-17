from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.workflow_job import WorkflowJob
from app.services.event_service import emit_event


def enqueue_job(
    session: Session,
    *,
    job_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
    actor_id: str | None = None,
) -> WorkflowJob:
    job = WorkflowJob(
        job_type=job_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        status="pending",
    )
    session.add(job)
    session.flush()
    emit_event(
        session,
        event_type="graph_job_enqueued",
        aggregate_type="workflow_job",
        aggregate_id=job.id,
        actor_id=actor_id,
        payload={
            "job_type": job.job_type,
            "target_aggregate_type": aggregate_type,
            "target_aggregate_id": aggregate_id,
        },
    )
    return job


def start_job(session: Session, job: WorkflowJob) -> None:
    job.status = "running"
    job.attempts += 1
    job.started_at = datetime.now(timezone.utc)
    session.add(job)
    session.flush()


def complete_job(session: Session, job: WorkflowJob, result: dict) -> None:
    job.status = "completed"
    job.result = result
    job.completed_at = datetime.now(timezone.utc)
    session.add(job)
    session.flush()


def fail_job(session: Session, job: WorkflowJob, message: str) -> None:
    job.status = "failed"
    job.error_message = message
    job.completed_at = datetime.now(timezone.utc)
    session.add(job)
    session.flush()


def should_run_inline() -> bool:
    return get_settings().run_jobs_inline
