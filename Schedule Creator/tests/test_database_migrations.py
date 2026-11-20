import app_path  # noqa: F401
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from database_migrations import (
    AppliedMigration, Migration, MigrationError, plan_migrations,
    rehearse_migrations, rehearsal_status,
)


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.first = Migration(1, "create-example", ("CREATE TABLE example (value TEXT)",),
                               ("CREATE TABLE example (value TEXT)",))
        self.second = Migration(2, "add-example", ("ALTER TABLE example ADD COLUMN note TEXT",),
                                ("ALTER TABLE example ADD COLUMN note TEXT",))

    def test_rehearsal_applies_in_order_and_is_repeatable(self):
        migrations = (self.first, self.second)
        self.assertEqual(rehearsal_status(self.connection, migrations), migrations)
        self.assertEqual(rehearse_migrations(self.connection, migrations), migrations)
        self.assertEqual(rehearsal_status(self.connection, migrations), ())
        self.assertEqual(rehearse_migrations(self.connection, migrations), ())
        self.assertEqual(
            [row[1] for row in self.connection.execute("PRAGMA table_info(example)")],
            ["value", "note"],
        )

    def test_failure_rolls_back_schema_and_history(self):
        broken = Migration(2, "broken", ("ALTER TABLE missing ADD COLUMN value TEXT",),
                           ("ALTER TABLE missing ADD COLUMN value TEXT",))
        with self.assertRaises(sqlite3.OperationalError):
            rehearse_migrations(self.connection, (self.first, broken))
        self.assertIsNone(self.connection.execute(
            "SELECT name FROM sqlite_master WHERE name='example'"
        ).fetchone())
        self.assertEqual(rehearsal_status(self.connection, (self.first, broken)), (self.first, broken))

    def test_changed_and_unknown_history_is_rejected(self):
        applied = (AppliedMigration(1, self.first.name, self.first.checksum()),)
        changed = Migration(1, self.first.name, ("CREATE TABLE example (changed TEXT)",),
                            self.first.postgres_statements)
        with self.assertRaises(MigrationError):
            plan_migrations((changed,), applied)
        with self.assertRaises(MigrationError):
            plan_migrations((), applied)
        with self.assertRaises(MigrationError):
            plan_migrations((self.second,), ())

    def test_disk_backed_and_attached_databases_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with closing(sqlite3.connect(str(Path(directory) / "test.sqlite3"))) as disk:
                with self.assertRaises(MigrationError):
                    rehearse_migrations(disk, (self.first,))
            self.connection.execute(
                "ATTACH DATABASE ? AS other", (str(Path(directory) / "attached.sqlite3"),)
            )
            with self.assertRaises(MigrationError):
                rehearse_migrations(self.connection, (self.first,))
            self.connection.execute("DETACH DATABASE other")

    def test_existing_transaction_is_not_committed(self):
        self.connection.execute("CREATE TABLE existing (value INTEGER)")
        self.connection.execute("INSERT INTO existing VALUES (1)")
        with self.assertRaises(MigrationError):
            rehearse_migrations(self.connection, (self.first,))
        self.connection.rollback()
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM existing").fetchone()[0], 0)

    def test_transaction_control_in_a_migration_is_refused(self):
        unsafe = Migration(2, "commit-early", ("COMMIT",), ("COMMIT",))
        with self.assertRaises(MigrationError):
            rehearse_migrations(self.connection, (self.first, unsafe))
        self.assertIsNone(self.connection.execute(
            "SELECT name FROM sqlite_master WHERE name='example'"
        ).fetchone())


if __name__ == "__main__":
    unittest.main()
