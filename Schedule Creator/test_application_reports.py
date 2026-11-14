import base64
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

    def test_executive_cutoff_uses_jamaica_day_end_and_exact_delay_bounds(self):
        reporting_day = datetime(2026, 11, 9).date()
        immediate = reports.executive_cutoff(reporting_day, 0, scheduler.ATTENDANCE_TIMEZONE)
        delayed = reports.executive_cutoff(reporting_day, 24, scheduler.ATTENDANCE_TIMEZONE)
        self.assertEqual(immediate, datetime(2026, 11, 10, 0, tzinfo=scheduler.ATTENDANCE_TIMEZONE))
        self.assertEqual(delayed, datetime(2026, 11, 11, 0, tzinfo=scheduler.ATTENDANCE_TIMEZONE))
        for invalid in (-1, 25, True):
            with self.assertRaises(ValueError):
                reports.executive_cutoff(reporting_day, invalid, scheduler.ATTENDANCE_TIMEZONE)

    def test_executive_settings_are_gold_gated_and_validate_delay(self):
        path = "/api/attendance/executive-reports"
        self.assertEqual(self.admin.get(path).status_code, 403)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE tenants SET membership_tier='gold' WHERE tenant_id=?", (scheduler.DEFAULT_TENANT_ID,))
        initial = self.admin.get(path)
        self.assertEqual(initial.status_code, 200)
        self.assertFalse(initial.get_json()["enabled"])
        for value in (-1, 25, True, 1.5):
            response = self.admin.put(path, headers=self.headers, json={"enabled": True, "delayHours": value})
            self.assertEqual(response.status_code, 400)
        saved = self.admin.put(path, headers=self.headers, json={"enabled": True, "delayHours": 24})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.admin.get(path).get_json()["delayHours"], 24)

    def test_executive_capture_is_aggregated_and_separate_from_snapshot_history(self):
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE tenants SET membership_tier='gold' WHERE tenant_id=?", (scheduler.DEFAULT_TENANT_ID,))
            connection.executemany(
                """
                INSERT INTO attendance_shift_records
                    (tenant_id,schedule_run_id,employee_id,shift_date,shift_start,status,source,reason,
                     employee_name,location,role,clock_in_at,clock_in_timezone,worked_minutes,
                     early_minutes,overtime_minutes,shift_end_at,updated_at)
                VALUES(?,?,?,?,?,?,'schedule','',?,?,?,?,'America/Jamaica',?,?,?,?,'2026-11-10T12:00:00-05:00')
                """,
                [
                    (scheduler.DEFAULT_TENANT_ID,"exec-present","emp-a","2026-11-09",8,"attended",
                     "Ann Kingston","Kingston","Cashier","2026-11-09T08:03:00-05:00",450,0,0,"2026-11-09T16:00:00-05:00"),
                    (scheduler.DEFAULT_TENANT_ID,"exec-absent","emp-b","2026-11-09",9,"absent",
                     "Bob Montego","Montego Bay","Cashier",None,None,0,0,"2026-11-09T17:00:00-05:00"),
                    (scheduler.DEFAULT_TENANT_ID,"exec-leave","emp-a","2026-11-09",10,"approved_leave",
                     "Ann Kingston","Kingston","Cashier",None,None,0,0,"2026-11-09T18:00:00-05:00"),
                ],
            )
        report_date = datetime(2026, 11, 9).date()
        generated = datetime(2026, 11, 10, 1, tzinfo=scheduler.ATTENDANCE_TIMEZONE)
        cutoff = reports.executive_cutoff(report_date, 1, scheduler.ATTENDANCE_TIMEZONE)
        with scheduler.app.app_context(), \
             patch.object(scheduler, "bamboohr_api_key", return_value="fixture"), \
             patch.object(scheduler, "bamboohr_json", return_value=[]), \
             patch.object(scheduler, "sync_attendance_data"):
            report_id = reports.capture_executive(
                scheduler, scheduler.DEFAULT_TENANT_ID, report_date, cutoff, 1, now=generated,
            )
        with closing(scheduler.database_connect()) as connection:
            state, payload_text = connection.execute(
                "SELECT state,payload FROM attendance_reports WHERE tenant_id=? AND id=?",
                (scheduler.DEFAULT_TENANT_ID, report_id),
            ).fetchone()
        payload = json.loads(payload_text)
        self.assertEqual(state, "ready")
        self.assertEqual(payload["summary"]["planned"], 2)
        self.assertEqual(payload["summary"]["actual"], 1)
        self.assertEqual(payload["summary"]["attendancePercent"], 50.0)
        self.assertEqual(payload["summary"]["leave"], 1)
        self.assertNotIn("Ann Kingston", payload["html"])
        self.assertIn("Kingston", payload["html"])
        self.assertEqual(self.admin.get("/api/attendance/reports").get_json()["reports"], [])
        history = self.admin.get("/api/attendance/executive-reports")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json()["reports"][0]["id"], report_id)
        download = self.admin.get(f"/api/attendance/executive-reports/{report_id}/download")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.mimetype, "text/html")

    def test_executive_worker_generates_once_at_configured_day_end_delay(self):
        report_date = datetime(2026, 11, 9).date()
        cutoff = reports.executive_cutoff(report_date, 0, scheduler.ATTENDANCE_TIMEZONE)
        now = cutoff + timedelta(seconds=30)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE tenants SET membership_tier='gold' WHERE tenant_id=?", (scheduler.DEFAULT_TENANT_ID,))
            connection.execute(
                "INSERT INTO executive_attendance_report_settings(tenant_id,enabled,delay_hours,checked_at) VALUES(?,1,0,?)",
                (scheduler.DEFAULT_TENANT_ID, (cutoff - timedelta(minutes=1)).isoformat()),
            )
        with scheduler.app.app_context(), patch.object(reports, "capture_executive") as capture:
            reports.run_executive_once(scheduler, now)
            reports.run_executive_once(scheduler, now)
        self.assertEqual(capture.call_count, 1)
        args, kwargs = capture.call_args
        self.assertEqual(args[2], report_date)
        self.assertEqual(args[3], cutoff)
        self.assertFalse(kwargs["missed"])

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

    def test_bamboohr_snapshot_uses_provider_population_and_labels_xlsx_source(self):
        now = datetime.now(scheduler.ATTENDANCE_TIMEZONE)
        with closing(scheduler.database_connect()) as c, c:
            c.execute(
                """
                INSERT INTO application_settings (setting_key, setting_value, tenant_id)
                VALUES ('attendance_shift_source', 'bamboohr', ?)
                ON CONFLICT (tenant_id, setting_key)
                DO UPDATE SET setting_value=excluded.setting_value
                """,
                (scheduler.DEFAULT_TENANT_ID,),
            )
        with scheduler.app.app_context(), \
             patch.object(scheduler, "bamboohr_api_key", return_value="fixture"), \
             patch.object(scheduler, "bamboohr_json", return_value=[]), \
             patch.object(scheduler, "fetch_bamboohr_scheduled_shifts", return_value=[]) as fetch:
            report_id = reports.capture(
                scheduler, scheduler.DEFAULT_TENANT_ID, now, "manual:bamboohr-source", now=now
            )
        self.assertTrue(fetch.call_args.kwargs["attendance_mode"])
        with closing(scheduler.database_connect()) as c:
            saved = c.execute(
                "SELECT payload FROM attendance_reports WHERE tenant_id=? AND id=?",
                (scheduler.DEFAULT_TENANT_ID, report_id),
            ).fetchone()
        payload = json.loads(saved[0])
        self.assertEqual(payload["attendance"]["shiftSource"]["selected"], "bamboohr")
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload["workbook"]))) as archive:
            self.assertIn(b"Shift source", archive.read("xl/worksheets/sheet1.xml"))
            self.assertIn(b"bamboohr", archive.read("xl/worksheets/sheet1.xml"))

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
            summary_rows = summary.findall("s:sheetData/s:row", ns)
            values = [cell.find("s:is/s:t", ns).text for cell in summary_rows[5]]
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
