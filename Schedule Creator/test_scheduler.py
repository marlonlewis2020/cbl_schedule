import json
import os
import sqlite3
import tempfile
import time
import unittest
import base64
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import MagicMock, patch

import scheduler

# Unit tests must never use the deployment database loaded from .env.
scheduler.DATABASE_URL = ""

def authenticate_test_admin(client):
    with closing(scheduler.database_connect()) as connection, connection:
        connection.execute(
            """
            INSERT INTO tenant_admins
                (id, tenant_id, email, display_name, password_hash,
                 mfa_secret, mfa_enabled, active, auth_version, is_primary)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, 1, 1)
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
        token = scheduler.secrets.token_urlsafe(32)
        browser_session["idle_session_id"] = token
        browser_session["idle_csrf"] = "idle-test-token"
    with closing(scheduler.database_connect()) as connection, connection:
        now = int(time.time())
        connection.execute(
            "INSERT INTO browser_sessions(id,started_at,last_activity) VALUES(?,?,?)",
            (token, now, now),
        )


class RetiredMfaBypassTests(unittest.TestCase):
    def test_obsolete_environment_setting_cannot_skip_admin_enrollment(self):
        with tempfile.TemporaryDirectory() as directory:
            original_path = scheduler.DATABASE_PATH
            scheduler.DATABASE_PATH = Path(directory) / "bypass.sqlite3"
            try:
                scheduler.initialize_database()
                scheduler.provision_tenant_admin("A", "a@example.com", "test-password-123456")
                credentials = {"email": "a@example.com", "password": "test-password-123456"}
                for setting in ("", "1"):
                    client = scheduler.app.test_client()
                    token = client.get("/api/tenant-auth/state").get_json()["csrfToken"]
                    with patch.dict(os.environ, {"SCHEDULE_CREATOR_TEMPORARY_MFA_BYPASS": setting}):
                        response = client.post(
                            "/api/tenant-auth/login",
                            headers={"X-CSRF-Token": token},
                            json=credentials | {"bamboohrSubdomain": "cbljm"},
                        )
                        self.assertEqual(response.status_code, 200)
                        self.assertTrue(response.get_json()["mfaEnrollmentRequired"])
                        self.assertFalse(response.get_json().get("authenticated"))
                        self.assertEqual(client.get("/api/employees").status_code, 401)
            finally:
                scheduler.DATABASE_PATH = original_path


class PrimaryAdminDataSettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.directory.name) / "primary.sqlite3"
        scheduler.initialize_database()
        self.primary = scheduler.app.test_client()
        authenticate_test_admin(self.primary)
        self.headers = {"X-CSRF-Token": "test-csrf-token"}
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """INSERT INTO tenant_admins
                   (id, tenant_id, email, display_name, password_hash,
                    mfa_secret, mfa_enabled, active, auth_version, is_primary)
                   SELECT 'additional', tenant_id, 'additional@example.test',
                          display_name, password_hash, mfa_secret, 1, 1, 1, 0
                   FROM tenant_admins WHERE id='test-admin'"""
            )
        self.additional = self.admin_client("additional")

    def tearDown(self):
        scheduler.DATABASE_PATH = self.original_path
        self.directory.cleanup()

    def admin_client(self, admin_id, tenant_id=None):
        client = scheduler.app.test_client()
        with self.primary.session_transaction() as current:
            state = dict(current)
        state["tenant_admin_id"] = admin_id
        state["tenant_id"] = tenant_id or scheduler.DEFAULT_TENANT_ID
        with client.session_transaction() as current:
            current.update(state)
        return client

    def test_primary_operations_require_live_permission_tenant_and_csrf(self):
        path = "/api/workspace/data-settings"
        state = self.primary.get("/api/tenant-auth/state").get_json()
        self.assertTrue(state["isPrimaryAdmin"])
        self.assertFalse(self.additional.get("/api/tenant-auth/state").get_json()["isPrimaryAdmin"])
        permission = self.primary.get(path)
        self.assertEqual(permission.status_code, 200)
        self.assertEqual(permission.headers["Cache-Control"], "no-store")
        for operation in ("source-import", "restore", "backup", "configured-inputs", "portable", "meta-update"):
            payload = {"operation": operation, "tenantId": scheduler.DEFAULT_TENANT_ID}
            denied = self.additional.post(path, headers=self.headers, json=payload)
            self.assertEqual(denied.status_code, 403)
            result = self.primary.post(path, headers=self.headers, json=payload)
            self.assertEqual(result.status_code, 200, result.get_json())
        self.assertEqual(self.primary.post(path, json=payload).status_code, 400)
        self.assertEqual(self.primary.post(
            path, headers=self.headers, json=payload | {"tenantId": "other"}).status_code, 409)
        self.assertEqual(self.primary.post(
            path, headers=self.headers, json=payload | {"operation": "unknown"}).status_code, 400)
        self.assertEqual(self.primary.post(
            path, headers=self.headers, json=payload | {"operation": {}}).status_code, 400)
        self.assertEqual(self.additional.get(path).status_code, 403)
        # Additional administrators retain normal scheduling and Settings APIs.
        for endpoint in ("/api/accepted-shifts", "/api/app-config", "/api/employees"):
            self.assertEqual(self.additional.get(endpoint).status_code, 200)
        self.assertEqual(self.additional.put(
            "/api/employees/import-review", headers=self.headers,
            json={"employees": []}).status_code, 403)
        self.assertEqual(self.primary.put(
            "/api/employees/import-review", json={"employees": []}).status_code, 400)
        with closing(scheduler.database_connect()) as connection, connection:
            events = connection.execute(
                "SELECT detail FROM hub_audit_events WHERE action='workspace-data-settings-authorized'"
            ).fetchall()
            self.assertEqual(len(events), 6)
            connection.execute("UPDATE tenant_admins SET is_primary=0 WHERE id='test-admin'")
            connection.execute("UPDATE tenant_admins SET is_primary=1 WHERE id='additional'")
        self.assertEqual(self.primary.get(path).status_code, 403)
        self.assertEqual(self.additional.get(path).status_code, 200)
        self.assertTrue(self.additional.get("/api/tenant-auth/state").get_json()["isPrimaryAdmin"])
        self.assertFalse(self.primary.get("/api/tenant-auth/state").get_json()["isPrimaryAdmin"])
        reloaded = self.admin_client("additional")
        self.assertEqual(reloaded.get(path).status_code, 200)

    def test_accept_bamboo_locations_initializes_meta_and_preserves_app_overrides(self):
        denied = self.additional.post(
            "/api/meta-settings/locations/accept",
            headers=self.headers,
            json={"source": "manual", "locations": ["Unauthorized location"]},
        )
        self.assertEqual(denied.status_code, 403)
        tenant_id = scheduler.DEFAULT_TENANT_ID
        with closing(scheduler.database_connect()) as connection, connection:
            connection.executemany(
                """INSERT INTO employees
                   (employee_id, tenant_id, bamboohr_id, name, location, role,
                    active, source_type, bamboohr_location)
                   VALUES (?, ?, ?, ?, ?, '', 0, 'bamboohr', 'KIDD')""",
                [
                    ("bamboo-unmapped", tenant_id, "bamboo-1", "Unmapped employee", ""),
                    ("bamboo-overridden", tenant_id, "bamboo-2", "App override", "Custom app location"),
                ],
            )
        response = self.primary.post(
            "/api/meta-settings/locations/accept",
            headers=self.headers,
            json={"source": "bamboohr", "locations": ["KIDD"]},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertEqual(result["accepted"], ["KIDD"])
        self.assertEqual(result["employeesAssigned"], 1)
        self.assertEqual(result["locations"], [{
            "name": "KIDD", "intensity": [None] * 7, "open": [None] * 7,
        }])
        settings = self.primary.get("/api/meta-settings").get_json()
        self.assertTrue(settings["configured"])
        with closing(scheduler.database_connect()) as connection:
            employees = {
                row[0]: row[1]
                for row in connection.execute(
                    "SELECT employee_id, location FROM employees WHERE tenant_id=?",
                    (tenant_id,),
                ).fetchall()
            }
        self.assertEqual(employees["bamboo-unmapped"], "KIDD")
        self.assertEqual(employees["bamboo-overridden"], "Custom app location")
        repeated = self.primary.post(
            "/api/meta-settings/locations/accept",
            headers=self.headers,
            json={"source": "bamboohr", "revision": result["revision"], "locations": ["KIDD"]},
        )
        self.assertEqual(repeated.status_code, 200, repeated.get_json())
        self.assertEqual(repeated.get_json()["accepted"], [])
        self.assertEqual(repeated.get_json()["employeesAssigned"], 0)
        rejected = self.primary.post(
            "/api/meta-settings/locations/accept",
            headers=self.headers,
            json={"source": "bamboohr", "revision": repeated.get_json()["revision"], "locations": ["Not in BambooHR"]},
        )
        self.assertEqual(rejected.status_code, 409)

    def test_no_owner_portal_or_cross_tenant_permission(self):
        path = "/api/workspace/data-settings"
        for role_session in (
            {}, {"platform_owner_id": "owner", "platform_auth_version": 1},
            {"access_user_id": "manager", "access_auth_version": 1},
            {"access_user_id": "employee", "access_auth_version": 1},
        ):
            client = scheduler.app.test_client()
            with client.session_transaction() as current:
                current.update(role_session)
            self.assertEqual(client.get(path).status_code, 401)
            self.assertEqual(client.put(
                "/api/employees/import-review", headers=self.headers, json={}).status_code, 401)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "INSERT INTO tenants(tenant_id,business_name) VALUES('other','Other business')"
            )
        forged = self.admin_client("test-admin", "other")
        self.assertEqual(forged.get(path).status_code, 401)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE tenant_admins SET active=0 WHERE id='test-admin'")
        self.assertEqual(self.primary.get(path).status_code, 401)

    def test_settings_is_separate_from_restricted_navigation_group(self):
        markup = (scheduler.APP_DIRECTORY / "CBL-Scheduler2.html").read_text(encoding="utf-8")
        group = markup.split('Data & settings</span>', 1)[1].split("</div>", 1)[0]
        self.assertIn('data-page="source" hidden', group)
        self.assertIn('data-page="meta" hidden', group)
        planning = markup.split('Plan schedules</span>', 1)[1].split("</div>", 1)[0]
        self.assertNotIn('data-page="meta"', planning)
        self.assertNotIn('data-page="settings"', group)
        self.assertIn('</div>\n                <button type="button" data-page="settings">', markup)


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
            json={
                "bamboohrSubdomain": "acme",
                "email": email,
                "password": password,
            },
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
            self.query(
                "SELECT bamboohr_subdomain FROM tenants WHERE tenant_id = ?",
                (tenant_id,),
            )[0][0],
            "acme",
        )
        self.assertEqual(
            self.query("SELECT action FROM hub_audit_events WHERE tenant_id = ?", (tenant_id,)),
            [("register",)],
        )
        duplicate, _ = self.register(businessName="Other Co")
        self.assertEqual(duplicate.status_code, 409)
        duplicate_domain, domain_check = self.register(
            businessName="Third Co",
            bamboohrSubdomain="ACME",
            adminEmail="third@acme.example",
        )
        self.assertEqual(duplicate_domain.status_code, 409)
        self.assertIn("already registered", duplicate_domain.get_json()["error"])
        domain_check.assert_not_called()
        self.assertEqual(len(self.query("SELECT 1 FROM tenants")), 2)

    def test_login_uses_subdomain_to_select_same_email_admin(self):
        first, _ = self.register()
        second, _ = self.register(
            businessName="Second Co",
            bamboohrSubdomain="second",
        )
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        first_tenant = self.tenant_id("Acme Foods")
        second_tenant = self.tenant_id("Second Co")
        with closing(scheduler.database_connect()) as connection, connection:
            first_admin = connection.execute(
                "SELECT id FROM tenant_admins WHERE tenant_id = ?",
                (first_tenant,),
            ).fetchone()[0]
            second_admin = connection.execute(
                "SELECT id FROM tenant_admins WHERE tenant_id = ?",
                (second_tenant,),
            ).fetchone()[0]
            _, first_mfa_uri = scheduler.start_mfa_enrollment(
                connection, first_admin, REGISTRATION["adminEmail"]
            )
            _, second_mfa_uri = scheduler.start_mfa_enrollment(
                connection, second_admin, REGISTRATION["adminEmail"]
            )
        self.assertNotEqual(first_mfa_uri, second_mfa_uri)

        first_client, _ = self.sign_in_admin()
        with first_client.session_transaction() as browser_session:
            self.assertEqual(browser_session["tenant_id"], first_tenant)

        second_client = scheduler.app.test_client()
        token = second_client.get("/api/tenant-auth/state").get_json()["csrfToken"]
        login = second_client.post(
            "/api/tenant-auth/login",
            headers={"X-CSRF-Token": token},
            json={
                "bamboohrSubdomain": "second",
                "email": REGISTRATION["adminEmail"],
                "password": REGISTRATION["password"],
            },
        )
        enrollment = login.get_json()
        self.assertEqual(login.status_code, 200)
        self.assertTrue(enrollment["mfaEnrollmentRequired"])
        code = scheduler.totp_value(
            enrollment["secret"], int(time.time() // 30)
        )
        verified = second_client.post(
            "/api/tenant-auth/verify-mfa",
            headers={"X-CSRF-Token": enrollment["csrfToken"]},
            json={"code": code},
        )
        self.assertEqual(verified.status_code, 200)
        with second_client.session_transaction() as browser_session:
            self.assertEqual(browser_session["tenant_id"], second_tenant)

        wrong_business = scheduler.app.test_client()
        token = wrong_business.get("/api/tenant-auth/state").get_json()["csrfToken"]
        wrong = wrong_business.post(
            "/api/tenant-auth/login",
            headers={"X-CSRF-Token": token},
            json={
                "bamboohrSubdomain": "unknown",
                "email": REGISTRATION["adminEmail"],
                "password": REGISTRATION["password"],
            },
        )
        self.assertEqual(wrong.status_code, 401)
        missing_domain = wrong_business.post(
            "/api/tenant-auth/login",
            headers={"X-CSRF-Token": token},
            json={
                "email": REGISTRATION["adminEmail"],
                "password": REGISTRATION["password"],
            },
        )
        self.assertEqual(missing_domain.status_code, 400)

    def test_business_settings_cannot_claim_another_business_domain(self):
        self.register()
        self.register(
            businessName="Second Co",
            bamboohrSubdomain="second",
            adminEmail="second@acme.example",
        )
        self.make_owner()
        owner, owner_csrf = self.sign_in_owner()
        self.assertEqual(
            self.set_status(owner, owner_csrf, self.tenant_id(), "active").status_code,
            200,
        )
        client, csrf = self.sign_in_admin()
        config = client.get("/api/app-config").get_json()
        config["tenantId"] = "SECOND"
        response = client.put(
            "/api/app-config",
            headers={"X-CSRF-Token": csrf},
            json=config,
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            self.query(
                "SELECT bamboohr_subdomain FROM tenants WHERE tenant_id = ?",
                (self.tenant_id(),),
            )[0][0],
            "acme",
        )

    def test_registration_attempts_are_rate_limited(self):
        statuses = [
            self.register(
                adminEmail=f"a{index}@acme.example",
                bamboohrSubdomain=f"acme{index}",
            )[0].status_code
            for index in range(6)
        ]
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

    def test_admin_can_update_own_profile_and_email_change_requires_password(self):
        self.register()
        admin, csrf = self.sign_in_admin()
        state = admin.get("/api/tenant-auth/state").get_json()
        self.assertEqual(state["displayName"], REGISTRATION["adminName"])
        self.assertEqual(state["email"], REGISTRATION["adminEmail"])
        headers = {"X-CSRF-Token": csrf}
        denied = admin.post(
            "/api/business/profile",
            headers=headers,
            json={"name": "Ada New", "email": "new-ada@acme.example"},
        )
        self.assertEqual(denied.status_code, 403)
        changed = admin.post(
            "/api/business/profile",
            headers=headers,
            json={
                "name": "Ada New",
                "email": "new-ada@acme.example",
                "currentPassword": REGISTRATION["password"],
            },
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(
            admin.get("/api/tenant-auth/state").get_json()["displayName"], "Ada New"
        )
        self.assertEqual(
            admin.get("/api/tenant-auth/state").get_json()["email"], "new-ada@acme.example"
        )
        self.assertEqual(
            admin.post(
                "/api/business/profile",
                headers=headers,
                json={"name": " ", "email": "new-ada@acme.example"},
            ).status_code,
            400,
        )

    def test_platform_owner_can_permanently_delete_a_business(self):
        self.register(
            businessName="Fraud Co",
            bamboohrSubdomain="fraud",
            adminEmail="fraud@example.com",
        )
        tenant_id = self.tenant_id("Fraud Co")
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO schedule_locations
                    (id, tenant_id, name, bamboo_schedule_id, location)
                VALUES ('fraud-location', ?, 'Fraud schedule', 'fraud-schedule', 'Fraud')
                """,
                (tenant_id,),
            )
            connection.execute(
                """
                INSERT INTO employees (employee_id, tenant_id, name, location, role)
                VALUES ('fraud-employee', ?, 'Fraud Employee', 'Fraud', 'Staff')
                """,
                (tenant_id,),
            )
            connection.execute(
                """
                INSERT INTO accepted_schedules
                    (run_id, tenant_id, week_start, location, role, payload)
                VALUES ('fraud-run', ?, '2026-11-02', 'Fraud', 'Staff', '{}')
                """,
                (tenant_id,),
            )
        self.make_owner()
        owner, csrf = self.sign_in_owner()
        headers = {"X-CSRF-Token": csrf}
        original = owner.delete(
            f"/api/hub/businesses/{scheduler.DEFAULT_TENANT_ID}", headers=headers
        )
        self.assertEqual(original.status_code, 409)
        deleted = owner.delete(
            f"/api/hub/businesses/{tenant_id}", headers=headers
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(
            self.query("SELECT 1 FROM tenants WHERE tenant_id = ?", (tenant_id,)), []
        )
        for table in (
            "tenant_admins",
            "employees",
            "accepted_schedules",
            "schedule_locations",
            "application_settings",
            "tenant_audit_events",
        ):
            self.assertEqual(
                self.query(f"SELECT 1 FROM {table} WHERE tenant_id = ?", (tenant_id,)),
                [],
                table,
            )
        self.assertEqual(
            self.query(
                "SELECT action FROM hub_audit_events WHERE tenant_id = ?",
                (tenant_id,),
            ),
            [("register",), ("business-permanently-deleted",)],
        )

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
        self.assertNotIn("acme-key-123", json.dumps(listing))
        self.assertNotIn("bamboohrApiKey", json.dumps(listing))
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
            json={
                "bamboohrSubdomain": "second",
                "email": "bo@second.example",
                "password": "correct-horse-battery",
            },
        )
        self.assertEqual(rejected_login.status_code, 401)
        self.assertEqual(self.set_status(owner, csrf, second, "pending").status_code, 200)
        actions = [row[0] for row in self.query("SELECT action FROM hub_audit_events")]
        self.assertIn("status-pending-to-active", actions)
        self.assertIn("status-active-to-suspended", actions)

    def test_platform_owner_assigns_tiers_and_sees_usage(self):
        self.register()
        self.make_owner()
        owner, csrf = self.sign_in_owner()
        tenant_id = self.tenant_id()
        listing = owner.get("/api/hub/businesses").get_json()["businesses"]
        business = next(item for item in listing if item["id"] == tenant_id)
        self.assertEqual(business["membership"]["tier"], "bronze")
        self.assertIn("locations", business["membership"]["usage"])
        changed = owner.post(
            f"/api/hub/businesses/{tenant_id}/tier",
            headers={"X-CSRF-Token": csrf},
            json={"tier": "gold"},
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.get_json()["membership"]["tier"], "gold")
        self.assertTrue(
            changed.get_json()["membership"]["features"]["overtimeForecasting"]
        )
        self.assertEqual(
            owner.post(
                f"/api/hub/businesses/{tenant_id}/tier",
                headers={"X-CSRF-Token": csrf},
                json={"tier": "diamond"},
            ).status_code,
            400,
        )

    def test_primary_admin_can_change_pause_resume_and_cancel_membership(self):
        self.register()
        tenant_id = self.tenant_id()
        self.make_owner()
        owner, owner_csrf = self.sign_in_owner()
        self.assertEqual(
            self.set_status(owner, owner_csrf, tenant_id, "active").status_code,
            200,
        )
        admin, csrf = self.sign_in_admin()
        headers = {"X-CSRF-Token": csrf}

        rejected = admin.post(
            "/api/business/membership",
            headers=headers,
            json={"action": "pause"},
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(
            admin.post(
                "/api/business/membership",
                headers={"X-CSRF-Token": "invalid"},
                json={"action": "pause", "confirmed": True},
            ).status_code,
            400,
        )

        added = admin.post(
            "/api/business/admins",
            headers=headers,
            json={
                "name": "Secondary Admin",
                "email": "secondary@acme.example",
                "password": "secondary-long-password",
            },
        )
        self.assertEqual(added.status_code, 201)
        secondary, secondary_csrf = self.sign_in_admin(
            "secondary@acme.example", "secondary-long-password"
        )
        denied = secondary.post(
            "/api/business/membership",
            headers={"X-CSRF-Token": secondary_csrf},
            json={"action": "change_tier", "tier": "gold", "confirmed": True},
        )
        self.assertEqual(denied.status_code, 403)

        changed = admin.post(
            "/api/business/membership",
            headers=headers,
            json={"action": "change_tier", "tier": "gold", "confirmed": True},
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.get_json()["membership"]["tier"], "gold")

        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO accepted_schedules
                    (run_id, tenant_id, week_start, location, role, payload)
                VALUES ('membership-preserved', ?, '2026-11-02',
                        'Kingston', 'Cashier', '{}')
                """,
                (tenant_id,),
            )

        paused = admin.post(
            "/api/business/membership",
            headers=headers,
            json={"action": "pause", "confirmed": True},
        )
        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.get_json()["membership"]["status"], "paused")
        self.assertFalse(paused.get_json()["accessEnabled"])
        blocked = admin.get("/api/employees")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.get_json()["membershipStatus"], "paused")
        status_page = admin.get("/")
        self.assertEqual(status_page.get_data(), (scheduler.APP_DIRECTORY / "business-status.html").read_bytes())
        status_page.close()

        resumed = admin.post(
            "/api/business/membership",
            headers=headers,
            json={"action": "resume", "confirmed": True},
        )
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.get_json()["membership"]["status"], "active")
        self.assertTrue(resumed.get_json()["accessEnabled"])
        self.assertEqual(admin.get("/api/employees").status_code, 200)

        cancelled = admin.post(
            "/api/business/membership",
            headers=headers,
            json={"action": "cancel", "confirmed": True},
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.get_json()["membership"]["status"], "cancelled")
        self.assertFalse(cancelled.get_json()["accessEnabled"])
        self.assertEqual(
            admin.get("/api/employees").get_json()["membershipStatus"], "cancelled"
        )
        self.assertEqual(
            self.query(
                "SELECT membership_status, membership_tier FROM tenants WHERE tenant_id = ?",
                (tenant_id,),
            ),
            [("cancelled", "gold")],
        )
        self.assertEqual(
            self.query(
                "SELECT run_id FROM accepted_schedules WHERE tenant_id = ?",
                (tenant_id,),
            ),
            [("membership-preserved",)],
        )
        membership_audit = self.query(
                "SELECT actor_email, action FROM tenant_audit_events "
                "WHERE tenant_id = ? AND action LIKE 'membership-%' ORDER BY created_at, action",
                (tenant_id,),
            )
        self.assertEqual(
            set(membership_audit),
            {
                ("ada@acme.example", "membership-status-active-to-cancelled"),
                ("ada@acme.example", "membership-status-active-to-paused"),
                ("ada@acme.example", "membership-status-paused-to-active"),
                ("ada@acme.example", "membership-tier-bronze-to-gold"),
            },
        )
        for action, extra in (
            ("resume", {}),
            ("change_tier", {"tier": "silver"}),
        ):
            denied_after_cancel = admin.post(
                "/api/business/membership",
                headers=headers,
                json={"action": action, "confirmed": True} | extra,
            )
            self.assertEqual(denied_after_cancel.status_code, 409)

        restored = owner.post(
            f"/api/hub/businesses/{tenant_id}/membership-status",
            headers={"X-CSRF-Token": owner_csrf},
            json={"confirmed": True},
        )
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.get_json()["membership"]["status"], "active")
        self.assertEqual(admin.get("/api/employees").status_code, 200)
        self.assertEqual(
            self.query(
                "SELECT COUNT(*) FROM hub_audit_events "
                "WHERE tenant_id = ? AND action = ?",
                (tenant_id, "membership-status-cancelled-to-active"),
            )[0][0],
            1,
        )

    @patch.dict(os.environ, {"SCHEDULE_CREATOR_TEMPORARY_MFA_BYPASS": "1"})
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
        self.assertEqual(
            primary.post(
                "/api/business/admins",
                headers=headers,
                json={"email": "missing-name@acme.example", "password": new_admin["password"]},
            ).status_code,
            400,
        )
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
        primary_list = primary.get("/api/business/admins").get_json()
        admins = primary_list["admins"]
        self.assertTrue(primary_list["isPrimaryAdmin"])
        self.assertEqual([admin["isPrimary"] for admin in admins], [True, False])
        self.assertTrue(all(admin["mfaEnabled"] for admin in admins))
        self.assertTrue(all(admin["joinedAt"] for admin in admins))
        extra_list = extra.get("/api/business/admins").get_json()
        self.assertFalse(extra_list["isPrimaryAdmin"])
        self.assertEqual(set(extra_list["admins"][0]), {"id", "email", "name", "isPrimary"})
        self.assertEqual(
            extra.post(
                f"/api/business/admins/{created.get_json()['id']}/reset-password",
                headers={"X-CSRF-Token": extra_csrf},
                json={},
            ).status_code,
            403,
        )
        self.assertEqual(
            extra.post(
                f"/api/business/admins/{created.get_json()['id']}/reset-mfa",
                headers={"X-CSRF-Token": extra_csrf},
                json={},
            ).status_code,
            403,
        )
        self.assertEqual(
            extra.put(
                f"/api/business/admins/{created.get_json()['id']}",
                headers={"X-CSRF-Token": extra_csrf},
                json={"name": "Changed", "email": "changed@acme.example"},
            ).status_code,
            403,
        )
        self.assertEqual(
            primary.put(
                f"/api/business/admins/{created.get_json()['id']}",
                headers=headers,
                json={"name": "Bo Updated", "email": "bo-updated@acme.example"},
            ).status_code,
            200,
        )
        self.assertEqual(
            primary.get("/api/business/admins").get_json()["admins"][1]["name"],
            "Bo Updated",
        )
        password_reset = primary.post(
            f"/api/business/admins/{created.get_json()['id']}/reset-password",
            headers=headers,
            json={},
        )
        self.assertEqual(password_reset.status_code, 200)
        temporary_password = password_reset.get_json()["temporaryPassword"]
        self.assertGreaterEqual(len(temporary_password), 14)
        self.assertEqual(extra.get("/api/employees").status_code, 401)
        self.assertTrue(
            scheduler.check_password_hash(
                self.query(
                    "SELECT password_hash FROM tenant_admins WHERE id = ?",
                    (created.get_json()["id"],),
                )[0][0],
                temporary_password,
            )
        )
        self.assertEqual(
            primary.post(
                f"/api/business/admins/{created.get_json()['id']}/reset-mfa",
                headers=headers,
                json={},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.query(
                "SELECT mfa_enabled, mfa_secret FROM tenant_admins WHERE id = ?",
                (created.get_json()["id"],),
            )[0],
            (0, None),
        )
        self.assertEqual(extra.get("/api/employees").status_code, 401)
        primary_id = admins[0]["id"]
        self.assertEqual(
            primary.delete(f"/api/business/admins/{primary_id}", headers=headers).status_code, 404
        )
        self.assertEqual(
            extra.delete(f"/api/business/admins/{primary_id}", headers={"X-CSRF-Token": extra_csrf}).status_code,
            401,
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
                        json={"bamboohrSubdomain": "acme", "email": "bo@acme.example",
                              "password": "temporary-password-1"}).status_code,
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


class MembershipEntitlementTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.temporary_directory.name) / "tiers.sqlite3"
        scheduler.initialize_database()
        scheduler.app.config["TESTING"] = True
        self.client = scheduler.app.test_client()
        authenticate_test_admin(self.client)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("DELETE FROM employees")
            connection.execute("DELETE FROM schedule_locations")
            connection.execute(
                "UPDATE tenant_admins SET is_primary = 1 WHERE id = 'test-admin'"
            )
            connection.execute(
                "UPDATE tenants SET membership_tier = 'bronze' WHERE tenant_id = ?",
                (scheduler.DEFAULT_TENANT_ID,),
            )
        self.headers = {"X-CSRF-Token": "test-csrf-token"}

    def tearDown(self):
        scheduler.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def set_tier(self, tier):
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET membership_tier = ? WHERE tenant_id = ?",
                (tier, scheduler.DEFAULT_TENANT_ID),
            )

    def schedule_location(self, name, location, role):
        return self.client.post(
            "/api/schedule-locations",
            headers=self.headers,
            json={
                "name": f"{name} schedule",
                "bambooScheduleId": f"{name}-schedule",
                "location": location,
                "roleGroup": role,
                "managerName": "Manager",
                "managerEmail": "manager@example.com",
            },
        )

    def test_bronze_admin_limit_blocks_only_additions(self):
        admin = {
            "name": "Second Admin",
            "email": "second@example.com",
            "password": "temporary-password-123",
        }
        created = self.client.post(
            "/api/business/admins", headers=self.headers, json=admin
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            self.client.post(
                "/api/business/admins",
                headers=self.headers,
                json=admin | {"email": "third@example.com"},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/business/admins/{created.get_json()['id']}",
                headers=self.headers,
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/business/admins",
                headers=self.headers,
                json=admin | {"email": "replacement@example.com"},
            ).status_code,
            201,
        )

    def test_employee_limit_counts_active_records_and_allows_downgrades(self):
        employee_ids = []
        for index in range(21):
            employee_id = f"manual-{index}"
            employee_ids.append(employee_id)
            response = self.client.post(
                "/api/employees",
                headers=self.headers,
                json={
                    "id": employee_id,
                    "name": f"Employee {index}",
                    "location": "Store",
                    "role": "Sales",
                    "active": False,
                },
            )
            self.assertEqual(response.status_code, 201)
        self.assertEqual(
            self.client.put(
                "/api/employees/status",
                headers=self.headers,
                json={"employeeIds": employee_ids[:20], "active": True},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.put(
                "/api/employees/status",
                headers=self.headers,
                json={"employeeIds": [employee_ids[20]], "active": True},
            ).status_code,
            409,
        )
        self.set_tier("platinum")
        self.assertEqual(
            self.client.put(
                "/api/employees/status",
                headers=self.headers,
                json={"employeeIds": [employee_ids[20]], "active": True},
            ).status_code,
            200,
        )
        self.set_tier("bronze")
        self.assertEqual(
            self.client.put(
                "/api/employees/status",
                headers=self.headers,
                json={"employeeIds": [employee_ids[0]], "active": False},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.put(
                f"/api/employees/{employee_ids[0]}",
                headers=self.headers,
                json={
                    "id": employee_ids[0],
                    "bamboohrId": "MANUAL-TEST",
                    "name": "Updated Employee",
                    "location": "Store",
                    "role": "Sales",
                    "active": True,
                },
            ).status_code,
            409,
        )

    def test_bronze_team_cap_and_gold_location_cap(self):
        self.assertEqual(self.schedule_location("first", "Store", "Sales").status_code, 201)
        self.assertEqual(self.schedule_location("second", "Store", "Service").status_code, 201)
        self.assertEqual(self.schedule_location("third", "Store", "Warehouse").status_code, 409)
        self.set_tier("gold")
        for index in range(2, 7):
            self.assertEqual(
                self.schedule_location(f"gold-{index}", f"Store {index}", "Sales").status_code,
                201,
            )
        self.assertEqual(
            self.schedule_location("gold-over", "Store 7", "Sales").status_code,
            409,
        )

    def test_schedule_location_quotas_are_tenant_scoped(self):
        self.assertEqual(self.schedule_location("first", "Store A", "Sales").status_code, 201)
        self.assertEqual(self.schedule_location("second", "Store B", "Service").status_code, 201)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO schedule_locations
                    (id, tenant_id, name, bamboo_schedule_id, location, role_group)
                VALUES ('other-location', 'other-business', 'Other schedule',
                        'other-schedule', 'Store C', 'Warehouse')
                """
            )
        self.assertEqual(
            self.schedule_location("third", "Store C", "Warehouse").status_code,
            409,
        )

    def test_downgrade_grandfathers_locations_but_blocks_increases(self):
        self.set_tier("gold")
        first = self.schedule_location("first", "Store A", "Sales")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(self.schedule_location("second", "Store A", "Service").status_code, 201)
        third = self.schedule_location("third", "Store B", "Sales")
        self.assertEqual(third.status_code, 201)
        self.set_tier("bronze")

        updated_payload = {
            "name": "third schedule",
            "bambooScheduleId": "third-schedule",
            "location": "Store C",
            "roleGroup": "Sales",
            "managerName": "Manager",
            "managerEmail": "manager@example.com",
        }
        self.assertEqual(
            self.client.put(
                f"/api/schedule-locations/{third.get_json()['id']}",
                headers=self.headers,
                json=updated_payload,
            ).status_code,
            200,
        )
        updated_payload["location"] = "Store D"
        self.assertEqual(
            self.client.put(
                f"/api/schedule-locations/{first.get_json()['id']}",
                headers=self.headers,
                json=updated_payload | {
                    "name": "first schedule",
                    "bambooScheduleId": "first-schedule",
                },
            ).status_code,
            409,
        )

    def test_tenant_state_exposes_tier_features_and_limits(self):
        state = self.client.get("/api/tenant-auth/state").get_json()
        self.assertEqual(state["membership"]["tier"], "bronze")
        self.assertEqual(state["membership"]["limits"]["employees"], 20)
        self.assertEqual(state["membership"]["limits"]["admins"], 2)
        self.assertEqual(scheduler.MEMBERSHIP_TIERS["silver"]["limits"], {
            "admins": 3, "teams": 4, "employees": 60, "locations": 4
        })
        self.assertEqual(scheduler.MEMBERSHIP_TIERS["gold"]["limits"], {
            "admins": 4, "teams": None, "employees": None, "locations": 6
        })
        self.assertEqual(scheduler.MEMBERSHIP_TIERS["platinum"]["limits"], {
            "admins": 8, "teams": None, "employees": None, "locations": None
        })
        self.assertFalse(state["membership"]["features"]["scheduleHistory"])
        self.assertFalse(state["membership"]["features"]["shiftTrades"])
        self.assertFalse(state["membership"]["features"]["overtimeForecasting"])
        self.set_tier("gold")
        state = self.client.get("/api/tenant-auth/state").get_json()
        self.assertTrue(state["membership"]["features"]["overtimeForecasting"])


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

    def test_existing_scrypt_password_support_preserves_mfa_and_stored_hash(self):
        import hashlib

        password = "scrypt-test-only-password"
        secret = "JBSWY3DPEHPK3PXP"
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=b"test-salt", n=32768, r=8, p=1,
            maxmem=128 * 1024 * 1024,
        ).hex()
        stored_hash = "scrypt:32768:8:1$test-salt$" + digest
        encrypted_secret = scheduler.mfa_cipher().encrypt(secret.encode("ascii")).decode("ascii")
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """INSERT INTO tenant_admins
                   (id,tenant_id,email,display_name,password_hash,mfa_secret,mfa_enabled)
                   VALUES(?,?,?,?,?,?,1)""",
                ("scrypt-admin", scheduler.DEFAULT_TENANT_ID, "scrypt@example.test",
                 "Scrypt Admin", stored_hash, encrypted_secret),
            )
        state = self.client.get("/api/tenant-auth/state").get_json()
        headers = {"X-CSRF-Token": state["csrfToken"]}
        payload = {
            "email": "scrypt@example.test", "password": "wrong-password",
            "bamboohrSubdomain": scheduler.DEFAULT_TENANT_ID, "code": "000000",
        }
        response = self.client.post("/api/tenant-auth/login", headers=headers, json=payload)
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.is_json)
        payload["password"] = password
        with patch.object(scheduler, "verify_totp", return_value=False) as verify:
            response = self.client.post("/api/tenant-auth/login", headers=headers, json=payload)
            self.assertEqual(response.status_code, 401)
            verify.assert_called_once_with(secret, "000000")
        with patch.object(scheduler, "verify_totp", return_value=True):
            response = self.client.post("/api/tenant-auth/login", headers=headers, json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["authenticated"])
        with closing(scheduler.database_connect()) as connection:
            self.assertEqual(connection.execute(
                "SELECT password_hash FROM tenant_admins WHERE id='scrypt-admin'",
            ).fetchone()[0], stored_hash)

    def test_sqlite_admin_email_migration_preserves_enrollment_and_scopes_uniqueness(self):
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "INSERT INTO tenants (tenant_id, business_name) VALUES (?, ?)",
                ("second-business", "Second Business"),
            )
            connection.execute(
                """
                INSERT INTO tenant_admins
                    (id, tenant_id, email, display_name, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("legacy-admin", scheduler.DEFAULT_TENANT_ID, "shared@example.com", "Admin", "hash"),
            )
            connection.execute(
                """
                INSERT INTO tenant_mfa_enrollments (admin_id, encrypted_secret)
                VALUES (?, ?)
                """,
                ("legacy-admin", "encrypted-enrollment"),
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX legacy_tenant_admins_email_unique
                ON tenant_admins (email)
                """
            )

        scheduler.initialize_database()

        with closing(scheduler.database_connect()) as connection, connection:
            enrollment = connection.execute(
                """
                SELECT encrypted_secret FROM tenant_mfa_enrollments
                WHERE admin_id = ?
                """,
                ("legacy-admin",),
            ).fetchone()
            self.assertEqual(enrollment, ("encrypted-enrollment",))
            indexes = connection.execute(
                "PRAGMA index_list(tenant_admins)"
            ).fetchall()
            indexed_columns = []
            for index in indexes:
                if index[2]:
                    escaped_name = index[1].replace('"', '""')
                    indexed_columns.append(
                        [
                            row[2]
                            for row in connection.execute(
                                f'PRAGMA index_info("{escaped_name}")'
                            ).fetchall()
                        ]
                    )
            self.assertNotIn(["email"], indexed_columns)
            self.assertIn(["tenant_id", "email"], indexed_columns)
            connection.execute(
                """
                INSERT INTO tenant_admins
                    (id, tenant_id, email, display_name, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("second-admin", "second-business", "shared@example.com", "Admin 2", "hash"),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO tenant_admins
                        (id, tenant_id, email, display_name, password_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("duplicate-admin", "second-business", "shared@example.com", "Admin 3", "hash"),
                )

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
                "bamboohrSubdomain": "cbljm",
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
                "bamboohrSubdomain": "cbljm",
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
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET membership_tier = 'platinum' WHERE tenant_id = ?",
                (scheduler.DEFAULT_TENANT_ID,),
            )

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
            test_urls = [
                call.args[0].full_url for call in mocked_urlopen.call_args_list
            ]
            self.assertTrue(
                any(
                    url.startswith(
                        "https://cbljm.bamboohr.com/api/v1/time_off/whos_out?start="
                    )
                    for url in test_urls
                )
            )
            self.assertTrue(
                any(
                    url.startswith(
                        "https://cbljm.bamboohr.com/api/v1/time_tracking/timesheet_entries?start="
                    )
                    for url in test_urls
                )
            )
            self.assertTrue(all("&end=" in url for url in test_urls))

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

    def test_bamboo_sync_maps_new_employees_to_accepted_meta_locations(self):
        tenant_id = scheduler.DEFAULT_TENANT_ID
        locations = scheduler.meta_settings.normalize_locations([{
            "name": "Airport",
            "intensity": [None] * 7,
            "open": [None] * 7,
        }])
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """INSERT INTO meta_configurations
                   (tenant_id, revision, locked, locations_json)
                   VALUES (?, 1, 0, ?)""",
                (tenant_id, json.dumps(locations)),
            )
            connection.executemany(
                """INSERT INTO employees
                   (employee_id, tenant_id, bamboohr_id, name, location, role,
                    active, source_type, bamboohr_location)
                   VALUES (?, ?, ?, ?, ?, '', 0, 'bamboohr', 'Airport')""",
                [
                    ("existing-blank", tenant_id, "bamboo-existing-blank", "Existing blank", ""),
                    ("existing-override", tenant_id, "bamboo-existing-override", "Existing override", "App override"),
                ],
            )
        remote = [
            {"id": "airport-employee", "bamboohrId": "bamboo-airport", "name": "Airport Employee", "bamboohrLocation": "Airport"},
            {"id": "existing-blank", "bamboohrId": "bamboo-existing-blank", "name": "Existing blank", "bamboohrLocation": "Airport"},
            {"id": "existing-override", "bamboohrId": "bamboo-existing-override", "name": "Existing override", "bamboohrLocation": "Airport"},
        ]
        with patch.object(scheduler, "fetch_bamboohr_employees", return_value=remote):
            response = self.client.post("/api/bamboohr/employees/sync", json={})
        self.assertEqual(response.status_code, 200, response.get_json())
        employee = next(
            row for row in self.client.get("/api/employees").get_json()["employees"]
            if row["id"] == "airport-employee"
        )
        self.assertEqual(employee["location"], "Airport")
        self.assertEqual(employee["role"], "")
        self.assertIsNone(employee["scheduleLocationId"])
        self.assertFalse(employee["active"])
        employees={row["id"]:row for row in self.client.get("/api/employees").get_json()["employees"]}
        self.assertEqual(employees["existing-blank"]["location"], "Airport")
        self.assertEqual(employees["existing-override"]["location"], "App override")

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
            headers={"X-CSRF-Token": "test-csrf-token"},
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
            headers={"X-CSRF-Token": "test-csrf-token"},
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


class AttendanceAutomationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.temporary_directory.name) / "attendance.sqlite3"
        scheduler.initialize_database()
        scheduler.app.config["TESTING"] = True
        self.client = scheduler.app.test_client()
        authenticate_test_admin(self.client)

    def tearDown(self):
        scheduler.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def query(self, sql, parameters=()):
        with closing(scheduler.database_connect()) as connection:
            return connection.execute(sql, parameters).fetchall()

    def test_attendance_source_requires_confirmation_and_live_read(self):
        response = self.client.get("/api/attendance")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["shiftSource"]["selected"], "app")
        today = scheduler.datetime.now(scheduler.ATTENDANCE_TIMEZONE).date()
        start = end = (today - scheduler.timedelta(days=1)).isoformat()
        unconfirmed = self.client.put(
            "/api/attendance/source",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"source": "bamboohr", "start": start, "end": end},
        )
        self.assertEqual(unconfirmed.status_code, 400)
        self.assertEqual(
            self.query(
                "SELECT setting_value FROM application_settings "
                "WHERE tenant_id = ? AND setting_key = 'attendance_shift_source'",
                (scheduler.DEFAULT_TENANT_ID,),
            ),
            [],
        )

        with patch.object(scheduler, "fetch_bamboohr_scheduled_shifts", return_value=[]) as fetch:
            saved = self.client.put(
                "/api/attendance/source",
                headers={"X-CSRF-Token": "test-csrf-token"},
                json={
                    "source": "bamboohr",
                    "confirmed": True,
                    "start": start,
                    "end": end,
                },
            )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["selected"], "bamboohr")
        self.assertEqual(saved.get_json()["unresolvedDiscrepancies"], [])
        fetch.assert_called_once()
        self.assertEqual(
            self.query(
                "SELECT setting_value FROM application_settings "
                "WHERE tenant_id = ? AND setting_key = 'attendance_shift_source'",
                (scheduler.DEFAULT_TENANT_ID,),
            ), [("bamboohr",)],
        )
        invalid = self.client.put(
            "/api/attendance/source",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"source": "other"},
        )
        self.assertEqual(invalid.status_code, 400)
        saved = self.client.put(
            "/api/attendance/source",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"source": "app"},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["selected"], "app")

    def seed_reconciliation_schedule(self):
        shift_date = scheduler.datetime.now(scheduler.ATTENDANCE_TIMEZONE).date() - scheduler.timedelta(days=2)
        week_start = shift_date - scheduler.timedelta(days=shift_date.weekday())
        day_index = shift_date.weekday()
        schedule_location_id = "reconciliation-location"
        schedule = {
            "id": "reconciliation-run",
            "start": week_start.isoformat(),
            "end": (week_start + scheduler.timedelta(days=6)).isoformat(),
            "location": "Kingston",
            "role": "Cashier",
            "controls": {"span": 8, "hours": 8},
            "employees": [
                {
                    "id": "attendance-111",
                    "name": "Reconciliation employee",
                    "bamboohrId": "111",
                    "location": "Kingston",
                    "role": "Cashier",
                    "scheduleLocationId": schedule_location_id,
                    "slots": [
                        6 if index == day_index else None for index in range(7)
                    ],
                }
            ],
        }
        local_start = scheduler.datetime.combine(
            shift_date, scheduler.time(7), tzinfo=scheduler.ATTENDANCE_TIMEZONE
        )
        bamboo_shift = {
            "id": "bamboo-shift-111",
            "scheduleId": "bamboo-schedule-111",
            "status": "published",
            "start": local_start.astimezone(scheduler.timezone.utc).isoformat(),
            "end": (local_start + scheduler.timedelta(hours=8)).astimezone(
                scheduler.timezone.utc
            ).isoformat(),
            "timezone": "America/Jamaica",
            "employeeIds": ["111"],
            "employees": [
                {
                    "employeeId": "attendance-111",
                    "bamboohrId": "111",
                    "name": "Reconciliation employee",
                    "location": "Kingston",
                    "role": "Cashier",
                }
            ],
            "location": "Kingston",
            "scheduleName": "Kingston Cashiers",
        }
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO schedule_locations
                    (id, tenant_id, name, bamboo_schedule_id, location, role_group)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule_location_id,
                    scheduler.DEFAULT_TENANT_ID,
                    "Kingston Cashiers",
                    "bamboo-schedule-111",
                    "Kingston",
                    "Cashier",
                ),
            )
            connection.execute(
                """
                INSERT INTO employees
                    (employee_id, tenant_id, bamboohr_id, name, location, role,
                     active, schedule_location_id)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    "attendance-111",
                    scheduler.DEFAULT_TENANT_ID,
                    "111",
                    "Reconciliation employee",
                    "Kingston",
                    "Cashier",
                    schedule_location_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO accepted_schedules
                    (run_id, tenant_id, week_start, location, role, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule["id"],
                    scheduler.DEFAULT_TENANT_ID,
                    schedule["start"],
                    schedule["location"],
                    schedule["role"],
                    json.dumps(schedule),
                ),
            )
            connection.execute(
                """
                INSERT INTO application_settings (setting_key, setting_value, tenant_id)
                VALUES ('attendance_shift_source', 'bamboohr', ?)
                """,
                (scheduler.DEFAULT_TENANT_ID,),
            )
            connection.execute(
                """
                INSERT INTO employees
                    (employee_id, tenant_id, bamboohr_id, name, location, role,
                     active, source_type, bamboohr_active)
                VALUES (?, ?, ?, ?, ?, ?, 0, 'manual', 0)
                """,
                (
                    "manual-placeholder",
                    scheduler.DEFAULT_TENANT_ID,
                    "MANUAL-test-only-id",
                    "Manual Placeholder",
                    "Kingston",
                    "Cashier",
                ),
            )
        return shift_date, schedule, bamboo_shift

    @staticmethod
    def mocked_bamboo_response(status):
        class FakeResponse:
            def __init__(self, response_status):
                self.status = response_status

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, *_):
                return b""

        return FakeResponse(status)

    def test_bamboohr_shift_read_parses_and_paginates_contract(self):
        shift_date, _, bamboo_shift = self.seed_reconciliation_schedule()

        class JsonResponse:
            status = 200

            def __init__(self, value):
                self.value = json.dumps(value).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, *_):
                return self.value

        item = {
            "id": bamboo_shift["id"],
            "scheduleId": bamboo_shift["scheduleId"],
            "status": bamboo_shift["status"],
            "color": "2e7918",
            "start": bamboo_shift["start"].replace("+00:00", "Z"),
            "end": bamboo_shift["end"].replace("+00:00", "Z"),
            "timezone": bamboo_shift["timezone"],
            "employeeIds": [111],
            "deletedAt": None,
        }
        page_one = {
            "data": [item],
            "meta": {"totalItems": 1001, "page": 1, "pageSize": 1000},
        }
        page_two = {
            "data": [],
            "meta": {"totalItems": 1001, "page": 2, "pageSize": 1000},
        }
        calls_by_batch = {}

        def response_for(request, **_):
            query = parse_qs(urlsplit(request.full_url).query)
            employee_batch = query["employeeIds"][0]
            page_number = int(query["page"][0])
            calls_by_batch.setdefault(employee_batch, []).append(page_number)
            if "111" not in employee_batch.split(","):
                return JsonResponse(
                    {
                        "data": [],
                        "meta": {"totalItems": 0, "page": page_number, "pageSize": 1000},
                    }
                )
            return JsonResponse(page_one if page_number == 1 else page_two)

        with patch.object(
            scheduler, "bamboohr_api_key", return_value="test-only-key"
        ), patch("scheduler.urlopen", side_effect=response_for) as open_url:
            with closing(scheduler.database_connect()) as connection:
                connection.execute(
                    """
                    INSERT INTO employees
                        (employee_id, tenant_id, bamboohr_id, name, location, role, active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        "attendance-112",
                        scheduler.DEFAULT_TENANT_ID,
                        "112",
                        "Second Bamboo employee",
                        "Kingston",
                        "Cashier",
                    ),
                )
                shifts = scheduler.fetch_bamboohr_scheduled_shifts(
                    connection, shift_date, shift_date
                )
        target_batch = next(
            batch for batch in calls_by_batch if "111" in batch.split(",")
        )
        self.assertEqual(calls_by_batch[target_batch], [1, 2])
        first_query = next(
            parse_qs(urlsplit(call.args[0].full_url).query)
            for call in open_url.call_args_list
            if "111" in parse_qs(urlsplit(call.args[0].full_url).query)["employeeIds"][0].split(",")
        )
        self.assertEqual(first_query["statuses"], ["planned,published"])
        self.assertEqual(first_query["page"], ["1"])
        queried_employee_ids = first_query["employeeIds"][0].split(",")
        self.assertIn("111", queried_employee_ids)
        self.assertIn("112", queried_employee_ids)
        self.assertTrue(all(employee_id.isdigit() for employee_id in queried_employee_ids))
        first_url = next(
            call.args[0].full_url
            for call in open_url.call_args_list
            if "111" in parse_qs(urlsplit(call.args[0].full_url).query)["employeeIds"][0].split(",")
        )
        self.assertRegex(first_url, r"employeeIds=[0-9,]+")
        self.assertIn("statuses=planned,published", first_url)
        self.assertNotIn("%2C", first_url)
        start_datetime = scheduler.datetime.combine(
            shift_date, scheduler.time.min, tzinfo=scheduler.ATTENDANCE_TIMEZONE
        ).astimezone(scheduler.timezone.utc)
        end_datetime = scheduler.datetime.combine(
            shift_date, scheduler.time(23, 59, 59), tzinfo=scheduler.ATTENDANCE_TIMEZONE
        ).astimezone(scheduler.timezone.utc)
        self.assertEqual(
            first_query["start"],
            [start_datetime.isoformat().replace("+00:00", "Z")],
        )
        self.assertEqual(
            first_query["end"],
            [end_datetime.isoformat().replace("+00:00", "Z")],
        )
        self.assertNotIn(".", first_query["end"][0])
        self.assertEqual(shifts[0]["id"], "bamboo-shift-111")
        self.assertEqual(shifts[0]["employees"][0]["employeeId"], "attendance-111")

    def discrepancy_id(self, shift_date, bamboo_shift):
        with closing(scheduler.database_connect()) as connection:
            discrepancies = scheduler.attendance_shift_discrepancies(
                connection, shift_date, shift_date, [bamboo_shift]
            )
        self.assertEqual(len(discrepancies), 1)
        return discrepancies[0]["id"]

    def test_reconciliation_adds_then_deletes_and_audits(self):
        shift_date, _, bamboo_shift = self.seed_reconciliation_schedule()
        discrepancy_id = self.discrepancy_id(shift_date, bamboo_shift)
        with patch.object(
            scheduler, "fetch_bamboohr_scheduled_shifts", return_value=[bamboo_shift]
        ), patch.object(
            scheduler, "bamboohr_api_key", return_value="test-only-key"
        ), patch(
            "scheduler.urlopen",
            side_effect=[
                self.mocked_bamboo_response(201),
                self.mocked_bamboo_response(204),
            ],
        ) as open_url:
            response = self.client.post(
                "/api/attendance/reconciliation/resolve",
                headers={"X-CSRF-Token": "test-csrf-token"},
                json={
                    "confirmed": True,
                    "discrepancyId": discrepancy_id,
                    "direction": "app_to_bamboohr",
                    "date": shift_date.isoformat(),
                    "reason": "Align BambooHR to the accepted schedule",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(
            [call.args[0].method for call in open_url.call_args_list], ["POST", "DELETE"]
        )
        self.assertIn(
            "recurrenceEditOption=instance",
            open_url.call_args_list[1].args[0].full_url,
        )
        audit = self.query(
            "SELECT direction, reason, before_json, after_json, outcome "
            "FROM attendance_reconciliation_audit_events"
        )
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0][0], "app_to_bamboohr")
        self.assertEqual(audit[0][1], "Align BambooHR to the accepted schedule")
        self.assertEqual(audit[0][4], "succeeded")

    def test_reconciliation_rejects_unconfirmed_stale_and_shared_shifts(self):
        shift_date, _, bamboo_shift = self.seed_reconciliation_schedule()
        discrepancy_id = self.discrepancy_id(shift_date, bamboo_shift)
        endpoint = "/api/attendance/reconciliation/resolve"
        headers = {"X-CSRF-Token": "test-csrf-token"}
        request_payload = {
            "confirmed": True,
            "discrepancyId": discrepancy_id,
            "direction": "app_to_bamboohr",
            "date": shift_date.isoformat(),
            "reason": "Test safety checks",
        }
        shared = bamboo_shift | {"employeeIds": ["111", "222"]}
        with patch.object(
            scheduler,
            "fetch_bamboohr_scheduled_shifts",
            side_effect=[[bamboo_shift], [shared]],
        ), patch("scheduler.urlopen") as open_url:
            unconfirmed = self.client.post(
                endpoint, headers=headers, json=request_payload | {"confirmed": False}
            )
            stale = self.client.post(
                endpoint,
                headers=headers,
                json=request_payload | {"discrepancyId": "f" * 24},
            )
            unsafe = self.client.post(
                endpoint,
                headers=headers,
                json=request_payload,
            )
        self.assertEqual(unconfirmed.status_code, 400)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(unsafe.status_code, 409)
        open_url.assert_not_called()

    def test_reconciliation_reports_partial_bamboohr_replacement(self):
        shift_date, _, bamboo_shift = self.seed_reconciliation_schedule()
        discrepancy_id = self.discrepancy_id(shift_date, bamboo_shift)
        with patch.object(
            scheduler, "fetch_bamboohr_scheduled_shifts", return_value=[bamboo_shift]
        ), patch.object(
            scheduler, "bamboohr_api_key", return_value="test-only-key"
        ), patch(
            "scheduler.urlopen",
            side_effect=[
                self.mocked_bamboo_response(201),
                self.mocked_bamboo_response(409),
            ],
        ):
            response = self.client.post(
                "/api/attendance/reconciliation/resolve",
                headers={"X-CSRF-Token": "test-csrf-token"},
                json={
                    "confirmed": True,
                    "discrepancyId": discrepancy_id,
                    "direction": "app_to_bamboohr",
                    "date": shift_date.isoformat(),
                    "reason": "Test partial outcome",
                },
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["outcome"], "partial")
        self.assertIn("delete: 409", response.get_json()["error"])
        self.assertEqual(
            self.query(
                "SELECT outcome FROM attendance_reconciliation_audit_events"
            ),
            [("partial",)],
        )

    def test_reconciliation_does_not_delete_when_add_fails(self):
        shift_date, _, bamboo_shift = self.seed_reconciliation_schedule()
        discrepancy_id = self.discrepancy_id(shift_date, bamboo_shift)
        with patch.object(
            scheduler, "fetch_bamboohr_scheduled_shifts", return_value=[bamboo_shift]
        ), patch.object(
            scheduler, "bamboohr_api_key", return_value="test-only-key"
        ), patch(
            "scheduler.urlopen",
            return_value=self.mocked_bamboo_response(409),
        ) as open_url:
            response = self.client.post(
                "/api/attendance/reconciliation/resolve",
                headers={"X-CSRF-Token": "test-csrf-token"},
                json={
                    "confirmed": True,
                    "discrepancyId": discrepancy_id,
                    "direction": "app_to_bamboohr",
                    "date": shift_date.isoformat(),
                    "reason": "Preserve the current shift after add rejection",
                },
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["outcome"], "failed")
        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(open_url.call_args.args[0].method, "POST")
        self.assertEqual(
            self.query(
                "SELECT outcome FROM attendance_reconciliation_audit_events"
            ),
            [("failed",)],
        )

    def test_bamboohr_to_app_records_full_schedule_history(self):
        shift_date, original_schedule, bamboo_shift = self.seed_reconciliation_schedule()
        discrepancy_id = self.discrepancy_id(shift_date, bamboo_shift)
        with patch.object(
            scheduler, "fetch_bamboohr_scheduled_shifts", return_value=[bamboo_shift]
        ):
            response = self.client.post(
                "/api/attendance/reconciliation/resolve",
                headers={"X-CSRF-Token": "test-csrf-token"},
                json={
                    "confirmed": True,
                    "discrepancyId": discrepancy_id,
                    "direction": "bamboohr_to_app",
                    "date": shift_date.isoformat(),
                    "reason": "Use confirmed BambooHR timing",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        audit = self.query(
            "SELECT before_json, after_json, outcome "
            "FROM attendance_reconciliation_audit_events"
        )[0]
        before, after = json.loads(audit[0]), json.loads(audit[1])
        self.assertEqual(before["acceptedSchedule"], original_schedule)
        updated_schedule = json.loads(
            self.query(
                "SELECT payload FROM accepted_schedules WHERE run_id = ?",
                ("reconciliation-run",),
            )[0][0]
        )
        self.assertEqual(updated_schedule["employees"][0]["slots"][shift_date.weekday()], 7)
        self.assertEqual(after["acceptedSchedule"], updated_schedule)
        self.assertEqual(audit[2], "succeeded")

    def seed_attendance_schedule(self):
        employees = (
            ("attendance-111", "111", "Clocked employee"),
            ("attendance-222", "222", "On leave employee"),
            ("attendance-333", "333", "Absent employee"),
        )
        shifts = [
            {
                "id": employee_id,
                "name": name,
                "bamboohrId": bamboohr_id,
                "location": "Kingston",
                "role": "Cashier",
                "slots": [6, None, None, None, None, None, None],
            }
            for employee_id, bamboohr_id, name in employees
        ]
        schedule = {
            "id": "attendance-run",
            "start": "2026-11-02",
            "end": "2026-11-08",
            "location": "Kingston",
            "role": "Cashier",
            "controls": {"span": 8, "hours": 8},
            "employees": shifts,
        }
        with closing(scheduler.database_connect()) as connection, connection:
            for employee_id, bamboohr_id, name in employees:
                connection.execute(
                    """
                    INSERT INTO employees
                        (employee_id, tenant_id, bamboohr_id, name, location, role, active)
                    VALUES (?, ?, ?, ?, 'Kingston', 'Cashier', 1)
                    """,
                    (
                        employee_id,
                        scheduler.DEFAULT_TENANT_ID,
                        bamboohr_id,
                        name,
                    ),
                )
            connection.execute(
                """
                INSERT INTO accepted_schedules
                    (run_id, tenant_id, week_start, location, role, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule["id"],
                    scheduler.DEFAULT_TENANT_ID,
                    schedule["start"],
                    schedule["location"],
                    schedule["role"],
                    json.dumps(schedule),
                ),
            )
        return [
            {
                "id": "7685",
                "bamboohrId": "111",
                "date": "2026-11-02",
                "start": "2026-11-02T11:20:00+00:00",
                "end": "2026-11-02T13:20:00+00:00",
                "timezone": "America/Jamaica",
                "approved": False,
            }
        ], [
            {
                "bamboohrId": "222",
                "start": "2026-11-02",
                "end": "2026-11-02",
            }
        ]

    def test_clock_entry_parser_uses_clock_starts_without_approval(self):
        parsed = scheduler.parse_bamboohr_clock_entries(
            [
                {
                    "id": 7685,
                    "employeeId": 111,
                    "type": "clock",
                    "date": "2026-11-02",
                    "start": "2026-11-02T05:00:00+00:00",
                    "end": "2026-11-02T11:10:00+00:00",
                    "timezone": "America/Bogota",
                    "hours": 6.1667,
                    "approved": False,
                },
                {
                    "id": 9,
                    "employeeId": 111,
                    "type": "hour",
                    "date": "2026-11-02",
                },
            ]
        )
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["id"], "7685")
        self.assertEqual(parsed[0]["bamboohrId"], "111")
        self.assertFalse(parsed[0]["approved"])
        with self.assertRaises(scheduler.AttendanceIntegrationError):
            scheduler.parse_bamboohr_clock_entries(
                [
                    {
                        "id": 10,
                        "employeeId": 111,
                        "type": "clock",
                        "date": "2026-11-02",
                        "start": "2026-11-02T05:00:00",
                        "end": None,
                        "timezone": "America/Jamaica",
                    }
                ]
            )

    def test_sync_classifies_late_absent_and_approved_leave_idempotently(self):
        clock_entries, time_off = self.seed_attendance_schedule()
        now = scheduler.datetime(2026, 11, 2, 12, 1, tzinfo=scheduler.ATTENDANCE_TIMEZONE)

        class CapturingConnection:
            def __init__(self, connection):
                self.connection = connection
                self.batch_parameters = None

            def __getattr__(self, name):
                return getattr(self.connection, name)

            def executemany(self, query, parameters):
                self.batch_parameters = list(parameters)
                return self.connection.executemany(query, self.batch_parameters)

        with closing(scheduler.database_connect()) as connection, connection:
            capturing_connection = CapturingConnection(connection)
            result = scheduler.sync_attendance_data(
                capturing_connection, clock_entries, time_off, now=now
            )
            self.assertIs(type(capturing_connection.batch_parameters[0][-1]), int)
            self.assertEqual(capturing_connection.batch_parameters[0][-1], 0)
        statuses = {
            item["employeeId"]: item["status"] for item in result["shifts"]
        }
        self.assertEqual(
            statuses,
            {
                "attendance-111": "late",
                "attendance-222": "approved_leave",
                "attendance-333": "absent",
            },
        )
        self.assertEqual(result["summary"]["expected"], 2)
        self.assertEqual(result["summary"]["clockedIn"], 1)
        self.assertEqual(result["summary"]["attendancePercent"], 50)
        self.assertEqual(result["summary"]["late"], 1)
        self.assertEqual(result["summary"]["absent"], 1)
        self.assertEqual(result["summary"]["approvedLeave"], 1)
        scores = {item["employeeId"]: item for item in result["scores"]}
        self.assertEqual(scores["attendance-111"]["score"], 100)
        self.assertIsNone(scores["attendance-222"]["score"])
        self.assertEqual(scores["attendance-333"]["score"], 0)
        self.assertEqual(result["classifiedChanges"], 3)

        with closing(scheduler.database_connect()) as connection, connection:
            repeated = scheduler.sync_attendance_data(
                connection, clock_entries, time_off, now=now
            )
            audit_count = connection.execute(
                "SELECT COUNT(*) FROM attendance_shift_audit_events"
            ).fetchone()[0]
        self.assertEqual(repeated["classifiedChanges"], 0)
        self.assertEqual(audit_count, 3)

    @staticmethod
    def clock_action_entry(entry_id, bamboohr_id, start, end=None):
        return {
            "id": entry_id, "employeeId": bamboohr_id, "type": "clock",
            "date": "2026-11-02", "start": start, "end": end,
            "timezone": "America/Jamaica", "approved": False,
        }

    @staticmethod
    def fixed_attendance_time(hour, minute):
        base_datetime = scheduler.datetime

        class FixedDateTime(base_datetime):
            @classmethod
            def now(cls, tz=None):
                fixed = base_datetime(2026, 11, 2, hour, minute, tzinfo=scheduler.ATTENDANCE_TIMEZONE)
                return fixed if tz is None else fixed.astimezone(tz)

        return patch.object(scheduler, "datetime", FixedDateTime)

    def test_clock_in_uses_mapped_employee_and_verifies_bamboohr_result(self):
        existing, time_off = self.seed_attendance_schedule()
        existing[0] = existing[0] | {"end": None}
        now = scheduler.datetime(2026, 11, 2, 12, 1, tzinfo=scheduler.ATTENDANCE_TIMEZONE)
        with patch.object(scheduler, "bamboohr_api_key", return_value="test-key"), \
             closing(scheduler.database_connect()) as connection, connection:
            before = scheduler.sync_attendance_data(connection, existing, time_off, now=now)
        before_rows = {row["employeeId"]: row for row in before["shifts"]}
        self.assertTrue(before_rows["attendance-333"]["canClockIn"])
        self.assertFalse(before_rows["attendance-111"]["canClockIn"])
        self.assertEqual(before_rows["attendance-333"]["shiftEndAt"], "2026-11-02T14:00:00-05:00")
        opened = self.clock_action_entry("new-clock", "333", "2026-11-02T17:01:00+00:00")
        raw_existing = self.clock_action_entry("7685", "111", "2026-11-02T11:20:00+00:00")
        clock_reads = [[], [opened], [raw_existing, opened], []]
        body = {"action":"clock_in", "requestId":"00000000-0000-4000-8000-000000000001",
                "runId":"attendance-run", "employeeId":"attendance-333", "date":"2026-11-02",
                "reason":"Manager verified start time."}
        with self.fixed_attendance_time(12, 1), \
             patch.object(scheduler, "bamboohr_api_key", return_value="test-key"), \
             patch.object(scheduler, "bamboohr_json", side_effect=clock_reads), \
             patch.object(scheduler, "bamboo_shift_request", return_value={"success":True,"status":201}) as write:
            response = self.client.post("/api/attendance/clock-events",
                                        headers={"X-CSRF-Token":"test-csrf-token"}, json=body)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["outcome"], "succeeded")
        self.assertEqual(write.call_args.args[1:4], (
            "POST", "time_tracking/employees/333/clock_in", {"date":"2026-11-02","start":"12:01"},
        ))
        updated = {row["employeeId"]:row for row in response.get_json()["attendance"]["shifts"]}
        self.assertEqual(updated["attendance-333"]["clockIn"], opened["start"])
        self.assertTrue(updated["attendance-333"]["canClockOut"])
        audit = self.query("SELECT action,outcome,reason,requested_date,requested_time,after_json FROM attendance_clock_action_audit_events")
        self.assertEqual((audit[0][0],audit[0][1],audit[0][2],audit[0][3],audit[0][4]),
                         ("clock_in","succeeded","Manager verified start time.","2026-11-02","12:01"))
        self.assertEqual(json.loads(audit[0][5])["id"], "new-clock")

    def test_clock_out_at_shift_end_waits_until_end_and_uses_that_shift_time(self):
        opened = self.clock_action_entry("open-clock", "111", "2026-11-02T11:20:00+00:00")
        closed = opened | {"end":"2026-11-02T19:00:00+00:00"}
        _, time_off = self.seed_attendance_schedule()
        body = {"action":"clock_out_shift_end", "requestId":"00000000-0000-4000-8000-000000000002",
                "runId":"attendance-run", "employeeId":"attendance-111", "date":"2026-11-02",
                "reason":"Manager confirmed the scheduled shift ended."}
        parsed_opened=scheduler.parse_bamboohr_clock_entries([opened])
        with patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             closing(scheduler.database_connect()) as connection, connection:
            scheduler.sync_attendance_data(connection,parsed_opened,time_off,
                now=scheduler.datetime(2026,11,2,13,59,tzinfo=scheduler.ATTENDANCE_TIMEZONE))
        with self.fixed_attendance_time(13,59), patch.object(scheduler,"bamboohr_api_key",return_value="test-key"):
            row=next(item for item in self.client.get("/api/attendance?date=2026-11-02").get_json()["shifts"]
                 if item["employeeId"]=="attendance-111")
        self.assertTrue(row["canClockOut"])
        self.assertFalse(row["canClockOutAtShiftEnd"])
        reads=[ [opened], [closed], [closed], [] ]
        with self.fixed_attendance_time(13,59), \
             patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             patch.object(scheduler,"bamboohr_json",side_effect=reads), \
             patch.object(scheduler,"bamboo_shift_request") as write:
            too_early=self.client.post("/api/attendance/clock-events",
                headers={"X-CSRF-Token":"test-csrf-token"},json=body)
            self.assertEqual(too_early.status_code,409)
            self.assertIn("after the scheduled shift end",too_early.get_json()["error"])
            write.assert_not_called()
            with self.fixed_attendance_time(14,1):
                response=self.client.post("/api/attendance/clock-events",
                    headers={"X-CSRF-Token":"test-csrf-token"},json=body | {
                        "requestId":"00000000-0000-4000-8000-000000000003"})
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(write.call_args.args[1:4],(
            "POST","time_tracking/employees/111/clock_out",{"date":"2026-11-02","end":"14:00"}))
        row=next(item for item in response.get_json()["attendance"]["shifts"] if item["employeeId"]=="attendance-111")
        self.assertEqual(row["clockOut"],closed["end"])
        audits=self.query("SELECT outcome,requested_date,requested_time FROM attendance_clock_action_audit_events ORDER BY created_at")
        self.assertEqual(audits,[ ("succeeded","2026-11-02","14:00") ])

    def test_clock_out_now_uses_current_jamaica_date_and_time(self):
        opened=self.clock_action_entry("open-clock","111","2026-11-02T11:20:00+00:00")
        closed=opened | {"end":"2026-11-02T18:30:00+00:00"}
        _,time_off=self.seed_attendance_schedule()
        with patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             closing(scheduler.database_connect()) as connection, connection:
            scheduler.sync_attendance_data(connection,
                scheduler.parse_bamboohr_clock_entries([opened]),time_off,
                now=scheduler.datetime(2026,11,2,13,59,tzinfo=scheduler.ATTENDANCE_TIMEZONE))
        body={"action":"clock_out","requestId":"00000000-0000-4000-8000-000000000005",
              "runId":"attendance-run","employeeId":"attendance-111","date":"2026-11-02",
              "reason":"Manager verified the employee left."}
        with self.fixed_attendance_time(13,30), \
             patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             patch.object(scheduler,"bamboohr_json",side_effect=[[opened],[closed],[closed],[]]), \
             patch.object(scheduler,"bamboo_shift_request",return_value={"success":True,"status":200}) as write:
            response=self.client.post("/api/attendance/clock-events",
                headers={"X-CSRF-Token":"test-csrf-token"},json=body)
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(write.call_args.args[1:4],(
            "POST","time_tracking/employees/111/clock_out",{"date":"2026-11-02","end":"13:30"}))

    def test_clock_out_rejects_an_open_entry_from_a_prior_shift(self):
        stale_entry=self.clock_action_entry("stale-clock","111","2026-11-01T11:20:00+00:00")
        _,time_off=self.seed_attendance_schedule()
        with patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             closing(scheduler.database_connect()) as connection, connection:
            scheduler.sync_attendance_data(connection,[],time_off,
                now=scheduler.datetime(2026,11,2,14,1,tzinfo=scheduler.ATTENDANCE_TIMEZONE))
        body={"action":"clock_out","requestId":"00000000-0000-4000-8000-000000000008",
              "runId":"attendance-run","employeeId":"attendance-111","date":"2026-11-02",
              "reason":"Reject a stale clock from another shift."}
        with self.fixed_attendance_time(14,1), \
             patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             patch.object(scheduler,"bamboohr_json",return_value=[stale_entry]), \
             patch.object(scheduler,"bamboo_shift_request") as write:
            response=self.client.post("/api/attendance/clock-events",
                headers={"X-CSRF-Token":"test-csrf-token"},json=body)
        self.assertEqual(response.status_code,409)
        self.assertIn("exactly one open BambooHR clock entry for this shift",response.get_json()["error"])
        write.assert_not_called()

    def test_unknown_clock_write_stays_locked_until_reconciled(self):
        opened=self.clock_action_entry("open-clock","111","2026-11-02T11:20:00+00:00")
        _,time_off=self.seed_attendance_schedule()
        with patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             closing(scheduler.database_connect()) as connection, connection:
            scheduler.sync_attendance_data(connection,
                scheduler.parse_bamboohr_clock_entries([opened]),time_off,
                now=scheduler.datetime(2026,11,2,14,1,tzinfo=scheduler.ATTENDANCE_TIMEZONE))
        body={"action":"clock_out","requestId":"00000000-0000-4000-8000-000000000006",
              "runId":"attendance-run","employeeId":"attendance-111","date":"2026-11-02",
              "reason":"Unknown outcome protection test."}
        with self.fixed_attendance_time(14,1), \
             patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             patch.object(scheduler,"bamboohr_json",return_value=[opened]), \
             patch.object(scheduler,"bamboo_shift_request",return_value={"success":False,"status":None,"outcome":"unknown"}) as write:
            first=self.client.post("/api/attendance/clock-events",
                headers={"X-CSRF-Token":"test-csrf-token"},json=body)
            self.assertEqual(first.status_code,502)
            self.assertEqual(first.get_json()["outcome"],"unknown")
            second=self.client.post("/api/attendance/clock-events",
                headers={"X-CSRF-Token":"test-csrf-token"},json=body | {
                    "requestId":"00000000-0000-4000-8000-000000000007"})
            self.assertEqual(second.status_code,409)
            self.assertIn("unresolved",second.get_json()["error"])
            write.assert_called_once()
        with self.fixed_attendance_time(13,59), patch.object(scheduler,"bamboohr_api_key",return_value="test-key"):
            row=next(item for item in self.client.get("/api/attendance?date=2026-11-02").get_json()["shifts"]
                     if item["employeeId"]=="attendance-111")
        self.assertFalse(row["canClockOut"])
        self.assertIn("unresolved",row["clockActionUnavailableReason"])

    def test_clock_actions_require_csrf_reject_duplicate_clocks_and_block_manager_api(self):
        opened=self.clock_action_entry("open-clock","111","2026-11-02T11:20:00+00:00")
        _,time_off=self.seed_attendance_schedule()
        parsed_opened=scheduler.parse_bamboohr_clock_entries([opened])
        with patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             closing(scheduler.database_connect()) as connection, connection:
            scheduler.sync_attendance_data(connection,parsed_opened,time_off,
                now=scheduler.datetime(2026,11,2,12,1,tzinfo=scheduler.ATTENDANCE_TIMEZONE))
        body={"action":"clock_in","requestId":"00000000-0000-4000-8000-000000000004",
              "runId":"attendance-run","employeeId":"attendance-111","date":"2026-11-02",
              "reason":"Duplicate protection test."}
        with self.fixed_attendance_time(12,1), \
             patch.object(scheduler,"bamboohr_api_key",return_value="test-key"), \
             patch.object(scheduler,"bamboohr_json",return_value=[opened]), \
             patch.object(scheduler,"bamboo_shift_request") as write:
            self.assertEqual(self.client.post("/api/attendance/clock-events",json=body).status_code,400)
            response=self.client.post("/api/attendance/clock-events",headers={"X-CSRF-Token":"test-csrf-token"},json=body)
            self.assertEqual(response.status_code,409)
            self.assertIn("already has an open",response.get_json()["error"])
            employee=scheduler.app.test_client()
            self.assertEqual(employee.post("/api/attendance/clock-events",json=body).status_code,401)
            write.assert_not_called()

    def test_timesheet_must_cover_an_hour_and_flags_early_leave_and_overtime(self):
        self.seed_attendance_schedule()
        now = scheduler.datetime(2026, 11, 2, 16, 0, tzinfo=scheduler.ATTENDANCE_TIMEZONE)

        def entry(entry_id, bamboohr_id, start_hour, end_hour):
            return {
                "id": entry_id, "bamboohrId": bamboohr_id, "date": "2026-11-02",
                "start": f"2026-11-02T{start_hour}:00+00:00",
                "end": f"2026-11-02T{end_hour}:00+00:00",
                "timezone": "America/Jamaica", "approved": False,
            }

        clock_entries = [
            entry("1", "111", "11:00", "11:30"),
            entry("2", "222", "11:00", "17:00"),
            entry("3", "333", "11:00", "20:30"),
        ]
        with closing(scheduler.database_connect()) as connection, connection:
            scheduler.sync_attendance_data(connection, clock_entries, [], now=now)
            rows = {
                row[0]: row[1:]
                for row in connection.execute(
                    """
                    SELECT employee_id, status, worked_minutes, early_minutes,
                           overtime_minutes, reason
                    FROM attendance_shift_records
                    """
                ).fetchall()
            }
            notifications = connection.execute(
                "SELECT employee_id, kind FROM attendance_notifications"
            ).fetchall()
        self.assertEqual(rows["attendance-111"][0], "absent")
        self.assertEqual(rows["attendance-111"][1], 30)
        self.assertIn("at least 60", rows["attendance-111"][4])
        self.assertEqual(rows["attendance-222"][:4], ("attended", 360, 120, 0))
        self.assertIn("Left 120 minutes", rows["attendance-222"][4])
        self.assertEqual(rows["attendance-333"][:4], ("attended", 480, 0, 90))
        self.assertIn(("attendance-222", "early_leave"), notifications)
        self.assertNotIn(("attendance-333", "early_leave"), notifications)

    def test_overnight_overlap_under_an_hour_does_not_count_for_next_shift(self):
        zone = scheduler.ATTENDANCE_TIMEZONE
        start = scheduler.datetime(2026, 11, 3, 0, 0, tzinfo=zone)
        end = start + scheduler.timedelta(hours=8)
        previous_night = {
            "start": "2026-11-02T16:00:00-05:00",
            "end": "2026-11-03T00:40:00-05:00",
        }
        now = end + scheduler.timedelta(hours=1)
        result = scheduler.evaluate_shift_timesheet([previous_night], start, end, now)
        self.assertFalse(result["qualifies"])
        self.assertEqual(result["workedMinutes"], 40)
        long_overlap = {**previous_night, "end": "2026-11-03T01:30:00-05:00"}
        self.assertTrue(
            scheduler.evaluate_shift_timesheet([long_overlap], start, end, now)["qualifies"]
        )

    def test_attendance_api_returns_historical_day_and_rejects_future_dates(self):
        base_datetime = scheduler.datetime

        class FixedDateTime(base_datetime):
            @classmethod
            def now(cls, tz=None):
                fixed = base_datetime(
                    2026, 11, 3, 12, 1, tzinfo=scheduler.ATTENDANCE_TIMEZONE
                )
                return fixed if tz is None else fixed.astimezone(tz)

        with patch.object(scheduler, "datetime", FixedDateTime):
            clock_entries, time_off = self.seed_attendance_schedule()
            with closing(scheduler.database_connect()) as connection, connection:
                scheduler.sync_attendance_data(
                    connection,
                    clock_entries,
                    time_off,
                    now=base_datetime(
                        2026, 11, 2, 12, 1, tzinfo=scheduler.ATTENDANCE_TIMEZONE
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO attendance_shift_records
                        (tenant_id, schedule_run_id, employee_id, shift_date,
                         shift_start, status, source, employee_name, location, role)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scheduler.DEFAULT_TENANT_ID,
                        "attendance-october-run",
                        "attendance-111",
                        "2026-10-12",
                        9,
                        "attended",
                        "manual",
                        "Clocked employee",
                        "Kingston",
                        "Cashier",
                    ),
                )

            response = self.client.get("/api/attendance?date=2026-11-02")
            self.assertEqual(response.status_code, 200)
            attendance = response.get_json()
            self.assertEqual(attendance["date"], "2026-11-02")
            self.assertEqual(attendance["currentDate"], "2026-11-03")
            self.assertEqual(attendance["summary"]["expected"], 2)
            self.assertEqual(attendance["summary"]["clockedIn"], 1)
            self.assertEqual(len(attendance["shifts"]), 3)

            self.assertEqual(
                self.client.get("/api/attendance?date=not-a-date").status_code,
                400,
            )
            self.assertEqual(
                self.client.get("/api/attendance?date=2026-11-04").status_code,
                400,
            )

            period = self.client.get(
                "/api/attendance?start=2026-10-01&end=2026-11-02"
            )
            self.assertEqual(period.status_code, 200)
            report = period.get_json()
            self.assertEqual(report["date"], None)
            self.assertEqual(report["periodStart"], "2026-10-01")
            self.assertEqual(report["periodEnd"], "2026-11-02")
            self.assertEqual(len(report["shifts"]), 4)
            self.assertEqual(report["summary"]["expected"], 3)
            self.assertEqual(report["summary"]["clockedIn"], 2)
            self.assertAlmostEqual(report["summary"]["attendancePercent"], 66.67)
            clocked_score = next(
                item for item in report["scores"]
                if item["employeeId"] == "attendance-111"
            )
            self.assertEqual(clocked_score["scheduled"], 2)
            self.assertEqual(
                self.client.get("/api/attendance?start=2026-11-01").status_code,
                400,
            )
            self.assertEqual(
                self.client.get(
                    "/api/attendance?start=2026-11-02&end=2026-11-01"
                ).status_code,
                400,
            )
            self.assertEqual(
                self.client.get(
                    "/api/attendance?start=2026-11-03&end=2026-11-04"
                ).status_code,
                400,
            )
            with patch.object(scheduler, "bamboohr_api_key", return_value="test-key"):
                too_long_sync = self.client.post(
                    "/api/attendance/sync",
                    headers={"X-CSRF-Token": "test-csrf-token"},
                    json={"start": "2025-11-04", "end": "2026-11-03"},
                )
            self.assertEqual(too_long_sync.status_code, 400)

    def test_admin_shift_correction_and_score_override_are_audited(self):
        base_datetime = scheduler.datetime

        class FixedDateTime(base_datetime):
            @classmethod
            def now(cls, tz=None):
                fixed = base_datetime(
                    2026, 11, 2, 12, 1, tzinfo=scheduler.ATTENDANCE_TIMEZONE
                )
                return fixed if tz is None else fixed.astimezone(tz)

        datetime_patcher = patch.object(scheduler, "datetime", FixedDateTime)
        datetime_patcher.start()
        self.addCleanup(datetime_patcher.stop)
        clock_entries, time_off = self.seed_attendance_schedule()
        now = scheduler.datetime(2026, 11, 2, 12, 1, tzinfo=scheduler.ATTENDANCE_TIMEZONE)
        with closing(scheduler.database_connect()) as connection, connection:
            scheduler.sync_attendance_data(
                connection, clock_entries, time_off, now=now
            )
        csrf = "test-csrf-token"
        corrected = self.client.post(
            "/api/attendance/shifts/override",
            headers={"X-CSRF-Token": csrf},
            json={
                "runId": "attendance-run",
                "employeeId": "attendance-333",
                "date": "2026-11-02",
                "status": "attended",
                "reason": "Verified with the manager.",
            },
        )
        self.assertEqual(corrected.status_code, 200)
        self.assertEqual(
            next(
                item["status"]
                for item in corrected.get_json()["attendance"]["shifts"]
                if item["employeeId"] == "attendance-333"
            ),
            "attended",
        )
        override = self.client.post(
            "/api/attendance/scores/attendance-333/override",
            headers={"X-CSRF-Token": csrf},
            json={"score": 75, "reason": "Approved attendance review."},
        )
        self.assertEqual(override.status_code, 200)
        employee_score = next(
            item
            for item in override.get_json()["attendance"]["scores"]
            if item["employeeId"] == "attendance-333"
        )
        self.assertEqual(employee_score["computedScore"], 100)
        self.assertEqual(employee_score["score"], 75)
        self.assertTrue(employee_score["manualOverride"])
        removed = self.client.delete(
            "/api/attendance/scores/attendance-333/override",
            headers={"X-CSRF-Token": csrf},
            json={"reason": "Removing temporary review override."},
        )
        self.assertEqual(removed.status_code, 200)
        employee_score = next(
            item
            for item in removed.get_json()["attendance"]["scores"]
            if item["employeeId"] == "attendance-333"
        )
        self.assertEqual(employee_score["score"], 100)
        self.assertFalse(employee_score["manualOverride"])
        with closing(scheduler.database_connect()) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM attendance_shift_audit_events"
                ).fetchone()[0],
                4,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM attendance_score_audit_events"
                ).fetchone()[0],
                2,
            )

    def test_attendance_settings_require_csrf_and_validate_bounds(self):
        invalid = self.client.put(
            "/api/attendance/settings",
            json={"latenessToleranceMinutes": 121, "scorePeriodDays": 30},
        )
        self.assertEqual(invalid.status_code, 400)
        saved = self.client.put(
            "/api/attendance/settings",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"latenessToleranceMinutes": 30, "scorePeriodDays": 45},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(
            saved.get_json()["settings"],
            {"latenessToleranceMinutes": 30, "scorePeriodDays": 45},
        )

    def test_attendance_sync_requests_bounded_time_tracking_and_time_off_ranges(self):
        today = scheduler.datetime.now(scheduler.ATTENDANCE_TIMEZONE).date()
        historical_start = today - scheduler.timedelta(days=60)
        with (
            patch.object(scheduler, "bamboohr_api_key", return_value="test-key"),
            patch.object(scheduler, "bamboohr_json", side_effect=[[], [], [], []]) as fetch,
        ):
            response = self.client.post(
                "/api/attendance/sync",
                headers={"X-CSRF-Token": "test-csrf-token"},
                json={},
            )
            historical = self.client.post(
                "/api/attendance/sync",
                headers={"X-CSRF-Token": "test-csrf-token"},
                json={"start": historical_start.isoformat(), "end": today.isoformat()},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(historical.status_code, 200)
        self.assertEqual(historical.get_json()["periodStart"], historical_start.isoformat())
        self.assertEqual(historical.get_json()["periodEnd"], today.isoformat())
        self.assertEqual(
            [call.args[1] for call in fetch.call_args_list],
            [
                "time_tracking/timesheet_entries",
                "time_off/whos_out",
                "time_tracking/timesheet_entries",
                "time_off/whos_out",
            ],
        )
        ranges = [call.args[2] for call in fetch.call_args_list]
        self.assertEqual(ranges[0], ranges[1])
        self.assertLessEqual(
            (
                scheduler.date.fromisoformat(ranges[0]["end"])
                - scheduler.date.fromisoformat(ranges[0]["start"])
            ).days,
            365,
        )
        self.assertEqual(ranges[2]["start"], (historical_start - scheduler.timedelta(days=1)).isoformat())
        self.assertEqual(ranges[2]["end"], today.isoformat())

    def test_key_validation_requires_time_tracking_read_access(self):
        response = MagicMock()
        response.__enter__.return_value = response
        denied = HTTPError("https://acme.bamboohr.com", 403, "Forbidden", {}, None)
        with patch.object(
            scheduler,
            "urlopen",
            side_effect=[response, denied],
        ):
            failure = scheduler.check_bamboohr_credentials("acme", "test-key")
        self.assertEqual(failure[1], 403)
        self.assertIn("time-tracking", failure[0])


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

    def test_manual_clock_actions_are_pending_and_preserved_on_restart(self):
        request_id = "attendance-manual-clock-actions"
        definition = next(item for item in scheduler.DEVELOPER_REQUESTS if item[0] == request_id)
        with closing(scheduler.database_connect()) as connection:
            row = connection.execute(
                "SELECT title, description, status FROM developer_change_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            dependencies = connection.execute(
                "SELECT COUNT(*) FROM developer_change_request_dependencies WHERE request_id=?",
                (request_id,),
            ).fetchone()[0]
        self.assertEqual(row, (definition[1], definition[2], "pending"))
        self.assertEqual(dependencies, len(definition[3]))
        for requirement in ("Clock in", "Clock out", "Clock out at shift end",
                            "same open attendance entry", "overnight", "BambooHR",
                            "implementation pending"):
            self.assertIn(requirement, definition[2])
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE developer_change_requests SET status='blocked' WHERE request_id=?",
                (request_id,),
            )
        scheduler.initialize_database()
        with closing(scheduler.database_connect()) as connection:
            self.assertEqual(connection.execute(
                "SELECT status FROM developer_change_requests WHERE request_id=?", (request_id,),
            ).fetchall(), [("blocked",)])

    def test_snapshot_request_migration_preserves_status_and_completed_requests(self):
        definition = next(
            item for item in scheduler.DEVELOPER_REQUESTS
            if item[0] == "snapshot-email-reports"
        )
        for status in ("pending", "in_progress", "blocked", "done", "rejected"):
            with self.subTest(status=status):
                with closing(scheduler.database_connect()) as connection, connection:
                    connection.execute(
                        """
                        UPDATE developer_change_requests
                        SET title = 'Old title', description = 'Old description', status = ?
                        WHERE request_id = 'snapshot-email-reports'
                        """,
                        (status,),
                    )
                    connection.execute(
                        "DELETE FROM app_migrations WHERE migration_id = ?",
                        ("scheduled-attendance-snapshot-request-v1",),
                    )
                scheduler.initialize_database()
                scheduler.initialize_database()
                with closing(scheduler.database_connect()) as connection:
                    row = connection.execute(
                        """
                        SELECT title, description, status FROM developer_change_requests
                        WHERE request_id = 'snapshot-email-reports'
                        """
                    ).fetchone()
                expected = (
                    (definition[1], definition[2], status)
                    if status in {"pending", "in_progress", "blocked"}
                    else ("Old title", "Old description", status)
                )
                self.assertEqual(row, expected)
        for requirement in (
            "7 AM, 3 PM and 11 PM", "America/Jamaica", "upon authorised request",
            "XLSX", "HTML", "amber", "red", "freshness", "Microsoft Graph",
            "independent of an open browser tab",
        ):
            self.assertIn(requirement, definition[2])
        self.assertEqual(definition[3], ("workforce-dashboards",))

    def test_attendance_automation_migration_refreshes_only_active_request(self):
        definition = next(
            request
            for request in scheduler.DEVELOPER_REQUESTS
            if request[0] == "attendance-automation"
        )
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                UPDATE developer_change_requests
                SET title = 'Old attendance title', description = 'Old attendance text',
                    status = 'in_progress'
                WHERE request_id = 'attendance-automation'
                """
            )
            connection.execute(
                "DELETE FROM app_migrations WHERE migration_id = ?",
                ("attendance-automation-implementation-v1",),
            )
        scheduler.initialize_database()
        with closing(scheduler.database_connect()) as connection:
            active = connection.execute(
                """
                SELECT title, description, status FROM developer_change_requests
                WHERE request_id = 'attendance-automation'
                """
            ).fetchone()
        self.assertEqual(active, (definition[1], definition[2], "in_progress"))
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                UPDATE developer_change_requests SET
                    title = 'Completed title', description = 'Completed description',
                    status = 'done'
                WHERE request_id = 'attendance-automation'
                """
            )
            connection.execute(
                "DELETE FROM app_migrations WHERE migration_id = ?",
                ("attendance-automation-implementation-v1",),
            )
        scheduler.initialize_database()
        with closing(scheduler.database_connect()) as connection:
            done = connection.execute(
                """
                SELECT title, description, status FROM developer_change_requests
                WHERE request_id = 'attendance-automation'
                """
            ).fetchone()
        self.assertEqual(
            done,
            ("Completed title", "Completed description", "done"),
        )

    def test_unified_application_shell_is_recorded_pending_with_dependencies(self):
        definition = next(row for row in scheduler.DEVELOPER_REQUESTS
                          if row[0] == "unified-application-shell")
        with closing(scheduler.database_connect()) as connection:
            row = connection.execute(
                "SELECT title,description,status FROM developer_change_requests WHERE request_id=?",
                (definition[0],),
            ).fetchone()
            dependencies = connection.execute(
                "SELECT depends_on FROM developer_change_request_dependencies WHERE request_id=?",
                (definition[0],),
            ).fetchall()
        expected = definition[2] + "\n\nImplementation update: " + scheduler.WORKFORCE_IMPLEMENTATION_NOTES[definition[0]]
        self.assertEqual(row, (definition[1], expected, "pending"))
        self.assertEqual({item[0] for item in dependencies}, set(definition[3]))
        for requirement in ("site-navigation-alerts", "MFA", "server-side", "deep links",
                            "platform owners", "15-minute"):
            self.assertIn(requirement, row[1])

    def test_live_attendance_request_migration_refreshes_only_active_requests(self):
        definitions = {
            request[0]: request for request in scheduler.DEVELOPER_REQUESTS
        }
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                UPDATE developer_change_requests
                SET title = 'Old title', description = 'Old description',
                    status = CASE request_id
                        WHEN 'attendance-automation' THEN 'done'
                        WHEN 'manager-employee-access' THEN 'in_progress'
                        ELSE 'pending'
                    END
                WHERE request_id IN (
                    'manager-employee-access', 'schedule-portal',
                    'attendance-automation', 'workforce-dashboards'
                )
                """
            )
            connection.execute(
                "DELETE FROM app_migrations WHERE migration_id = ?",
                ("live-attendance-dashboard-requests-v1",),
            )
        scheduler.initialize_database()

        with closing(scheduler.database_connect()) as connection:
            refreshed = {
                row[0]: row[1:]
                for row in connection.execute(
                    """
                    SELECT request_id, title, description, status
                    FROM developer_change_requests
                    WHERE request_id IN (
                        'manager-employee-access', 'schedule-portal',
                        'attendance-automation', 'workforce-dashboards'
                    )
                    """
                )
            }
        for request_id in (
            "manager-employee-access",
            "schedule-portal",
            "workforce-dashboards",
        ):
            self.assertEqual(refreshed[request_id][0], definitions[request_id][1])
            self.assertEqual(refreshed[request_id][1], definitions[request_id][2])
            self.assertEqual(refreshed[request_id][2], "pending" if request_id != "manager-employee-access" else "in_progress")
        self.assertEqual(refreshed["attendance-automation"][0], "Old title")
        self.assertEqual(refreshed["attendance-automation"][1], "Old description")
        self.assertEqual(refreshed["attendance-automation"][2], "done")
        self.assertIn("four hours", definitions["manager-employee-access"][2])
        self.assertIn("All locations", definitions["workforce-dashboards"][2])
        self.assertIn("location × role team", definitions["schedule-portal"][2])

    def test_business_membership_controls_request_is_seeded_with_prerequisites(self):
        with closing(scheduler.database_connect()) as connection:
            request = connection.execute(
                """
                SELECT title, description, status
                FROM developer_change_requests
                WHERE request_id = ?
                """,
                ("business-membership-controls",),
            ).fetchone()
            dependencies = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT depends_on
                    FROM developer_change_request_dependencies
                    WHERE request_id = ?
                    """,
                    ("business-membership-controls",),
                )
            }

        self.assertIsNotNone(request)
        self.assertEqual(request[0], "Business admin membership controls")
        self.assertIn("main business admin", request[1])
        self.assertIn("pause membership", request[1])
        self.assertIn("cancel membership", request[1])
        self.assertIn("change the business membership tier", request[1])
        self.assertEqual(request[2], "pending")
        self.assertEqual(dependencies, {"business-hub", "tier-entitlements"})

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

    def test_change_request_listing_uses_stable_seed_order(self):
        self.setup_developer()
        listing = self.client.get("/api/developer/change-requests")
        self.assertEqual(listing.status_code, 200)
        request_ids = [item["id"] for item in listing.get_json()["requests"]]
        expected = [
            item[0]
            for item in scheduler.DEVELOPER_REQUESTS
            if item[0] != "developer-change-log"
        ] + ["developer-change-log"]
        self.assertEqual(request_ids, expected)

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


class ManagerEmployeeAccessTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.temporary_directory.name) / "access.sqlite3"
        scheduler.initialize_database()
        scheduler.app.config["TESTING"] = True
        self.admin = scheduler.app.test_client()
        authenticate_test_admin(self.admin)
        tenant = scheduler.DEFAULT_TENANT_ID
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET bamboohr_subdomain = 'acme', status = 'active', "
                "membership_status = 'active', membership_tier = 'silver' WHERE tenant_id = ?",
                (tenant,),
            )
            for location_id, name, manager in (
                ("loc1", "Kingston", "mgr@acme.example"),
                ("loc2", "Montego Bay", "other@acme.example"),
            ):
                connection.execute(
                    """
                    INSERT INTO schedule_locations
                        (id, tenant_id, name, bamboo_schedule_id, location, manager_email)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (location_id, tenant, name, "sched-" + location_id, name, manager),
                )
            for employee_id, name, location_id, location in (
                ("emp-a", "Ann Kingston", "loc1", "Kingston"),
                ("emp-b", "Bob Montego", "loc2", "Montego Bay"),
            ):
                connection.execute(
                    """
                    INSERT INTO employees
                        (employee_id, tenant_id, name, location, role, active,
                         schedule_location_id, source_type)
                    VALUES (?, ?, ?, ?, 'Cashier', 1, ?, 'manual')
                    """,
                    (employee_id, tenant, name, location, location_id),
                )
            for employee_id, name, location in (
                ("emp-a", "Ann Kingston", "Kingston"),
                ("emp-b", "Bob Montego", "Montego Bay"),
            ):
                scheduler.record_attendance_status(
                    connection, run_id="run-1", employee_id=employee_id,
                    shift_date="2026-11-02", shift_start=1.0, status="late",
                    source="attendance_rule", reason="", employee_name=name,
                    location=location, role="Cashier", clock_in_at=None,
                    clock_in_timezone="", existing={},
                )

    def tearDown(self):
        scheduler.DATABASE_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    def create_account(self, **fields):
        response = self.admin.post(
            "/api/access-accounts", headers={"X-CSRF-Token": "test-csrf-token"}, json=fields
        )
        return response

    def new_client(self):
        client = scheduler.app.test_client()
        self.csrf = {"X-CSRF-Token": client.get("/api/access/state").get_json()["csrfToken"]}
        return client

    def sign_in_manager(self, employee_id=None):
        fields = {"role": "manager", "displayName": "Mary Manager", "email": "mgr@acme.example"}
        if employee_id:
            fields["employeeId"] = employee_id
        created = self.create_account(**fields).get_json()
        client = self.new_client()
        credentials = {
            "bamboohrSubdomain": "acme", "identifier": "MGR@acme.example",
            "password": created["temporaryPassword"],
        }
        first = client.post("/api/access/login", headers=self.csrf, json=credentials)
        self.assertTrue(first.get_json()["passwordChangeRequired"])
        enrolling = client.post(
            "/api/access/login", headers=self.csrf,
            json=credentials | {"newPassword": "Manager-New-Password-2026!"},
        ).get_json()
        self.assertTrue(enrolling["mfaEnrollmentRequired"])
        self.csrf = {"X-CSRF-Token": enrolling["csrfToken"]}
        done = client.post(
            "/api/access/verify-mfa", headers=self.csrf,
            json={"code": scheduler.totp_value(enrolling["secret"], int(time.time() // 30))},
        )
        self.assertEqual(done.status_code, 200)
        self.csrf = {"X-CSRF-Token": done.get_json()["csrfToken"]}
        return client, enrolling["secret"], created

    def shared_roster_import_payload(self):
        tenant = scheduler.DEFAULT_TENANT_ID
        with closing(scheduler.database_connect()) as connection:
            rows = connection.execute(
                """
                SELECT employee_id, location, role
                FROM employees WHERE tenant_id = ? AND active = 1
                ORDER BY employee_id
                """,
                (tenant,),
            ).fetchall()
        pools = [
            {"location": location, "role": role, "starts": [8]}
            for location, role in sorted({(row[1], row[2]) for row in rows})
        ]
        employees = [
            {
                "employeeId": employee_id,
                "settings": {
                    "flex": "", "reason": "", "preferred": None,
                    "proximity": None, "random": None, "attendance": None,
                    "days": [None] * 7, "shiftAvailability": {"8": 0},
                },
            }
            for employee_id, _, _ in rows
        ]
        return {
            "tenantId": tenant, "locked": False, "pools": pools, "employees": employees,
        }

    def initialize_shared_roster(self):
        payload = self.shared_roster_import_payload()
        headers = {"X-CSRF-Token": "test-csrf-token"}
        preview = self.admin.post(
            "/api/roster-settings/import/preview", headers=headers, json=payload
        )
        self.assertEqual(preview.status_code, 200, preview.get_json())
        imported = self.admin.post(
            "/api/roster-settings/import",
            headers=headers,
            json=payload | {"confirmed": True},
        )
        self.assertEqual(imported.status_code, 201, imported.get_json())

    def shared_meta_import_payload(self, locked=False):
        open_days = [1, 1, 1, 1, 1, 0, 0]
        intensity = [0.2, 0.2, 0.2, 0.2, 0.2, 0, 0]
        return {
            "tenantId": scheduler.DEFAULT_TENANT_ID,
            "locked": locked,
            "locations": [
                {"name": "Kingston", "open": open_days, "intensity": intensity},
                {"name": "Montego Bay", "open": open_days, "intensity": intensity},
            ],
        }

    def initialize_shared_meta(self, locked=False):
        payload = self.shared_meta_import_payload(locked)
        headers = {"X-CSRF-Token": "test-csrf-token"}
        preview = self.admin.post(
            "/api/meta-settings/import/preview", headers=headers, json=payload
        )
        self.assertEqual(preview.status_code, 200, preview.get_json())
        imported = self.admin.post(
            "/api/meta-settings/import",
            headers=headers,
            json=payload | {"confirmed": True},
        )
        self.assertEqual(imported.status_code, 201, imported.get_json())

    def test_shared_roster_settings_enforce_manager_scope_and_field_permissions(self):
        self.initialize_shared_roster()
        manager, _, _ = self.sign_in_manager()
        response = manager.get("/api/access/roster-settings")
        self.assertEqual(response.status_code, 200, response.get_json())
        records = response.get_json()["employees"]
        self.assertEqual([record["employeeId"] for record in records], ["emp-a"])
        record = records[0]
        forbidden = manager.put(
            "/api/access/roster-settings",
            headers=self.csrf,
            json={
                "employeeId": "emp-a", "revision": record["revision"],
                "changes": {"random": 2},
            },
        )
        self.assertEqual(forbidden.status_code, 403)
        allowed = manager.put(
            "/api/access/roster-settings",
            headers=self.csrf,
            json={
                "employeeId": "emp-a", "revision": record["revision"],
                "changes": {"proximity": 2},
            },
        )
        self.assertEqual(allowed.status_code, 200, allowed.get_json())
        stale = manager.put(
            "/api/access/roster-settings",
            headers=self.csrf,
            json={
                "employeeId": "emp-a", "revision": record["revision"],
                "changes": {"proximity": 1},
            },
        )
        self.assertEqual(stale.status_code, 409)
        outside_scope = manager.put(
            "/api/access/roster-settings",
            headers=self.csrf,
            json={
                "employeeId": "emp-b", "revision": 1,
                "changes": {"proximity": 2},
            },
        )
        self.assertEqual(outside_scope.status_code, 403)
        with closing(scheduler.database_connect()) as connection:
            audit = connection.execute(
                """
                SELECT 1 FROM tenant_audit_events
                WHERE tenant_id = ? AND action = ?
                """,
                (scheduler.DEFAULT_TENANT_ID, "roster-settings-updated:emp-a:proximity"),
            ).fetchone()
        self.assertIsNotNone(audit)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE schedule_locations SET manager_email = 'other@acme.example' WHERE id = 'loc1'"
            )
        self.assertEqual(manager.get("/api/access/roster-settings").get_json()["employees"], [])
        revoked = manager.put(
            "/api/access/roster-settings",
            headers=self.csrf,
            json={
                "employeeId": "emp-a", "revision": allowed.get_json()["revision"],
                "changes": {"proximity": 3},
            },
        )
        self.assertEqual(revoked.status_code, 403)

    def test_initial_shared_roster_import_is_primary_only_and_never_overwrites(self):
        payload = self.shared_roster_import_payload()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO tenant_admins
                    (id, tenant_id, email, display_name, password_hash,
                     mfa_secret, mfa_enabled, active, auth_version, is_primary)
                SELECT 'secondary-admin', tenant_id, 'secondary@example.test',
                       display_name, password_hash, mfa_secret, 1, 1, 1, 0
                FROM tenant_admins WHERE id = 'test-admin'
                """
            )
        secondary = scheduler.app.test_client()
        with self.admin.session_transaction() as current:
            state = dict(current)
        state["tenant_admin_id"] = "secondary-admin"
        with secondary.session_transaction() as current:
            current.update(state)
        headers = {"X-CSRF-Token": "test-csrf-token"}
        self.assertEqual(
            secondary.post(
                "/api/roster-settings/import/preview", headers=headers, json=payload
            ).status_code,
            403,
        )
        preview = self.admin.post(
            "/api/roster-settings/import/preview", headers=headers, json=payload
        )
        self.assertEqual(preview.status_code, 200, preview.get_json())
        imported = self.admin.post(
            "/api/roster-settings/import",
            headers=headers,
            json=payload | {"confirmed": True},
        )
        self.assertEqual(imported.status_code, 201, imported.get_json())
        repeated = self.admin.post(
            "/api/roster-settings/import",
            headers=headers,
            json=payload | {"confirmed": True},
        )
        self.assertEqual(repeated.status_code, 409)

    def test_locking_shared_roster_rejects_manager_profile_updates(self):
        self.initialize_shared_roster()
        settings = self.admin.get("/api/roster-settings").get_json()
        locked = self.admin.put(
            "/api/roster-settings/configuration",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={
                "revision": settings["revision"], "locked": True,
                "pools": settings["pools"],
            },
        )
        self.assertEqual(locked.status_code, 200, locked.get_json())
        manager, _, _ = self.sign_in_manager()
        roster = manager.get("/api/access/roster-settings").get_json()
        self.assertTrue(roster["locked"])
        employee = roster["employees"][0]
        rejected = manager.put(
            "/api/access/roster-settings",
            headers=self.csrf,
            json={
                "employeeId": employee["employeeId"], "revision": employee["revision"],
                "changes": {"proximity": 2},
            },
        )
        self.assertEqual(rejected.status_code, 409)

    def test_manager_meta_is_location_wide_scoped_validated_audited_and_revisioned(self):
        self.initialize_shared_meta()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO schedule_locations
                    (id, tenant_id, name, bamboo_schedule_id, location, role_group, manager_email)
                VALUES ('loc1-other-role', ?, 'Kingston Other Role', 'sched-loc1-other',
                        'Kingston', 'Other role', 'other@acme.example')
                """,
                (scheduler.DEFAULT_TENANT_ID,),
            )
            connection.execute(
                """
                INSERT INTO accepted_schedules
                    (run_id, tenant_id, week_start, location, role, payload)
                VALUES ('meta-preserved-run', ?, '2026-11-02', 'Kingston', 'Cashier', '{}')
                """,
                (scheduler.DEFAULT_TENANT_ID,),
            )
        manager, _, _ = self.sign_in_manager()
        response = manager.get("/api/access/meta-settings")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual([location["name"] for location in response.get_json()["locations"]], ["Kingston"])
        revision = response.get_json()["revision"]
        updated = manager.put(
            "/api/access/meta-settings",
            headers=self.csrf,
            json={
                "revision": revision,
                "location": "Kingston",
                "changes": [
                    {"field": "open", "day": 0, "value": 0},
                    {"field": "intensity", "day": 1, "value": 0.35},
                ],
            },
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["location"]["open"][0], 0)
        self.assertEqual(updated.get_json()["location"]["intensity"][1], 0.35)
        stale = manager.put(
            "/api/access/meta-settings",
            headers=self.csrf,
            json={
                "revision": revision, "location": "Kingston",
                "changes": [{"field": "open", "day": 0, "value": 1}],
            },
        )
        self.assertEqual(stale.status_code, 409)
        outside = manager.put(
            "/api/access/meta-settings",
            headers=self.csrf,
            json={
                "revision": updated.get_json()["revision"], "location": "Montego Bay",
                "changes": [{"field": "open", "day": 0, "value": 1}],
            },
        )
        self.assertEqual(outside.status_code, 403)
        invalid = manager.put(
            "/api/access/meta-settings",
            headers=self.csrf,
            json={
                "revision": updated.get_json()["revision"], "location": "Kingston",
                "changes": [{"field": "intensity", "day": 2, "value": 1.5}],
            },
        )
        self.assertEqual(invalid.status_code, 400)
        with closing(scheduler.database_connect()) as connection:
            audit = connection.execute(
                """
                SELECT 1 FROM tenant_audit_events
                WHERE tenant_id = ? AND action LIKE 'meta-settings-updated:Kingston:%'
                """,
                (scheduler.DEFAULT_TENANT_ID,),
            ).fetchone()
            accepted = connection.execute(
                "SELECT payload FROM accepted_schedules WHERE run_id = 'meta-preserved-run'"
            ).fetchone()
        self.assertIsNotNone(audit)
        self.assertEqual(accepted[0], "{}")

    def test_meta_import_is_primary_only_and_one_time(self):
        payload = self.shared_meta_import_payload()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO tenant_admins
                    (id, tenant_id, email, display_name, password_hash,
                     mfa_secret, mfa_enabled, active, auth_version, is_primary)
                SELECT 'secondary-admin', tenant_id, 'secondary@example.test',
                       display_name, password_hash, mfa_secret, 1, 1, 1, 0
                FROM tenant_admins WHERE id = 'test-admin'
                """
            )
        secondary = scheduler.app.test_client()
        with self.admin.session_transaction() as current:
            state = dict(current)
        state["tenant_admin_id"] = "secondary-admin"
        with secondary.session_transaction() as current:
            current.update(state)
        headers = {"X-CSRF-Token": "test-csrf-token"}
        self.assertEqual(
            secondary.post("/api/meta-settings/import/preview", headers=headers, json=payload).status_code,
            403,
        )
        preview = self.admin.post(
            "/api/meta-settings/import/preview", headers=headers, json=payload
        )
        self.assertEqual(preview.status_code, 200, preview.get_json())
        imported = self.admin.post(
            "/api/meta-settings/import",
            headers=headers,
            json=payload | {"confirmed": True},
        )
        self.assertEqual(imported.status_code, 201, imported.get_json())
        settings = self.admin.get("/api/meta-settings").get_json()
        edited = self.admin.put(
            "/api/meta-settings/Kingston",
            headers=headers,
            json={
                "revision": settings["revision"],
                "changes": [{"field": "intensity", "day": 0, "value": 0.3}],
            },
        )
        self.assertEqual(edited.status_code, 200, edited.get_json())
        self.assertEqual(edited.get_json()["location"]["intensity"][0], 0.3)
        self.assertEqual(secondary.get("/api/meta-settings").status_code, 403)
        repeated = self.admin.post(
            "/api/meta-settings/import",
            headers=headers,
            json=payload | {"confirmed": True},
        )
        self.assertEqual(repeated.status_code, 409)

    def test_meta_lock_tracks_shared_roster_and_blocks_managers(self):
        self.initialize_shared_roster()
        self.initialize_shared_meta()
        roster = self.admin.get("/api/roster-settings").get_json()
        locked = self.admin.put(
            "/api/roster-settings/configuration",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={
                "revision": roster["revision"], "locked": True, "pools": roster["pools"],
            },
        )
        self.assertEqual(locked.status_code, 200, locked.get_json())
        self.assertTrue(self.admin.get("/api/meta-settings").get_json()["locked"])
        manager, _, _ = self.sign_in_manager()
        meta = manager.get("/api/access/meta-settings").get_json()
        self.assertTrue(meta["locked"])
        rejected = manager.put(
            "/api/access/meta-settings",
            headers=self.csrf,
            json={
                "revision": meta["revision"], "location": "Kingston",
                "changes": [{"field": "open", "day": 0, "value": 0}],
            },
        )
        self.assertEqual(rejected.status_code, 409)

    def test_employee_and_linked_manager_personal_views_cannot_access_meta(self):
        self.initialize_shared_meta()
        employee = self.portal_employee_client()
        self.assertEqual(employee.get("/api/access/meta-settings").status_code, 403)
        manager, _, _ = self.sign_in_manager(employee_id="emp-b")
        self.assertEqual(manager.get("/api/access/meta-settings?view=employee").status_code, 403)

    def test_employee_shared_roster_settings_are_self_only_and_field_scoped(self):
        self.initialize_shared_roster()
        employee = self.portal_employee_client()
        response = employee.get("/api/access/my/roster-settings")
        self.assertEqual(response.status_code, 200, response.get_json())
        record = response.get_json()["employee"]
        self.assertEqual(record["employeeId"], "emp-a")
        saved = employee.put(
            "/api/access/my/roster-settings",
            headers=self.csrf,
            json={
                "revision": record["revision"],
                "changes": {"flex": "No", "reason": "School schedule"},
            },
        )
        self.assertEqual(saved.status_code, 200, saved.get_json())
        forbidden = employee.put(
            "/api/access/my/roster-settings",
            headers=self.csrf,
            json={
                "revision": saved.get_json()["revision"],
                "changes": {"proximity": 2},
            },
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_linked_manager_uses_employee_permissions_in_personal_roster_view(self):
        self.initialize_shared_roster()
        manager, _, _ = self.sign_in_manager(employee_id="emp-a")
        response = manager.get("/api/access/my/roster-settings")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["employee"]["employeeId"], "emp-a")
        forbidden = manager.put(
            "/api/access/my/roster-settings",
            headers=self.csrf,
            json={
                "revision": response.get_json()["employee"]["revision"],
                "changes": {"random": 1},
            },
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(
            manager.get("/api/access/roster-settings?view=employee").status_code,
            403,
        )

    def test_new_shared_shift_start_is_unavailable_by_default(self):
        self.initialize_shared_roster()
        settings = self.admin.get("/api/roster-settings").get_json()
        pools = settings["pools"]
        target = next(pool for pool in pools if pool["location"] == "Kingston" and pool["role"] == "Cashier")
        target["starts"].append(9)
        updated = self.admin.put(
            "/api/roster-settings/configuration",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"revision": settings["revision"], "locked": False, "pools": pools},
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        records = self.admin.get("/api/roster-settings").get_json()["employees"]
        employee = next(record for record in records if record["employeeId"] == "emp-a")
        self.assertEqual(employee["settings"]["shiftAvailability"]["9"], 0)

    def test_shift_start_sync_conflict_rolls_back_configuration_and_profiles(self):
        self.initialize_shared_roster()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                CREATE TRIGGER ignore_roster_profile_update
                BEFORE UPDATE ON roster_employee_settings
                WHEN NEW.employee_id = 'emp-a'
                BEGIN
                    SELECT RAISE(IGNORE);
                END
                """
            )
        settings = self.admin.get("/api/roster-settings").get_json()
        pools = settings["pools"]
        target = next(pool for pool in pools if pool["location"] == "Kingston" and pool["role"] == "Cashier")
        target["starts"].append(9)
        updated = self.admin.put(
            "/api/roster-settings/configuration",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"revision": settings["revision"], "locked": False, "pools": pools},
        )
        self.assertEqual(updated.status_code, 409, updated.get_json())
        current = self.admin.get("/api/roster-settings").get_json()
        self.assertEqual(current["revision"], settings["revision"])
        self.assertEqual(
            next(pool for pool in current["pools"] if pool["location"] == "Kingston" and pool["role"] == "Cashier")["starts"],
            [8],
        )
        employee = next(record for record in current["employees"] if record["employeeId"] == "emp-a")
        self.assertEqual(employee["revision"], 1)
        self.assertEqual(employee["settings"]["shiftAvailability"], {"8": 0})

    def test_manager_sees_only_their_locations_and_cannot_use_admin_api(self):
        client, _, _ = self.sign_in_manager()
        records = client.get("/api/access/manager/attendance?start=2026-11-01&end=2026-11-30")
        self.assertEqual(records.status_code, 200)
        self.assertEqual(
            [record["employeeId"] for record in records.get_json()["records"]], ["emp-a"]
        )
        self.assertEqual(client.get("/api/attendance").status_code, 401)
        self.assertEqual(client.get("/api/access-accounts").status_code, 401)

    @patch.dict(os.environ, {"SCHEDULE_CREATOR_TEMPORARY_MFA_BYPASS": "1"})
    def test_temporary_password_cannot_be_reused_and_mfa_is_required_on_return(self):
        client, secret, created = self.sign_in_manager()
        self.assertEqual(client.post("/api/access/logout", headers=self.csrf, json={}).status_code, 200)
        again = self.new_client()
        old = again.post(
            "/api/access/login", headers=self.csrf,
            json={"bamboohrSubdomain": "acme", "identifier": "mgr@acme.example",
                  "password": created["temporaryPassword"]},
        )
        self.assertEqual(old.status_code, 401)
        credentials = {"bamboohrSubdomain": "acme", "identifier": "mgr@acme.example",
                       "password": "Manager-New-Password-2026!"}
        self.assertTrue(
            again.post("/api/access/login", headers=self.csrf, json=credentials).get_json()["mfaCodeRequired"]
        )
        bad = again.post("/api/access/login", headers=self.csrf, json=credentials | {"code": "000000"})
        self.assertEqual(bad.status_code, 401)
        good = again.post(
            "/api/access/login", headers=self.csrf,
            json=credentials | {"code": scheduler.totp_value(secret, int(time.time() // 30))},
        )
        self.assertTrue(good.get_json()["authenticated"])

    def test_notifications_are_scoped_deduplicated_and_markable(self):
        client, _, _ = self.sign_in_manager()
        notifications = client.get("/api/access/notifications").get_json()
        self.assertEqual(notifications["unread"], 1)
        self.assertIn("Ann Kingston", notifications["notifications"][0]["message"])
        with closing(scheduler.database_connect()) as connection, connection:
            scheduler.record_attendance_status(
                connection, run_id="run-1", employee_id="emp-a", shift_date="2026-11-02",
                shift_start=1.0, status="late", source="attendance_rule", reason="",
                employee_name="Ann Kingston", location="Kingston", role="Cashier",
                clock_in_at=None, clock_in_timezone="",
                existing={("run-1", "emp-a", "2026-11-02"): ("scheduled", "schedule", "")},
            )
        self.assertEqual(client.get("/api/access/notifications").get_json()["unread"], 1)
        admin_view = self.admin.get("/api/attendance/notifications").get_json()
        self.assertEqual(admin_view["unread"], 2)
        marked = client.post("/api/access/notifications/read", headers=self.csrf, json={})
        self.assertEqual(marked.get_json()["marked"], 1)
        self.assertEqual(client.get("/api/access/notifications").get_json()["unread"], 0)
        self.assertEqual(self.admin.get("/api/attendance/notifications").get_json()["unread"], 2)

    def test_archiving_notifications_is_per_reader_and_viewable_in_archive(self):
        client, _, _ = self.sign_in_manager()
        item = client.get("/api/access/notifications").get_json()["notifications"][0]
        no_token = client.post("/api/access/notifications/archive", json={"ids": [item["id"]]})
        self.assertEqual(no_token.status_code, 400)
        none = client.post("/api/access/notifications/archive", headers=self.csrf, json={})
        self.assertEqual(none.get_json()["archived"], 0)
        done = client.post(
            "/api/access/notifications/archive", headers=self.csrf, json={"ids": [item["id"]]}
        )
        self.assertEqual(done.get_json()["archived"], 1)
        active = client.get("/api/access/notifications").get_json()
        self.assertEqual((active["unread"], active["notifications"]), (0, []))
        archived = client.get("/api/access/notifications?archived=1").get_json()
        self.assertEqual([entry["id"] for entry in archived["notifications"]], [item["id"]])
        self.assertTrue(archived["notifications"][0]["archived"])
        again = client.post(
            "/api/access/notifications/archive", headers=self.csrf, json={"ids": [item["id"]]}
        )
        self.assertEqual(again.get_json()["archived"], 0)
        admin_view = self.admin.get("/api/attendance/notifications").get_json()
        self.assertEqual(admin_view["unread"], 2)
        archived_admin = self.admin.get("/api/attendance/notifications?archived=1").get_json()
        self.assertEqual(archived_admin["notifications"], [])

    def test_manager_can_mark_late_absent_only_within_scope(self):
        client, _, _ = self.sign_in_manager()
        shift = {"runId": "run-1", "date": "2026-11-02", "reason": "No call, no show"}
        outside = client.post(
            "/api/access/manager/mark-absent", headers=self.csrf, json=shift | {"employeeId": "emp-b"}
        )
        self.assertEqual(outside.status_code, 403)
        missing_reason = client.post(
            "/api/access/manager/mark-absent", headers=self.csrf,
            json=shift | {"employeeId": "emp-a", "reason": " "},
        )
        self.assertEqual(missing_reason.status_code, 400)
        no_token = client.post(
            "/api/access/manager/mark-absent", json=shift | {"employeeId": "emp-a"}
        )
        self.assertEqual(no_token.status_code, 400)
        done = client.post(
            "/api/access/manager/mark-absent", headers=self.csrf, json=shift | {"employeeId": "emp-a"}
        )
        self.assertEqual(done.status_code, 200)
        again = client.post(
            "/api/access/manager/mark-absent", headers=self.csrf, json=shift | {"employeeId": "emp-a"}
        )
        self.assertEqual(again.status_code, 409)
        with closing(scheduler.database_connect()) as connection:
            audit = connection.execute(
                "SELECT status, actor_email FROM attendance_shift_audit_events "
                "WHERE employee_id = 'emp-a' ORDER BY created_at DESC, id LIMIT 5"
            ).fetchall()
        self.assertIn(("absent", "mgr@acme.example"), audit)

    def test_employee_sees_only_own_attendance_and_needs_silver(self):
        created = self.create_account(role="employee", employeeId="emp-a").get_json()
        client = self.new_client()
        credentials = {"bamboohrSubdomain": "acme", "identifier": "emp-a",
                       "password": created["temporaryPassword"]}
        signed_in = client.post(
            "/api/access/login", headers=self.csrf,
            json=credentials | {"newPassword": "Employee-New-Password-26!"},
        )
        self.assertTrue(signed_in.get_json()["authenticated"])
        self.csrf = {"X-CSRF-Token": signed_in.get_json()["csrfToken"]}
        own = client.get("/api/access/me/attendance?start=2026-11-01&end=2026-11-30").get_json()
        self.assertEqual({record["employeeId"] for record in own["records"]}, {"emp-a"})
        self.assertEqual(own["counts"], {"late": 1})
        self.assertEqual(client.get("/api/access/manager/attendance").status_code, 403)
        self.assertEqual(client.get("/api/access/notifications").status_code, 403)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET membership_tier = 'bronze' WHERE tenant_id = ?",
                (scheduler.DEFAULT_TENANT_ID,),
            )
        self.assertEqual(client.get("/api/access/me/attendance").status_code, 403)
        denied = self.admin.post(
            "/api/access-accounts", headers={"X-CSRF-Token": "test-csrf-token"},
            json={"role": "employee", "employeeId": "emp-b"},
        )
        self.assertEqual(denied.status_code, 403)

    def portal_employee_client(self):
        created = self.create_account(role="employee", employeeId="emp-a").get_json()
        client = self.new_client()
        response = client.post(
            "/api/access/login", headers=self.csrf,
            json={"bamboohrSubdomain": "acme", "identifier": "emp-a",
                  "password": created["temporaryPassword"],
                  "newPassword": "Employee-New-Password-26!"},
        )
        self.assertEqual(response.status_code, 200)
        self.csrf = {"X-CSRF-Token": response.get_json()["csrfToken"]}
        return client

    def test_workspace_schedule_deletion_authorization_is_admin_scoped_and_non_destructive(self):
        self.seed_portal_schedule("browser-week")
        path = "/api/workspace/schedule-deletions"
        payload = {"runId": "browser-week", "tenantId": scheduler.DEFAULT_TENANT_ID,
                   "scope": "browser-workspace"}
        headers = {"X-CSRF-Token": "test-csrf-token"}
        employee = self.portal_employee_client()
        self.assertEqual(employee.post(path, headers=self.csrf, json=payload).status_code, 401)
        manager, _, _ = self.sign_in_manager()
        self.assertEqual(manager.post(path, headers=self.csrf, json=payload).status_code, 401)
        self.assertEqual(self.admin.post(path, json=payload).status_code, 400)
        self.assertEqual(self.admin.post(path, headers=headers,
                                        json=payload | {"tenantId": "another-business"}).status_code, 409)
        self.assertEqual(self.admin.post(path, headers=headers,
                                        json=payload | {"scope": "accepted"}).status_code, 400)
        with closing(scheduler.database_connect()) as c:
            before = [tuple(row) for row in c.execute("SELECT * FROM accepted_schedules").fetchall()]
        self.assertTrue(before)
        with patch.object(scheduler, "urlopen", side_effect=AssertionError("No provider calls")):
            response = self.admin.post(path, headers=headers, json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()["authorized"])
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(
                [tuple(row) for row in c.execute("SELECT * FROM accepted_schedules").fetchall()], before)
            event = c.execute("SELECT tenant_id,detail FROM hub_audit_events "
                              "WHERE action='workspace-schedule-delete-authorized'").fetchone()
        self.assertEqual(event[0], scheduler.DEFAULT_TENANT_ID)
        self.assertEqual(json.loads(event[1])["runId"], "browser-week")

    def test_access_role_round_trip_preserves_identity_and_enforces_mfa_and_scope(self):
        employee = self.portal_employee_client()
        account = self.admin.get("/api/access-accounts").get_json()["accounts"][0]
        user_id = account["id"]
        headers = {"X-CSRF-Token": "test-csrf-token"}
        changed = self.admin.put(f"/api/access-accounts/{user_id}/role", headers=headers,
                                 json={"role": "manager", "previousRole": "employee",
                                       "authVersion": account["authVersion"], "email": "MGR@acme.example"})
        self.assertEqual(changed.status_code, 200, changed.get_json())
        self.assertFalse(employee.get("/api/access/state").get_json()["authenticated"])
        client = self.new_client()
        enrollment = client.post("/api/access/login", headers=self.csrf, json={
            "bamboohrSubdomain": "acme", "identifier": "emp-a",
            "password": "Employee-New-Password-26!",
        }).get_json()
        self.assertTrue(enrollment["mfaEnrollmentRequired"])
        self.csrf = {"X-CSRF-Token": enrollment["csrfToken"]}
        verified = client.post("/api/access/verify-mfa", headers=self.csrf,
                               json={"code": scheduler.totp_value(enrollment["secret"], int(time.time() // 30))})
        self.assertEqual(verified.status_code, 200, verified.get_json())
        attendance = client.get("/api/access/manager/attendance?start=2026-11-01&end=2026-11-30")
        self.assertEqual([r["employeeId"] for r in attendance.get_json()["records"]], ["emp-a"])
        changed = self.admin.put(f"/api/access-accounts/{user_id}/role", headers=headers,
                                 json={"role": "employee", "previousRole": "manager",
                                       "authVersion": self.admin.get("/api/access-accounts").get_json()["accounts"][0]["authVersion"]})
        self.assertEqual(changed.status_code, 200, changed.get_json())
        self.assertFalse(client.get("/api/access/state").get_json()["authenticated"])
        client = self.new_client()
        signed_in = client.post("/api/access/login", headers=self.csrf, json={
            "bamboohrSubdomain": "acme", "identifier": "emp-a", "password": "Employee-New-Password-26!",
        })
        self.assertTrue(signed_in.get_json()["authenticated"])
        self.assertEqual(client.get("/api/access/manager/attendance?start=2026-11-01&end=2026-11-30").status_code, 403)
        current = self.admin.get("/api/access-accounts").get_json()["accounts"][0]
        self.assertEqual(current["id"], user_id)
        self.assertEqual(current["employeeId"], "emp-a")
        self.assertEqual(current["displayName"], account["displayName"])
        self.assertTrue(current["mfaEnabled"])
        with closing(scheduler.database_connect()) as connection:
            events = connection.execute("SELECT detail FROM hub_audit_events WHERE action='access-account-role-change'").fetchall()
        self.assertEqual([json.loads(r[0])["role"] for r in events], ["manager", "employee"])

    def test_access_role_validation_conflicts_and_permissions(self):
        account = self.create_account(role="manager", displayName="Manager", email="mgr@acme.example").get_json()["account"]
        path = f"/api/access-accounts/{account['id']}/role"
        headers = {"X-CSRF-Token": "test-csrf-token"}
        payload = {"role": "employee", "previousRole": "manager", "authVersion": account["authVersion"]}
        self.assertEqual(self.admin.put(path, headers=headers, json=payload).status_code, 400)
        self.assertEqual(self.admin.put(path, headers=headers, json=payload | {"employeeId": "missing"}).status_code, 400)
        self.assertEqual(self.admin.put(path, json=payload).status_code, 400)
        self.assertEqual(self.admin.put(path, headers=headers, json=payload | {"role": "admin"}).status_code, 400)
        self.assertEqual(self.admin.put(path, headers=headers, json=payload | {"previousRole": "employee"}).status_code, 409)
        self.assertEqual(self.admin.put(path, headers=headers, json=payload | {"authVersion": 0}).status_code, 409)
        employee = self.portal_employee_client()
        self.assertEqual(employee.put(path, headers=self.csrf, json=payload).status_code, 401)
        self.assertEqual(self.admin.put(path, headers=headers, json=payload | {"employeeId": "emp-a"}).status_code, 409)
        employee_account = next(a for a in self.admin.get("/api/access-accounts").get_json()["accounts"] if a["role"] == "employee")
        promote_path = f"/api/access-accounts/{employee_account['id']}/role"
        promotion = {"role": "manager", "previousRole": "employee", "authVersion": employee_account["authVersion"]}
        self.assertEqual(self.admin.put(promote_path, headers=headers, json=promotion).status_code, 400)
        self.assertEqual(self.admin.put(promote_path, headers=headers, json=promotion | {"email": "mgr@acme.example"}).status_code, 409)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE tenants SET membership_tier='bronze' WHERE tenant_id=?", (scheduler.DEFAULT_TENANT_ID,))
        self.assertEqual(self.admin.put(path, headers=headers, json=payload | {"employeeId": "emp-b"}).status_code, 403)

    def test_access_role_change_keeps_disabled_state_and_blocks_cross_tenant_target(self):
        account = self.create_account(role="manager", displayName="Manager", email="mgr@acme.example").get_json()["account"]
        headers = {"X-CSRF-Token": "test-csrf-token"}
        self.admin.post(f"/api/access-accounts/{account['id']}/active", headers=headers, json={"active": False})
        payload = {"role": "employee", "previousRole": "manager", "employeeId": "emp-b",
                   "authVersion": account["authVersion"] + 1}
        response = self.admin.put(f"/api/access-accounts/{account['id']}/role", headers=headers, json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertFalse(self.admin.get("/api/access-accounts").get_json()["accounts"][0]["active"])
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("INSERT INTO tenants(tenant_id,business_name) VALUES('other','Other')")
            connection.execute("UPDATE tenant_users SET tenant_id='other' WHERE id=?", (account["id"],))
        self.assertEqual(self.admin.put(f"/api/access-accounts/{account['id']}/role", headers=headers,
                                       json={"role": "manager", "previousRole": "employee", "email": "mgr@acme.example"}).status_code, 404)

    def seed_portal_schedule(self, run_id="portal-a", employee_id="emp-a",
                             location="Kingston", weeks_ahead=0):
        today = scheduler.datetime.now(scheduler.ATTENDANCE_TIMEZONE).date()
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=weeks_ahead)
        payload = {
            "id": run_id, "start": start.isoformat(), "location": location,
            "role": "Cashier", "controls": {"span": 9, "confidential": "not public"},
            "employees": [
                {"id": employee_id, "name": "Untrusted snapshot name",
                 "slots": [23, None, 7, None, None, None, None],
                 "privateEmail": "do-not-expose@example.test"},
            ],
            "confidential": "not public",
        }
        response = self.admin.post(
            "/api/accepted-shifts", headers={"X-CSRF-Token": "test-csrf-token"},
            json=payload,
        )
        self.assertEqual(response.status_code, 200)
        return payload

    def portal_codes(self, *run_ids):
        response = self.admin.post(
            "/api/schedule-portal/codes", headers={"X-CSRF-Token": "test-csrf-token"},
            json={"runIds": list(run_ids)},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["codes"]

    def test_portal_employee_requires_code_and_returns_only_assigned_team(self):
        self.seed_portal_schedule()
        self.seed_portal_schedule("portal-b", "emp-b", "Montego Bay")
        codes = self.portal_codes("portal-a", "portal-b")
        self.assertNotEqual(codes[0]["code"], codes[1]["code"])
        client = self.portal_employee_client()
        listed = client.get("/api/access/schedules").get_json()
        self.assertEqual(listed["visibilityWeeks"], 4)
        self.assertEqual([g["runId"] for g in listed["schedules"]], ["portal-a"])
        self.assertNotIn("employees", listed["schedules"][0])
        self.assertNotIn("managerEmail", listed["schedules"][0])
        code = next(c for c in codes if c["runId"] == "portal-a")
        body = {"runId": "portal-a", "locationId": "loc1", "code": code["code"]}
        self.assertEqual(client.post("/api/access/schedules/unlock", json=body).status_code, 400)
        unlocked = client.post("/api/access/schedules/unlock", headers=self.csrf, json=body)
        self.assertEqual(unlocked.status_code, 200)
        group = unlocked.get_json()["schedule"]
        self.assertEqual([e["id"] for e in group["employees"]], ["emp-a"])
        self.assertEqual(group["employees"][0]["name"], "Ann Kingston")
        self.assertEqual(group["shiftDuration"], 9)
        self.assertNotIn("privateEmail", group["employees"][0])
        self.assertNotIn("confidential", group)
        self.assertEqual(client.post(
            "/api/access/schedules/unlock", headers=self.csrf,
            json=body | {"runId": "portal-b", "locationId": "loc2"},
        ).status_code, 403)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE employees SET schedule_location_id='loc2' WHERE employee_id='emp-a'")
        self.assertEqual(client.post(
            "/api/access/schedules/unlock", headers=self.csrf, json=body,
        ).status_code, 403)

    def test_portal_code_can_choose_only_visible_assigned_schedules(self):
        self.seed_portal_schedule()
        self.seed_portal_schedule(run_id="revision-a")
        self.seed_portal_schedule(run_id="portal-b", employee_id="emp-b", location="Montego Bay")
        codes = self.portal_codes("portal-a", "revision-a", "portal-b")
        client = self.portal_employee_client()
        code = next(item for item in codes if item["locationId"] == "loc1")["code"]
        unlocked = client.post("/api/access/schedules/unlock", headers=self.csrf, json={"code": code})
        self.assertEqual(unlocked.status_code, 200, unlocked.get_json())
        self.assertEqual({schedule["runId"] for schedule in unlocked.get_json()["schedules"]}, {"portal-a", "revision-a"})
        selected = client.post("/api/access/schedules/unlock", headers=self.csrf, json={
            "code": code, "runId": "revision-a", "locationId": "loc1",
        })
        self.assertEqual(len(selected.get_json()["schedules"]), 1)
        foreign = next(item for item in codes if item["locationId"] == "loc2")["code"]
        self.assertEqual(client.post("/api/access/schedules/unlock", headers=self.csrf, json={"code": foreign}).status_code, 403)
        self.assertEqual(client.post("/api/access/schedules/unlock", headers=self.csrf, json={"code": code, "runId": "portal-a"}).status_code, 400)
        self.assertEqual(client.post("/api/access/schedules/unlock", json={"code": code}).status_code, 400)

    def test_portal_codes_reuse_period_expire_and_throttle_guessing(self):
        schedule = self.seed_portal_schedule()
        with patch.object(scheduler.secrets, "randbelow", return_value=7):
            code = self.portal_codes("portal-a")[0]
        self.assertEqual(code["code"], "000007")
        end = scheduler.date.fromisoformat(schedule["start"]) + timedelta(days=7)
        self.assertEqual(
            code["expiresAt"],
            scheduler.datetime.combine(end, scheduler.time.min,
                                       tzinfo=scheduler.ATTENDANCE_TIMEZONE).isoformat(),
        )
        self.assertEqual(self.portal_codes("portal-a")[0]["code"], code["code"])
        self.seed_portal_schedule("revision-a")
        self.assertEqual(self.portal_codes("revision-a")[0]["code"], code["code"])
        client = self.portal_employee_client()
        body = {"runId": "portal-a", "locationId": "loc1", "code": "999999"}
        for _ in range(5):
            self.assertEqual(client.post(
                "/api/access/schedules/unlock", headers=self.csrf, json=body,
            ).status_code, 403)
        self.assertEqual(client.post(
            "/api/access/schedules/unlock", headers=self.csrf,
            json=body | {"code": code["code"]},
        ).status_code, 429)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("DELETE FROM tenant_login_attempts")
            connection.execute("UPDATE schedule_portal_codes SET expires_at = ?",
                               (int(time.time()),))
        self.assertEqual(client.post(
            "/api/access/schedules/unlock", headers=self.csrf,
            json=body | {"code": code["code"]},
        ).status_code, 403)
        with closing(scheduler.database_connect()) as connection:
            stored = connection.execute(
                "SELECT code_hash, encrypted_code FROM schedule_portal_codes"
            ).fetchone()
        self.assertNotEqual(stored[0], code["code"])
        self.assertNotEqual(stored[1], code["code"])

    def test_portal_shared_schedule_group_does_not_expose_another_role(self):
        payload = self.seed_portal_schedule()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE employees SET role='Warehouse' WHERE employee_id='emp-a'")
            for employee_id, role in (("emp-c", "Warehouse"), ("emp-d", "DC Associate")):
                connection.execute(
                    """
                    INSERT INTO employees
                        (employee_id,tenant_id,name,location,role,schedule_location_id,source_type)
                    VALUES (?,?,'Test colleague','Kingston',?,'loc1','manual')
                    """,
                    (employee_id, scheduler.DEFAULT_TENANT_ID, role),
                )
        payload["role"] = "Warehouse/Delivery"
        payload["employees"].extend(
            {"id": employee_id, "slots": [7, None, None, None, None, None, None]}
            for employee_id in ("emp-c", "emp-d")
        )
        self.admin.put("/api/accepted-shifts/portal-a",
                       headers={"X-CSRF-Token": "test-csrf-token"}, json=payload)
        code = self.portal_codes("portal-a")[0]["code"]
        client = self.portal_employee_client()
        unlocked = client.post(
            "/api/access/schedules/unlock", headers=self.csrf,
            json={"runId": "portal-a", "locationId": "loc1", "code": code},
        )
        self.assertEqual(unlocked.status_code, 200)
        self.assertEqual(
            {e["id"] for e in unlocked.get_json()["schedule"]["employees"]},
            {"emp-a", "emp-c"},
        )

    def test_portal_visibility_settings_and_manager_multiple_locations(self):
        self.seed_portal_schedule()
        self.seed_portal_schedule("portal-b", "emp-b", "Montego Bay")
        self.seed_portal_schedule("future", weeks_ahead=4)
        client, _, _ = self.sign_in_manager()
        self.assertEqual([g["runId"] for g in client.get(
            "/api/access/schedules").get_json()["schedules"]], ["portal-a"])
        self.assertEqual(client.put(
            "/api/schedule-portal/settings", headers=self.csrf,
            json={"visibilityWeeks": 52},
        ).status_code, 401)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE schedule_locations SET manager_email='mgr@acme.example' WHERE id='loc2'")
        visible = client.get("/api/access/schedules").get_json()["schedules"]
        self.assertEqual({g["runId"] for g in visible}, {"portal-a", "portal-b"})
        self.assertTrue(all("employees" in g for g in visible))
        for invalid in (0, 53, True, 2.5, "4"):
            response = self.admin.put(
                "/api/schedule-portal/settings", headers={"X-CSRF-Token": "test-csrf-token"},
                json={"visibilityWeeks": invalid},
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.admin.put(
            "/api/schedule-portal/settings", json={"visibilityWeeks": 5},
        ).status_code, 400)
        updated = self.admin.put(
            "/api/schedule-portal/settings", headers={"X-CSRF-Token": "test-csrf-token"},
            json={"visibilityWeeks": 5},
        )
        self.assertEqual(updated.get_json()["visibilityWeeks"], 5)
        self.assertIn("future", {g["runId"] for g in client.get(
            "/api/access/schedules").get_json()["schedules"]})

    def test_portal_unassigned_employee_and_bronze_cannot_view_schedule(self):
        payload = self.seed_portal_schedule()
        code = self.portal_codes("portal-a")[0]
        client = self.portal_employee_client()
        body = {"runId": "portal-a", "locationId": "loc1", "code": code["code"]}
        payload["employees"][0]["slots"] = [None] * 7
        self.admin.put("/api/accepted-shifts/portal-a",
                       headers={"X-CSRF-Token": "test-csrf-token"}, json=payload)
        self.assertEqual(client.get("/api/access/schedules").get_json()["schedules"], [])
        self.assertEqual(client.post(
            "/api/access/schedules/unlock", headers=self.csrf, json=body,
        ).status_code, 403)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE tenants SET membership_tier='bronze' WHERE tenant_id=?",
                               (scheduler.DEFAULT_TENANT_ID,))
        self.assertEqual(client.get("/api/access/schedules").status_code, 403)
        self.assertEqual(client.get("/api/access/me/team-attendance").status_code, 403)
        self.assertEqual(client.post(
            "/api/access/schedules/unlock", headers=self.csrf, json=body,
        ).status_code, 403)

    def test_employee_team_dashboard_counts_only_current_location_role(self):
        client = self.portal_employee_client()
        today = scheduler.datetime.now(scheduler.ATTENDANCE_TIMEZONE).date().isoformat()
        with closing(scheduler.database_connect()) as connection, connection:
            for employee_id, status in (("emp-a", "attended"), ("emp-b", "absent")):
                scheduler.record_attendance_status(
                    connection, run_id="dashboard", employee_id=employee_id,
                    shift_date=today, shift_start=0, status=status, source="manual",
                    reason="Test", employee_name="Test", location="Test", role="Cashier",
                    clock_in_at=None, clock_in_timezone="", existing={},
                )
        result = client.get("/api/access/me/team-attendance").get_json()
        self.assertEqual(result["counts"], {"attended": 1})
        self.assertEqual(result["attendancePercent"], 100)
        self.assertNotIn("records", result)
        self.assertEqual(result["timezone"], "America/Jamaica")

    def test_portal_code_generation_validates_accepted_schedules_and_collisions(self):
        self.seed_portal_schedule()
        self.seed_portal_schedule("portal-b", "emp-b", "Montego Bay")
        with patch.object(scheduler.secrets, "randbelow", side_effect=[1, 1, 2]):
            codes = self.portal_codes("portal-a", "portal-b")
        self.assertEqual({c["code"] for c in codes}, {"000001", "000002"})
        for ids in ([], ["missing"], ["portal-a", "portal-a"], [False]):
            response = self.admin.post(
                "/api/schedule-portal/codes", headers={"X-CSRF-Token": "test-csrf-token"},
                json={"runIds": ids},
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.admin.post(
            "/api/schedule-portal/codes", json={"runIds": ["portal-a"]},
        ).status_code, 400)
        self.assertEqual(scheduler.app.test_client().get(
            "/api/access/schedules").status_code, 401)

    def test_manager_link_revokes_session_and_keeps_scopes_separate(self):
        client, secret, created = self.sign_in_manager()
        account_id = created["account"]["id"]
        linked = self.admin.put(
            f"/api/access-accounts/{account_id}/employee",
            headers={"X-CSRF-Token": "test-csrf-token"}, json={"employeeId": "emp-b"},
        )
        self.assertEqual(linked.status_code, 200)
        self.assertEqual(client.get("/api/access/manager/attendance").status_code, 401)
        client = self.new_client()
        response = client.post("/api/access/login", headers=self.csrf, json={
            "bamboohrSubdomain": "acme", "identifier": "mgr@acme.example",
            "password": "Manager-New-Password-2026!",
            "code": scheduler.totp_value(secret, int(time.time() // 30)),
        })
        self.assertTrue(response.get_json()["authenticated"])
        self.csrf = {"X-CSRF-Token": response.get_json()["csrfToken"]}
        self.seed_portal_schedule("own", "emp-b", "Montego Bay")
        self.seed_portal_schedule("team", "emp-a", "Kingston")
        own = client.get("/api/access/me/shifts").get_json()["schedules"]
        self.assertEqual({g["runId"] for g in own}, {"own"})
        self.assertEqual({e["id"] for g in own for e in g["employees"]}, {"emp-b"})
        managed = client.get("/api/access/schedules").get_json()["schedules"]
        self.assertEqual({g["runId"] for g in managed}, {"team"})
        personal = client.get("/api/access/schedules?view=employee").get_json()["schedules"]
        self.assertEqual({g["runId"] for g in personal}, {"own"})
        self.assertNotIn("employees", personal[0])
        self.assertEqual(client.post(
            "/api/access/manager/mark-absent", headers=self.csrf,
            json={"runId": "run-1", "employeeId": "emp-b", "date": "2026-11-02",
                  "reason": "self correction"},
        ).status_code, 403)

    def test_manager_link_conflicts_invalid_link_and_tier_checks(self):
        client, _, created = self.sign_in_manager()
        user_id = created["account"]["id"]
        self.create_account(role="employee", employeeId="emp-b")
        for employee_id, status in (("emp-b", 409), ("missing", 400)):
            self.assertEqual(self.admin.put(
                f"/api/access-accounts/{user_id}/employee",
                headers={"X-CSRF-Token": "test-csrf-token"},
                json={"employeeId": employee_id},
            ).status_code, status)
        self.assertEqual(client.get("/api/access/me/shifts").status_code, 403)
        self.assertEqual(self.admin.put(
            f"/api/access-accounts/{user_id}/employee",
            headers={"X-CSRF-Token": "test-csrf-token"}, json={"employeeId": None},
        ).status_code, 200)

    def test_obsolete_bypass_setting_cannot_skip_manager_enrollment(self):
        created = self.create_account(
            role="manager", displayName="Mary Manager", email="mgr@acme.example"
        ).get_json()
        with patch.dict(os.environ, {"SCHEDULE_CREATOR_TEMPORARY_MFA_BYPASS": "1"}):
            client = self.new_client()
            signed_in = client.post(
                "/api/access/login", headers=self.csrf,
                json={"bamboohrSubdomain": "acme", "identifier": "mgr@acme.example",
                      "password": created["temporaryPassword"],
                      "newPassword": "Manager-New-Password-2026!"},
            )
            self.assertTrue(signed_in.get_json()["mfaEnrollmentRequired"])
            self.assertFalse(signed_in.get_json().get("authenticated"))
            self.assertEqual(client.get("/api/access/manager/attendance").status_code, 401)
        self.assertEqual(client.get("/api/access/manager/attendance").status_code, 401)

    def test_disabling_an_account_ends_its_session(self):
        created = self.create_account(role="employee", employeeId="emp-a").get_json()
        client = self.new_client()
        signed_in = client.post(
            "/api/access/login", headers=self.csrf,
            json={"bamboohrSubdomain": "acme", "identifier": "emp-a",
                  "password": created["temporaryPassword"],
                  "newPassword": "Employee-New-Password-26!"},
        )
        self.assertTrue(signed_in.get_json()["authenticated"])
        self.assertEqual(client.get("/api/access/me/attendance").status_code, 200)
        disabled = self.admin.post(
            f"/api/access-accounts/{created['account']['id']}/active",
            headers={"X-CSRF-Token": "test-csrf-token"}, json={"active": False},
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(client.get("/api/access/me/attendance").status_code, 401)

    def test_admin_account_creation_validates_input_and_reset_issues_new_password(self):
        self.assertEqual(self.create_account(role="manager", displayName="No Email").status_code, 400)
        self.assertEqual(self.create_account(role="employee", employeeId="missing").status_code, 400)
        first = self.create_account(role="manager", displayName="M", email="m@acme.example")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(
            self.create_account(role="manager", displayName="M2", email="M@acme.example").status_code, 409
        )
        account_id = first.get_json()["account"]["id"]
        reset = self.admin.post(
            f"/api/access-accounts/{account_id}/reset-password",
            headers={"X-CSRF-Token": "test-csrf-token"}, json={"resetMfa": True},
        )
        self.assertEqual(reset.status_code, 200)
        self.assertNotEqual(reset.get_json()["temporaryPassword"], first.get_json()["temporaryPassword"])
        self.assertEqual(
            self.admin.post("/api/access-accounts", json={"role": "manager"}).status_code, 400
        )
        listed = self.admin.get("/api/access-accounts").get_json()["accounts"]
        self.assertNotIn("passwordHash", listed[0])
        self.assertNotIn("temporaryPassword", listed[0])


class UserManualTests(unittest.TestCase):
    def test_manual_files_are_current(self):
        import build_user_manual

        self.assertTrue(build_user_manual.DOCX_PATH.exists(), "Run python build_user_manual.py")
        self.assertEqual(
            build_user_manual.HTML_PATH.read_text(encoding="utf-8"),
            build_user_manual.build_html(),
            "docs/User-Manual.html is stale; update user_manual_content.py and run python build_user_manual.py",
        )


if __name__ == "__main__":
    unittest.main()
