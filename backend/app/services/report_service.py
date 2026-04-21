from __future__ import annotations

import base64
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.cluster import Cluster
from app.models.thought import Thought
from app.models.user import User
from app.models.weekly_report import WeeklyReport
from app.schemas.report import WeeklyReportRead
from app.services.broadcast import manager
from app.services.influence_service import list_influence_scores
from app.services.notification_service import create_notification
from app.services.user_service import ensure_user_exists


def _to_data_uri(svg: str) -> str:
    return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode('utf-8')).decode('ascii')}"


def _render_report_image(display_name: str, content: dict, week_start: date, week_end: date) -> str:
    insight_lines = "".join(
        f"<text x='80' y='{520 + index * 48}' fill='#e8e6f0' font-size='28'>{escape(line)}</text>"
        for index, line in enumerate(content.get("insights", [])[:3])
    )
    return _to_data_uri(
        f"""
        <svg xmlns='http://www.w3.org/2000/svg' width='1080' height='1080' viewBox='0 0 1080 1080'>
          <defs>
            <linearGradient id='g' x1='0' x2='1'>
              <stop offset='0%' stop-color='#7c5bf5'/>
              <stop offset='50%' stop-color='#4a8eff'/>
              <stop offset='100%' stop-color='#22d3ee'/>
            </linearGradient>
          </defs>
          <rect width='1080' height='1080' fill='#08080f'/>
          <circle cx='860' cy='220' r='180' fill='rgba(124,91,245,0.18)'/>
          <text x='80' y='100' fill='#22d3ee' font-family='monospace' font-size='22'>YOUR MIND THIS WEEK</text>
          <text x='80' y='180' fill='#e8e6f0' font-family='serif' font-size='66'>{escape(display_name)}</text>
          <text x='80' y='235' fill='#8a88a0' font-family='monospace' font-size='18'>{week_start.isoformat()} - {week_end.isoformat()}</text>
          <text x='80' y='330' fill='#e8e6f0' font-family='sans-serif' font-size='34'>{escape(content.get('summary', 'No summary available.'))}</text>
          <text x='80' y='450' fill='#8a88a0' font-family='monospace' font-size='20'>Signals</text>
          {insight_lines}
          <text x='80' y='880' fill='#8a88a0' font-family='sans-serif' font-size='28'>Thoughts: {content.get('thought_count', 0)} • Mood: {escape(content.get('mood_trend', 'steady'))}</text>
          <text x='80' y='980' fill='url(#g)' font-family='serif' font-size='58'>ThoughtGraph</text>
        </svg>
        """.strip()
    )


def _serialize_report(session: Session, report: WeeklyReport) -> WeeklyReportRead:
    user = session.get(User, report.user_id)
    return WeeklyReportRead(
        id=report.id,
        user_id=report.user_id,
        user_display_name=user.display_name if user else report.user_id,
        week_start=report.week_start,
        week_end=report.week_end,
        content=report.content,
        image_url=report.image_url,
        seen=report.seen,
        created_at=report.created_at,
    )


