import io
import json
import unittest
import zipfile
from contextlib import closing
from datetime import datetime, timedelta
from unittest.mock import patch
from xml.etree import ElementTree

import attendance_reports as reports
import scheduler
import test_scheduler
import test_workforce_workflows as workflows


class ApplicationReportTests(unittest.TestCase):
    setUp = test_scheduler.ManagerEmployeeAccessTests.setUp
    tearDown = test_scheduler.ManagerEmployeeAccessTests.tearDown
    create_account = test_scheduler.ManagerEmployeeAccessTests.create_account
    new_client = test_scheduler.ManagerEmployeeAccessTests.new_client
    portal_employee_client = test_scheduler.ManagerEmployeeAccessTests.portal_employee_client
    headers = {"X-CSRF-Token": "test-csrf-token"}

    def test_shared_routes_keep_admin_workspace_and_assets(self):
        anon = scheduler.app.test_client()
        for client, path, text in (
            (anon, "/", b'Account experience'),
            (anon, "/?legacyLogin=1", b'Create administrator'),
            (self.admin, "/", b'CBL-Scheduler2'),
            (self.admin, "/app/business", b'<base href="/">'),
        ):
            with client.get(path) as response:
                self.assertEqual(response.status_code, 200)
                self.assertIn(text, response.data)
        with self.admin.get("/app/trades?adminView=1&trade=123") as response:
            self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        for asset in ("application-shell.js", "application-shell.css", "attendance-reports.js"):
            with anon.get("/" + asset) as response:
                self.assertEqual(response.status_code, 200)
        response = anon.get("/app/trades?trade=123")
        self.assertEqual(response.status_code, 302)
        self.assertIn("experience=workforce", response.location)
        self.assertIn("next=", response.location)

    def test_shell_authorization_and_branding_do_not_merge_identities(self):
        employee = self.portal_employee_client()
        data = employee.get("/api/access/application-state").get_json()
        self.assertEqual(data["role"], "employee")
        self.assertFalse(data["isPrimaryAdmin"])
        self.assertNotIn("apiKeyConfigured", data)
        self.assertEqual(employee.get("/api/application/state").status_code, 401)
        self.assertEqual(employee.get("/api/hub/application-state").status_code, 401)
        self.assertEqual(employee.get("/app/business").status_code, 302)
        with employee.get("/app/access") as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.admin.get("/api/application/state").get_json()["role"], "admin")
        self.assertEqual(self.admin.get("/api/hub/application-state").status_code, 401)
        self.assertEqual(self.admin.get("/app/owner").status_code, 302)

    def test_snapshot_entitlement_csrf_primary_and_tenant_scope(self):
        endpoint = "/api/attendance/reports"
        employee = self.portal_employee_client()
        self.assertEqual(employee.get(endpoint).status_code, 401)
        self.assertEqual(self.admin.post(endpoint, json={}).status_code, 400)
        self.assertEqual(self.admin.put(endpoint, headers=self.headers, json={"enabled": "yes"}).status_code, 400)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE tenant_admins SET is_primary=0")
        self.assertEqual(self.admin.put(endpoint, headers=self.headers, json={"enabled": True}).status_code, 403)
        self.assertEqual(self.admin.get(endpoint).status_code, 200)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE tenants SET membership_tier='bronze'")
        self.assertEqual(self.admin.get(endpoint).status_code, 403)

    def test_owner_shell_is_separate_from_business_permissions(self):
        test_scheduler.BusinessHubTests.make_owner(self)
        owner, _ = test_scheduler.BusinessHubTests.sign_in_owner(self)
        state = owner.get("/api/hub/application-state")
        self.assertEqual(state.get_json()["role"], "owner")
        self.assertEqual(state.headers["Cache-Control"], "no-store")
        self.assertEqual(owner.get("/api/application/state").status_code, 401)
        self.assertEqual(owner.get("/api/attendance/reports").status_code, 401)
        with owner.get("/app/owner") as page:
            self.assertEqual(page.status_code, 200)
        self.assertEqual(owner.get("/app/business").status_code, 302)

    def test_stale_download_is_immutable_and_does_not_send_email(self):
        endpoint = "/api/attendance/reports"
        with patch.object(scheduler, "bamboohr_api_key", return_value=""), patch.object(scheduler, "bamboohr_json") as remote:
            result = self.admin.post(endpoint, headers=self.headers, json={})
            remote.assert_not_called()
        self.assertEqual(result.status_code, 201)
        report_id = result.get_json()["id"]
        history = self.admin.get(endpoint).get_json()
        self.assertEqual(history["reports"][0]["state"], "stale")
        self.assertIn("deferred", history["emailStatus"])
        path = endpoint + "/" + report_id + "/download"
        response = self.admin.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response.mimetype)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertIn(b"BambooHR API key", archive.read("xl/worksheets/sheet1.xml"))
            for name in archive.namelist():
                ElementTree.fromstring(archive.read(name))
        with closing(scheduler.database_connect()) as c, c:
            c.execute("DELETE FROM attendance_shift_records")
        self.assertEqual(self.admin.get(path).data, response.data)
        self.assertEqual(self.admin.post(endpoint, headers=self.headers, json={}).status_code, 429)
        self.assertEqual(self.admin.get(endpoint + "/unknown/download").status_code, 404)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE attendance_reports SET tenant_id='other'")
        self.assertEqual(self.admin.get(path).status_code, 404)
        self.assertEqual(self.admin.get(endpoint).get_json()["reports"], [])

    def test_worker_missed_cutoffs_idempotence_and_failure_history(self):
        now = datetime(2026, 11, 5, 15, 0, 30, tzinfo=scheduler.ATTENDANCE_TIMEZONE)
        tenant = scheduler.DEFAULT_TENANT_ID
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO attendance_report_settings(tenant_id,enabled,checked_at) VALUES(?,1,?)",
                      (tenant, now.replace(hour=6).isoformat()))
        with scheduler.app.app_context(), patch.object(scheduler, "bamboohr_api_key", return_value=""):
            reports.run_once(scheduler, now)
            reports.run_once(scheduler, now)
        with closing(scheduler.database_connect()) as c:
            rows = c.execute("SELECT cutoff,state FROM attendance_reports ORDER BY cutoff").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual([r[1] for r in rows], ["missed", "stale"])
        self.assertEqual(self.admin.get("/api/attendance/reports").get_json()["heartbeat"], now.isoformat())
        with scheduler.app.app_context(), patch.object(scheduler, "bamboohr_api_key", return_value=""), patch.object(reports, "workbook", side_effect=ValueError("Invalid fixture")):
            with self.assertRaisesRegex(ValueError, "Invalid fixture"):
                reports.capture(scheduler, tenant, now, "manual:failed", now=now)
        with closing(scheduler.database_connect()) as c:
            failed = c.execute("SELECT state,error FROM attendance_reports WHERE run_key='manual:failed'").fetchone()
        self.assertEqual(failed, ("failed", "Invalid fixture"))

    def test_worker_ready_refresh_uses_existing_classification(self):
        now = datetime.now(scheduler.ATTENDANCE_TIMEZONE)
        with scheduler.app.app_context(), patch.object(scheduler, "bamboohr_api_key", return_value="fixture"), patch.object(scheduler, "bamboohr_json", return_value=[]), patch.object(scheduler, "sync_attendance_data", wraps=scheduler.sync_attendance_data) as sync:
            report_id = reports.capture(scheduler, scheduler.DEFAULT_TENANT_ID, now, "manual:ready", now=now)
            self.assertEqual(sync.call_count, 1)
        history = self.admin.get("/api/attendance/reports").get_json()["reports"]
        self.assertEqual(history[0]["id"], report_id)
        self.assertEqual(history[0]["state"], "ready")

    def test_exact_cutoff_excludes_future_shifts_and_keeps_overnight(self):
        cutoff = datetime(2026, 11, 5, 7, tzinfo=scheduler.ATTENDANCE_TIMEZONE)
        document = {"id": "overnight", "start": "2026-11-02", "location": "Kingston",
                    "role": "Cashier", "controls": {"span": 8},
                    "employees": [
                        {"id": "emp-a", "name": "Ann", "slots": [None, None, 23, None, None, None, None]},
                        {"id": "emp-b", "name": "Bob", "slots": [None, None, None, 8, None, None, None]},
                    ]}
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO accepted_schedules(run_id,tenant_id,week_start,location,role,payload) VALUES(?,?,?,?,?,?)",
                      ("overnight", scheduler.DEFAULT_TENANT_ID, "2026-11-02", "Kingston", "Cashier", json.dumps(document)))
        with scheduler.app.app_context(), patch.object(scheduler, "bamboohr_api_key", return_value="fixture"), patch.object(scheduler, "bamboohr_json", return_value=[]):
            report_id = reports.capture(scheduler, scheduler.DEFAULT_TENANT_ID, cutoff, "scheduled:overnight",
                                        now=cutoff + timedelta(seconds=30))
        with closing(scheduler.database_connect()) as c:
            payload = json.loads(c.execute("SELECT payload FROM attendance_reports WHERE id=?", (report_id,)).fetchone()[0])
        shifts = payload["attendance"]["shifts"]
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0]["employeeId"], "emp-a")
        self.assertEqual(shifts[0]["shiftEnd"], cutoff.isoformat())
        self.assertEqual(payload["attendance"]["reportedAt"], cutoff.isoformat())
        self.assertEqual(payload["attendance"]["summary"]["expected"], 1)
        self.assertEqual(payload["generatedAt"], (cutoff + timedelta(seconds=30)).isoformat())

    def test_other_tenant_and_disabled_worker_are_not_captured(self):
        now = datetime.now(scheduler.ATTENDANCE_TIMEZONE)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO attendance_report_settings(tenant_id,enabled,checked_at) VALUES(?,0,?)",
                      (scheduler.DEFAULT_TENANT_ID, (now - timedelta(days=1)).isoformat()))
            c.execute("INSERT INTO attendance_reports(tenant_id,id,run_key,cutoff,created_at,state,payload) VALUES('other','foreign','key',?,?,'ready','{}')",
                      (now.isoformat(), now.isoformat()))
        with scheduler.app.app_context(), patch.object(reports, "capture") as capture:
            reports.run_once(scheduler, now)
            capture.assert_not_called()
        self.assertEqual(self.admin.get("/api/attendance/reports").get_json()["reports"], [])
        self.assertEqual(self.admin.get("/api/attendance/reports/foreign/download").status_code, 404)

    def test_workbook_counts_and_exception_colors_and_no_formulas(self):
        base = dict(name="=HYPERLINK(\"bad\")", employeeId="e1", location="A", role="Cashier",
                    shiftStart="2026-11-05T06:00:00-05:00", clockIn=None, clockOut=None,
                    workedMinutes=None, earlyMinutes=0, overtimeMinutes=0, reason="")
        rows = [base | {"status": status} for status in ("late", "absent", "approved_leave", "scheduled")]
        payload = {"cutoff": "cutoff", "generatedAt": "now", "refreshError": "",
                   "attendance": {"shifts": rows, "lastSyncedAt": "fresh"}}
        with zipfile.ZipFile(io.BytesIO(reports.workbook(payload))) as archive:
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            exceptions = ElementTree.fromstring(archive.read("xl/worksheets/sheet2.xml"))
            self.assertFalse(exceptions.findall(".//s:f", ns))
            data = exceptions.findall("s:sheetData/s:row", ns)
            self.assertEqual(data[1][0].get("s"), "2")
            self.assertEqual(data[2][0].get("s"), "3")
            summary = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            values = [cell.find("s:is/s:t", ns).text for cell in summary.findall("s:sheetData/s:row", ns)[4]]
            self.assertEqual(values[3:7], ["3", "1", "1", "1"])


