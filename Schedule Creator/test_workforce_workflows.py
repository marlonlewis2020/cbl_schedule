import json
import io
import sqlite3
import time
import unittest
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import membership_billing as billing
import scheduler
import test_scheduler


class TradeWorkflowTests(unittest.TestCase):
    setUp = test_scheduler.ManagerEmployeeAccessTests.setUp
    tearDown = test_scheduler.ManagerEmployeeAccessTests.tearDown
    create_account = test_scheduler.ManagerEmployeeAccessTests.create_account
    new_client = test_scheduler.ManagerEmployeeAccessTests.new_client
    sign_in_manager = test_scheduler.ManagerEmployeeAccessTests.sign_in_manager
    portal_employee_client = test_scheduler.ManagerEmployeeAccessTests.portal_employee_client
    headers = {"X-CSRF-Token": "test-csrf-token"}

    def test_bamboo_validation_error_retains_provider_details(self):
        error = HTTPError("https://example.test", 422, "Unprocessable Entity", {},
                          io.BytesIO(b'{"errors":{"start":["Shift overlaps an existing shift"]}}'))
        with patch.object(scheduler, "urlopen", side_effect=error):
            result = scheduler.bamboo_shift_request("test-key", "POST", "scheduling/shifts", {})
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], 422)
        self.assertIn("Shift overlaps an existing shift", result["error"])

    def seed(self):
        tenant = scheduler.DEFAULT_TENANT_ID
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE employees SET schedule_location_id='loc1',location='Kingston' WHERE employee_id='emp-b'")
        today = scheduler.datetime.now(scheduler.ATTENDANCE_TIMEZONE).date()
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=1)
        doc = {"id": "trade-week", "start": start.isoformat(), "location": "Kingston",
               "role": "Cashier", "controls": {"span": 8, "rest": 11, "shifts": 5},
               "employees": [
                   {"id": "emp-a", "name": "Ann", "slots": [6, None, 6, 6, 6, 6, None]},
                   {"id": "emp-b", "name": "Bob", "slots": [14, None, 14, 14, 14, 14, None]},
               ]}
        response = self.admin.post("/api/accepted-shifts", headers=self.headers, json=doc)
        self.assertEqual(response.status_code, 200, response.get_json())
        return doc

    def create(self, client=None, headers=None):
        response = (client or self.admin).post(
            "/api/access/trades" if client else "/api/shift-trades",
            headers=headers or self.headers,
            json={"runId": "trade-week", "day": 0, "employeeA": "emp-a",
                  "employeeB": "emp-b", "reason": "Coverage arrangement"},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["id"]

    def apply(self, trade, mode="app_only"):
        preview = self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,
                                  json={"remoteMode": mode})
        self.assertEqual(preview.status_code, 200, preview.get_json())
        return self.admin.post(f"/api/shift-trades/{trade}/apply", headers=self.headers,
                               json={"confirmed": True, "reason": "Approved coverage",
                                     "fingerprint": preview.get_json()["fingerprint"]})

    def test_admin_application_is_durable_and_single_use(self):
        self.seed()
        trade = self.create()
        with patch.object(scheduler, "bamboo_shift_request") as remote:
            applied = self.apply(trade)
            self.assertEqual(applied.status_code, 200, applied.get_json())
            remote.assert_not_called()
        with closing(scheduler.database_connect()) as c:
            doc = json.loads(c.execute("SELECT payload FROM accepted_schedules WHERE run_id='trade-week'").fetchone()[0])
            self.assertEqual([e["slots"][0] for e in doc["employees"]], [14, 6])
            self.assertEqual(doc["tradeHistory"][0]["tradeId"], trade)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM shift_trade_events WHERE trade_id=?", (trade,)).fetchone()[0], 2)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,
                                        json={"remoteMode": "app_only"}).status_code, 409)

    def save_doc(self, doc):
        response = self.admin.post("/api/accepted-shifts", headers=self.headers, json=doc)
        self.assertEqual(response.status_code, 200, response.get_json())

    def test_inbox_identifies_actual_initiator_and_handles_removed_account(self):
        self.seed()
        employee = self.portal_employee_client()
        self.target_client()
        trade_id = self.create(employee, self.csrf)
        record = employee.get("/api/access/trades").get_json()["trades"][0]
        with closing(scheduler.database_connect()) as c, c:
            name = c.execute("SELECT display_name FROM tenant_users WHERE id=? AND tenant_id=?",
                             (record["createdBy"], scheduler.DEFAULT_TENANT_ID)).fetchone()[0]
            self.assertEqual(record["initiatorName"], name)
            self.assertEqual(record["initiatedRole"], "employee")
            c.execute("UPDATE shift_trades SET created_by='removed-account' WHERE id=?", (trade_id,))
        record = employee.get("/api/access/trades").get_json()["trades"][0]
        self.assertEqual(record["initiatorName"], "Former account")

    def target_client(self):
        original_headers = self.csrf.copy()
        created = self.create_account(role="employee", employeeId="emp-b").get_json()
        client = self.new_client()
        response = client.post("/api/access/login", headers=self.csrf, json={
            "bamboohrSubdomain": "acme", "identifier": "emp-b",
            "password": created["temporaryPassword"], "newPassword": "Target-New-Password-2026!",
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.csrf = original_headers
        return client, {"X-CSRF-Token": response.get_json()["csrfToken"]}

    def options(self, client=None, headers=None):
        response = (client or self.admin).post(
            "/api/access/trades/options" if client else "/api/shift-trades/options",
            headers=headers or self.headers,
            json={"runId": "trade-week", "employeeA": "emp-a", "employeeB": "emp-b"},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_combined_days_can_balance_weekly_cap_and_block_pending_intersections(self):
        doc = self.seed()
        doc["controls"]["rest"] = 0
        doc["employees"][0]["slots"] = [6, None, 6, 6, 6, 6, None]
        doc["employees"][1]["slots"] = [None, 14, 14, 14, 14, 14, None]
        self.save_doc(doc)
        options = self.options()
        self.assertIn([0, 1], [option["days"] for option in options["combinations"]])
        self.assertNotIn([0], [option["days"] for option in options["combinations"]])
        body = {"runId": "trade-week", "days": [0, 1], "employeeA": "emp-a",
                "employeeB": "emp-b", "reason": "Balanced two-day swap"}
        rejected = self.admin.post("/api/shift-trades", headers=self.headers, json=dict(body, days=[0]))
        self.assertEqual(rejected.status_code, 409)
        response = self.admin.post("/api/shift-trades", headers=self.headers, json=body)
        self.assertEqual(response.status_code, 201, response.get_json())
        trade = response.get_json()["id"]
        self.assertTrue(all(day["day"] not in (0, 1) for day in self.options()["days"]))
        override = self.admin.post("/api/shift-overrides", headers=self.headers, json={
            "runId": "trade-week", "day": 1, "employeeId": "emp-a", "start": 6,
            "confirmed": True, "reason": "Conflicting manual override",
        })
        self.assertEqual(override.status_code, 409)
        self.assertEqual(self.apply(trade).status_code, 200)
        with closing(scheduler.database_connect()) as c:
            applied = json.loads(c.execute("SELECT payload FROM accepted_schedules WHERE run_id='trade-week'").fetchone()[0])
        self.assertEqual(applied["employees"][0]["slots"][:2], [None, 14])
        self.assertEqual(applied["employees"][1]["slots"][:2], [6, None])
        self.assertEqual(applied["tradeHistory"][0]["days"], [0, 1])

    def test_picker_scopes_teams_and_locks_employee_one(self):
        self.seed()
        employee = self.portal_employee_client()
        self.target_client()
        choices = employee.get("/api/access/trades/choices").get_json()
        self.assertEqual(choices["employee1"], "emp-a")
        self.assertEqual({item["runId"] for item in choices["schedules"]}, {"trade-week"})
        self.assertEqual({person["id"] for person in choices["schedules"][0]["employees"]}, {"emp-a", "emp-b"})
        invalid = employee.post("/api/access/trades/options", headers=self.csrf, json={
            "runId": "trade-week", "employeeA": "emp-b", "employeeB": "emp-a",
        })
        self.assertEqual(invalid.status_code, 403)
        manager, _, _ = self.sign_in_manager()
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE schedule_locations SET manager_email='other@example.com' WHERE id='loc1'")
        self.assertEqual(manager.get("/api/access/trades/choices").get_json()["schedules"], [])
        self.assertEqual(manager.post("/api/access/trades/options", headers=self.csrf, json={
            "runId": "trade-week", "employeeA": "emp-a", "employeeB": "emp-b",
        }).status_code, 403)

    def test_minimum_five_is_enforced_at_submit_approve_and_apply_without_maximum(self):
        doc = self.seed()
        body = {"runId": "trade-week", "days": [0], "employeeA": "emp-a",
                "employeeB": "emp-b", "reason": "Five-shift requirement", "overrideReason": "Cannot bypass"}
        doc["employees"][0]["slots"][5] = None
        self.save_doc(doc)
        rejected = self.admin.post("/api/shift-trades", headers=self.headers, json=body)
        self.assertEqual(rejected.status_code, 409)
        self.assertIn("Ann would have 4", rejected.get_json()["error"])
        self.assertEqual(self.options()["combinations"], [])
        doc["controls"].update(rest=0, shifts=7)
        for count in (6, 7):
            doc["employees"][0]["slots"] = [6] * count + [None] * (7 - count)
            doc["employees"][1]["slots"] = [14] * count + [None] * (7 - count)
            self.save_doc(doc)
            accepted = self.admin.post("/api/shift-trades", headers=self.headers, json=body)
            self.assertEqual(accepted.status_code, 201, accepted.get_json())
            trade = accepted.get_json()["id"]
            self.assertEqual(self.apply(trade).status_code, 200)
        doc["employees"][0]["slots"] = [6, None, 6, 6, 6, 6, None]
        doc["employees"][1]["slots"] = [14, None, 14, 14, 14, 14, None]
        self.save_doc(doc)
        manager, _, _ = self.sign_in_manager()
        accepted = manager.post("/api/access/trades", headers=self.csrf, json=body)
        self.assertEqual(accepted.status_code, 201)
        trade = accepted.get_json()["id"]
        doc["employees"][0]["slots"][5] = None
        self.save_doc(doc)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/action", headers=self.headers,
                                        json={"action": "approve", "version": 1, "reason": "Review"}).status_code, 409)
        doc["employees"][0]["slots"][5] = 6
        self.save_doc(doc)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/action", headers=self.headers,
                                        json={"action": "approve", "version": 1, "reason": "Review"}).status_code, 200)
        preview = self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,
                                  json={"remoteMode": "app_only"}).get_json()
        doc["employees"][0]["slots"][5] = None
        self.save_doc(doc)
        rejected = self.admin.post(f"/api/shift-trades/{trade}/apply", headers=self.headers,
                                   json={"confirmed": True, "reason": "Apply", "fingerprint": preview["fingerprint"]})
        self.assertEqual(rejected.status_code, 409)

    def test_all_constraints_warn_and_both_employees_and_management_must_acknowledge(self):
        doc = self.seed()
        doc["controls"]["shifts"] = 4
        doc["controls"]["rest"] = 0
        doc["locationPattern"] = {"open": [False]*7}
        doc["employees"][0].update(days=[False]*7, timeOff=[True]*8,
                                    shiftAvailability={"6": 1, "14": 0}, flex="No", preferred=6)
        doc["employees"][1].update(shiftAvailability={"6": 0, "14": 1})
        self.save_doc(doc)
        employee = self.portal_employee_client()
        target, target_headers = self.target_client()
        option = next(option for option in self.options(employee, self.csrf)["combinations"] if option["days"] == [0])
        warnings = option["warnings"]
        text = json.dumps(warnings)
        for label in ("Weekly shift cap", "Approved leave", "Availability", "Operating days", "permission", "Fixed shift preference"):
            self.assertIn(label, text)
        self.assertEqual(option["shiftCounts"], {"emp-a": 5, "emp-b": 5})
        response = employee.post("/api/access/trades", headers=self.csrf, json={
            "runId": "trade-week", "days": [0], "employeeA": "emp-a", "employeeB": "emp-b",
            "reason": "Approve exceptions", "warnings": warnings, "acknowledgeWarnings": True,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        trade = response.get_json()["id"]
        action = {"action": "confirm", "version": 1, "reason": "Agree", "warnings": warnings}
        self.assertEqual(target.post(f"/api/access/trades/{trade}/action", headers=target_headers, json=action).status_code, 400)
        action["acknowledgeWarnings"] = True
        self.assertEqual(target.post(f"/api/access/trades/{trade}/action", headers=target_headers, json=action).status_code, 200)
        manager, _, _ = self.sign_in_manager()
        manager_record = manager.get("/api/access/trades").get_json()["trades"][0]
        self.assertEqual(manager_record["state"], "confirmed")
        self.assertIn("accept", manager_record["actions"])
        self.assertNotIn("approve", self.admin.get("/api/shift-trades").get_json()["trades"][0]["actions"])
        action.update(action="accept", version=2, acknowledgeWarnings=False)
        self.assertEqual(manager.post(f"/api/access/trades/{trade}/action", headers=self.csrf,json=action).status_code, 400)
        action["acknowledgeWarnings"] = True
        self.assertEqual(manager.post(f"/api/access/trades/{trade}/action", headers=self.csrf,json=action).status_code, 200)
        admin_record = self.admin.get("/api/shift-trades").get_json()["trades"][0]
        self.assertEqual(admin_record["state"], "manager_accepted")
        self.assertIn("approve", admin_record["actions"])
        self.assertTrue(admin_record["unread"])
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/read", headers=self.headers,
                                        json={"version": admin_record["version"]}).status_code, 200)
        seen = self.admin.get("/api/shift-trades").get_json()["trades"][0]
        self.assertFalse(seen["unread"])
        self.assertEqual(seen["state"], "manager_accepted")
        action.update(action="approve", version=3, acknowledgeWarnings=False)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/action", headers=self.headers,json=action).status_code, 400)
        action["acknowledgeWarnings"] = True
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/action", headers=self.headers,json=action).status_code, 200)
        self.assertNotEqual(self.admin.get("/api/shift-trades").get_json()["trades"][0]["state"], "manager_accepted")
        self.assertEqual(self.apply(trade).status_code, 200)
        record = self.admin.get("/api/shift-trades").get_json()["trades"][0]
        self.assertEqual(record["employeeNameA"], "Ann")
        self.assertTrue(any("Scheduling warnings acknowledged" in e["reason"] for e in record["history"]))

    def test_trade_window_is_same_origin_only_and_still_requires_admin_api_auth(self):
        response = self.admin.get("/trades?adminView=1&trade=missing")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(response.headers["Content-Security-Policy"], "frame-ancestors 'self'")
        response.close()
        anonymous = scheduler.app.test_client()
        self.assertEqual(anonymous.get("/api/shift-trades").status_code, 401)
        with anonymous.get("/") as home:
            self.assertEqual(home.headers["X-Frame-Options"], "DENY")

    def test_unaffected_employee_still_consents_to_exception_and_legacy_minimum_applies(self):
        doc = self.seed()
        doc["employees"][0]["days"] = [False]*7
        self.save_doc(doc)
        employee = self.portal_employee_client()
        target, target_headers = self.target_client()
        warnings = next(option for option in self.options(employee, self.csrf)["combinations"] if option["days"] == [0])["warnings"]
        self.assertEqual(set(warnings), {"emp-a"})
        response = self.admin.post("/api/shift-trades", headers=self.headers, json={
            "runId": "trade-week", "days": [0], "employeeA": "emp-a", "employeeB": "emp-b",
            "reason": "Admin request", "warnings": warnings, "acknowledgeWarnings": True,
        })
        self.assertEqual(response.status_code, 201)
        trade = response.get_json()["id"]
        action = {"action": "confirm", "version": 1, "reason": "Consent"}
        self.assertEqual(target.post(f"/api/access/trades/{trade}/action", headers=target_headers,json=action).status_code, 400)
        action.update(acknowledgeWarnings=True, warnings=warnings)
        self.assertEqual(target.post(f"/api/access/trades/{trade}/action", headers=target_headers,json=action).get_json()["state"], "requested")
        action.update(action="acknowledge",version=2)
        self.assertEqual(employee.post(f"/api/access/trades/{trade}/action", headers=self.csrf,json=action).get_json()["state"], "confirmed")
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE shift_trades SET constraint_policy='legacy',override_reason='old override',state='approved' WHERE id=?", (trade,))
        doc["employees"][0]["slots"][5] = None
        self.save_doc(doc)
        rejected = self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,json={"remoteMode":"app_only"})
        self.assertEqual(rejected.status_code, 409)
        self.assertIn("at least 5", rejected.get_json()["error"])

    def rest_fixture(self):
        doc = self.seed()
        doc["employees"][0]["slots"][1] = 6
        doc["employees"][0]["slots"][2] = None
        doc["employees"][1]["previous"] = 14
        self.save_doc(doc)
        employee = self.portal_employee_client()
        target, target_headers = self.target_client()
        warnings = next(option for option in self.options(employee, self.csrf)["combinations"] if option["days"] == [0])["warnings"]
        self.assertEqual(set(warnings), {"emp-a", "emp-b"})
        self.assertEqual([warnings[person][0]["hours"] for person in ("emp-a", "emp-b")], [8, 8])
        return doc, employee, target, target_headers, warnings

    def test_employee_and_recipient_must_acknowledge_their_own_rest_warnings(self):
        doc, employee, target, target_headers, warnings = self.rest_fixture()
        body = {"runId": "trade-week", "days": [0], "employeeA": "emp-a", "employeeB": "emp-b",
                "reason": "Acknowledged reduced rest", "restWarnings": warnings}
        self.assertEqual(employee.post("/api/access/trades", headers=self.csrf, json=body).status_code, 400)
        response = employee.post("/api/access/trades", headers=self.csrf, json=dict(body, acknowledgeRest=True))
        self.assertEqual(response.status_code, 201, response.get_json())
        trade = response.get_json()["id"]
        action = {"action": "confirm", "version": 1, "reason": "Accept swap"}
        self.assertEqual(target.post(f"/api/access/trades/{trade}/action", headers=target_headers, json=action).status_code, 400)
        action.update(acknowledgeWarnings=True, warnings=warnings)
        self.assertEqual(target.post(f"/api/access/trades/{trade}/action", headers=target_headers, json=action).status_code, 200)
        manager, _, _ = self.sign_in_manager()
        self.assertEqual(manager.post(f"/api/access/trades/{trade}/action", headers=self.csrf,
                                     json={"action": "accept", "version": 2, "reason": "Reviewed",
                                           "acknowledgeWarnings": True, "warnings": warnings}).status_code, 200)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/action", headers=self.headers,
                                        json={"action": "approve", "version": 3, "reason": "Approve",
                                              "acknowledgeWarnings": True, "warnings": warnings}).status_code, 200)
        doc["controls"]["rest"] = 12
        self.save_doc(doc)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,
                                        json={"remoteMode": "app_only"}).status_code, 409)
        doc["controls"]["rest"] = 11
        self.save_doc(doc)
        self.assertEqual(self.apply(trade).status_code, 200)
        record = self.admin.get("/api/shift-trades").get_json()["trades"][0]
        self.assertTrue({"emp-a", "emp-b"} <= set(record["acknowledged"]))
        self.assertTrue(any(v.startswith("manager:") for v in record["acknowledged"]))
        self.assertTrue(any(v.startswith("admin:") for v in record["acknowledged"]))

    def test_admin_cannot_substitute_for_employee_rest_acknowledgements(self):
        _, employee, target, target_headers, warnings = self.rest_fixture()
        response = self.admin.post("/api/shift-trades", headers=self.headers, json={
            "runId": "trade-week", "days": [0], "employeeA": "emp-a", "employeeB": "emp-b",
            "reason": "Administrator proposal", "restWarnings": warnings, "acknowledgeRest": True,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["state"], "requested")
        trade = response.get_json()["id"]
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,
                                        json={"remoteMode": "app_only"}).status_code, 409)
        action = {"action": "confirm", "version": 1, "reason": "Recipient accepts",
                  "acknowledgeWarnings": True, "warnings": warnings}
        self.assertEqual(target.post(f"/api/access/trades/{trade}/action", headers=target_headers, json=action).get_json()["state"], "requested")
        action.update(action="acknowledge", version=2)
        self.assertEqual(employee.post(f"/api/access/trades/{trade}/action", headers=self.csrf, json=action).get_json()["state"], "confirmed")
        manager, _, _ = self.sign_in_manager()
        action.update(action="accept", version=3)
        self.assertEqual(manager.post(f"/api/access/trades/{trade}/action", headers=self.csrf,json=action).status_code, 200)
        action.update(action="approve", version=4)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/action", headers=self.headers,json=action).status_code, 200)
        self.assertEqual(self.apply(trade).status_code, 200)

    def test_stale_warnings_require_new_review_and_constraints_are_warnings(self):
        doc, employee, _, _, warnings = self.rest_fixture()
        body = {"runId": "trade-week", "days": [0], "employeeA": "emp-a", "employeeB": "emp-b",
                "reason": "Review warnings", "restWarnings": warnings, "acknowledgeRest": True}
        doc["controls"]["rest"] = 12
        self.save_doc(doc)
        response = employee.post("/api/access/trades", headers=self.csrf, json=body)
        self.assertEqual(response.status_code, 409)
        self.assertNotEqual(response.get_json()["restWarnings"], warnings)
        doc["employees"][0]["shiftAvailability"] = {"6": 1, "14": 0}
        self.save_doc(doc)
        option = next(option for option in self.options(employee, self.csrf)["combinations"] if option["days"] == [0])
        self.assertIn("permission", json.dumps(option["warnings"]))
        response = employee.post("/api/access/trades", headers=self.csrf, json=body)
        self.assertEqual(response.status_code, 409)
        self.assertIn("permission", json.dumps(response.get_json()["warnings"]))
        doc["employees"][0].pop("shiftAvailability")
        doc["controls"]["span"] = 12
        doc["employees"][0]["slots"][1] = 0
        self.save_doc(doc)
        option = next(option for option in self.options(employee, self.csrf)["combinations"] if option["days"] == [0])
        self.assertIn("overlap", json.dumps(option["warnings"]))
        response = employee.post("/api/access/trades", headers=self.csrf, json=body)
        self.assertEqual(response.status_code, 409)
        self.assertIn("overlap", json.dumps(response.get_json()["warnings"]))
        body["warnings"] = option["warnings"]
        body["acknowledgeWarnings"] = True
        self.assertEqual(employee.post("/api/access/trades", headers=self.csrf, json=body).status_code, 201)

    def test_employee_confirmation_manager_acceptance_admin_approval(self):
        self.seed()
        employee = self.portal_employee_client()
        employee_headers = self.csrf.copy()
        target_created = self.create_account(role="employee", employeeId="emp-b").get_json()
        target = self.new_client()
        response = target.post("/api/access/login", headers=self.csrf, json={
            "bamboohrSubdomain": "acme", "identifier": "emp-b",
            "password": target_created["temporaryPassword"], "newPassword": "Target-New-Password-2026!",
        })
        target_headers = {"X-CSRF-Token": response.get_json()["csrfToken"]}
        trade = self.create(employee, employee_headers)
        body = {"action": "confirm", "version": 1, "reason": "Agree"}
        self.assertEqual(employee.post(f"/api/access/trades/{trade}/action", headers=employee_headers, json=body).status_code, 403)
        self.assertEqual(target.post(f"/api/access/trades/{trade}/action", headers=target_headers, json=body).status_code, 200)
        self.assertEqual(target.post(f"/api/access/trades/{trade}/action", headers=target_headers,
                                     json=dict(body, action="approve", version=2)).status_code, 403)
        manager, _, _ = self.sign_in_manager()
        self.assertEqual(manager.post(f"/api/access/trades/{trade}/action", headers=self.csrf,
                                      json=dict(body, action="accept", version=2)).status_code, 200)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/action", headers=self.headers,
                                         json=dict(body, action="approve", version=3)).status_code, 200)
        self.assertEqual(self.apply(trade).status_code, 200)

    def test_stale_preview_and_permissions_are_rejected(self):
        doc = self.seed()
        trade = self.create()
        preview = self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,
                                  json={"remoteMode": "app_only"}).get_json()
        doc["employees"][0]["slots"][0] = 22
        self.admin.post("/api/accepted-shifts", headers=self.headers, json=doc)
        response = self.admin.post(f"/api/shift-trades/{trade}/apply", headers=self.headers,
                                   json={"confirmed": True, "reason": "Apply", "fingerprint": preview["fingerprint"]})
        self.assertEqual(response.status_code, 409)
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(c.execute("SELECT state FROM shift_trades WHERE id=?", (trade,)).fetchone()[0], "approved")
        doc["employees"][0]["slots"][0] = 6
        doc["employees"][0]["shiftAvailability"] = {"14": None}
        self.admin.post("/api/accepted-shifts", headers=self.headers, json=doc)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,
                                        json={"remoteMode": "app_only"}).status_code, 409)
        self.assertEqual(scheduler.app.test_client().get("/api/shift-trades").status_code, 401)
        self.assertEqual(self.admin.post("/api/shift-trades", json={}).status_code, 400)

    def test_published_partial_failure_retry_does_not_repeat_success(self):
        doc = self.seed()
        trade = self.create()
        ops = [{"method": "POST", "path": "scheduling/shifts", "payload": {}, "state": "pending"},
               {"method": "DELETE", "path": "scheduling/shifts/old", "payload": None, "state": "pending"}]
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO shift_trade_publish VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                      (trade, scheduler.DEFAULT_TENANT_ID, "unused", "{}", json.dumps(doc), json.dumps(ops), "bamboohr", "pending"))
        with patch.object(scheduler, "bamboo_shift_request", side_effect=[
            {"success": True, "status": 201}, {"success": False, "status": 403},
        ]) as remote:
            result = self.admin.post(f"/api/shift-trades/{trade}/retry", headers=self.headers, json={"confirmed": True})
            self.assertEqual(result.status_code, 502)
            self.assertEqual(remote.call_count, 2)
        with patch.object(scheduler, "bamboo_shift_request", return_value={"success": True, "status": 204}) as remote:
            result = self.admin.post(f"/api/shift-trades/{trade}/retry", headers=self.headers, json={"confirmed": True})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(remote.call_count, 1)
            self.assertEqual(remote.call_args.args[1], "POST")

    def test_multi_day_remote_plan_and_reconciliation_cover_entire_date_range(self):
        doc = self.seed()
        doc["controls"]["rest"] = 0
        doc["employees"][0]["slots"][2] = 6
        doc["employees"][1]["slots"][2] = 14
        self.save_doc(doc)
        response = self.admin.post("/api/shift-trades", headers=self.headers, json={
            "runId": "trade-week", "days": [0, 2], "employeeA": "emp-a", "employeeB": "emp-b",
            "reason": "Two-day remote plan",
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        trade = response.get_json()["id"]
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE employees SET source_type='bamboohr',bamboohr_id='101' WHERE employee_id='emp-a'")
            c.execute("UPDATE employees SET source_type='bamboohr',bamboohr_id='102' WHERE employee_id='emp-b'")
            c.execute("UPDATE schedule_locations SET bamboo_schedule_id='501',role_group='Cashier' WHERE id='loc1'")
        start = scheduler.date.fromisoformat(doc["start"])
        remote = [{
            "id": f"{day}-{person}", "employeeIds": [numeric],
            "employees": [{"employeeId": person}], "scheduleId": "501",
            "start": (start + timedelta(days=day)).isoformat() + time,
            "end": (start + timedelta(days=day)).isoformat() + end,
        } for day in (0, 2) for person, numeric, time, end in (
            ("emp-a", "101", "T11:00:00+00:00", "T19:00:00+00:00"),
            ("emp-b", "102", "T19:00:00+00:00", "T23:00:00+00:00"),
        )]
        with patch.object(scheduler, "fetch_bamboohr_scheduled_shifts", return_value=remote) as reads, \
             patch.object(scheduler, "bamboo_shift_request", return_value={"success": False, "status": 500, "error": "Unknown outcome"}) as writes:
            preview = self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers, json={"remoteMode": "bamboohr"})
            self.assertEqual(preview.status_code, 200, preview.get_json())
            self.assertEqual(len(preview.get_json()["operations"]), 8)
            self.assertEqual(reads.call_count, 1)
            self.assertEqual(reads.call_args.args[1:], (start, start + timedelta(days=2)))
            applied = self.admin.post(f"/api/shift-trades/{trade}/apply", headers=self.headers, json={
                "confirmed": True, "reason": "Apply both days", "fingerprint": preview.get_json()["fingerprint"],
            })
            self.assertEqual(applied.status_code, 502, applied.get_json())
            writes.assert_called_once()
            self.assertEqual(applied.get_json()["remoteState"], "unknown")
            reads.reset_mock()
            reconciled = self.admin.post(f"/api/shift-trades/{trade}/reconcile", headers=self.headers,
                                         json={"confirmed": True, "reason": "Read all swapped days"})
            self.assertEqual(reconciled.status_code, 200, reconciled.get_json())
            self.assertEqual(reads.call_args.args[1:], (start, start + timedelta(days=2)))

    def test_retry_old_overlap_failed_plan_removes_both_originals_before_creating(self):
        doc = self.seed()
        trade = self.create()
        ops = [
            {"method": "POST", "path": "scheduling/shifts", "payload": {"employeeIds": [101]},
             "state": "failed", "result": {"success": False, "status": 422}},
            {"method": "DELETE", "path": "scheduling/shifts/old-a", "payload": None, "state": "pending"},
            {"method": "POST", "path": "scheduling/shifts", "payload": {"employeeIds": [102]}, "state": "pending"},
            {"method": "DELETE", "path": "scheduling/shifts/old-b", "payload": None, "state": "pending"},
        ]
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO shift_trade_publish VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                      (trade, scheduler.DEFAULT_TENANT_ID, "unused", "{}", json.dumps(doc),
                       json.dumps(ops), "bamboohr", "failed"))
        remaining = {"scheduling/shifts/old-a", "scheduling/shifts/old-b"}
        def remote_result(key, method, path, payload):
            if method == "DELETE":
                remaining.remove(path)
                return {"success": True, "status": 204}
            return {"success": not remaining, "status": 422 if remaining else 201}
        with patch.object(scheduler, "bamboo_shift_request", side_effect=remote_result) as writes:
            response = self.admin.post(f"/api/shift-trades/{trade}/retry", headers=self.headers,
                                       json={"confirmed": True})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual([call.args[1] for call in writes.call_args_list],
                         ["DELETE", "DELETE", "POST", "POST"])

    def test_failed_original_removal_does_not_attempt_replacement_creation(self):
        doc = self.seed()
        trade = self.create()
        ops = [{"method": "POST", "path": "scheduling/shifts", "payload": {}, "state": "pending"},
               {"method": "DELETE", "path": "scheduling/shifts/old", "payload": None, "state": "pending"}]
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO shift_trade_publish VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                      (trade, scheduler.DEFAULT_TENANT_ID, "unused", "{}", json.dumps(doc),
                       json.dumps(ops), "bamboohr", "pending"))
        with patch.object(scheduler, "bamboo_shift_request",
                          return_value={"success": False, "status": 403, "error": "Deletion denied"}) as writes:
            response = self.admin.post(f"/api/shift-trades/{trade}/retry", headers=self.headers,
                                       json={"confirmed": True})
        self.assertEqual(response.status_code, 502)
        self.assertIn("Deletion denied", response.get_json()["error"])
        writes.assert_called_once()
        self.assertEqual(writes.call_args.args[1], "DELETE")

    def test_remote_preview_uses_single_employee_payloads_and_rejects_shared_shifts(self):
        doc = self.seed()
        trade = self.create()
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE employees SET source_type='bamboohr',bamboohr_id='101' WHERE employee_id='emp-a'")
            c.execute("UPDATE employees SET source_type='bamboohr',bamboohr_id='102' WHERE employee_id='emp-b'")
            c.execute("UPDATE schedule_locations SET bamboo_schedule_id='501',role_group='Cashier' WHERE id='loc1'")
        remote = [
            {"id": "900", "employeeIds": ["101"], "employees": [{"employeeId": "emp-a"}],
             "scheduleId": "501", "start": doc["start"] + "T11:00:00+00:00",
             "end": doc["start"] + "T19:00:00+00:00"},
            {"id": "901", "employeeIds": ["102"], "employees": [{"employeeId": "emp-b"}],
             "scheduleId": "501", "start": doc["start"] + "T19:00:00+00:00",
             "end": doc["start"] + "T23:00:00+00:00"},
        ]
        with patch.object(scheduler, "fetch_bamboohr_scheduled_shifts", return_value=remote), \
             patch.object(scheduler, "bamboo_shift_request", return_value={"success": True, "status": 201}) as writes:
            response = self.apply(trade, "bamboohr")
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(writes.call_count, 4)
            self.assertEqual([call.args[1] for call in writes.call_args_list],
                             ["DELETE", "DELETE", "POST", "POST"])
            creates = [call.args[3] for call in writes.call_args_list if call.args[1] == "POST"]
            self.assertEqual([payload["employeeIds"] for payload in creates], [[101], [102]])
            self.assertEqual(creates[0]["scheduleId"], 501)
        # A second approved trade cannot delete a shared BambooHR shift.
        trade2 = self.create()
        remote[0]["employeeIds"] = ["101", "102"]
        with patch.object(scheduler, "fetch_bamboohr_scheduled_shifts", return_value=remote), \
             patch.object(scheduler, "bamboo_shift_request") as writes:
            result = self.admin.post(f"/api/shift-trades/{trade2}/preview", headers=self.headers,
                                     json={"remoteMode": "bamboohr"})
            self.assertEqual(result.status_code, 409)
            writes.assert_not_called()

    def test_remote_preview_and_application_preserve_uuid_schedule_id(self):
        self.seed()
        trade = self.create()
        schedule_id = "01a0fea5-d380-7271-90cc-98e6a4a24321"
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE schedule_locations SET bamboo_schedule_id='unused-test-mapping' WHERE bamboo_schedule_id=?",
                      (schedule_id,))
            c.execute("UPDATE employees SET source_type='bamboohr',bamboohr_id='101' WHERE employee_id='emp-a'")
            c.execute("UPDATE employees SET source_type='bamboohr',bamboohr_id='102' WHERE employee_id='emp-b'")
            c.execute("UPDATE schedule_locations SET bamboo_schedule_id=?,role_group='Cashier' WHERE id='loc1'",
                      (schedule_id,))
        with patch.object(scheduler, "fetch_bamboohr_scheduled_shifts", return_value=[]), \
             patch.object(scheduler, "bamboo_shift_request", return_value={"success": True, "status": 201}) as writes:
            preview = self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,
                                      json={"remoteMode": "bamboohr"})
            self.assertEqual(preview.status_code, 200, preview.get_json())
            writes.assert_not_called()
            operations = preview.get_json()["operations"]
            self.assertEqual([op["payload"]["scheduleId"] for op in operations], [schedule_id, schedule_id])
            self.assertEqual([op["payload"]["employeeIds"] for op in operations], [[101], [102]])
            applied = self.admin.post(f"/api/shift-trades/{trade}/apply", headers=self.headers,
                                      json={"confirmed": True, "reason": "Test UUID mapping",
                                            "fingerprint": preview.get_json()["fingerprint"]})
            self.assertEqual(applied.status_code, 200, applied.get_json())
            self.assertEqual(writes.call_count, 2)
            self.assertTrue(all(call.args[3]["scheduleId"] == schedule_id for call in writes.call_args_list))

    def test_manual_day_off_and_constraint_override_are_audited(self):
        self.seed()
        response = self.admin.post("/api/shift-overrides", headers=self.headers, json={
            "runId": "trade-week", "employeeId": "emp-a", "day": 0, "start": None,
            "confirmed": True, "reason": "Approved day off",
        })
        self.assertEqual(response.status_code, 201)
        trade = response.get_json()["id"]
        self.assertEqual(self.apply(trade).status_code, 200)
        with closing(scheduler.database_connect()) as c:
            doc = json.loads(c.execute("SELECT payload FROM accepted_schedules WHERE run_id='trade-week'").fetchone()[0])
            self.assertIsNone(doc["employees"][0]["slots"][0])
            self.assertEqual(doc["employees"][1]["slots"][0], 14)
        self.assertEqual(self.admin.get("/api/shift-trades").get_json()["unread"], 1)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/read", headers=self.headers,
                                         json={"version": 2}).status_code, 200)
        self.assertEqual(self.admin.get("/api/shift-trades").get_json()["unread"], 0)

    def test_non_admin_started_shifts_and_stale_confirmation_are_blocked(self):
        doc = self.seed()
        manager, _, _ = self.sign_in_manager()
        response = manager.post("/api/access/trades", headers=self.csrf, json={
            "runId": "trade-week", "day": 0, "employeeA": "emp-a", "employeeB": "emp-b", "reason": "Team request",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["state"], "manager_accepted")
        trade = response.get_json()["id"]
        doc["employees"][1]["slots"][0] = 22
        self.admin.post("/api/accepted-shifts", headers=self.headers, json=doc)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/action", headers=self.headers,
            json={"action": "approve", "version": 1, "reason": "Stale"}).status_code, 409)
        doc["id"] = "past-week"
        doc["start"] = (scheduler.date.fromisoformat(doc["start"]) - timedelta(weeks=2)).isoformat()
        self.admin.post("/api/accepted-shifts", headers=self.headers, json=doc)
        self.assertEqual(manager.post("/api/access/trades", headers=self.csrf, json={
            "runId": "past-week", "day": 0, "employeeA": "emp-a", "employeeB": "emp-b", "reason": "Past",
        }).status_code, 409)

    def test_linked_manager_confirms_only_in_personal_trade_view(self):
        self.seed()
        manager, secret, created = self.sign_in_manager()
        result = self.admin.put(f"/api/access-accounts/{created['account']['id']}/employee",
                                headers=self.headers, json={"employeeId": "emp-b"})
        self.assertEqual(result.status_code, 200)
        manager = self.new_client()
        response = manager.post("/api/access/login", headers=self.csrf, json={
            "bamboohrSubdomain": "acme", "identifier": "mgr@acme.example",
            "password": "Manager-New-Password-2026!",
            "code": scheduler.totp_value(secret, int(time.time() // 30)),
        })
        manager_headers = {"X-CSRF-Token": response.get_json()["csrfToken"]}
        self.assertIsNone(manager.get("/api/access/trades/choices").get_json()["lockedLocation"])
        personal_choices = manager.get("/api/access/trades/choices?view=employee").get_json()
        self.assertEqual(personal_choices["employee1"], "emp-b")
        self.assertEqual(personal_choices["lockedLocation"]["id"], "loc1")
        employee = self.portal_employee_client()
        trade = self.create(employee, self.csrf.copy())
        body = {"action": "confirm", "version": 1, "reason": "My own trade"}
        self.assertEqual(manager.post(f"/api/access/trades/{trade}/action",
            headers=manager_headers, json=body).status_code, 403)
        self.assertEqual(manager.post(f"/api/access/trades/{trade}/action?view=employee",
            headers=manager_headers, json=body).status_code, 200)
        self.assertEqual(manager.post(f"/api/access/trades/{trade}/action?view=employee",
            headers=manager_headers, json=dict(body, action="accept", version=2)).status_code, 403)

    def test_admin_constraint_override_requires_explicit_flag(self):
        doc = self.seed()
        doc["employees"][0]["days"] = [False, True, True, True, True, True, True]
        self.admin.post("/api/accepted-shifts", headers=self.headers, json=doc)
        body = {"runId": "trade-week", "employeeId": "emp-a", "day": 0, "start": 14,
                "confirmed": True, "reason": "Exceptional coverage"}
        trade = self.admin.post("/api/shift-overrides", headers=self.headers, json=body).get_json()["id"]
        result = self.admin.post(f"/api/shift-trades/{trade}/preview", headers=self.headers,
                                 json={"remoteMode": "app_only"})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/action", headers=self.headers,
            json={"action": "reject", "version": 1, "reason": "Replace with explicit override"}).status_code, 200)
        trade = self.admin.post("/api/shift-overrides", headers=self.headers,
                                json=dict(body, overrideConstraints=True)).get_json()["id"]
        self.assertEqual(self.apply(trade).status_code, 200)

    def test_unknown_trade_write_needs_read_reconciliation_before_retry(self):
        doc = self.seed()
        trade = self.create()
        payload = {"scheduleId": 501, "employeeIds": [101], "start": doc["start"] + "T19:00:00+00:00",
                   "end": doc["start"] + "T23:00:00+00:00"}
        ops = [{"method": "POST", "path": "scheduling/shifts", "payload": payload, "state": "unknown"}]
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO shift_trade_publish VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                      (trade, scheduler.DEFAULT_TENANT_ID, "unused", "{}", json.dumps(doc), json.dumps(ops), "bamboohr", "unknown"))
        with patch.object(scheduler, "bamboo_shift_request") as writes:
            self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/retry", headers=self.headers,
                                             json={"confirmed": True}).status_code, 409)
            with patch.object(scheduler, "fetch_bamboohr_scheduled_shifts",
                              return_value=[dict(payload, id="901", employeeIds=["101"])]):
                result = self.admin.post(f"/api/shift-trades/{trade}/reconcile", headers=self.headers,
                                          json={"confirmed": True, "reason": "Verified unknown remote result"})
                self.assertEqual(result.status_code, 200, result.get_json())
                self.assertEqual(result.get_json()["operations"][0]["state"], "success")
            self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/retry", headers=self.headers,
                                             json={"confirmed": True}).status_code, 200)
            writes.assert_not_called()


    def test_unknown_missing_write_requires_explicit_retry_and_duplicate_matches_block_it(self):
        doc = self.seed()
        payload = {"scheduleId": 501, "employeeIds": [101],
                   "start": doc["start"] + "T19:00:00+00:00",
                   "end": doc["start"] + "T23:00:00+00:00"}
        trade = self.create()
        ops = [{"method": "POST", "path": "scheduling/shifts",
                "payload": payload, "state": "unknown"}]
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO shift_trade_publish VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                      (trade, scheduler.DEFAULT_TENANT_ID, "unused", "{}", json.dumps(doc),
                       json.dumps(ops), "bamboohr", "unknown"))
        body = {"confirmed": True, "reason": "Isolated recovery verification"}
        with patch.object(scheduler, "bamboo_shift_request") as writes:
            duplicates = [dict(payload, id=str(i)) for i in (901, 902)]
            with patch.object(scheduler, "fetch_bamboohr_scheduled_shifts", return_value=duplicates):
                response = self.admin.post(f"/api/shift-trades/{trade}/reconcile",
                                           headers=self.headers, json=body)
                self.assertEqual(response.status_code, 409)
                self.assertIn("Duplicate", response.get_json()["error"])
            self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/retry",
                                            headers=self.headers, json={"confirmed": True}).status_code, 409)
            with patch.object(scheduler, "fetch_bamboohr_scheduled_shifts", return_value=[]):
                response = self.admin.post(f"/api/shift-trades/{trade}/reconcile",
                                           headers=self.headers, json=body)
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertEqual(response.get_json()["operations"][0]["state"], "pending")
            writes.assert_not_called()
            self.assertEqual(self.admin.post(f"/api/shift-trades/{trade}/retry",
                                            headers=self.headers, json={"confirmed": False}).status_code, 400)
            writes.assert_not_called()
        with patch.object(scheduler, "bamboo_shift_request",
                          return_value={"success": True, "status": 201}) as writes:
            response = self.admin.post(f"/api/shift-trades/{trade}/retry",
                                       headers=self.headers, json={"confirmed": True})
            self.assertEqual(response.status_code, 200, response.get_json())
            writes.assert_called_once()
            self.assertEqual(response.get_json()["state"], "published")


