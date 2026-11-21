import app_path  # noqa: F401
import unittest
import time
from contextlib import closing
from unittest.mock import patch

import scheduler
import test_scheduler


class BusinessSubdomainTests(unittest.TestCase):
    create_account = test_scheduler.ManagerEmployeeAccessTests.create_account

    def setUp(self):
        test_scheduler.ManagerEmployeeAccessTests.setUp(self)
        patcher = patch.dict(scheduler.app.config, {
            "BUSINESS_SUBDOMAINS_ENABLED": True,
            "BUSINESS_DOMAIN": "propawfm.com",
            "BUSINESS_SHARED_HOSTS": frozenset({"service.onrender.com"}),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        scheduler.initialize_database()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "INSERT INTO tenants(tenant_id,business_name,bamboohr_subdomain,propa_subdomain) "
                "VALUES('other','Other business','otherbamboo','other')"
            )

    def tearDown(self):
        test_scheduler.ManagerEmployeeAccessTests.tearDown(self)

    def choose(self, value):
        return self.admin.post(
            "/api/business/subdomain", headers={"X-CSRF-Token": "test-csrf-token"},
            json={"subdomain": value},
        )

    def test_primary_chooses_once_with_unique_valid_name(self):
        for value in ("www", "api", "-bad", "bad-", "a.b", ""):
            self.assertEqual(self.choose(value).status_code, 400, value)
        self.assertEqual(self.choose("OTHER").status_code, 409)
        self.assertEqual(self.admin.post("/api/business/subdomain", json={"subdomain": "acme"}).status_code, 400)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE tenant_admins SET is_primary=0 WHERE id='test-admin'")
        self.assertEqual(self.choose("acme").status_code, 403)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE tenant_admins SET is_primary=1 WHERE id='test-admin'")
        self.assertEqual(self.choose("Acme").get_json()["subdomain"], "acme")
        self.assertEqual(self.choose("new-name").status_code, 409)

    def test_unknown_hosts_and_foreign_session_are_rejected(self):
        self.assertEqual(self.choose("acme").status_code, 200)
        client = scheduler.app.test_client()
        self.assertEqual(client.get("/", base_url="https://unknown.propawfm.com").status_code, 404)
        self.assertEqual(client.get("/", base_url="https://other.example.com").status_code, 404)
        response = client.get("/", base_url="https://acme.propawfm.com")
        self.assertIn(b"Welcome back.", response.data)
        self.assertEqual(client.get("/api/hub/state", base_url="https://acme.propawfm.com").status_code, 404)
        with self.admin.session_transaction() as state:
            admin_state = dict(state)
        with client.session_transaction(base_url="https://other.propawfm.com") as state:
            state.update(admin_state)
        self.assertEqual(client.get("/api/employees", base_url="https://other.propawfm.com").status_code, 403)

    def test_signin_states_return_only_the_resolved_business_name(self):
        self.assertEqual(self.choose("acme").status_code, 200)
        name = "Ada's <Market>"
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET business_name=? WHERE tenant_id=?",
                (name, scheduler.DEFAULT_TENANT_ID),
            )
        client = scheduler.app.test_client()
        for endpoint in ("/api/tenant-auth/state", "/api/access/state"):
            with self.subTest(endpoint=endpoint):
                acme = client.get(endpoint, base_url="https://acme.propawfm.com")
                self.assertEqual(acme.status_code, 200)
                self.assertEqual(acme.get_json()["businessSiteName"], name)
                other = client.get(endpoint, base_url="https://other.propawfm.com")
                self.assertEqual(other.get_json()["businessSiteName"], "Other business")
                shared = client.get(endpoint, base_url="https://propawfm.com")
                self.assertIsNone(shared.get_json()["businessSiteName"])
                self.assertFalse(shared.get_json()["businessSite"])
                self.assertEqual(client.get(endpoint, base_url="https://unknown.propawfm.com").status_code, 404)

    def test_employee_login_uses_site_business_not_submitted_bamboo_domain(self):
        self.assertEqual(self.choose("acme").status_code, 200)
        created = self.create_account(role="employee", employeeId="emp-a").get_json()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET bamboohr_subdomain=NULL WHERE tenant_id=?", (scheduler.DEFAULT_TENANT_ID,)
            )
        client = scheduler.app.test_client()
        host = "https://acme.propawfm.com"
        state = client.get("/api/access/state", base_url=host).get_json()
        self.assertTrue(state["businessSite"])
        response = client.post(
            "/api/access/login", base_url=host, headers={"X-CSRF-Token": state["csrfToken"]},
            json={"identifier": "emp-a", "password": created["temporaryPassword"],
                  "newPassword": "Employee-New-Password-26!", "bamboohrSubdomain": "otherbamboo"},
        )
        self.assertTrue(response.get_json().get("authenticated"), response.get_json())
        self.assertEqual(client.get("/api/access/state", base_url=host).get_json()["user"]["employeeId"], "emp-a")

    def test_admin_login_rejects_another_business_even_with_valid_password(self):
        self.assertEqual(self.choose("acme").status_code, 200)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "INSERT INTO tenant_admins(id,tenant_id,email,display_name,password_hash,mfa_enabled,active) "
                "VALUES('other-admin','other','other@example.com','Other',?,0,1)",
                (scheduler.generate_password_hash("test-only-password"),),
            )
        client = scheduler.app.test_client()
        host = "https://acme.propawfm.com"
        state = client.get("/api/tenant-auth/state", base_url=host).get_json()
        self.assertTrue(state["businessSite"])
        response = client.post(
            "/api/tenant-auth/login", base_url=host, headers={"X-CSRF-Token": state["csrfToken"]},
            json={"email": "other@example.com", "password": "test-only-password",
                  "bamboohrSubdomain": "otherbamboo"},
        )
        self.assertEqual(response.status_code, 401)

    def test_manager_login_enrolls_and_is_bound_to_business_site(self):
        self.assertEqual(self.choose("acme").status_code, 200)
        created = self.create_account(
            role="manager", displayName="Mary Manager", email="mgr@acme.example"
        ).get_json()
        client = scheduler.app.test_client()
        host = "https://acme.propawfm.com"
        token = client.get("/api/access/state", base_url=host).get_json()["csrfToken"]
        response = client.post(
            "/api/access/login", base_url=host, headers={"X-CSRF-Token": token},
            json={"identifier": "mgr@acme.example", "password": created["temporaryPassword"],
                  "newPassword": "Manager-New-Password-2026!"},
        ).get_json()
        self.assertTrue(response.get("mfaEnrollmentRequired"), response)
        code = scheduler.totp_value(response["secret"], int(time.time() // 30))
        verified = client.post(
            "/api/access/verify-mfa", base_url=host,
            headers={"X-CSRF-Token": response["csrfToken"]}, json={"code": code},
        ).get_json()
        self.assertTrue(verified.get("authenticated"), verified)
        self.assertEqual(client.get("/api/access/state", base_url=host).get_json()["user"]["role"], "manager")


class RegistrationSubdomainTests(unittest.TestCase):
    query = test_scheduler.BusinessHubTests.query
    register = test_scheduler.BusinessHubTests.register
    tenant_id = test_scheduler.BusinessHubTests.tenant_id

    def setUp(self):
        test_scheduler.BusinessHubTests.setUp(self)
        patcher = patch.dict(scheduler.app.config, {
            "BUSINESS_SUBDOMAINS_ENABLED": True,
            "BUSINESS_DOMAIN": "propawfm.com",
            "BUSINESS_SHARED_HOSTS": frozenset(),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        scheduler.initialize_database()

    def tearDown(self):
        test_scheduler.BusinessHubTests.tearDown(self)

    def test_registration_reserves_chosen_address_and_rejects_duplicates(self):
        invalid, _ = self.register(propaSubdomain="www")
        self.assertEqual(invalid.status_code, 400)
        registered, _ = self.register(propaSubdomain="Acme")
        self.assertEqual(registered.status_code, 201, registered.get_json())
        self.assertEqual(registered.get_json()["businessUrl"], "https://acme.propawfm.com")
        tenant = self.tenant_id()
        self.assertEqual(self.query(
            "SELECT propa_subdomain FROM tenants WHERE tenant_id=?", (tenant,)
        )[0][0], "acme")
        duplicate, _ = self.register(
            propaSubdomain="ACME", bamboohrSubdomain="otherbamboo", adminEmail="other@example.com"
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_business_admin_signs_in_on_chosen_host_with_mfa(self):
        response, _ = self.register(propaSubdomain="acme")
        self.assertEqual(response.status_code, 201, response.get_json())
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET bamboohr_subdomain=NULL WHERE tenant_id=?", (self.tenant_id(),)
            )
        client = scheduler.app.test_client()
        host = "https://acme.propawfm.com"
        state = client.get("/api/tenant-auth/state", base_url=host).get_json()
        response = client.post(
            "/api/tenant-auth/login", base_url=host,
            headers={"X-CSRF-Token": state["csrfToken"]},
            json={"email": "ada@acme.example", "password": "correct-horse-battery"},
        ).get_json()
        self.assertTrue(response.get("mfaEnrollmentRequired"), response)
        code = scheduler.totp_value(response["secret"], int(time.time() // 30))
        verified = client.post(
            "/api/tenant-auth/verify-mfa", base_url=host,
            headers={"X-CSRF-Token": response["csrfToken"]}, json={"code": code},
        ).get_json()
        self.assertTrue(verified.get("authenticated"), verified)
        self.assertEqual(client.get("/api/tenant-auth/state", base_url=host).get_json()["tenantId"], self.tenant_id())


if __name__ == "__main__":
    unittest.main()
