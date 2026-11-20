"""Migration planning and disposable SQLite rehearsal.

Production execution, baselining, backups and startup integration are deliberately
not enabled until the deployment and backup arrangements have been confirmed.
"""

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass


class MigrationError(RuntimeError):
    """The migration history or rehearsal is unsafe."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sqlite_statements: tuple[str, ...]
    postgres_statements: tuple[str, ...]

    def checksum(self) -> str:
        content = json.dumps(
            [self.version, self.name, self.sqlite_statements, self.postgres_statements],
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AppliedMigration:
    version: int
    name: str
    checksum: str


def plan_migrations(
    migrations: tuple[Migration, ...], applied: tuple[AppliedMigration, ...]
) -> tuple[Migration, ...]:
    """Return pending migrations, rejecting altered or out-of-order history."""
    names = set()
    for index, migration in enumerate(migrations, start=1):
        if (
            type(migration.version) is not int
            or migration.version != index
            or not isinstance(migration.name, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", migration.name)
            or migration.name in names
            or not migration.sqlite_statements
            or not migration.postgres_statements
            or any(not isinstance(statement, str) or not statement.strip()
                   for statement in (*migration.sqlite_statements, *migration.postgres_statements))
        ):
            raise MigrationError("Invalid migration definition or version order.")
        names.add(migration.name)
    if len(applied) > len(migrations):
        raise MigrationError("Database contains unknown migrations; use the matching application version.")
    for saved, migration in zip(applied, migrations):
        if (
            saved.version != migration.version
            or saved.name != migration.name
            or saved.checksum != migration.checksum()
        ):
            raise MigrationError("Migration history is out of order or differs from the source definition.")
    return migrations[len(applied):]


def rehearsal_status(
    connection: sqlite3.Connection, migrations: tuple[Migration, ...]
) -> tuple[Migration, ...]:
    """Inspect migration history in an in-memory SQLite rehearsal database."""
    _require_memory_database(connection)
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migration_history'"
    ).fetchone()
    applied = ()
    if exists:
        rows = connection.execute(
            "SELECT version, name, checksum FROM schema_migration_history ORDER BY version"
        ).fetchall()
        applied = tuple(AppliedMigration(*row) for row in rows)
    return plan_migrations(migrations, applied)


def _require_memory_database(connection: sqlite3.Connection) -> None:
    databases = connection.execute("PRAGMA database_list").fetchall()
    if not databases or any(database[2] for database in databases):
        raise MigrationError("Only in-memory SQLite databases are allowed during rehearsal.")


def rehearse_migrations(
    connection: sqlite3.Connection, migrations: tuple[Migration, ...]
) -> tuple[Migration, ...]:
    """Apply migrations atomically to an in-memory SQLite database only."""
    _require_memory_database(connection)
    if connection.in_transaction:
        raise MigrationError("Rehearsal requires a connection without an active transaction.")
    connection.execute("BEGIN IMMEDIATE")
    try:
        pending = rehearsal_status(connection, migrations)
        for migration in pending:
            for statement in migration.sqlite_statements:
                # Do not let a statement end the transaction or attach a disk database.
                if not re.match(r"\s*(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE)\b", statement, re.IGNORECASE):
                    raise MigrationError("Unsupported SQLite rehearsal statement.")
        if pending:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migration_history ("
                "version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL)"
            )
            for migration in pending:
                for statement in migration.sqlite_statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migration_history (version, name, checksum) VALUES (?, ?, ?)",
                    (migration.version, migration.name, migration.checksum()),
                )
        connection.commit()
        return pending
    except Exception:
        connection.rollback()
        raise


# Real migrations and an existing-database baseline will be defined only after
# the current startup initialization and deployment backup policy are reconciled.
MIGRATIONS: tuple[Migration, ...] = ()
