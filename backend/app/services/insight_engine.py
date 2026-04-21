from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cluster import Cluster
from app.models.insight import Insight
from app.models.thought import Thought


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_cluster_distribution(
    thoughts: list[Thought],
    start: datetime,
    end: datetime,
) -> dict[str, float]:
    window = [thought for thought in thoughts if start <= ensure_utc(thought.created_at) <= end and thought.cluster_id]
    if not window:
        return {}
    counts = Counter(thought.cluster_id for thought in window if thought.cluster_id)
    total = sum(counts.values())
    return {cluster_id: count / total for cluster_id, count in counts.items()}


def generate_focus_shift(thoughts: list[Thought], cluster_labels: dict[str, str], now: datetime) -> tuple[str, dict] | None:
    current_week = get_cluster_distribution(thoughts, now - timedelta(days=7), now)
    previous_window = get_cluster_distribution(thoughts, now - timedelta(days=30), now - timedelta(days=7))
    max_delta_cluster = None
    max_delta = 0.0
    for cluster_id, current_pct in current_week.items():
        delta = current_pct - previous_window.get(cluster_id, 0.0)
        if delta > max_delta and delta > 0.12:
            max_delta = delta
            max_delta_cluster = cluster_id
    if not max_delta_cluster:
        return None

    cluster_label = cluster_labels.get(max_delta_cluster, "that theme")
    content = f"You've become {int(max_delta * 100)}% more focused on {cluster_label.lower()} this week."
    return content, {"cluster_id": max_delta_cluster, "period": "this week", "delta": round(max_delta, 3)}


def generate_emotional_pattern(thoughts: list[Thought]) -> tuple[str, dict] | None:
    recent = [
        thought
        for thought in thoughts
        if ensure_utc(thought.created_at) >= datetime.now(timezone.utc) - timedelta(days=14)
    ]
    if len(recent) < 5:
        return None

    hour_emotion_map: dict[str, Counter] = defaultdict(Counter)
    for thought in recent:
        hour = ensure_utc(thought.created_at).hour
        if 6 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 18:
            period = "afternoon"
        elif 18 <= hour < 22:
            period = "evening"
        else:
            period = "late night"
        hour_emotion_map[period][thought.emotion] += 1

    for period in ["late night", "evening", "afternoon", "morning"]:
        counts = hour_emotion_map[period]
        total = sum(counts.values())
        if total < 3:
            continue
        negative = counts.get("anger", 0) + counts.get("fear", 0) + counts.get("sadness", 0)
        if total > 0 and (negative / total) > 0.5:
            ratio = round(negative / total * 100)
            return (
                f"{ratio}% of your {period} thoughts carry negative emotion.",
                {"period": period, "negative_ratio": ratio},
            )
    return None


def generate_echo_chamber(thoughts: list[Thought], cluster_labels: dict[str, str], now: datetime) -> tuple[str, dict] | None:
    distribution = get_cluster_distribution(thoughts, now - timedelta(days=30), now)
    if len(distribution) < 2:
        return None
    entropy = -sum(prob * math.log2(prob) for prob in distribution.values() if prob > 0)
    max_entropy = math.log2(len(distribution))
    diversity_score = entropy / max_entropy if max_entropy > 0 else 0
    if diversity_score >= 0.5:
        return None

    dominant_cluster = max(distribution, key=distribution.get)
    dominant_pct = int(distribution[dominant_cluster] * 100)
    dominant_label = cluster_labels.get(dominant_cluster, "one theme")
    return (
        f"{dominant_pct}% of your thinking is concentrated in {dominant_label.lower()}. Your perspective may be narrowing.",
        {
            "cluster_id": dominant_cluster,
            "dominant_percentage": dominant_pct,
            "diversity_score": round(diversity_score, 3),
        },
    )


def refine_insight_sentence(raw: str) -> str:
    sentence = raw.replace("  ", " ").strip()
    sentence = sentence.replace("perhaps", "").replace("maybe", "").replace("it seems", "")
    words = sentence.split()
    if len(words) <= 25:
        return sentence
    return " ".join(words[:25]).rstrip(",.") + "."


def refresh_insights(session: Session, user_id: str) -> list[Insight]:
    thoughts = list(
        session.scalars(
            select(Thought).where(Thought.user_id == user_id).order_by(Thought.created_at.asc())
        )
    )
    if len(thoughts) < 5:
        return []

    clusters = {
        cluster.id: cluster.label
        for cluster in session.scalars(select(Cluster).where(Cluster.user_id == user_id))
    }
    now = datetime.now(timezone.utc)
    generators = [
        ("focus_shift", generate_focus_shift(thoughts, clusters, now)),
        ("emotional_pattern", generate_emotional_pattern(thoughts)),
        ("echo_chamber", generate_echo_chamber(thoughts, clusters, now)),
    ]

    created: list[Insight] = []
    existing = {
        insight.content
        for insight in session.scalars(
            select(Insight).where(Insight.user_id == user_id, Insight.dismissed.is_(False))
        )
    }

    for kind, result in generators:
        if not result:
            continue
        raw_content, supporting_data = result
        content = refine_insight_sentence(raw_content)
        if content in existing:
            continue
        insight = Insight(
            user_id=user_id,
            kind=kind,
            content=content,
            raw_content=raw_content,
            supporting_data=supporting_data,
        )
        session.add(insight)
        created.append(insight)
        existing.add(content)

    session.commit()
    for insight in created:
        session.refresh(insight)
    return created