class BillingWorkflowTests(unittest.TestCase):
    def setUp(self):
        test_scheduler.ManagerEmployeeAccessTests.setUp(self)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE tenant_admins SET is_primary=1")

    tearDown = test_scheduler.ManagerEmployeeAccessTests.tearDown
    headers = {"X-CSRF-Token": "test-csrf-token"}

    def seed(self, state="idle"):
        tenant = scheduler.DEFAULT_TENANT_ID
        with closing(scheduler.database_connect()) as c, c:
            settings = {"enabled": True, "prices": {f"{tier}:{period}": "10.00"
                        for tier in scheduler.MEMBERSHIP_TIERS for period in ("monthly", "annual")},
                        "plans": {}, "features": {}}
            c.execute("INSERT INTO billing_configuration VALUES(1,?,CURRENT_TIMESTAMP)", (json.dumps(settings),))
            c.execute("INSERT INTO billing_accounts(tenant_id,subscription_id,checkout_id,tier,period,"
                      "auto_renew,provider_status,retry_state,next_retry) VALUES(?,'I-TEST','checkout-test','silver','monthly',1,'ACTIVE',?,?)",
                      (tenant, state, int(time.time()) - 1))
            c.execute("INSERT INTO billing_subscription_index VALUES('I-TEST',?)", (tenant,))
        return tenant

    def subscription(self, balance="0.00"):
        return {"id": "I-TEST", "custom_id": "checkout-test", "status": "ACTIVE",
                "billing_info": {"last_payment": {"time": scheduler.datetime.now(scheduler.timezone.utc).isoformat()},
                                 "outstanding_balance": {"value": balance, "currency_code": "USD"}}}

    def test_disabled_checkout_and_webhook_signature(self):
        result = self.admin.post("/api/business/billing", headers=self.headers,
                                json={"confirmed": True, "tier": "silver", "period": "monthly", "autoRenew": True})
        self.assertEqual(result.status_code, 503)
        with patch.object(scheduler.billing_provider, "verify_webhook", return_value=False):
            self.assertEqual(scheduler.app.test_client().post("/api/payments/paypal/webhook",
                              json={"id": "event-1"}).status_code, 400)

    def test_verified_webhook_is_idempotent_and_preserves_manual_pause(self):
        tenant = self.seed()
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE tenants SET membership_status='paused' WHERE tenant_id=?", (tenant,))
            c.execute("UPDATE billing_accounts SET access_state='suspended' WHERE tenant_id=?", (tenant,))
        with patch.object(scheduler.billing_provider, "verify_webhook", return_value=True), \
             patch.object(scheduler.billing_provider, "subscription", return_value=self.subscription()):
            client = scheduler.app.test_client()
            event = {"id": "event-1", "event_type": "PAYMENT.SALE.COMPLETED", "resource": {"billing_agreement_id": "I-TEST"}}
            self.assertEqual(client.post("/api/payments/paypal/webhook", json=event).status_code, 200)
            self.assertTrue(client.post("/api/payments/paypal/webhook", json=event).get_json()["duplicate"])
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(c.execute("SELECT membership_status FROM tenants WHERE tenant_id=?", (tenant,)).fetchone()[0], "paused")
            self.assertEqual(c.execute("SELECT access_state FROM billing_accounts WHERE tenant_id=?", (tenant,)).fetchone()[0], "active")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM billing_events WHERE kind='payment-reconciled'").fetchone()[0], 1)

    def test_daily_retry_ceiling_and_unknown_outcomes(self):
        tenant = self.seed("failed")
        with patch.object(scheduler.billing_provider, "subscription", return_value=self.subscription("10.00")), \
             patch.object(scheduler.billing_provider, "api", side_effect=billing.PaymentError("Sandbox declined")) as capture:
            for number in range(7):
                with closing(scheduler.database_connect()) as c, c:
                    c.execute("UPDATE billing_accounts SET next_retry=? WHERE tenant_id=?", (int(time.time()) - 1, tenant))
                with scheduler.app.app_context():
                    billing.run_once(scheduler, scheduler.billing_provider)
            with scheduler.app.app_context():
                billing.run_once(scheduler, scheduler.billing_provider)
            self.assertEqual(capture.call_count, 7)
        with closing(scheduler.database_connect()) as c, c:
            row = c.execute("SELECT retry_count,retry_state,access_state FROM billing_accounts").fetchone()
            self.assertEqual(row, (7, "exhausted", "suspended"))
            c.execute("UPDATE billing_accounts SET retry_count=0,retry_state='failed',next_retry=?", (int(time.time()) - 1,))
        with patch.object(scheduler.billing_provider, "subscription", return_value=self.subscription("10.00")), \
             patch.object(scheduler.billing_provider, "api", side_effect=billing.PaymentError("Unknown result", unknown=True)) as capture:
            with scheduler.app.app_context():
                billing.run_once(scheduler, scheduler.billing_provider)
                billing.run_once(scheduler, scheduler.billing_provider)
            self.assertEqual(capture.call_count, 1)
        self.assertEqual(self.admin.get("/api/accepted-shifts").status_code, 403)

    def test_manual_payment_audited_and_owner_configuration_validation(self):
        tenant = self.seed("exhausted")
        with patch.object(scheduler, "platform_owner_guard", return_value=None):
            result = self.admin.post("/api/hub/billing/manual-payment", json={
                "confirmed": True, "tenantId": tenant, "reason": "Verified external payment",
                "paidUntil": (scheduler.datetime.now(scheduler.timezone.utc) + timedelta(days=30)).isoformat(),
            })
            self.assertEqual(result.status_code, 200, result.get_json())
            result = self.admin.put("/api/hub/billing", json={
                "confirmed": True, "enabled": False, "prices": {"silver:monthly": "-1"},
            })
            self.assertEqual(result.status_code, 400)
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(c.execute("SELECT retry_state FROM billing_accounts").fetchone()[0], "manual")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM hub_audit_events WHERE action='manual-payment'").fetchone()[0], 1)

    def test_owner_feature_form_definitions_and_override_round_trip(self):
        self.seed()
        prices = {f"{tier}:{period}": "10.00" for tier in scheduler.MEMBERSHIP_TIERS for period in ("monthly", "annual")}
        with patch.object(scheduler, "platform_owner_guard", return_value=None):
            result = self.admin.get("/api/hub/billing")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.get_json()["tierDefinitions"], scheduler.MEMBERSHIP_TIERS)
            result = self.admin.put("/api/hub/billing", json={
                "confirmed": True, "enabled": False, "prices": prices,
                "features": {"bronze": {"shiftTrades": True}, "gold": {"overtimeForecasting": False}},
            })
            self.assertEqual(result.status_code, 200, result.get_json())
            self.assertEqual(result.get_json()["configuration"]["features"]["gold"]["overtimeForecasting"], False)
            result = self.admin.put("/api/hub/billing", json={
                "confirmed": True, "enabled": False, "prices": prices, "features": {},
            })
            self.assertEqual(result.status_code, 200, result.get_json())
            self.assertEqual(self.admin.get("/api/hub/billing").get_json()["configuration"]["features"], {})

    def test_sandbox_hosted_checkout_and_cancel_do_not_bypass_suspension(self):
        prices = {f"{tier}:{period}": "10.00" for tier in scheduler.MEMBERSHIP_TIERS for period in ("monthly", "annual")}
        plan = "P-" + "A" * 24
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO billing_configuration VALUES(1,?,CURRENT_TIMESTAMP)", (json.dumps({
                "enabled": True, "prices": prices, "plans": {"silver:monthly:1": plan}, "features": {},
            }),))
        checkout = {"id": "I-TEST", "status": "APPROVAL_PENDING", "links": [
            {"rel": "approve", "href": "https://www.sandbox.paypal.com/checkout/test"},
        ]}
        with patch.object(scheduler.billing_provider, "configured", return_value=True), \
             patch.object(scheduler.billing_provider, "api", return_value=checkout) as provider:
            result = self.admin.post("/api/business/billing", headers=self.headers, json={
                "confirmed": True, "tier": "silver", "period": "monthly", "autoRenew": True,
            })
            self.assertEqual(result.status_code, 201, result.get_json())
            self.assertEqual(provider.call_args.args[2]["plan_id"], plan)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE billing_accounts SET access_state='suspended'")
        with patch.object(scheduler.billing_provider, "subscription", return_value=dict(self.subscription(), status="CANCELLED")):
            result = self.admin.post("/api/business/billing/cancel", headers=self.headers, json={"confirmed": True})
            self.assertEqual(result.status_code, 200)
        self.assertEqual(self.admin.get("/api/accepted-shifts").status_code, 403)

    def test_live_retry_lease_is_not_stolen_and_read_failures_do_not_count_as_charges(self):
        tenant = self.seed("running")
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE billing_accounts SET next_retry=?", (int(time.time()) + 3600,))
        with patch.object(scheduler.billing_provider, "subscription") as provider:
            with scheduler.app.app_context():
                billing.run_once(scheduler, scheduler.billing_provider)
            provider.assert_not_called()
        with closing(scheduler.database_connect()) as c, c:
            self.assertEqual(c.execute("SELECT retry_state FROM billing_accounts").fetchone()[0], "running")
            c.execute("UPDATE billing_accounts SET retry_state='failed',next_retry=?", (int(time.time()) - 1,))
        with patch.object(scheduler.billing_provider, "subscription", side_effect=billing.PaymentError("Read unavailable")):
            with scheduler.app.app_context():
                billing.run_once(scheduler, scheduler.billing_provider)
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(c.execute("SELECT retry_count FROM billing_accounts WHERE tenant_id=?", (tenant,)).fetchone()[0], 0)

    def test_import_preserves_workflows_revokes_user_sessions_and_disables_billing(self):
        self.seed()
        TradeWorkflowTests.seed(self)
        trade = TradeWorkflowTests.create(self)
        self.assertEqual(TradeWorkflowTests.apply(self, trade).status_code, 200)
        account = self.admin.post("/api/access-accounts", headers=self.headers,
                                  json={"role": "employee", "employeeId": "emp-a"}).get_json()["account"]
        source = scheduler.DATABASE_PATH
        destination = Path(self.temporary_directory.name) / "migration-target.sqlite3"
        scheduler.DATABASE_PATH = destination
        scheduler.initialize_database()
        with closing(scheduler.database_connect()) as c, c:
            for table, columns in (
                ("schedule_locations", "tenant_id,id"), ("employees", "tenant_id,employee_id"),
                ("accepted_schedules", "tenant_id,run_id"),
                ("attendance_time_entries", "tenant_id,entry_id"),
                ("attendance_shift_records", "tenant_id,schedule_run_id,employee_id,shift_date"),
                ("attendance_score_overrides", "tenant_id,employee_id"),
                ("application_settings", "tenant_id,setting_key"),
            ):
                c.execute(f"CREATE UNIQUE INDEX migration_{table}_key ON {table}({columns})")
        # Exercise the import SQL on SQLite without opening any PostgreSQL connection.
        with patch.object(scheduler, "DATABASE_URL", "postgresql://test-only"), \
             patch.object(scheduler, "database_connect", side_effect=lambda: sqlite3.connect(destination)):
            scheduler.migrate_sqlite_business_data(source)
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(c.execute("SELECT state FROM shift_trades WHERE id=?", (trade,)).fetchone()[0], "applied")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM shift_trade_events").fetchone()[0], 2)
            self.assertEqual(c.execute("SELECT auth_version FROM tenant_users WHERE id=?", (account["id"],)).fetchone()[0], 2)
            self.assertEqual(c.execute("SELECT membership_tier FROM tenants WHERE tenant_id=?",
                                      (scheduler.DEFAULT_TENANT_ID,)).fetchone()[0], "silver")
            self.assertFalse(billing.config(c)["enabled"])


if __name__ == "__main__":
    unittest.main()
