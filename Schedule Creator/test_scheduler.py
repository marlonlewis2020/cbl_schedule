import json
import os
import sqlite3
import tempfile
import time
import unittest
import base64
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

import scheduler

scheduler.MFA_BYPASS = False

def authenticate_test_admin(client):
    with closing(scheduler.database_connect()) as connection, connection:
        connection.execute(
            """
            INSERT INTO tenant_admins
                (id, tenant_id, email, display_name, password_hash,
                 mfa_secret, mfa_enabled, active, auth_version)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, 1)
            """,
            (
                "test-admin",
                scheduler.DEFAULT_TENANT_ID,
                "test-admin@example.com",
                "Test Admin",
                scheduler.generate_password_hash("test-only-password"),
                "test-encrypted-secret",
            ),
        )
    with client.session_transaction() as browser_session:
        browser_session["tenant_admin_id"] = "test-admin"
        browser_session["tenant_id"] = scheduler.DEFAULT_TENANT_ID
        browser_session["tenant_admin_email"] = "test-admin@example.com"
        browser_session["tenant_auth_version"] = 1
        browser_session["tenant_auth_csrf"] = "test-csrf-token"


class TemporaryMfaBypassTests(unittest.TestCase):
    def test_bypass_signs_in_with_password_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            original_path = scheduler.DATABASE_PATH
            scheduler.DATABASE_PATH = Path(directory) / "bypass.sqlite3"
            try:
                scheduler.initialize_database()
                scheduler.provision_tenant_admin("A", "a@example.com", "test-password-123456")
                credentials = {"email": "a@example.com", "password": "test-password-123456"}
                for enabled, expected in ((False, 200), (True, 200)):
                    client = scheduler.app.test_client()
                    token = client.get("/api/tenant-auth/state").get_json()["csrfToken"]
                    with patch.object(scheduler, "MFA_BYPASS", enabled):
                        response = client.post(
                            "/api/tenant-auth/login",
                            headers={"X-CSRF-Token": token},
                            json=credentials,
                        )
                        self.assertEqual(response.status_code, expected)
                        self.assertEqual(
                            bool(response.get_json().get("authenticated")), enabled
                        )
                        self.assertEqual(
                            client.get("/api/employees").status_code,
                            200 if enabled else 401,
                        )
            finally:
                scheduler.DATABASE_PATH = original_path


class TemporaryLanHttpTests(unittest.TestCase):
    def test_plain_http_only_allowed_for_private_clients_when_enabled(self):
        def probe(enabled, address, forwarded=None):
            headers = {"X-Forwarded-For": forwarded} if forwarded else {}
            with patch.object(scheduler, "ALLOW_LAN_HTTP", enabled), patch.object(
                scheduler, "DATABASE_URL", "postgresql://unused"
            ), scheduler.app.test_request_context(
                "/", headers=headers, environ_overrides={"REMOTE_ADDR": address}
            ):
                return scheduler.http_allowed_for_client()

        self.assertFalse(probe(False, "192.168.100.73"))
        self.assertTrue(probe(True, "192.168.100.73"))
        self.assertTrue(probe(True, "127.0.0.1"))
        self.assertFalse(probe(True, "8.8.8.8"))
        self.assertFalse(probe(True, "192.168.100.73", forwarded="8.8.8.8"))


REGISTRATION = {
    "businessName": "Acme Foods",
    "bamboohrSubdomain": "acme",
    "bamboohrApiKey": "acme-key-123",
    "adminName": "Ada Admin",
    "adminEmail": "ada@acme.example",
    "password": "correct-horse-battery",
}
OWNER_PASSWORD = "owner-password-123456"


class BusinessHubTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.directory.name) / "hub.sqlite3"
        scheduler.initialize_database()
        multi_business = patch.object(scheduler, "MULTI_BUSINESS", True)
        multi_business.start()
        self.addCleanup(multi_business.stop)

    def tearDown(self):
        scheduler.DATABASE_PATH = self.original_path
        self.directory.cleanup()

    def query(self, sql, parameters=()):
        with closing(scheduler.database_connect()) as connection:
            return connection.execute(sql, parameters).fetchall()

    def register(self, failure=None, **changes):
        client = scheduler.app.test_client()
        token = client.get("/api/hub/state").get_json()["csrfToken"]
        with patch.object(
            scheduler, "check_bamboohr_credentials", return_value=failure
        ) as check:
            response = client.post(
                "/api/hub/register",
                headers={"X-CSRF-Token": token},
                json=REGISTRATION | changes,
            )
        return response, check

    def tenant_id(self, name="Acme Foods"):
        return self.query("SELECT tenant_id FROM tenants WHERE business_name = ?", (name,))[0][0]

    def sign_in_admin(self, email="ada@acme.example", password="correct-horse-battery"):
        client = scheduler.app.test_client()
        token = client.get("/api/tenant-auth/state").get_json()["csrfToken"]
        login = client.post(
            "/api/tenant-auth/login",
            headers={"X-CSRF-Token": token},
            json={"email": email, "password": password},
        )
        result = login.get_json()
        if result.get("mfaEnrollmentRequired"):
            code = scheduler.totp_value(result["secret"], int(time.time() // 30))
            result = client.post(
                "/api/tenant-auth/verify-mfa",
                headers={"X-CSRF-Token": result["csrfToken"]},
                json={"code": code},
            ).get_json()
        return client, result["csrfToken"]

    def sign_in_owner(self):
        client = scheduler.app.test_client()
        token = client.get("/api/hub/state").get_json()["csrfToken"]
        result = client.post(
            "/api/hub/owner/login",
            headers={"X-CSRF-Token": token},
            json={"email": "owner@platform.example", "password": OWNER_PASSWORD},
        ).get_json()
        if result.get("mfaEnrollmentRequired"):
            code = scheduler.totp_value(result["secret"], int(time.time() // 30))
            result = client.post(
                "/api/hub/owner/verify-mfa",
                headers={"X-CSRF-Token": result["csrfToken"]},
                json={"code": code},
            ).get_json()
        return client, result["csrfToken"]

    def make_owner(self):
        scheduler.provision_platform_owner("Owner", "owner@platform.example", OWNER_PASSWORD)

    def set_status(self, owner, csrf, tenant_id, status, note=""):
        return owner.post(
            f"/api/hub/businesses/{tenant_id}/status",
            headers={"X-CSRF-Token": csrf},
            json={"status": status, "note": note},
        )

    def test_registration_requires_multi_business_mode(self):
        with patch.object(scheduler, "MULTI_BUSINESS", False):
            response, check = self.register()
        self.assertEqual(response.status_code, 503)
        check.assert_not_called()

    def test_registration_validates_input_and_bamboohr_credentials(self):
        for changes in (
            {"password": "short"},
            {"adminEmail": "not-an-email"},
            {"bamboohrSubdomain": "bad.domain/evil"},
            {"bamboohrApiKey": "has:colon"},
            {"businessName": " "},
        ):
            response, check = self.register(**changes)
            self.assertEqual(response.status_code, 400, changes)
            check.assert_not_called()
        response, _ = self.register(failure=("BambooHR rejected this API key.", 401))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.query("SELECT 1 FROM tenants")), 1)

        client = scheduler.app.test_client()
        client.get("/api/hub/state")
        self.assertEqual(
            client.post("/api/hub/register", json=REGISTRATION).status_code, 400
        )

    def test_registration_creates_pending_business_with_encrypted_key(self):
        response, check = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["businessStatus"], "pending")
        check.assert_called_once_with("acme", "acme-key-123")
        tenant_id = self.tenant_id()
        status, contact, stored = self.query(
            "SELECT status, contact_email, bamboohr_api_key_encrypted FROM tenants WHERE tenant_id = ?",
            (tenant_id,),
        )[0]
        self.assertEqual((status, contact), ("pending", "ada@acme.example"))
        self.assertNotIn("acme-key-123", stored)
        self.assertEqual(
            self.query(
                "SELECT is_primary, mfa_enabled FROM tenant_admins WHERE tenant_id = ?",
                (tenant_id,),
            ),
            [(1, 0)],
        )
        settings = dict(
            self.query(
                "SELECT setting_key, setting_value FROM application_settings WHERE tenant_id = ?",
                (tenant_id,),
            )
        )
        self.assertEqual(settings["businessName"], "Acme Foods")
        self.assertEqual(settings["tenantId"], "acme")
        self.assertEqual(
            self.query("SELECT action FROM hub_audit_events WHERE tenant_id = ?", (tenant_id,)),
            [("register",)],
        )
        duplicate, _ = self.register(businessName="Other Co")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(len(self.query("SELECT 1 FROM tenants")), 2)

    def test_registration_attempts_are_rate_limited(self):
        statuses = [self.register(adminEmail=f"a{index}@acme.example")[0].status_code for index in range(6)]
        self.assertEqual(statuses[:5], [201] * 5)
        self.assertEqual(statuses[5], 429)

    def test_pending_business_can_only_view_its_status(self):
        self.register()
        client, csrf = self.sign_in_admin()
        for method, path in (
            ("get", "/api/employees"),
            ("get", "/api/schedule-locations"),
            ("get", "/api/accepted-shifts"),
            ("post", "/api/bamboohr/publish"),
        ):
            response = getattr(client, method)(path, headers={"X-CSRF-Token": csrf})
            self.assertEqual(response.status_code, 403, path)
            self.assertEqual(response.get_json()["businessStatus"], "pending")
        status = client.get("/api/business/status").get_json()
        self.assertEqual((status["status"], status["isPrimaryAdmin"]), ("pending", True))
        self.assertEqual(
            client.get("/api/tenant-auth/state").get_json()["businessStatus"], "pending"
        )
        page = client.get("/").get_data()
        self.assertEqual(page, (scheduler.APP_DIRECTORY / "business-status.html").read_bytes())
        self.assertNotEqual(page, (scheduler.APP_DIRECTORY / "CBL-Scheduler2.html").read_bytes())

    def test_owner_reviews_businesses_and_status_gates_access(self):
        self.register()
        self.register(businessName="Second Co", adminEmail="bo@second.example", bamboohrSubdomain="second")
        tenant_id = self.tenant_id()
        self.make_owner()
        anonymous = scheduler.app.test_client()
        self.assertEqual(anonymous.get("/api/hub/businesses").status_code, 401)
        admin_client, admin_csrf = self.sign_in_admin()
        self.assertEqual(admin_client.get("/api/hub/businesses").status_code, 401)
        self.assertEqual(
            self.set_status(admin_client, admin_csrf, tenant_id, "active").status_code, 401
        )

        owner, csrf = self.sign_in_owner()
        listing = owner.get("/api/hub/businesses").get_json()["businesses"]
        self.assertEqual([item["status"] for item in listing][:2], ["pending", "pending"])
        self.assertNotIn("bamboohr", json.dumps(listing).casefold())
        self.assertEqual(
            owner.post(
                f"/api/hub/businesses/{tenant_id}/status", json={"status": "active"}
            ).status_code,
            400,
        )
        self.assertEqual(self.set_status(owner, csrf, tenant_id, "suspended").status_code, 409)
        self.assertEqual(self.set_status(owner, csrf, "missing", "active").status_code, 404)

        self.assertEqual(self.set_status(owner, csrf, tenant_id, "active", "Verified").status_code, 200)
        self.assertEqual(admin_client.get("/api/employees").status_code, 200)
        self.assertNotEqual(
            admin_client.get("/").get_data(),
            (scheduler.APP_DIRECTORY / "business-status.html").read_bytes(),
        )
        self.assertEqual(self.set_status(owner, csrf, tenant_id, "rejected").status_code, 409)
        self.assertEqual(self.set_status(owner, csrf, tenant_id, "suspended", "Billing").status_code, 200)
        blocked = admin_client.get("/api/employees")
        self.assertEqual(
            (blocked.status_code, blocked.get_json()["businessStatus"]), (403, "suspended")
        )
        self.assertEqual(admin_client.get("/api/business/status").status_code, 200)
        self.assertEqual(self.set_status(owner, csrf, tenant_id, "active").status_code, 200)

        second = self.tenant_id("Second Co")
        self.assertEqual(self.set_status(owner, csrf, second, "rejected", "No").status_code, 200)
        client = scheduler.app.test_client()
        token = client.get("/api/tenant-auth/state").get_json()["csrfToken"]
        rejected_login = client.post(
            "/api/tenant-auth/login",
            headers={"X-CSRF-Token": token},
            json={"email": "bo@second.example", "password": "correct-horse-battery"},
        )
        self.assertEqual(rejected_login.status_code, 401)
        self.assertEqual(self.set_status(owner, csrf, second, "pending").status_code, 200)
        actions = [row[0] for row in self.query("SELECT action FROM hub_audit_events")]
        self.assertIn("status-pending-to-active", actions)
        self.assertIn("status-active-to-suspended", actions)

    def test_platform_owner_requires_mfa_enrollment_and_valid_codes(self):
        self.make_owner()
        client = scheduler.app.test_client()
        token = client.get("/api/hub/state").get_json()["csrfToken"]
        credentials = {"email": "owner@platform.example", "password": OWNER_PASSWORD}
        wrong = client.post("/api/hub/owner/login", headers={"X-CSRF-Token": token},
                            json=credentials | {"password": "wrong-password-123456"})
        self.assertEqual(wrong.status_code, 401)
        enrollment = client.post(
            "/api/hub/owner/login", headers={"X-CSRF-Token": token}, json=credentials
        ).get_json()
        self.assertTrue(enrollment["mfaEnrollmentRequired"])
        self.assertTrue(enrollment["qrCode"].startswith("data:image/svg+xml"))
        self.assertEqual(client.get("/api/hub/businesses").status_code, 401)
        bad = client.post("/api/hub/owner/verify-mfa",
                          headers={"X-CSRF-Token": enrollment["csrfToken"]}, json={"code": "000000"})
        self.assertEqual(bad.status_code, 400)
        code = scheduler.totp_value(enrollment["secret"], int(time.time() // 30))
        ok = client.post("/api/hub/owner/verify-mfa",
                         headers={"X-CSRF-Token": enrollment["csrfToken"]}, json={"code": code})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(client.get("/api/hub/businesses").status_code, 200)
        self.assertEqual(
            client.post("/api/hub/owner/logout", headers={"X-CSRF-Token": ok.get_json()["csrfToken"]}).status_code,
            200,
        )
        self.assertEqual(client.get("/api/hub/businesses").status_code, 401)

        again = scheduler.app.test_client()
        again_token = again.get("/api/hub/state").get_json()["csrfToken"]
        for payload, expected in ((credentials, 401), (credentials | {"code": "000000"}, 401)):
            self.assertEqual(
                again.post("/api/hub/owner/login", headers={"X-CSRF-Token": again_token}, json=payload).status_code,
                expected,
            )
        good = again.post(
            "/api/hub/owner/login",
            headers={"X-CSRF-Token": again_token},
            json=credentials | {"code": scheduler.totp_value(enrollment["secret"], int(time.time() // 30))},
        )
        self.assertTrue(good.get_json()["authenticated"])

    def test_owner_reset_commands_invalidate_sessions(self):
        self.make_owner()
        owner, _ = self.sign_in_owner()
        self.assertEqual(owner.get("/api/hub/businesses").status_code, 200)
        scheduler.reset_platform_owner_mfa("owner@platform.example")
        self.assertEqual(owner.get("/api/hub/businesses").status_code, 401)
        owner, _ = self.sign_in_owner()
        scheduler.reset_platform_owner_password("owner@platform.example", "another-password-1234")
        self.assertEqual(owner.get("/api/hub/businesses").status_code, 401)
        with self.assertRaises(RuntimeError):
            scheduler.reset_platform_owner_mfa("nobody@platform.example")
        with self.assertRaises(RuntimeError):
            scheduler.provision_platform_owner("Owner", "owner@platform.example", OWNER_PASSWORD)

    def test_primary_admin_manages_additional_admins(self):
        self.register()
        self.make_owner()
        owner, owner_csrf = self.sign_in_owner()
        self.set_status(owner, owner_csrf, self.tenant_id(), "active")
        primary, csrf = self.sign_in_admin()
        headers = {"X-CSRF-Token": csrf}
        new_admin = {"name": "Bo", "email": "bo@acme.example", "password": "temporary-password-1"}
        self.assertEqual(primary.post("/api/business/admins", json=new_admin).status_code, 400)
        self.assertEqual(
            primary.post("/api/business/admins", headers=headers, json=new_admin | {"password": "short"}).status_code,
            400,
        )
        created = primary.post("/api/business/admins", headers=headers, json=new_admin)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            primary.post("/api/business/admins", headers=headers, json=new_admin).status_code, 409
        )
        extra, extra_csrf = self.sign_in_admin("bo@acme.example", "temporary-password-1")
        self.assertEqual(extra.get("/api/employees").status_code, 200)
        self.assertFalse(extra.get("/api/business/status").get_json()["isPrimaryAdmin"])
        self.assertEqual(
            extra.post("/api/business/admins", headers={"X-CSRF-Token": extra_csrf}, json=new_admin | {"email": "c@acme.example"}).status_code,
            403,
        )
        admins = primary.get("/api/business/admins").get_json()["admins"]
        self.assertEqual([admin["isPrimary"] for admin in admins], [True, False])
        self.assertTrue(all(admin["mfaEnabled"] for admin in admins))
        primary_id = admins[0]["id"]
        self.assertEqual(
            primary.delete(f"/api/business/admins/{primary_id}", headers=headers).status_code, 404
        )
        self.assertEqual(
            extra.delete(f"/api/business/admins/{primary_id}", headers={"X-CSRF-Token": extra_csrf}).status_code,
            403,
        )
        self.assertEqual(
            primary.delete(f"/api/business/admins/{created.get_json()['id']}", headers=headers).status_code,
            200,
        )
        self.assertEqual(extra.get("/api/employees").status_code, 401)
        client = scheduler.app.test_client()
        token = client.get("/api/tenant-auth/state").get_json()["csrfToken"]
        self.assertEqual(
            client.post("/api/tenant-auth/login", headers={"X-CSRF-Token": token},
                        json={"email": "bo@acme.example", "password": "temporary-password-1"}).status_code,
            401,
        )

    def test_bamboohr_key_is_stored_per_business(self):
        self.register()
        acme = self.tenant_id()

        def key_for(tenant_id):
            with scheduler.app.test_request_context("/"):
                scheduler.g.tenant_id = tenant_id
                return scheduler.bamboohr_api_key()

        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "legacy-env-key"}):
            self.assertEqual(key_for(acme), "acme-key-123")
            self.assertEqual(key_for(scheduler.DEFAULT_TENANT_ID), "legacy-env-key")
            self.assertEqual(key_for("unknown-business"), "")
            self.assertTrue(scheduler.migrate_environment_bamboohr_key())
            self.assertFalse(scheduler.migrate_environment_bamboohr_key())
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": ""}):
            self.assertEqual(key_for(scheduler.DEFAULT_TENANT_ID), "legacy-env-key")
            self.assertEqual(key_for(acme), "acme-key-123")

    def test_existing_business_stays_active_after_upgrade(self):
        self.assertEqual(
            self.query("SELECT status FROM tenants WHERE tenant_id = ?", (scheduler.DEFAULT_TENANT_ID,)),
            [("active",)],
        )


class PostgresAdapterTests(unittest.TestCase):
    def test_sqlite_placeholders_and_conflict_compatibility_are_translated(self):
        class CaptureConnection:
            def execute(self, query, parameters):
                self.query = query
                self.parameters = parameters
                return self

        connection = CaptureConnection()
        adapter = scheduler.PostgresConnection(connection)
        adapter.execute(
            "INSERT OR IGNORE INTO values_table (name, value) "
            "SELECT ?, '?' WHERE ? COLLATE NOCASE = 'beta'",
            ("alpha", "beta"),
        )
        self.assertIn("SELECT %s, '?'", connection.query)
        self.assertIn("WHERE %s  = 'beta'", connection.query)
        self.assertIn("ON CONFLICT DO NOTHING", connection.query)
        self.assertNotIn("NOCASE", connection.query)
        self.assertEqual(connection.parameters, ("alpha", "beta"))


class AcceptedScheduleApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.temporary_directory.name) / "schedules.sqlite3"
        scheduler.initialize_database()
        scheduler.app.config["TESTING"] = True
        self.client = scheduler.app.test_client()
        authenticate_test_admin(self.client)
        self.schedule = {
            "id": "pool|2026-11-02|r1",
            "start": "2026-11-02",
            "location": "Kingston",
            "role": "Cashier",
            "controls": {"span": 9},
            "shiftStarts": [6, 8.5, 14, 22],
            "employees": [
                {
                    "id": "1",
                    "name": "Sample Employee",
                    "slots": [6, None, None, None, None, None, None],
                    "types": ["Demand", None, None, None, None, None, None],
                }
            ],
        }

    def tearDown(self):
        scheduler.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_accept_list_and_update_schedule(self):
        accepted = self.client.post(
            "/api/accepted-shifts",
            data=json.dumps(self.schedule),
            content_type="application/json",
        )
        self.assertEqual(accepted.status_code, 200)

        listing = self.client.get("/api/accepted-shifts")
        self.assertEqual(listing.status_code, 200)
        saved = listing.get_json()["schedules"][0]
        self.assertEqual(saved["schedule"]["employees"][0]["slots"][0], 6)

        self.schedule["employees"][0]["slots"][0] = 8.5
        updated = self.client.put(
            "/api/accepted-shifts/pool%7C2026-11-02%7Cr1",
            data=json.dumps(self.schedule),
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        listing = self.client.get("/api/accepted-shifts")
        self.assertEqual(
            listing.get_json()["schedules"][0]["schedule"]["employees"][0]["slots"][0],
            8.5,
        )

    def test_accepted_schedule_can_be_unaccepted(self):
        self.assertEqual(self.client.post("/api/accepted-shifts", json=self.schedule).status_code, 200)

        deleted = self.client.delete("/api/accepted-shifts/pool%7C2026-11-02%7Cr1")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.get_json()["id"], self.schedule["id"])
        self.assertEqual(self.client.get("/api/accepted-shifts").get_json()["schedules"], [])
        self.assertEqual(
            self.client.delete("/api/accepted-shifts/pool%7C2026-11-02%7Cr1").status_code,
            404,
        )

    def test_rejects_malformed_schedule(self):
        response = self.client.post(
            "/api/accepted-shifts",
            json={"id": "incomplete"},
        )
        self.assertEqual(response.status_code, 400)


class TenantAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.temporary_directory.name) / "schedules.sqlite3"
        scheduler.initialize_database()
        scheduler.app.config["TESTING"] = True
        self.client = scheduler.app.test_client()

    def tearDown(self):
        scheduler.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_existing_sqlite_settings_are_migrated_without_data_loss(self):
        with closing(scheduler.database_connect()) as legacy_database, legacy_database:
            legacy_database.execute("DROP TABLE application_settings")
            legacy_database.execute(
                """
                CREATE TABLE application_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL
                )
                """
            )
            legacy_database.execute(
                "INSERT INTO application_settings VALUES (?, ?)",
                ("businessName", "Existing Business"),
            )

        scheduler.initialize_database()

        with closing(scheduler.database_connect()) as connection:
            settings = connection.execute(
                """
                SELECT setting_value, tenant_id FROM application_settings
                WHERE setting_key = ?
                """,
                ("businessName",),
            ).fetchone()
            primary_key = [
                row[1]
                for row in sorted(
                    (
                        row
                        for row in connection.execute(
                            "PRAGMA table_info(application_settings)"
                        ).fetchall()
                        if row[5]
                    ),
                    key=lambda row: row[5],
                )
            ]
        self.assertEqual(settings, ("Existing Business", scheduler.DEFAULT_TENANT_ID))
        self.assertEqual(primary_key, ["tenant_id", "setting_key"])

    def test_admin_bootstrap_requires_mfa_and_protects_business_apis(self):
        login_page = self.client.get("/")
        self.assertIn(b"Administrator sign-in", login_page.data)
        login_page.close()
        self.assertEqual(self.client.get("/api/employees").status_code, 401)
        auth_state = self.client.get("/api/tenant-auth/state").get_json()
        self.assertTrue(auth_state["canBootstrap"])
        self.assertEqual(
            self.client.post(
                "/api/tenant-auth/bootstrap",
                headers={"X-CSRF-Token": auth_state["csrfToken"]},
                json={
                    "name": "First Admin",
                    "email": "admin@example.com",
                    "password": "a-very-long-test-password",
                },
            ).status_code,
            201,
        )
        with closing(scheduler.database_connect()) as connection:
            audit_event = connection.execute(
                """
                SELECT action, route, actor_id FROM tenant_audit_events
                WHERE route = 'bootstrap_tenant_admin'
                """
            ).fetchone()
        self.assertEqual(audit_event[0:2], ("POST", "bootstrap_tenant_admin"))
        self.assertTrue(audit_event[2])

        self.client.get("/api/tenant-auth/state")
        with self.client.session_transaction() as browser_session:
            pending_csrf = browser_session["tenant_auth_csrf"]
            pending_admin_id = browser_session["pending_tenant_admin_id"]
        with closing(scheduler.database_connect()) as connection:
            encrypted = connection.execute(
                "SELECT encrypted_secret FROM tenant_mfa_enrollments WHERE admin_id = ?",
                (pending_admin_id,),
            ).fetchone()[0]
        secret = scheduler.mfa_cipher().decrypt(encrypted.encode("ascii")).decode("ascii")
        code = scheduler.totp_value(secret, int(time.time() // 30))
        verified = self.client.post(
            "/api/tenant-auth/verify-mfa",
            headers={"X-CSRF-Token": pending_csrf},
            json={"code": code},
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(self.client.get("/api/app-config").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/tenant-auth/logout",
                headers={"X-CSRF-Token": verified.get_json()["csrfToken"]},
                json={},
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/employees").status_code, 401)

        csrf = self.client.get("/api/tenant-auth/state").get_json()["csrfToken"]
        invalid_mfa = self.client.post(
            "/api/tenant-auth/login",
            headers={"X-CSRF-Token": csrf},
            json={
                "email": "admin@example.com",
                "password": "a-very-long-test-password",
                "code": "invalid",
            },
        )
        self.assertEqual(invalid_mfa.status_code, 401)
        valid_login = self.client.post(
            "/api/tenant-auth/login",
            headers={"X-CSRF-Token": csrf},
            json={
                "email": "admin@example.com",
                "password": "a-very-long-test-password",
                "code": scheduler.totp_value(secret, int(time.time() // 30)),
            },
        )
        self.assertEqual(valid_login.status_code, 200)
        scheduler_page = self.client.get("/")
        self.assertIn(b"Scheduling Command Centre", scheduler_page.data)
        scheduler_page.close()
        cross_origin = self.client.post(
            "/api/app-config",
            headers={"Origin": "https://attacker.example"},
            json={},
        )
        self.assertEqual(cross_origin.status_code, 403)

    def test_mfa_enrollment_verification_is_rate_limited(self):
        auth_state = self.client.get("/api/tenant-auth/state").get_json()
        created = self.client.post(
            "/api/tenant-auth/bootstrap",
            headers={"X-CSRF-Token": auth_state["csrfToken"]},
            json={
                "name": "First Admin",
                "email": "admin@example.com",
                "password": "a-very-long-test-password",
            },
        )
        self.assertEqual(created.status_code, 201)
        enrollment = created.get_json()
        self.assertTrue(enrollment["qrCode"].startswith("data:image/svg+xml;base64,"))
        csrf = enrollment["csrfToken"]
        for _ in range(5):
            rejected = self.client.post(
                "/api/tenant-auth/verify-mfa",
                headers={"X-CSRF-Token": csrf},
                json={"code": "invalid"},
            )
            self.assertEqual(rejected.status_code, 400)
        locked = self.client.post(
            "/api/tenant-auth/verify-mfa",
            headers={"X-CSRF-Token": csrf},
            json={"code": "invalid"},
        )
        self.assertEqual(locked.status_code, 429)


class DirectoryAndBambooApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.temporary_directory.name) / "schedules.sqlite3"
        scheduler.initialize_database()
        scheduler.app.config["TESTING"] = True
        self.client = scheduler.app.test_client()
        authenticate_test_admin(self.client)

    def tearDown(self):
        scheduler.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def test_application_settings_validate_and_persist_branding_and_tenant(self):
        defaults = self.client.get("/api/app-config").get_json()
        self.assertEqual(defaults["businessName"], "Celebration Brands Limited")
        self.assertEqual(defaults["teamName"], "Schedule Management")
        self.assertEqual(defaults["tenantId"], "cbljm")

        logo = "data:image/png;base64," + base64.b64encode(
            b"\x89PNG\r\n\x1a\n"
        ).decode("ascii")
        config = {
            "businessName": "Example Business",
            "teamName": "Operations",
            "tenantId": "acme-hr",
            "logoDataUrl": logo,
            "primaryColor": "#123456",
            "accentColor": "#abcdef",
        }
        saved = self.client.put("/api/app-config", json=config)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["tenantId"], "acme-hr")
        self.assertEqual(saved.get_json()["teamName"], "Operations")
        with closing(scheduler.database_connect()) as connection:
            business_name = connection.execute(
                "SELECT business_name FROM tenants WHERE tenant_id = ?",
                (scheduler.DEFAULT_TENANT_ID,),
            ).fetchone()[0]
        self.assertEqual(business_name, "Example Business")
        self.assertEqual(scheduler.bamboohr_endpoint("time_off/whos_out"),
                         "https://acme-hr.bamboohr.com/api/v1/time_off/whos_out")

        config["tenantId"] = "https://attacker.example"
        self.assertEqual(self.client.put("/api/app-config", json=config).status_code, 400)
        config["tenantId"] = "acme-hr"
        config["logoDataUrl"] = "data:image/png;base64,SGVsbG8="
        self.assertEqual(self.client.put("/api/app-config", json=config).status_code, 400)

    def test_bamboo_key_requires_successful_tenant_validation_before_promotion(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"[]"
        env_path = Path(self.temporary_directory.name) / ".env"

        with patch.object(scheduler, "ENV_PATH", env_path), patch.dict(
            os.environ, {"BAMBOOHR_API_KEY": ""}
        ), patch.object(scheduler, "urlopen", return_value=response) as mocked_urlopen:
            untested = self.client.post(
                "/api/bamboohr/promote-key",
                json={"tenantId": "cbljm", "promotionToken": "not-tested"},
            )
            self.assertEqual(untested.status_code, 400)
            self.assertFalse(env_path.exists())

            first_test = self.client.post(
                "/api/bamboohr/validate-key",
                json={"tenantId": "cbljm", "apiKey": "test-key"},
            )
            self.assertEqual(first_test.status_code, 200)
            self.assertNotIn("apiKey", first_test.get_json())
            self.assertFalse(env_path.exists())
            test_url = mocked_urlopen.call_args.args[0].full_url
            self.assertTrue(
                test_url.startswith(
                    "https://cbljm.bamboohr.com/api/v1/time_off/whos_out?start="
                )
            )
            self.assertIn("&end=", test_url)

            wrong_tenant = self.client.post(
                "/api/bamboohr/promote-key",
                json={
                    "tenantId": "other",
                    "promotionToken": first_test.get_json()["promotionToken"],
                },
            )
            self.assertEqual(wrong_tenant.status_code, 400)
            self.assertFalse(env_path.exists())

            valid_test = self.client.post(
                "/api/bamboohr/validate-key",
                json={"tenantId": "cbljm", "apiKey": "test-key"},
            )
            promoted = self.client.post(
                "/api/bamboohr/promote-key",
                json={
                    "tenantId": "cbljm",
                    "promotionToken": valid_test.get_json()["promotionToken"],
                },
            )
            self.assertEqual(promoted.status_code, 200)
            self.assertFalse(env_path.exists())
            with patch.dict(os.environ, {"BAMBOOHR_API_KEY": ""}):
                self.assertEqual(scheduler.bamboohr_api_key(), "test-key")
            with closing(scheduler.database_connect()) as connection:
                stored = connection.execute(
                    "SELECT bamboohr_api_key_encrypted FROM tenants WHERE tenant_id = ?",
                    (scheduler.DEFAULT_TENANT_ID,),
                ).fetchone()[0]
            self.assertNotIn("test-key", stored)
            self.assertNotIn("test-key", promoted.get_data(as_text=True))

    def test_seeded_directory_and_employee_validation(self):
        employees = self.client.get("/api/employees").get_json()["employees"]
        locations = self.client.get("/api/schedule-locations").get_json()["scheduleLocations"]
        self.assertEqual(len(employees), len(scheduler.EMPLOYEE_ASSIGNMENTS) + 1)
        self.assertEqual(len(locations), len(scheduler.SCHEDULE_LOCATIONS))
        self.assertEqual(
            next(employee for employee in employees if employee["id"] == "901405")["role"],
            "Warehouse",
        )
        location_by_id = {location["id"]: location for location in locations}
        for employee in employees:
            if employee["scheduleLocationId"]:
                self.assertTrue(
                    scheduler.role_matches_schedule_group(
                        employee["role"],
                        location_by_id[employee["scheduleLocationId"]]["roleGroup"],
                    )
                )
        warehouse_location = next(
            location
            for location in locations
            if location["roleGroup"] == "Warehouse/Delivery"
        )
        wrong_role = {
            "id": "900997",
            "bamboohrId": "997",
            "name": "Wrong Role",
            "location": warehouse_location["location"],
            "role": "Settlement",
            "active": False,
            "scheduleLocationId": warehouse_location["id"],
        }
        self.assertEqual(self.client.post("/api/employees", json=wrong_role).status_code, 400)

        payload = {
            "id": "900999",
            "name": "Test Employee",
            "location": "Kingston",
            "role": "Cashier",
            "active": False,
            "scheduleLocationId": None,
        }
        created = self.client.post("/api/employees", json=payload)
        self.assertEqual(created.status_code, 201)
        manual_employee = created.get_json()["employee"]
        self.assertEqual(manual_employee["source"], "manual")
        self.assertTrue(manual_employee["bamboohrId"].startswith("MANUAL-"))
        self.assertFalse(manual_employee["active"])
        self.assertEqual(self.client.post("/api/employees", json=payload).status_code, 409)
        case_variant_payload = {**payload, "id": "manual-test-id"}
        self.assertEqual(
            self.client.post("/api/employees", json=case_variant_payload).status_code,
            201,
        )
        self.assertEqual(
            self.client.post(
                "/api/employees",
                json={**case_variant_payload, "id": "MANUAL-TEST-ID"},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post("/api/employees", json={**payload, "role": ""}).status_code,
            400,
        )

    def test_existing_schedule_location_table_gets_manager_columns(self):
        migration_database = Path(self.temporary_directory.name) / "pre_manager.sqlite3"
        with closing(sqlite3.connect(migration_database)) as connection, connection:
            connection.execute(
                """
                CREATE TABLE schedule_locations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    bamboo_schedule_id TEXT NOT NULL UNIQUE,
                    location TEXT NOT NULL,
                    role_group TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                INSERT INTO schedule_locations
                    (id, name, bamboo_schedule_id, location, role_group)
                VALUES ('existing', 'Existing Site', 'existing-id', 'Kingston', '')
                """
            )
        scheduler.DATABASE_PATH = migration_database
        scheduler.initialize_database()
        with closing(sqlite3.connect(migration_database)) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(schedule_locations)")
            }
            location = connection.execute(
                "SELECT name, manager_name, manager_email FROM schedule_locations WHERE id = 'existing'"
            ).fetchone()
        self.assertIn("manager_name", columns)
        self.assertIn("manager_email", columns)
        self.assertEqual(location, ("Existing Site", "", ""))

    def test_batch_employee_status_updates_are_atomic_and_preserve_assignments(self):
        employees = {
            employee["id"]: employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
        }
        active_id, inactive_id = "901033", "901442"
        self.assertTrue(employees[active_id]["active"])
        self.assertFalse(employees[inactive_id]["active"])
        original_location = employees[inactive_id]["scheduleLocationId"]

        deactivated = self.client.put(
            "/api/employees/status",
            json={"employeeIds": [active_id, inactive_id], "active": False},
        )
        self.assertEqual(deactivated.status_code, 200)
        activated = self.client.put(
            "/api/employees/status",
            json={"employeeIds": [active_id, inactive_id], "active": True},
        )
        self.assertEqual(activated.status_code, 200)

        updated = {
            employee["id"]: employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
        }
        self.assertTrue(updated[active_id]["active"])
        self.assertTrue(updated[inactive_id]["active"])
        self.assertEqual(updated[inactive_id]["scheduleLocationId"], original_location)

        invalid = self.client.put(
            "/api/employees/status",
            json={"employeeIds": [active_id, "missing-employee"], "active": False},
        )
        self.assertEqual(invalid.status_code, 404)
        unchanged = {
            employee["id"]: employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
        }
        self.assertTrue(unchanged[active_id]["active"])
        for payload in (
            {"employeeIds": [], "active": True},
            {"employeeIds": [active_id, active_id], "active": False},
            {"employeeIds": [active_id], "active": 1},
        ):
            self.assertEqual(
                self.client.put("/api/employees/status", json=payload).status_code,
                400,
            )
        self.assertEqual(self.client.delete("/api/employees/901033").status_code, 409)

    def test_batch_role_assignment_validates_schedule_groups_and_deactivates_changes(self):
        response = self.client.put(
            "/api/employees/roles",
            json={"employeeIds": ["901033"], "role": "Supervisor"},
        )
        self.assertEqual(response.status_code, 400)
        accepted = self.client.put(
            "/api/employees/roles",
            json={"employeeIds": ["901033"], "role": "DC Associate"},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.get_json()["deactivatedIds"], ["901033"])
        employee = next(
            item
            for item in self.client.get("/api/employees").get_json()["employees"]
            if item["id"] == "901033"
        )
        self.assertEqual(employee["role"], "DC Associate")
        self.assertFalse(employee["active"])
        self.assertIsNotNone(employee["scheduleLocationId"])

    def test_bamboo_employee_sync_preserves_mappings_and_deactivates_missing_records(self):
        remote = [
            {
                "id": "901033",
                "bamboohrId": "186",
                "name": "Candino Updated",
                "bamboohrLocation": "KIDD",
            },
            {
                "id": "990099",
                "bamboohrId": "99099",
                "name": "New Bamboo Employee",
                "bamboohrLocation": "",
            },
        ]
        with patch.object(scheduler, "fetch_bamboohr_employees", return_value=remote):
            response = self.client.post("/api/bamboohr/employees/sync", json={})
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["added"], 1)
        self.assertGreater(result["inactivated"], 0)
        employees = {
            employee["id"]: employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
        }
        self.assertEqual(employees["901033"]["name"], "Candino Updated")
        self.assertEqual(employees["901033"]["role"], "Warehouse")
        self.assertEqual(
            employees["901033"]["scheduleLocationId"], "kidd-warehouse-delivery"
        )
        self.assertTrue(employees["901033"]["active"])
        self.assertEqual(employees["990099"]["source"], "bamboohr")
        self.assertEqual(employees["990099"]["role"], "")
        self.assertFalse(employees["990099"]["active"])
        self.assertFalse(employees["901442"]["active"])
        self.assertFalse(employees["901442"]["bamboohrActive"])

    def test_bamboo_employee_fetch_follows_cursor_pages_and_accepts_filtered_records_without_status(self):
        class FakeResponse:
            def __init__(self, value):
                self.value = value

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, _limit):
                return json.dumps(self.value).encode()

        pages = [
            {
                "meta": {"total": 2, "page": {"nextCursor": "next-cursor"}},
                "data": [
                    {
                        "employeeId": 501,
                        "employeeNumber": "900501",
                        "firstName": "Page",
                        "lastName": "One",
                        "location": "KIDD",
                    }
                ],
            },
            {
                "meta": {"total": 2, "page": {"nextCursor": None}},
                "data": [
                    {
                        "employeeId": 502,
                        "employeeNumber": "900502",
                        "preferredName": "Page Two",
                        "lastName": "Person",
                        "location": "Ferry",
                    }
                ],
            },
        ]
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "test-key"}), patch(
            "scheduler.urlopen",
            side_effect=[FakeResponse(page) for page in pages],
        ) as open_url:
            employees = scheduler.fetch_bamboohr_employees()
        self.assertEqual(len(employees), 2)
        self.assertEqual(employees[1]["name"], "Page Two Person")
        self.assertIn("filter%5Bstatus%5D=active", open_url.call_args_list[0].args[0].full_url)
        self.assertIn("page%5Bafter%5D=next-cursor", open_url.call_args_list[1].args[0].full_url)

    def test_bamboo_sync_requires_and_applies_manual_duplicate_resolution(self):
        manual = self.client.post(
            "/api/employees",
            json={
                "id": "990098",
                "name": "Manual Candidate",
                "location": "Kingston",
                "role": "Cashier",
                "active": False,
            },
        )
        self.assertEqual(manual.status_code, 201)
        remote = [
            {
                "id": "990098",
                "bamboohrId": "99098",
                "name": "Bamboo Candidate",
                "bamboohrLocation": "Kingston",
            }
        ]
        with patch.object(scheduler, "fetch_bamboohr_employees", return_value=remote):
            review = self.client.post("/api/bamboohr/employees/sync", json={})
            self.assertTrue(review.get_json()["requiresReview"])
            merged = self.client.post(
                "/api/bamboohr/employees/sync",
                json={
                    "resolutions": [
                        {
                            "bamboohrId": "99098",
                            "employeeId": "990098",
                            "samePerson": True,
                        }
                    ]
                },
            )
        self.assertEqual(merged.status_code, 200)
        employee = next(
            item
            for item in self.client.get("/api/employees").get_json()["employees"]
            if item["id"] == "990098"
        )
        self.assertEqual(employee["source"], "bamboohr")
        self.assertEqual(employee["bamboohrId"], "99098")
        self.assertEqual(employee["role"], "Cashier")
        self.assertFalse(employee["active"])

    def test_bamboo_sync_merging_existing_record_transfers_manual_mapping(self):
        with closing(sqlite3.connect(scheduler.DATABASE_PATH)) as connection, connection:
            connection.execute(
                """
                INSERT INTO employees
                    (employee_id, bamboohr_id, name, location, role, active,
                     schedule_location_id, source_type, bamboohr_active)
                VALUES ('990097', '99097', 'Existing Bamboo', 'Kingston', '', 0,
                        NULL, 'bamboohr', 1)
                """
            )
        self.client.post(
            "/api/employees",
            json={
                "id": "990098",
                "name": "Manual Candidate",
                "location": "Kingston",
                "role": "Cashier",
                "active": False,
            },
        )
        remote = [
            {
                "id": "990098",
                "bamboohrId": "99097",
                "name": "Bamboo Candidate",
                "bamboohrLocation": "Kingston",
            }
        ]
        with patch.object(scheduler, "fetch_bamboohr_employees", return_value=remote):
            self.client.post("/api/bamboohr/employees/sync", json={})
            merged = self.client.post(
                "/api/bamboohr/employees/sync",
                json={
                    "resolutions": [
                        {
                            "bamboohrId": "99097",
                            "employeeId": "990098",
                            "samePerson": True,
                        }
                    ]
                },
            )
        self.assertEqual(merged.status_code, 200)
        employees = {
            employee["id"]: employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
        }
        self.assertNotIn("990097", employees)
        self.assertEqual(employees["990098"]["source"], "bamboohr")
        self.assertEqual(employees["990098"]["role"], "Cashier")
        self.assertEqual(employees["990098"]["location"], "Kingston")

    def test_bamboo_sync_keeps_distinct_manual_employee_and_rejects_reused_id(self):
        self.client.post(
            "/api/employees",
            json={
                "id": "990098",
                "name": "Manual Person",
                "location": "Kingston",
                "role": "Cashier",
                "active": False,
            },
        )
        remote = [
            {
                "id": "990098",
                "bamboohrId": "99098",
                "name": "Different Bamboo Person",
                "bamboohrLocation": "Kingston",
            }
        ]
        with patch.object(scheduler, "fetch_bamboohr_employees", return_value=remote):
            self.client.post("/api/bamboohr/employees/sync", json={})
            rejected = self.client.post(
                "/api/bamboohr/employees/sync",
                json={
                    "resolutions": [
                        {
                            "bamboohrId": "99098",
                            "employeeId": "990098",
                            "samePerson": False,
                            "newManualEmployeeId": "901033",
                        }
                    ]
                },
            )
            accepted = self.client.post(
                "/api/bamboohr/employees/sync",
                json={
                    "resolutions": [
                        {
                            "bamboohrId": "99098",
                            "employeeId": "990098",
                            "samePerson": False,
                            "newManualEmployeeId": "990099",
                        }
                    ]
                },
            )
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(accepted.status_code, 200)
        employees = {
            employee["id"]: employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
        }
        self.assertEqual(employees["990098"]["source"], "bamboohr")
        self.assertEqual(employees["990099"]["source"], "manual")

    def test_source_import_review_is_atomic_and_adds_only_approved_manual_employees(self):
        seeded = next(
            employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
            if employee["id"] == "901033"
        )
        assigned = self.client.put(
            "/api/employees/import-review",
            json={
                "employees": [
                    {
                        "id": "901033",
                        "name": seeded["name"],
                        "location": seeded["location"],
                        "role": "DC Associate",
                        "scheduleLocationId": seeded["scheduleLocationId"],
                        "addManual": False,
                    },
                    {
                        "id": "990098",
                        "name": "Imported Manual",
                        "location": "Kingston",
                        "role": "Cashier",
                        "scheduleLocationId": None,
                        "addManual": True,
                    },
                    {
                        "id": "990099",
                        "name": "Unapproved Unknown",
                        "location": "Kingston",
                        "role": "Cashier",
                        "scheduleLocationId": None,
                        "addManual": False,
                    },
                ]
            },
        )
        self.assertEqual(assigned.status_code, 200)
        employees = {
            employee["id"]: employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
        }
        self.assertEqual(employees["901033"]["role"], "DC Associate")
        self.assertFalse(employees["901033"]["active"])
        self.assertEqual(employees["990098"]["source"], "manual")
        self.assertFalse(employees["990098"]["active"])
        self.assertNotIn("990099", employees)

        invalid_batch = self.client.put(
            "/api/employees/import-review",
            json={
                "employees": [
                    {
                        "id": "990100",
                        "name": "Should Not Be Added",
                        "location": "Kingston",
                        "role": "Cashier",
                        "scheduleLocationId": None,
                        "addManual": True,
                    },
                    {
                        "id": "990101",
                        "name": "Invalid Mapping",
                        "location": "Kingston",
                        "role": "Cashier",
                        "scheduleLocationId": "missing-location",
                        "addManual": True,
                    },
                ]
            },
        )
        self.assertEqual(invalid_batch.status_code, 400)
        after = {
            employee["id"]
            for employee in self.client.get("/api/employees").get_json()["employees"]
        }
        self.assertNotIn("990100", after)

    def test_role_correction_migration_updates_legacy_seeded_employee(self):
        with closing(sqlite3.connect(scheduler.DATABASE_PATH)) as connection, connection:
            connection.execute(
                "UPDATE employees SET role = 'DC Associate' WHERE employee_id = '901405'"
            )
            connection.execute(
                "DELETE FROM app_migrations WHERE migration_id = ?",
                ("correct-kidd-warehouse-role-v2",),
            )
        scheduler.initialize_database()
        employee = next(
            employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
            if employee["id"] == "901405"
        )
        self.assertEqual(employee["role"], "Warehouse")

    def test_assignment_update_preserves_inactive_employee_mappings(self):
        employees = self.client.get("/api/employees").get_json()["employees"]
        inactive = next(employee for employee in employees if employee["id"] == "901442")
        rejected = self.client.put(
            f"/api/schedule-locations/{inactive['scheduleLocationId']}/employees",
            json={"employeeIds": [inactive["id"]]},
        )
        self.assertEqual(rejected.status_code, 400)
        settlement_employee = next(
            employee
            for employee in employees
            if employee["active"] and employee["role"] == "Settlement"
        )
        rejected_role = self.client.put(
            f"/api/schedule-locations/{inactive['scheduleLocationId']}/employees",
            json={"employeeIds": [settlement_employee["id"]]},
        )
        self.assertEqual(rejected_role.status_code, 400)
        response = self.client.put(
            f"/api/schedule-locations/{inactive['scheduleLocationId']}/employees",
            json={"employeeIds": []},
        )
        self.assertEqual(response.status_code, 200)
        updated = {
            employee["id"]: employee
            for employee in self.client.get("/api/employees").get_json()["employees"]
        }
        self.assertEqual(updated[inactive["id"]]["scheduleLocationId"], inactive["scheduleLocationId"])

    def test_schedule_location_delete_is_blocked_until_employees_are_removed(self):
        created = self.client.post(
            "/api/schedule-locations",
            json={
                "name": "Temporary Schedule",
                "bambooScheduleId": "temporary-schedule",
                "location": "Kingston",
                "managerName": "Test Manager",
                "managerEmail": "manager@example.com",
            },
        )
        self.assertEqual(created.status_code, 201)
        location_id = created.get_json()["id"]
        employee = {
            "id": "900998",
            "name": "Temporary Employee",
            "location": "Kingston",
            "role": "Cashier",
            "active": False,
            "scheduleLocationId": None,
        }
        created_employee = self.client.post("/api/employees", json=employee)
        self.assertEqual(created_employee.status_code, 201)
        self.assertEqual(
            self.client.put(
                "/api/employees/900998",
                json={
                    **employee,
                    "bamboohrId": created_employee.get_json()["employee"]["bamboohrId"],
                    "scheduleLocationId": location_id,
                },
            ).status_code,
            200,
        )
        self.assertEqual(self.client.delete(f"/api/schedule-locations/{location_id}").status_code, 409)
        self.assertEqual(self.client.delete("/api/employees/900998").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/schedule-locations/{location_id}").status_code, 200)

    def prepare_publish_schedule(self):
        location_response = self.client.post(
            "/api/schedule-locations",
            json={
                "name": "Test Kingston Schedule",
                "bambooScheduleId": "test-schedule-1",
                "location": "Kingston",
                "roleGroup": "Cashier",
                "managerName": "Kingston Manager",
                "managerEmail": "kingston.manager@example.com",
            },
        )
        self.assertEqual(location_response.status_code, 201)
        location_id = location_response.get_json()["id"]
        with closing(sqlite3.connect(scheduler.DATABASE_PATH)) as connection, connection:
            connection.execute(
                """
                INSERT INTO employees
                    (employee_id, bamboohr_id, name, location, role, active,
                     schedule_location_id, source_type, bamboohr_active)
                VALUES ('990001', '9901', 'Publish Test', 'Kingston', 'Cashier',
                        1, ?, 'bamboohr', 1)
                """,
                (location_id,),
            )
        schedule = {
            "id": "publish-test-run",
            "start": "2026-11-02",
            "location": "Kingston",
            "role": "Cashier",
            "controls": {"span": 9},
            "shiftStarts": [6],
            "employees": [
                {
                    "id": "990001",
                    "name": "Publish Test",
                    "slots": [6, None, None, None, None, None, None],
                    "types": ["Demand", None, None, None, None, None, None],
                    "bamboohrId": "9901",
                    "scheduleLocationId": location_id,
                    "active": True,
                    "directoryLocation": "Kingston",
                    "directoryRole": "Cashier",
                    "bambooScheduleId": "test-schedule-1",
                }
            ],
        }
        self.assertEqual(self.client.post("/api/accepted-shifts", json=schedule).status_code, 200)
        return schedule

    def test_schedule_location_manager_is_required_and_persisted(self):
        payload = {
            "name": "Manager Test Schedule",
            "bambooScheduleId": "manager-test-schedule",
            "location": "Kingston",
            "roleGroup": "Cashier",
            "managerName": "Morgan Manager",
            "managerEmail": "morgan.manager@example.com",
        }
        created = self.client.post("/api/schedule-locations", json=payload)
        self.assertEqual(created.status_code, 201)
        location_id = created.get_json()["id"]
        location = next(
            item
            for item in self.client.get("/api/schedule-locations").get_json()["scheduleLocations"]
            if item["id"] == location_id
        )
        self.assertEqual(location["managerName"], payload["managerName"])
        self.assertEqual(location["managerEmail"], payload["managerEmail"])

        payload["managerName"] = "Updated Manager"
        payload["managerEmail"] = "updated.manager@example.com"
        self.assertEqual(
            self.client.put(f"/api/schedule-locations/{location_id}", json=payload).status_code,
            200,
        )
        invalid_email = {**payload, "managerEmail": "not-an-email"}
        self.assertEqual(
            self.client.put(f"/api/schedule-locations/{location_id}", json=invalid_email).status_code,
            400,
        )
        missing_manager = {key: value for key, value in payload.items() if key != "managerName"}
        self.assertEqual(self.client.post("/api/schedule-locations", json=missing_manager).status_code, 400)

    def test_bamboo_time_off_endpoint_filters_approved_period_records(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, _limit):
                return json.dumps(
                    [
                        {
                            "id": 1,
                            "type": "timeOff",
                            "status": "approved",
                            "employeeId": 901033,
                            "name": "Candino Boothe",
                            "start": "2026-11-03",
                            "end": "2026-11-04",
                        },
                        {
                            "type": "timeOff",
                            "status": "denied",
                            "name": "Denied Employee",
                            "start": "2026-11-03",
                            "end": "2026-11-04",
                        },
                        {
                            "type": "holiday",
                            "name": "Company holiday",
                            "start": "2026-11-03",
                            "end": "2026-11-04",
                        },
                        {
                            "type": "timeOff",
                            "name": "Outside period",
                            "start": "2026-12-01",
                            "end": "2026-12-02",
                        },
                    ]
                ).encode()

        config = self.client.get("/api/app-config").get_json()
        config["tenantId"] = "acme-hr"
        self.assertEqual(self.client.put("/api/app-config", json=config).status_code, 200)
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "test-key"}), patch(
            "scheduler.urlopen", return_value=FakeResponse()
        ) as open_url:
            response = self.client.get(
                "/api/bamboohr/time-offs?start=2026-11-02&end=2026-11-08"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["entries"],
            [
                {
                    "id": 1,
                    "type": "timeOff",
                    "employeeId": 901033,
                    "name": "Candino Boothe",
                    "start": "2026-11-03",
                    "end": "2026-11-04",
                }
            ],
        )
        outbound = open_url.call_args.args[0]
        self.assertEqual(outbound.get_method(), "GET")
        self.assertIn(
            ("Authorization", "Basic dGVzdC1rZXk6eA=="),
            outbound.header_items(),
        )
        self.assertTrue(
            outbound.full_url.startswith(
                "https://acme-hr.bamboohr.com/api/v1/time_off/whos_out?"
            )
        )
        self.assertIn("start=2026-11-02", outbound.full_url)

    def test_bamboo_time_off_endpoint_reports_missing_key_invalid_range_and_upstream_failure(self):
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": ""}):
            missing_key = self.client.get(
                "/api/bamboohr/time-offs?start=2026-11-02&end=2026-11-08"
            )
        self.assertEqual(missing_key.status_code, 503)

        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "test-key"}):
            invalid_range = self.client.get(
                "/api/bamboohr/time-offs?start=2026-11-08&end=2026-11-02"
            )
        self.assertEqual(invalid_range.status_code, 400)

        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "test-key"}), patch(
            "scheduler.urlopen", side_effect=HTTPError("url", 401, "unauthorized", {}, None)
        ):
            rejected_key = self.client.get(
                "/api/bamboohr/time-offs?start=2026-11-02&end=2026-11-08"
            )
        self.assertEqual(rejected_key.status_code, 502)
        self.assertIn("HTTP 401", rejected_key.get_json()["error"])

        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "test-key"}), patch(
            "scheduler.urlopen", side_effect=URLError("offline")
        ):
            unavailable = self.client.get(
                "/api/bamboohr/time-offs?start=2026-11-02&end=2026-11-08"
            )
        self.assertEqual(unavailable.status_code, 502)

    def test_publish_preview_builds_jamaica_time_payload(self):
        schedule = self.prepare_publish_schedule()
        response = self.client.post(
            "/api/bamboohr/preview",
            json={
                "selections": [
                    {"runId": schedule["id"], "day": 0, "start": 6},
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["payloads"][0]
        self.assertEqual(payload["scheduleId"], "test-schedule-1")
        self.assertEqual(payload["start"], "2026-11-02T11:00:00Z")
        self.assertEqual(payload["end"], "2026-11-02T20:00:00Z")
        self.assertEqual(payload["employeeIds"], [9901])
        schedule["employees"][0]["bamboohrId"] = "changed"
        self.client.put(f"/api/accepted-shifts/{schedule['id']}", json=schedule)
        stale = self.client.post(
            "/api/bamboohr/preview",
            json={
                "selections": [
                    {"runId": schedule["id"], "day": 0, "start": 6},
                ]
            },
        )
        self.assertEqual(stale.status_code, 400)
        self.assertIn("different BambooHR ID", stale.get_json()["error"])

    def test_publish_preview_excludes_manual_employees(self):
        schedule = self.prepare_publish_schedule()
        created = self.client.post(
            "/api/employees",
            json={
                "id": "990002",
                "name": "Manual Publish Test",
                "location": "Kingston",
                "role": "Cashier",
                "active": False,
            },
        )
        self.assertEqual(created.status_code, 201)
        manual_id = created.get_json()["employee"]["bamboohrId"]
        schedule["employees"].append(
            {
                "id": "990002",
                "name": "Manual Publish Test",
                "slots": [6, None, None, None, None, None, None],
                "types": ["Demand", None, None, None, None, None, None],
                "bamboohrId": manual_id,
                "scheduleLocationId": None,
                "active": False,
            }
        )
        self.assertEqual(
            self.client.put(f"/api/accepted-shifts/{schedule['id']}", json=schedule).status_code,
            200,
        )
        response = self.client.post(
            "/api/bamboohr/preview",
            json={"selections": [{"runId": schedule["id"], "day": 0, "start": 6}]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["payloads"][0]["employeeIds"], [9901])

    def test_publish_requires_confirmation_and_reports_mocked_success(self):
        config = self.client.get("/api/app-config").get_json()
        config["tenantId"] = "acme-hr"
        self.assertEqual(self.client.put("/api/app-config", json=config).status_code, 200)
        schedule = self.prepare_publish_schedule()
        selections = [{"runId": schedule["id"], "day": 0, "start": 6}]
        response = self.client.post(
            "/api/bamboohr/publish",
            json={"confirmed": False, "selections": selections},
        )
        self.assertEqual(response.status_code, 400)

        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": ""}):
            response = self.client.post(
                "/api/bamboohr/publish",
                json={"confirmed": True, "selections": selections},
            )
        self.assertEqual(response.status_code, 503)

        class FakeResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "test-key"}), patch(
            "scheduler.urlopen", return_value=FakeResponse()
        ) as open_url:
            response = self.client.post(
                "/api/bamboohr/publish",
                json={"confirmed": True, "selections": selections},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["results"][0]["success"])
        self.assertEqual(
            open_url.call_args.args[0].full_url,
            "https://acme-hr.bamboohr.com/api/v1/scheduling/shifts",
        )


class DeveloperChangeRequestTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.temporary_directory.name) / "developer.sqlite3"
        scheduler.initialize_database()
        scheduler.app.config["TESTING"] = True
        self.client = scheduler.app.test_client()

    def tearDown(self):
        scheduler.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def setup_developer(self, username="reviewer", password="Strong-Developer-2026!"):
        state = self.client.get("/api/developer/auth-state").get_json()
        response = self.client.post(
            "/api/developer/setup",
            headers={"X-CSRF-Token": state["csrfToken"]},
            json={"username": username, "password": password},
        )
        return response

    def test_change_request_log_requires_developer_login_and_exposes_dependencies(self):
        self.assertEqual(
            self.client.get("/api/developer/change-requests").status_code,
            401,
        )
        state = self.client.get("/api/developer/auth-state").get_json()
        remote_setup = self.client.post(
            "/api/developer/setup",
            environ_base={"REMOTE_ADDR": "192.0.2.1"},
            headers={"X-CSRF-Token": state["csrfToken"]},
            json={
                "username": "remote-reviewer",
                "password": "Strong-Developer-2026!",
            },
        )
        self.assertEqual(remote_setup.status_code, 403)
        setup = self.setup_developer()
        self.assertEqual(setup.status_code, 200)

        listing = self.client.get("/api/developer/change-requests")
        self.assertEqual(listing.status_code, 200)
        requests = listing.get_json()["requests"]
        self.assertEqual(len(requests), len(scheduler.DEVELOPER_REQUESTS))
        self.assertEqual(listing.get_json()["nextEligible"]["id"], "tenant-identity")
        hub = next(item for item in requests if item["id"] == "business-hub")
        self.assertEqual(hub["dependencies"][0]["id"], "tenant-identity")
        self.assertEqual(hub["dependencies"][0]["status"], "pending")
        self.assertEqual(
            self.client.get("/api/developer/change-requests?status=invalid").status_code,
            400,
        )
        done_filter = self.client.get(
            "/api/developer/change-requests?status=done"
        ).get_json()
        self.assertEqual(done_filter["requests"][0]["id"], "developer-change-log")
        self.assertEqual(done_filter["nextEligible"]["id"], "tenant-identity")

    def test_change_request_status_cannot_bypass_blocking_requests(self):
        setup = self.setup_developer()
        token = setup.get_json()["csrfToken"]
        blocked = self.client.put(
            "/api/developer/change-requests/business-hub",
            headers={"X-CSRF-Token": token},
            json={"status": "in_progress"},
        )
        self.assertEqual(blocked.status_code, 409)

        started = self.client.put(
            "/api/developer/change-requests/tenant-identity",
            headers={"X-CSRF-Token": token},
            json={"status": "in_progress"},
        )
        self.assertEqual(started.status_code, 200)
        completed = self.client.put(
            "/api/developer/change-requests/tenant-identity",
            headers={"X-CSRF-Token": token},
            json={"status": "done"},
        )
        self.assertEqual(completed.status_code, 200)
        unblocked = self.client.put(
            "/api/developer/change-requests/business-hub",
            headers={"X-CSRF-Token": token},
            json={"status": "in_progress"},
        )
        self.assertEqual(unblocked.status_code, 200)

    def test_developer_credentials_can_be_changed_and_rotated(self):
        setup = self.setup_developer()
        token = setup.get_json()["csrfToken"]
        changed = self.client.post(
            "/api/developer/credentials",
            headers={"X-CSRF-Token": token},
            json={
                "currentPassword": "Strong-Developer-2026!",
                "username": "reviewer-two",
                "newPassword": "Another-Strong-Password-2026!",
            },
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.get_json()["username"], "reviewer-two")
        self.client.post(
            "/api/developer/logout",
            headers={"X-CSRF-Token": changed.get_json()["csrfToken"]},
            json={},
        )
        state = self.client.get("/api/developer/auth-state").get_json()
        old_login = self.client.post(
            "/api/developer/login",
            headers={"X-CSRF-Token": state["csrfToken"]},
            json={
                "username": "reviewer",
                "password": "Strong-Developer-2026!",
            },
        )
        self.assertEqual(old_login.status_code, 401)
        new_login = self.client.post(
            "/api/developer/login",
            headers={"X-CSRF-Token": state["csrfToken"]},
            json={
                "username": "reviewer-two",
                "password": "Another-Strong-Password-2026!",
            },
        )
        self.assertEqual(new_login.status_code, 200)


if __name__ == "__main__":
    unittest.main()
