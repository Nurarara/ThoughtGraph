from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models import Cluster, Edge, Follow, GraphSnapshot, InfluenceScore, Insight, Notification, Thought, User, WeeklyReport
from app.models.base import Base


ADDITIVE_SQLITE_MIGRATIONS: dict[str, list[str]] = {
    "users": [
        "ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)",
        "ALTER TABLE users ADD COLUMN is_public BOOLEAN DEFAULT 1",
        "ALTER TABLE users ADD COLUMN follower_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN following_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN created_at_public BOOLEAN DEFAULT 1",
        "ALTER TABLE users ADD COLUMN notification_prefs JSON DEFAULT '{}'",
        "ALTER TABLE users ADD COLUMN onboarding_v2_completed BOOLEAN DEFAULT 0",
    ],
    "thoughts": [
        "ALTER TABLE thoughts ADD COLUMN visibility VARCHAR(20) DEFAULT 'public'",
        "ALTER TABLE thoughts ADD COLUMN reply_to_id VARCHAR(36)",
        "ALTER TABLE thoughts ADD COLUMN reply_to_user_id VARCHAR(64)",
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


def _bootstrap_users() -> None:
    settings = get_settings()
    session = SessionLocal()
    try:
        known_user_ids = {user_id for user_id in session.execute(text("SELECT id FROM users")).scalars().all()}

        if settings.default_user_id not in known_user_ids:
            session.add(
                User(
                    id=settings.default_user_id,
                    display_name="You",
                    bio="The default local ThoughtGraph user.",
                    is_public=True,
                )
            )
            known_user_ids.add(settings.default_user_id)

        thought_user_ids = session.execute(text("SELECT DISTINCT user_id FROM thoughts")).scalars().all()
        for user_id in thought_user_ids:
            if user_id and user_id not in known_user_ids:
                session.add(
                    User(
                        id=user_id,
                        display_name=user_id.replace("-", " ").title(),
                        bio="",
                        is_public=True,
                    )
                )
                known_user_ids.add(user_id)
        session.commit()
    finally:
        session.close()