class TradeLocationTests(unittest.TestCase):
    setUp = workflows.TradeWorkflowTests.setUp
    tearDown = workflows.TradeWorkflowTests.tearDown
    seed = workflows.TradeWorkflowTests.seed
    create_account = workflows.TradeWorkflowTests.create_account
    new_client = workflows.TradeWorkflowTests.new_client
    portal_employee_client = workflows.TradeWorkflowTests.portal_employee_client
    headers = workflows.TradeWorkflowTests.headers

    def test_employee_lock_tampering_and_assignment_changes(self):
        self.seed()
        employee = self.portal_employee_client()
        choices = employee.get("/api/access/trades/choices").get_json()
        self.assertEqual(choices["lockedLocation"]["id"], "loc1")
        self.assertEqual(choices["lockedLocation"]["role"], "Cashier")
        self.assertTrue(all(x["locationId"] == "loc1" for x in choices["schedules"]))
        payload = {"runId": "trade-week", "employeeA": "emp-a", "employeeB": "emp-b",
                   "locationId": "loc2", "reason": "Coverage", "days": [0]}
        for endpoint in ("/api/access/trades/options", "/api/access/trades"):
            response = employee.post(endpoint, headers=self.csrf, json=payload)
            self.assertEqual(response.status_code, 409, response.get_json())
            self.assertIn("fixed", response.get_json()["error"])
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE employees SET schedule_location_id='loc2',location='Montego Bay' WHERE employee_id='emp-a'")
        self.assertEqual(employee.get("/api/access/trades/choices").get_json()["schedules"], [])
        self.assertEqual(employee.post("/api/access/trades/options", headers=self.csrf, json=payload | {"locationId": "loc1"}).status_code, 409)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE employees SET schedule_location_id=NULL WHERE employee_id='emp-a'")
        response = employee.get("/api/access/trades/choices")
        self.assertEqual(response.status_code, 403)
        self.assertIn("verified", response.get_json()["error"])
        self.assertIsNone(self.admin.get("/api/shift-trades/choices").get_json()["lockedLocation"])


if __name__ == "__main__":
    unittest.main()
