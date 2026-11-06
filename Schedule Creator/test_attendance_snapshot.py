import base64
import hashlib
import json
import re
import unittest
from contextlib import closing
from datetime import datetime
from unittest.mock import patch

import attendance_reports
import attendance_snapshot
import scheduler
import test_scheduler


LOGO = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0c8AAAAASUVORK5CYII="


def example_payload():
    base = {
        "runId": "fixture", "employeeId": "1", "name": "Alex Example",
        "location": "Kingston", "role": "Warehouse", "date": "2026-11-06",
        "shiftStart": "2026-11-06T06:00:00-05:00", "shiftEnd": "2026-11-06T14:00:00-05:00",
        "status": "attended", "source": "bamboohr", "reason": "",
        "clockIn": "2026-11-06T06:00:00-05:00", "clockOut": "2026-11-06T14:00:00-05:00",
        "workedMinutes": 480, "earlyMinutes": 0, "overtimeMinutes": 0,
    }
    rows = [
        base,
        base | {"employeeId": "2", "name": "Blair Example", "status": "late",
                "clockIn": "2026-11-06T07:00:00-05:00", "workedMinutes": 420},
        base | {"employeeId": "3", "name": "Casey Example", "status": "late",
                "clockIn": None, "clockOut": None, "workedMinutes": None,
                "reason": "No matching clock-in after lateness tolerance."},
        base | {"employeeId": "4", "name": "Devon Example", "status": "absent",
                "clockIn": None, "clockOut": None, "workedMinutes": None},
        base | {"employeeId": "5", "name": "Eden Example", "status": "approved_leave",
                "clockIn": None, "clockOut": None, "workedMinutes": None},
        base | {"employeeId": "6", "name": "Flynn Example", "location": "Ferry", "role": "Dispatch",
                "status": "scheduled", "shiftStart": "2026-11-06T14:00:00-05:00",
                "shiftEnd": "2026-11-06T22:00:00-05:00", "clockIn": "2026-11-06T14:45:00-05:00",
                "clockOut": None, "workedMinutes": 15},
        base | {"employeeId": "7", "name": "Gray Example", "location": "Ferry", "role": "Dispatch",
                "clockOut": None, "workedMinutes": 540, "overtimeMinutes": 61},
        base | {"employeeId": "8", "name": "Hayden Example", "location": "Ferry", "role": "Dispatch",
                "clockOut": "2026-11-06T12:00:00-05:00", "workedMinutes": 360, "earlyMinutes": 120},
    ]
    return {
        "cutoff": "2026-11-06T15:00:00-05:00", "generatedAt": "2026-11-06T15:00:30-05:00",
        "businessName": "Example Logistics", "logoDataUrl": LOGO, "refreshError": "",
        "attendance": {"shifts": rows, "lastSyncedAt": "2026-11-06T15:00:00-05:00",
                       "settings": {"latenessToleranceMinutes": 15}, "shiftSource": {"selected": "app"}},
    }


