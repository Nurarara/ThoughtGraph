from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.thought import Thought
from app.services.insight_engine import generate_echo_chamber, generate_emotional_pattern, generate_focus_shift


def build_thought(cluster_id: str, emotion: str, days_ago: int, hour: int = 12) -> Thought:
    return Thought(
        user_id="local-user",
        content="test",
        emotion=emotion,
        topics=["career"],
        vector=[0.1, 0.2],
        cluster_id=cluster_id,
        created_at=(datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(hour=hour),
    )


def test_generate_focus_shift_detects_delta() -> None:
    thoughts = [build_thought("career", "growth", 2) for _ in range(7)] + [build_thought("health", "neutral", 20) for _ in range(3)]
    result = generate_focus_shift(thoughts, {"career": "Career", "health": "Health"}, datetime.now(timezone.utc))
    assert result is not None
    assert "career" in result[0].lower()


def test_generate_emotional_pattern_detects_late_night_negativity() -> None:
    thoughts = [build_thought("career", "fear", 1, hour=23) for _ in range(4)] + [build_thought("career", "sadness", 3, hour=1)]
    result = generate_emotional_pattern(thoughts)
    assert result is not None
    assert "late night" in result[0]


def test_generate_echo_chamber_flags_low_diversity() -> None:
    thoughts = [build_thought("ai", "growth", 3) for _ in range(9)] + [build_thought("health", "neutral", 10)]
    result = generate_echo_chamber(thoughts, {"ai": "AI", "health": "Health"}, datetime.now(timezone.utc))
    assert result is not None
    assert "narrowing" in result[0].lower()

