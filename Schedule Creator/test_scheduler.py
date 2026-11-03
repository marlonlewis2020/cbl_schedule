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

# Unit tests must never use the deployment database loaded from .env.
scheduler.DATABASE_URL = ""
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
                            json=credentials | {"bamboohrSubdomain": "cbljm"},
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


if __name__ == "__main__":
    unittest.main()
