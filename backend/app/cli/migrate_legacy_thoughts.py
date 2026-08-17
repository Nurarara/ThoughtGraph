from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.services.legacy_thought_migration import LegacyThoughtMigrationConflict, migrate_legacy_thoughts


REQUIRED_TABLES = {"users", "thoughts", "content_nodes", "node_edges"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate V1 thoughts into canonical ContentNodes.")
    parser.add_argument("--database", required=True, type=Path, help="Explicit path to the SQLite database.")
    parser.add_argument(
        "--visibility",
        choices=("preserve", "private"),
        default="preserve",
        help="Preserve legacy visibility (default) or make every imported thought private.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Inspect and report without modifying the database.")
    mode.add_argument("--apply", action="store_true", help="Back up the database, then apply one atomic migration.")
    parser.add_argument(
        "--reconcile-projection",
        action="store_true",
        help="Rebuild canonical semantic edges, clusters, and counts for affected users during apply.",
    )
    args = parser.parse_args(argv)

    database = args.database.expanduser().resolve()
    if not database.is_file():
        parser.error(f"database does not exist: {database}")

    backup: Path | None = None
    if args.apply:
        backup = _create_backup(database)

    url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(url, future=True)
    try:
        missing = REQUIRED_TABLES.difference(inspect(engine).get_table_names())
        if missing:
            raise RuntimeError(f"database is missing required tables: {', '.join(sorted(missing))}")
        with Session(engine) as session:
            report = migrate_legacy_thoughts(
                session,
                apply=args.apply,
                visibility_policy=args.visibility,
                reconcile_projection=args.reconcile_projection,
            )
    except LegacyThoughtMigrationConflict as exc:
        print(json.dumps({"status": "conflict", "error": str(exc), "backup": str(backup) if backup else None}, indent=2))
        return 2
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc), "backup": str(backup) if backup else None}, indent=2))
        return 1
    finally:
        engine.dispose()

    output = {"status": "applied" if args.apply else "dry-run", "database": str(database), **report.to_dict()}
    if backup:
        output["backup"] = str(backup)
    print(json.dumps(output, indent=2))
    return 0


def _create_backup(database: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = database.with_name(f"{database.name}.backup-{stamp}")
    source = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    destination = sqlite3.connect(backup)
    try:
        source.backup(destination)
        integrity = destination.execute("PRAGMA integrity_check").fetchone()
    finally:
        destination.close()
        source.close()
    if not backup.is_file() or not integrity or integrity[0] != "ok":
        raise RuntimeError(f"backup verification failed: {backup}")
    return backup


if __name__ == "__main__":
    sys.exit(main())