class SnapshotHtmlTests(unittest.TestCase):
    setUp = test_scheduler.ManagerEmployeeAccessTests.setUp
    tearDown = test_scheduler.ManagerEmployeeAccessTests.tearDown
    create_account = test_scheduler.ManagerEmployeeAccessTests.create_account
    new_client = test_scheduler.ManagerEmployeeAccessTests.new_client
    portal_employee_client = test_scheduler.ManagerEmployeeAccessTests.portal_employee_client
    headers = {"X-CSRF-Token": "test-csrf-token"}

    def save(self, payload=None, state="ready", tenant=None):
        payload = payload or example_payload()
        payload["workbook"] = base64.b64encode(attendance_reports.workbook(payload)).decode()
        if "html" not in payload:
            payload["html"] = attendance_snapshot.render(payload)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO attendance_reports(tenant_id,id,run_key,cutoff,created_at,state,payload) VALUES(?,?,?,?,?,?,?)",
                      (tenant or scheduler.DEFAULT_TENANT_ID, "html-fixture", "manual:html-fixture",
                       payload["cutoff"], payload["generatedAt"], state, json.dumps(payload)))
        return payload

    def test_html_authorized_view_download_and_immutable_branding(self):
        payload = self.save()
        path = "/api/attendance/reports/html-fixture/html"
        view = self.admin.get(path)
        self.assertEqual(view.status_code, 200)
        self.assertEqual(view.mimetype, "text/html")
        self.assertIn("inline", view.headers["Content-Disposition"])
        self.assertEqual(view.headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", view.headers["Content-Security-Policy"])
        self.assertEqual(view.data.decode(), payload["html"])
        download = self.admin.get(path + "/download")
        self.assertEqual(view.data, download.data)
        self.assertIn("attachment", download.headers["Content-Disposition"])
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO application_settings(tenant_id,setting_key,setting_value) VALUES(?, 'logoDataUrl', '') ON CONFLICT(tenant_id,setting_key) DO UPDATE SET setting_value=excluded.setting_value",
                      (scheduler.DEFAULT_TENANT_ID,))
            c.execute("DELETE FROM employees")
        with patch.object(attendance_snapshot, "render", side_effect=AssertionError("Must use persisted HTML")):
            self.assertEqual(self.admin.get(path).data, view.data)

    def test_html_authorization_entitlement_and_unavailable_states(self):
        self.save()
        paths = ["/api/attendance/reports/html-fixture/html", "/api/attendance/reports/html-fixture/html/download"]
        employee = self.portal_employee_client()
        for path in paths:
            self.assertEqual(scheduler.app.test_client().get(path).status_code, 401)
            self.assertEqual(employee.get(path).status_code, 401)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE tenants SET membership_tier='bronze'")
        for path in paths:
            self.assertEqual(self.admin.get(path).status_code, 403)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE tenants SET membership_tier='silver'")
            c.execute("UPDATE attendance_reports SET state='missed'")
        for path in paths:
            self.assertEqual(self.admin.get(path).status_code, 409)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE attendance_reports SET state='ready',tenant_id='another-business'")
        for path in paths:
            self.assertEqual(self.admin.get(path).status_code, 404)

    def test_legacy_html_uses_saved_evidence_without_current_logo_or_writes(self):
        payload = self.save()
        payload.pop("html")
        payload.pop("businessName")
        payload.pop("logoDataUrl")
        encoded = json.dumps(payload)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE attendance_reports SET payload=?", (encoded,))
        with patch.object(scheduler, "current_app_config", side_effect=AssertionError("No current branding")):
            response = self.admin.get("/api/attendance/reports/html-fixture/html")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"logoDataUrl": ""', response.data)
        self.assertNotIn(LOGO.encode(), response.data)
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(c.execute("SELECT payload FROM attendance_reports").fetchone()[0], encoded)

    def test_new_captures_persist_saved_logo_and_complete_html(self):
        with closing(scheduler.database_connect()) as c, c:
            for key, value in (("logoDataUrl", LOGO), ("businessName", "Snapshot Business")):
                c.execute("INSERT INTO application_settings(tenant_id,setting_key,setting_value) VALUES(?,?,?) ON CONFLICT(tenant_id,setting_key) DO UPDATE SET setting_value=excluded.setting_value",
                          (scheduler.DEFAULT_TENANT_ID, key, value))
        with patch.object(scheduler, "bamboohr_api_key", return_value=""):
            result = self.admin.post("/api/attendance/reports", headers=self.headers, json={})
        self.assertEqual(result.status_code, 201)
        with closing(scheduler.database_connect()) as c:
            payload = json.loads(c.execute("SELECT payload FROM attendance_reports").fetchone()[0])
        self.assertEqual(payload["logoDataUrl"], LOGO)
        self.assertEqual(payload["businessName"], "Snapshot Business")
        self.assertIn('"logoDataUrl": "' + LOGO + '"', payload["html"])
        self.assertIn("Source warning:", payload["html"])

    def test_inert_data_content_policy_and_self_contained_assets(self):
        payload = example_payload()
        attack = '</script><img src=x onerror="alert(1)"><script>alert(2)</script>'
        payload["attendance"]["shifts"][0]["name"] = attack
        payload["businessName"] = attack
        payload["workbook"] = "workbook-is-not-part-of-html"
        html = attendance_snapshot.render(payload)
        self.assertNotIn(attack, html)
        self.assertNotIn(payload["workbook"], html)
        self.assertIn("\\u003c/script\\u003e", html)
        self.assertNotRegex(html, r'<(?:script|link)[^>]+(?:src|href)=')
        self.assertNotIn("__SNAPSHOT_", html)
        for kind in ("style", "script"):
            for block in re.findall(rf"<{kind}>(.*?)</{kind}>", html, re.DOTALL):
                digest = base64.b64encode(hashlib.sha256(block.encode()).digest()).decode()
                self.assertIn("'sha256-" + digest + "'", html)
        self.assertIn("img-src data:", html)
        self.assertIn("default-src 'none'", html)
        data = json.loads(re.search(r'<script id="snapshot-data" type="application/json">(.*?)</script>', html).group(1))
        self.assertEqual(data["shifts"][0]["name"], attack)
        self.assertLess(html.index("Executive highlights"), html.index("Employee exceptions and risks"))

    def test_template_placeholder_literals_in_names_remain_inert_data(self):
        payload = example_payload()
        name = "__SNAPSHOT_CSP__ __SNAPSHOT_DATA__"
        payload["businessName"] = name
        payload["attendance"]["shifts"][0]["name"] = name
        html = attendance_snapshot.render(payload)
        data = json.loads(re.search(r'<script id="snapshot-data" type="application/json">(.*?)</script>', html).group(1))
        self.assertEqual(data["businessName"], name)
        self.assertEqual(data["shifts"][0]["name"], name)

    def test_invalid_saved_logo_is_explicit_capture_failure(self):
        now = datetime.now(scheduler.ATTENDANCE_TIMEZONE)
        with scheduler.app.app_context(), patch.object(scheduler, "bamboohr_api_key", return_value=""), patch.object(
            scheduler, "current_app_config", return_value={"logoDataUrl": "https://example.invalid/logo.png", "businessName": "Business"}
        ):
            with self.assertRaisesRegex(ValueError, "saved business logo is invalid"):
                attendance_reports.capture(scheduler, scheduler.DEFAULT_TENANT_ID, now, "manual:invalid-logo")
        with closing(scheduler.database_connect()) as c:
            state, payload, error = c.execute("SELECT state,payload,error FROM attendance_reports").fetchone()
        self.assertEqual(state, "failed")
        self.assertEqual(payload, "{}")
        self.assertIn("saved business logo is invalid", error)

    def test_generation_failure_does_not_save_partial_success(self):
        now = datetime.now(scheduler.ATTENDANCE_TIMEZONE)
        with scheduler.app.app_context(), patch.object(scheduler, "bamboohr_api_key", return_value=""), patch.object(attendance_snapshot, "render", side_effect=ValueError("Invalid snapshot template")):
            with self.assertRaisesRegex(ValueError, "Invalid snapshot template"):
                attendance_reports.capture(scheduler, scheduler.DEFAULT_TENANT_ID, now, "manual:html-failure")
        with closing(scheduler.database_connect()) as c:
            state, payload, error = c.execute("SELECT state,payload,error FROM attendance_reports").fetchone()
        self.assertEqual(state, "failed")
        self.assertEqual(payload, "{}")
        self.assertIn("Invalid snapshot template", error)

    def test_change_request_is_recorded_with_existing_report_dependency(self):
        with closing(scheduler.database_connect()) as c:
            row = c.execute("SELECT title,description,status FROM developer_change_requests WHERE request_id='interactive-attendance-snapshot'").fetchone()
            dependency = c.execute("SELECT depends_on FROM developer_change_request_dependencies WHERE request_id='interactive-attendance-snapshot'").fetchone()
        self.assertIn("Interactive branded HTML", row[0])
        self.assertIn("company logo", row[1])
        self.assertEqual(row[2], "pending")
        self.assertEqual(dependency, ("snapshot-email-reports",))


if __name__ == "__main__":
    unittest.main()
