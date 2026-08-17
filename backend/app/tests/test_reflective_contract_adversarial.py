from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app import db as db_package
from app.db.session import init_db, set_database_url
from app.models.domain_event import DomainEvent
from app.models.insight import Insight
from app.schemas.reflective_insight import ReflectiveFeedbackUpdate
from app.services.reflective_insight_service import (
    generate_reflective_insight_loop,
    list_persisted_reflective_insights,
    update_reflective_insight_feedback,
)
from app.tests.fixtures.magic_moment_histories import REFERENCE_TIME, builder_pivot


def test_reflective_list_uses_current_versions_generated_order_filters_and_limit(tmp_path: Path) -> None:
    set_database_url(f"sqlite:///{tmp_path / 'reflective-list.db'}")
    init_db()
    with db_package.session.SessionLocal() as session:
        builder_pivot(session)
        # Create the newer logical window first so created_at order is deliberately misleading.
        generate_reflective_insight_loop(session, "local-user", reference_time=REFERENCE_TIME)
        generate_reflective_insight_loop(session, "local-user", reference_time=REFERENCE_TIME - timedelta(days=1))

        newest_attention = session.scalar(
            select(Insight).where(Insight.stable_key == "local-user:attention_drift:2026-08-17:v1")
        )
        assert newest_attention is not None
        legacy_contract = dict(newest_attention.supporting_data)
        legacy_contract["contract_version"] = 0
        session.add(
            legacy_model := Insight(
                user_id="local-user",
                kind="reflective_attention_drift",
                content="Legacy contract row",
                raw_content="Legacy contract row",
                stable_key="local-user:attention_drift:2026-08-17:v0",
                supporting_data=legacy_contract,
            )
        )
        session.commit()

        attention = list_persisted_reflective_insights(session, "local-user", kind="attention_drift")
        assert [item.contract_version for item in attention] == [1, 1]
        assert [item.generated_at for item in attention] == sorted(
            [item.generated_at for item in attention], reverse=True
        )
        assert len(list_persisted_reflective_insights(session, "local-user", kind="attention_drift", limit=1)) == 1
        assert all(
            item.kind == "source_shaping_summary"
            for item in list_persisted_reflective_insights(session, "local-user", kind="source_shaping_summary")
        )
        assert update_reflective_insight_feedback(
            session,
            "local-user",
            legacy_model.id,
            ReflectiveFeedbackUpdate(dismissed=True),
        ) is None


def test_reflective_feedback_event_excludes_annotation_and_evidence_text(tmp_path: Path) -> None:
    set_database_url(f"sqlite:///{tmp_path / 'reflective-event-privacy.db'}")
    init_db()
    with db_package.session.SessionLocal() as session:
        builder_pivot(session)
        generate_reflective_insight_loop(session, "local-user", reference_time=REFERENCE_TIME)
        source = list_persisted_reflective_insights(
            session, "local-user", kind="source_shaping_summary"
        )[0]
        secret_annotation = "private correction details must remain on the insight only"
        updated = update_reflective_insight_feedback(
            session,
            "local-user",
            source.id,
            ReflectiveFeedbackUpdate(correction="wrong_evidence", annotation=secret_annotation),
        )
        assert updated is not None
        assert updated.feedback.annotation == secret_annotation

        event = session.scalar(
            select(DomainEvent)
            .where(DomainEvent.event_type == "reflective_insight_feedback_updated")
            .order_by(DomainEvent.created_at.desc())
        )
        assert event is not None
        serialized_payload = str(event.payload)
        assert secret_annotation not in serialized_payload
        assert "evidence" not in event.payload
        assert event.payload == {
            "dismissed": False,
            "correction": "wrong_evidence",
            "has_annotation": True,
        }
