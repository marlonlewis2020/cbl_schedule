import unittest
from contextlib import closing
from unittest.mock import patch

import scheduler
import test_scheduler


class DeveloperAccountTests(unittest.TestCase):
    setUp = test_scheduler.DeveloperChangeRequestTests.setUp
    tearDown = test_scheduler.DeveloperChangeRequestTests.tearDown
    setup_developer = test_scheduler.DeveloperChangeRequestTests.setup_developer

    def login(self, client, username, password):
        token = client.get("/api/developer/auth-state").get_json()["csrfToken"]
        return client.post("/api/developer/login", headers={"X-CSRF-Token": token},
                           json={"username": username, "password": password})

    def test_independent_accounts_and_rotation(self):
        first = self.setup_developer().get_json()
        body = {"username": "Second-Developer", "currentPassword": "Strong-Developer-2026!",
                "newPassword": "Second-Strong-Password-2026!"}
        headers = {"X-CSRF-Token": first["csrfToken"]}
        self.assertEqual(self.client.post("/api/developer/accounts", headers=headers, json=body).status_code, 201)
        other = scheduler.app.test_client()
        second = self.login(other, "SECOND-DEVELOPER", body["newPassword"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(other.get("/api/developer/change-requests").status_code, 200)
        self.assertEqual(self.client.get("/api/developer/change-requests").status_code, 200)
        stale = scheduler.app.test_client()
        self.assertEqual(self.login(stale, body["username"], body["newPassword"]).status_code, 200)
        changed = other.post("/api/developer/credentials", headers={"X-CSRF-Token": second.get_json()["csrfToken"]},
                             json={"username": "Renamed-Developer", "currentPassword": body["newPassword"],
                                   "newPassword": "Rotated-Strong-Password-2026!"})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(stale.get("/api/developer/change-requests").status_code, 401)
        self.assertEqual(self.client.get("/api/developer/change-requests").status_code, 200)
        self.assertEqual(other.get("/api/developer/change-requests").status_code, 200)
        scheduler.initialize_database()
        self.assertEqual(self.login(scheduler.app.test_client(), "Renamed-Developer", "Rotated-Strong-Password-2026!").status_code, 200)

    def test_creation_guards_duplicates_and_closed_bootstrap(self):
        first = self.setup_developer().get_json()
        headers = {"X-CSRF-Token": first["csrfToken"]}
        body = {"username": "REVIEWER", "currentPassword": "Strong-Developer-2026!",
                "newPassword": "Second-Strong-Password-2026!"}
        self.assertEqual(scheduler.app.test_client().post("/api/developer/accounts", json=body).status_code, 401)
        self.assertEqual(self.client.post("/api/developer/accounts", json=body).status_code, 400)
        self.assertEqual(self.client.post("/api/developer/accounts", headers=headers, json=body | {"currentPassword": "wrong"}).status_code, 403)
        self.assertEqual(self.client.post("/api/developer/accounts", headers=headers, json=body).status_code, 409)
        self.assertEqual(self.client.post("/api/developer/accounts", headers=headers, json=body | {"newPassword": "short"}).status_code, 400)
        self.assertEqual(self.client.post("/api/developer/setup", headers=headers, json=body | {"password": body["newPassword"]}).status_code, 409)
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM developer_users").fetchone()[0], 1)

    def test_singleton_migration_preserves_credentials_and_timestamps(self):
        self.setup_developer()
        with closing(scheduler.database_connect()) as c, c:
            original = c.execute("SELECT id,username,password_hash,auth_version,created_at,updated_at FROM developer_users").fetchall()
            c.execute("DROP TABLE developer_users")
            c.execute("CREATE TABLE developer_users(id INTEGER PRIMARY KEY CHECK(id=1),username TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,auth_version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            c.executemany("INSERT INTO developer_users VALUES(?,?,?,?,?,?)", original)
            scheduler.migrate_developer_accounts(c)
            scheduler.migrate_developer_accounts(c)
            self.assertEqual(c.execute("SELECT id,username,password_hash,auth_version,created_at,updated_at FROM developer_users").fetchall(), original)
        self.assertEqual(self.client.get("/api/developer/change-requests").status_code, 200)

    def test_local_command_creates_account_without_full_initialization(self):
        self.setup_developer()
        with patch("sys.argv", ["scheduler.py", "add-developer", "--username", "local-developer"]), patch.object(
            scheduler, "getpass", side_effect=["Local-Strong-Password-2026!"] * 2
        ), patch.object(scheduler, "initialize_database", side_effect=AssertionError("Do not run unrelated migrations")):
            scheduler.main()
        self.assertEqual(self.login(scheduler.app.test_client(), "local-developer", "Local-Strong-Password-2026!").status_code, 200)


if __name__ == "__main__":
    unittest.main()
