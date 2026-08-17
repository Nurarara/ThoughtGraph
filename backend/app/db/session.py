from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models import (
    Cluster,
    ContentNode,
    DiscoveryMaterialization,
    DomainEvent,
    Edge,
    Follow,
    Friendship,
    GraphProjectionRun,
    GraphReadModelEdge,
    GraphReadModelNode,
    GraphSnapshot,
    InfraDeadLetterRecord,
    InfraEventConsumerState,
    InfluenceScore,
    Insight,
    MagicToken,
    MediaAsset,
    NodeCluster,
    NodeEdge,
    Notification,
    Post,
    PostComment,
    PostReaction,
    ProvenanceSnapshot,
    SearchIndexDocument,
    SessionToken,
    Thought,
    TrustClaim,
    TrustRationaleVersion,
    TrustSource,
    ClaimEvidence,
    ModerationEnforcementState,
    ModerationEventLog,
    ModerationReport,
    User,
    UserRestriction,
    WeeklyReport,
    WorkflowJob,
)
from app.models.base import Base


ADDITIVE_SQLITE_MIGRATIONS: dict[str, list[str]] = {
    "users": [
        "ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)",
        "ALTER TABLE users ADD COLUMN is_public BOOLEAN DEFAULT 1",
        "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN follower_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN following_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN created_at_public BOOLEAN DEFAULT 1",
        "ALTER TABLE users ADD COLUMN serendipity_enabled BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN notification_prefs JSON DEFAULT '{}'",
        "ALTER TABLE users ADD COLUMN onboarding_v2_completed BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN email VARCHAR(320)",
    ],
    "thoughts": [
        "ALTER TABLE thoughts ADD COLUMN visibility VARCHAR(20) DEFAULT 'public'",
        "ALTER TABLE thoughts ADD COLUMN reply_to_id VARCHAR(36)",
        "ALTER TABLE thoughts ADD COLUMN reply_to_user_id VARCHAR(64)",
    ],
    "content_nodes": [
        "ALTER TABLE content_nodes ADD COLUMN reply_to_node_id VARCHAR(36)",
        "ALTER TABLE content_nodes ADD COLUMN quote_of_node_id VARCHAR(36)",
    ],
    "media_assets": [
        "ALTER TABLE media_assets ADD COLUMN filename VARCHAR(255)",
        "ALTER TABLE media_assets ADD COLUMN playback_storage_key VARCHAR(500)",
        "ALTER TABLE media_assets ADD COLUMN thumbnail_storage_key VARCHAR(500)",
        "ALTER TABLE media_assets ADD COLUMN size_bytes INTEGER",
        "ALTER TABLE media_assets ADD COLUMN duration_seconds FLOAT",
        "ALTER TABLE media_assets ADD COLUMN moderation_status VARCHAR(24) DEFAULT 'pending'",
        "ALTER TABLE media_assets ADD COLUMN upload_token VARCHAR(128)",
        "ALTER TABLE media_assets ADD COLUMN upload_expires_at DATETIME",
        "ALTER TABLE media_assets ADD COLUMN error_message VARCHAR(500)",
    ],
    "insights": [
        "ALTER TABLE insights ADD COLUMN stable_key VARCHAR(255)",
        "ALTER TABLE insights ADD COLUMN feedback_json JSON DEFAULT '{}'",
        "ALTER TABLE insights ADD COLUMN feedback_updated_at DATETIME",
    ],
}


def _build_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, future=True, connect_args=connect_args)


settings = get_settings()
engine = _build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _run_additive_migrations()
    _bootstrap_users()


def set_database_url(database_url: str) -> None:
    global engine, SessionLocal
    engine.dispose()
    engine = _build_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _run_additive_migrations() -> None:
    if not engine.url.drivername.startswith("sqlite"):
        return

    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, statements in ADDITIVE_SQLITE_MIGRATIONS.items():
            if table_name not in inspector.get_table_names():
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for statement in statements:
                column_name = statement.split(" ADD COLUMN ", 1)[1].split()[0]
                if column_name in existing_columns:
                    continue
                connection.execute(text(statement))
                existing_columns.add(column_name)
        if "users" in inspector.get_table_names():
            _normalize_sqlite_user_emails(connection)
            connection.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_unique ON users(email) WHERE email IS NOT NULL")
            )
        if "insights" in inspector.get_table_names():
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_insights_stable_key_unique "
                    "ON insights(stable_key) WHERE stable_key IS NOT NULL"
                )
            )


def _normalize_sqlite_user_emails(connection) -> None:
    seen: set[str] = set()
    rows = list(connection.execute(text("SELECT id, email FROM users WHERE email IS NOT NULL ORDER BY id ASC")).mappings())
    for row in rows:
        normalized = row["email"].strip().casefold()
        if not normalized or normalized in seen:
            connection.execute(text("UPDATE users SET email = NULL WHERE id = :user_id"), {"user_id": row["id"]})
            continue
        seen.add(normalized)
        if row["email"] != normalized:
            connection.execute(
                text("UPDATE users SET email = :email WHERE id = :user_id"),
                {"email": normalized, "user_id": row["id"]},
            )


def _bootstrap_users() -> None:
    settings = get_settings()
    session = SessionLocal()
    try:
        known_user_ids = {user_id for user_id in session.execute(text("SELECT id FROM users")).scalars().all()}

        if settings.auth_mode == "development" and settings.default_user_id not in known_user_ids:
            session.add(
                User(
                    id=settings.default_user_id,
                    display_name="You",
                    bio="The default local ThoughtGraph user.",
                    is_public=True,
                    is_admin=True,
                    onboarding_v2_completed=False,
                )
            )
            known_user_ids.add(settings.default_user_id)

        if settings.auth_mode == "development":
            session.execute(
                text("UPDATE users SET is_admin = 1 WHERE id = :user_id"),
                {"user_id": settings.default_user_id},
            )

        for admin_user_id in settings.admin_user_ids:
            session.execute(
                text("UPDATE users SET is_admin = 1 WHERE id = :user_id"),
                {"user_id": admin_user_id},
            )

        if settings.auth_mode == "development":
            thought_user_ids = session.execute(text("SELECT DISTINCT user_id FROM thoughts")).scalars().all()
            for user_id in thought_user_ids:
                if user_id and user_id not in known_user_ids:
                    session.add(
                        User(
                            id=user_id,
                            display_name=user_id.replace("-", " ").title(),
                            bio="",
                            is_public=True,
                            onboarding_v2_completed=False,
                        )
                    )
                    known_user_ids.add(user_id)
        session.commit()
    finally:
        session.close()