async def generate_weekly_report(
    session: Session,
    user_id: str,
    *,
    reference_time: datetime | None = None,
) -> WeeklyReportRead:
    ensure_user_exists(session, user_id)
    now = reference_time or datetime.now(timezone.utc)
    week_end = now.date()
    week_start = week_end - timedelta(days=6)
    existing = session.scalar(
        select(WeeklyReport).where(WeeklyReport.user_id == user_id, WeeklyReport.week_start == week_start)
    )

    start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
    previous_start = datetime.combine(week_start - timedelta(days=7), datetime.min.time(), tzinfo=timezone.utc)
    previous_end = datetime.combine(week_start - timedelta(days=1), datetime.max.time(), tzinfo=timezone.utc)
    thoughts = list(
        session.scalars(
            select(Thought).where(Thought.user_id == user_id, Thought.created_at >= start_dt).order_by(Thought.created_at.asc())
        )
    )
    previous_thoughts = list(
        session.scalars(
            select(Thought)
            .where(Thought.user_id == user_id, Thought.created_at >= previous_start, Thought.created_at <= previous_end)
        )
    )
    cluster_map = {cluster.id: cluster for cluster in session.scalars(select(Cluster).where(Cluster.user_id == user_id))}
    cluster_counts = Counter(cluster_map[thought.cluster_id].label for thought in thoughts if thought.cluster_id in cluster_map)
    previous_cluster_counts = Counter(
        cluster_map[thought.cluster_id].label for thought in previous_thoughts if thought.cluster_id in cluster_map
    )
    top_clusters = [label for label, _ in cluster_counts.most_common(3)]
    dominant_emotion = Counter(thought.emotion for thought in thoughts).most_common(1)
    top_influence = next(iter(list_influence_scores(session, user_id)), None)
    growth_label = top_clusters[0] if top_clusters else "General Reflection"
    growth_delta = cluster_counts.get(growth_label, 0) - previous_cluster_counts.get(growth_label, 0)
    thought_delta = len(thoughts) - len(previous_thoughts)
    mood_trend = "calm" if dominant_emotion and dominant_emotion[0][0] in {"joy", "growth", "neutral"} else "charged"
    summary = f"You posted {len(thoughts)} thoughts this week ({thought_delta:+d} vs last week), with {growth_label} taking the lead."
    if top_influence:
        summary += f" {top_influence.target_display_name} is the clearest outside influence in the graph right now."
    insights = [
        f"{growth_label} moved by {growth_delta:+d} thoughts this week.",
        f"Dominant emotion: {dominant_emotion[0][0] if dominant_emotion else 'neutral'}.",
        f"New connections formed: {sum(thought.connection_count for thought in thoughts)}.",
    ]
    content = {
        "summary": summary,
        "insights": insights,
        "cluster_changes": [
            {"label": label, "delta": cluster_counts[label] - previous_cluster_counts.get(label, 0)}
            for label in top_clusters
        ],
        "new_connections": sum(thought.connection_count for thought in thoughts),
        "mood_trend": mood_trend,
        "thought_count": len(thoughts),
        "top_influence": top_influence.model_dump() if top_influence else None,
        "top_clusters": top_clusters,
    }
    user = session.get(User, user_id)
    image_url = _render_report_image(user.display_name if user else user_id, content, week_start, week_end)

    report = existing or WeeklyReport(user_id=user_id, week_start=week_start, week_end=week_end)
    report.week_end = week_end
    report.content = content
    report.image_url = image_url
    report.sent_at = week_end
    session.add(report)
    session.commit()
    session.refresh(report)

    notification = create_notification(
        session,
        user_id,
        "weekly_report",
        content=f"Your weekly report for {week_start.isoformat()} is ready.",
    )
    if notification.id != "suppressed":
        await manager.send_to_user(
            user_id,
            {"type": "weekly_report_ready", "report_id": report.id, "week_start": week_start.isoformat()},
        )

    return _serialize_report(session, report)


def list_reports(session: Session, user_id: str) -> list[WeeklyReportRead]:
    reports = list(
        session.scalars(select(WeeklyReport).where(WeeklyReport.user_id == user_id).order_by(desc(WeeklyReport.week_start)))
    )
    return [_serialize_report(session, report) for report in reports]


def get_report(session: Session, user_id: str, report_id: str) -> WeeklyReportRead | None:
    report = session.scalar(select(WeeklyReport).where(WeeklyReport.id == report_id, WeeklyReport.user_id == user_id))
    if not report:
        return None
    return _serialize_report(session, report)


def get_latest_report(session: Session, user_id: str) -> WeeklyReportRead | None:
    report = session.scalar(
        select(WeeklyReport).where(WeeklyReport.user_id == user_id).order_by(desc(WeeklyReport.week_start)).limit(1)
    )
    if not report:
        return None
    return _serialize_report(session, report)
