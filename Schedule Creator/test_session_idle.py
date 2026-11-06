import time
import unittest
from contextlib import closing
from unittest.mock import patch

import scheduler
import test_scheduler


class IdleSessionTests(test_scheduler.PrimaryAdminDataSettingsTests):
    def clock(self, client, started=None, last=None):
        with client.session_transaction() as state:
            token = state["idle_session_id"]
        with closing(scheduler.database_connect()) as c, c:
            if started is not None:
                c.execute("UPDATE browser_sessions SET started_at=?,last_activity=? WHERE id=?",
                          (started, last, token))
            return c.execute("SELECT started_at,last_activity FROM browser_sessions WHERE id=?",
                             (token,)).fetchone()

    def post_activity(self, client, **kwargs):
        with client.session_transaction() as state:
            token = state["idle_csrf"]
        return client.post("/api/session/state", headers={"X-CSRF-Token": token},
                           json={"activity": "interaction"}, **kwargs)

    def test_exact_idle_boundary_and_polling_does_not_extend(self):
        now = int(time.time())
        self.clock(self.primary, now, now)
        with patch.object(scheduler.time_module, "time", return_value=now + 899):
            self.assertEqual(self.primary.get("/api/app-config").status_code, 200)
            self.assertEqual(self.primary.get("/api/session/state").status_code, 200)
        self.assertEqual(self.clock(self.primary), (now, now))
        with patch.object(scheduler.time_module, "time", return_value=now + 900):
            result = self.primary.get("/api/app-config")
            self.assertEqual(result.status_code, 401)
            self.assertTrue(result.get_json()["sessionExpired"])
            self.assertEqual(self.primary.get("/api/app-config").status_code, 401)

    def test_activity_renewal_shared_tabs_and_no_cookie_replay_resurrection(self):
        now = int(time.time())
        self.clock(self.primary, now, now)
        tab = self.admin_client("test-admin")
        with patch.object(scheduler.time_module, "time", return_value=now + 899):
            result = self.post_activity(self.primary)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.get_json()["idleExpiresAt"], now + 1799)
        with patch.object(scheduler.time_module, "time", return_value=now + 900):
            self.assertEqual(tab.get("/api/app-config").status_code, 200)
            self.assertEqual(tab.get("/api/session/state").get_json()["idleExpiresAt"], now + 1799)
        with patch.object(scheduler.time_module, "time", return_value=now + 1799):
            self.assertEqual(self.post_activity(tab).status_code, 401)
        with patch.object(scheduler.time_module, "time", return_value=now + 1800):
            self.assertEqual(self.post_activity(self.primary).status_code, 401)

    def test_absolute_boundary_cannot_be_extended_by_activity(self):
        now = int(time.time())
        self.clock(self.primary, now, now + 28000)
        with patch.object(scheduler.time_module, "time", return_value=now + 28799):
            self.assertEqual(self.post_activity(self.primary).status_code, 200)
        with patch.object(scheduler.time_module, "time", return_value=now + 28800):
            response = self.primary.get("/api/session/state")
            self.assertEqual(response.status_code, 401)

    def test_activity_is_csrf_protected_bounded_and_throttled(self):
        now = int(time.time())
        self.clock(self.primary, now, now)
        path = "/api/session/state"
        with patch.object(scheduler.time_module, "time", return_value=now + 10):
            self.assertEqual(self.post_activity(self.primary).status_code, 200)
            self.assertEqual(self.clock(self.primary), (now, now))
        with patch.object(scheduler.time_module, "time", return_value=now + 20):
            self.assertEqual(self.primary.post(path, json={"activity": "interaction"}).status_code, 400)
            for value in ({"activity": "poll"}, {"activity": "interaction", "timestamp": now}, {"activity": []}):
                self.assertEqual(self.primary.post(
                    path, headers={"X-CSRF-Token": "idle-test-token"}, json=value).status_code, 400)
            self.assertEqual(self.post_activity(
                self.primary, environ_overrides={"HTTP_ORIGIN": "https://other.example"}).status_code, 403)
            self.assertEqual(self.primary.post(
                path, headers={"X-CSRF-Token": "idle-test-token"},
                json={"activity": "x" * 300}).status_code, 413)
            self.assertEqual(self.clock(self.primary), (now, now))
            self.assertEqual(self.post_activity(self.primary).status_code, 200)
            self.assertEqual(self.clock(self.primary), (now, now + 20))

    def test_missing_legacy_clock_fails_closed_and_logout_revokes_replay(self):
        replay = self.admin_client("test-admin")
        self.primary.post("/api/tenant-auth/logout",
                          headers={"X-CSRF-Token": "test-csrf-token"})
        self.assertEqual(replay.get("/api/app-config").status_code, 401)
        with self.additional.session_transaction() as state:
            state.pop("idle_session_id", None)
        self.assertEqual(self.additional.get("/api/app-config").status_code, 401)

    def test_repeat_startup_preserves_clock_and_webhook_is_not_browser_activity(self):
        now = int(time.time())
        self.clock(self.primary, now, now)
        scheduler.initialize_database()
        self.assertEqual(self.clock(self.primary), (now, now))
        with patch.object(scheduler.time_module, "time", return_value=now + 900):
            response = self.primary.post("/api/payments/paypal/webhook", json={})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.clock(self.primary), (now, now))
            self.assertEqual(self.primary.get("/api/session/state").status_code, 401)

    def test_partial_sign_in_cannot_reset_existing_absolute_clock(self):
        now = int(time.time())
        self.clock(self.primary, now - 100, now)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("""INSERT INTO tenant_users
                         (id,tenant_id,role,email,display_name,password_hash,must_change_password)
                         VALUES('pending-manager',?,'manager','pending@example.test','Manager',?,0)""",
                      (scheduler.DEFAULT_TENANT_ID, scheduler.generate_password_hash("test-manager-password")))
        token = self.primary.get("/api/access/state").get_json()["csrfToken"]
        response = self.primary.post(
            "/api/access/login", headers={"X-CSRF-Token": token},
            json={"bamboohrSubdomain": "cbljm", "identifier": "pending@example.test",
                  "password": "test-manager-password"})
        self.assertTrue(response.get_json()["mfaEnrollmentRequired"])
        # A partial login has cleared the admin identity, not minted a new clock.
        with self.primary.session_transaction() as state:
            self.assertNotIn("idle_session_id", state)
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM browser_sessions").fetchone()[0], 0)

    def test_all_roles_expire_and_activity_checks_account_validity(self):
        now = int(time.time())
        with closing(scheduler.database_connect()) as c, c:
            c.execute("""INSERT INTO platform_owners(id,email,display_name,password_hash,mfa_enabled)
                         VALUES('owner','owner@example.test','Owner','hash',1)""")
            c.execute("INSERT INTO developer_users(id,username,password_hash) VALUES(1,'developer','hash')")
            for role in ("manager", "employee"):
                c.execute("""INSERT INTO tenant_users
                             (id,tenant_id,role,display_name,password_hash,mfa_enabled,must_change_password)
                             VALUES(?,?,?,?,?,1,0)""",
                          (role, scheduler.DEFAULT_TENANT_ID, role, role, "hash"))
        identities = [
            {"platform_owner_id": "owner", "platform_auth_version": 1},
            {"developer_username": "developer", "developer_auth_version": 1},
            *[{"access_user_id": role, "access_tenant_id": scheduler.DEFAULT_TENANT_ID,
               "access_auth_version": 1} for role in ("manager", "employee")],
        ]
        for identity in identities:
            client = scheduler.app.test_client()
            token = scheduler.secrets.token_urlsafe(32)
            with client.session_transaction() as state:
                state.update(identity, idle_session_id=token, idle_csrf="role-token")
            with closing(scheduler.database_connect()) as c, c:
                c.execute("INSERT INTO browser_sessions VALUES(?,?,?)", (token, now, now))
            with patch.object(scheduler.time_module, "time", return_value=now + 899):
                self.assertEqual(client.get("/api/session/state").status_code, 200, identity)
            with patch.object(scheduler.time_module, "time", return_value=now + 900):
                self.assertEqual(client.get("/api/session/state").status_code, 401, identity)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE tenant_admins SET active=0 WHERE id='test-admin'")
        self.assertEqual(self.post_activity(self.primary).status_code, 401)


if __name__ == "__main__":
    unittest.main()
