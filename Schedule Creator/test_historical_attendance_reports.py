import io
import json
import unittest
import zipfile
from contextlib import closing
from datetime import date
from html.parser import HTMLParser
from unittest.mock import patch
from xml.etree import ElementTree

import historical_attendance_reports as historical
import scheduler
import test_scheduler


class HistoricalAttendanceReportTests(unittest.TestCase):
    setUp = test_scheduler.ManagerEmployeeAccessTests.setUp
    tearDown = test_scheduler.ManagerEmployeeAccessTests.tearDown
    create_account = test_scheduler.ManagerEmployeeAccessTests.create_account
    new_client = test_scheduler.ManagerEmployeeAccessTests.new_client
    sign_in_manager = test_scheduler.ManagerEmployeeAccessTests.sign_in_manager
    admin_headers = {"X-CSRF-Token": "test-csrf-token"}

    def test_dashboard_branding_is_saved(self):
        from test_attendance_snapshot import LOGO
        self.seed_week()
        branding = {"businessName": "Saved Business", "logoDataUrl": LOGO,
                "supportingImages": [LOGO], "reportTheme": "dark",
                "primaryColor": "#123456", "accentColor": "#abcdef"}
        with patch.object(scheduler, "current_app_config", return_value=branding):
            response = self.create_week(self.admin, self.admin_headers)
        self.assertEqual(response.status_code, 201)
        report = response.get_json()["report"]
        self.assertEqual(report["supportingImages"], [LOGO])
        self.assertEqual(report["reportTheme"], "dark")
        self.assertEqual(report["primaryColor"], "#123456")
        self.assertEqual(report["accentColor"], "#abcdef")
        report_id = response.get_json()["id"]
        path = f"/api/attendance/historical-reports/{report_id}/download?format=html"
        with patch.object(scheduler, "current_app_config", side_effect=AssertionError("No current branding")):
            response = self.admin.get(path)
        self.assertIn(b"Saved Business", response.data)
        self.assertIn(LOGO.encode(), response.data)
        self.assertIn(b'"reportTheme":"dark"', response.data)
        self.assertIn(b'"supportingImages":["data:image/png;base64,', response.data)
        self.assertIn(b'"primaryColor":"#123456"', response.data)
        self.assertIn(b'"accentColor":"#abcdef"', response.data)
        self.assertIn("img-src data:", response.headers["Content-Security-Policy"])

    def add_shift(
        self, employee_id, day, status, location="Kingston", role="Cashier",
        run_id=None, name="Ann Kingston",
    ):
        run_id = run_id or "historical-" + day
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO employees
                    (employee_id, tenant_id, name, location, role, active, source_type)
                VALUES (?, ?, ?, ?, ?, 1, 'manual')
                ON CONFLICT DO NOTHING
                """,
                (employee_id, scheduler.DEFAULT_TENANT_ID, name, location, role),
            )
            connection.execute(
                """
                INSERT INTO attendance_shift_records
                    (tenant_id, schedule_run_id, employee_id, shift_date, shift_start,
                     status, source, reason, employee_name, location, role, clock_in_at,
                     clock_in_timezone, worked_minutes, updated_at)
                VALUES (?, ?, ?, ?, 8, ?, 'schedule', '', ?, ?, ?, ?, 'America/Jamaica', ?, CURRENT_TIMESTAMP)
                """,
                (
                    scheduler.DEFAULT_TENANT_ID, run_id, employee_id, day, status,
                    name, location, role,
                    "2026-11-02T08:03:00-05:00" if status in {"attended", "late"} else None,
                    450 if status in {"attended", "late"} else None,
                ),
            )

    def seed_week(self):
        self.add_shift("emp-a", "2026-10-26", "attended", run_id="prev-a")
        self.add_shift("emp-a", "2026-10-27", "absent", run_id="prev-b")
        self.add_shift("emp-a", "2026-11-03", "attended")
        self.add_shift("emp-a", "2026-11-04", "absent")
        self.add_shift("emp-a", "2026-11-05", "approved_leave")
        self.add_shift("emp-a", "2026-11-06", "attended")
        self.add_shift("emp-b", "2026-11-03", "attended", "Montego Bay", name="Bob Montego")
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO attendance_shift_records
                    (tenant_id,schedule_run_id,employee_id,shift_date,shift_start,status,source,
                     employee_name,location,role)
                VALUES ('other','foreign','private','2026-11-03',8,'attended','schedule','Private','Kingston','Cashier')
                """
            )

    def create_week(self, client, headers, endpoint="/api/attendance/historical-reports", **filters):
        payload = {"period": "week", "start": "2026-11-04"} | filters
        return client.post(
            endpoint, headers=headers, json=payload
        )

    def test_monday_week_comparison_scores_and_evidence_patterns(self):
        self.seed_week()
        response = self.create_week(self.admin, self.admin_headers)
        self.assertEqual(response.status_code, 201, response.get_json())
        report = response.get_json()["report"]
        self.assertEqual((report["start"], report["end"]), ("2026-11-02", "2026-11-06"))
        self.assertEqual((report["comparison"]["start"], report["comparison"]["end"]), ("2026-10-26", "2026-11-01"))
        self.assertEqual(report["summary"]["expected"], 6)
        self.assertEqual(report["summary"]["present"], 5)
        self.assertEqual(report["summary"]["score"], 83.33)
        self.assertEqual(report["summary"]["lateDates"], 1)
        self.assertEqual(
            report["summary"]["lateDateValues"],
            sorted({row["date"] for row in report["records"] if row["status"] == "late"}),
        )
        self.assertEqual(report["summary"]["absentDates"], 1)
        self.assertEqual(
            report["summary"]["absentDateValues"],
            sorted({row["date"] for row in report["records"] if row["status"] == "absent"}),
        )
        self.assertTrue(all(row["durationEvidence"] == "insufficient_evidence" for row in report["records"]))
        self.assertIn("Insufficient evidence", report["evidence"]["schedule"])
        self.assertEqual(report["comparison"]["previous"]["score"], 50.0)
        self.assertEqual(report["comparison"]["change"], 33.33)
        self.assertIn("emp-a", [row["employeeId"] for row in report["comparison"]["byEmployee"]])
        bob = next(row for row in report["comparison"]["byEmployee"] if row["employeeId"] == "emp-b")
        self.assertIsNone(bob["previous"])
        self.assertEqual(bob["evidence"], "insufficient_evidence")
        self.assertIn("Kingston", [row["distributionCenter"] for row in report["comparison"]["byDistributionCenter"]])
        self.assertNotIn("Private", {row["name"] for row in report["records"]})
        self.assertEqual(report["patterns"]["minimumEligibleShifts"], 3)
        self.assertTrue(any(row["analysis"] == "available" for row in report["patterns"]["shiftTimes"]))
        self.assertEqual(report["patterns"]["postDayOff"]["analysis"], "insufficient_evidence")
        self.assertEqual(report["patterns"]["postApprovedTimeOff"]["analysis"], "uncertain_first_scheduled_shift")
        self.assertEqual(report["patterns"]["postApprovedTimeOff"]["sampleAnalysis"], "insufficient_sample")
        self.assertIn("missing row", report["evidence"]["schedule"])
        self.assertIn("emp-b", [row["employeeId"] for row in report["records"]])

    def test_bamboohr_source_reports_unregistered_provider_employees_only(self):
        self.seed_week()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO application_settings (setting_key, setting_value, tenant_id)
                VALUES ('attendance_shift_source', 'bamboohr', ?)
                ON CONFLICT (tenant_id, setting_key)
                DO UPDATE SET setting_value=excluded.setting_value
                """,
                (scheduler.DEFAULT_TENANT_ID,),
            )
            connection.execute(
                """
                INSERT INTO attendance_score_overrides
                    (tenant_id, employee_id, score, reason)
                VALUES (?, 'bamboohr:999', 1, 'App-local override must not apply')
                """,
                (scheduler.DEFAULT_TENANT_ID,),
            )
            connection.execute(
                """
                INSERT INTO attendance_shift_records
                    (tenant_id, schedule_run_id, employee_id, shift_date, shift_start,
                     status, source, employee_name, location, role)
                VALUES (?, 'bamboohr:shift-999', 'bamboohr:999', '2026-11-03', 8,
                        'attended', 'bamboohr', 'Unregistered Provider Employee',
                        'Kingston', 'Cashier')
                """,
                (scheduler.DEFAULT_TENANT_ID,),
            )
        response = self.create_week(self.admin, self.admin_headers)
        self.assertEqual(response.status_code, 201, response.get_json())
        report = response.get_json()["report"]
        self.assertEqual(report["shiftSource"], "BambooHR schedules")
        self.assertTrue(report["records"])
        self.assertTrue(all(row["runId"].startswith("bamboohr:") for row in report["records"]))
        self.assertIn("bamboohr:999", {row["employeeId"] for row in report["records"]})
        provider_employee = next(
            row for row in report["employees"] if row["employeeId"] == "bamboohr:999"
        )
        self.assertEqual(provider_employee["effectiveScore"], 100.0)
        self.assertIsNone(provider_employee["scoreOverride"])

    def test_app_source_reports_only_currently_active_app_employees(self):
        self.seed_week()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE employees SET active=0 WHERE tenant_id=? AND employee_id='emp-b'",
                (scheduler.DEFAULT_TENANT_ID,),
            )
        response = self.create_week(self.admin, self.admin_headers)
        self.assertEqual(response.status_code, 201, response.get_json())
        report = response.get_json()["report"]
        self.assertEqual(report["shiftSource"], "Accepted app shifts")
        self.assertNotIn("emp-b", {row["employeeId"] for row in report["records"]})

    def test_post_day_off_and_leave_need_three_eligible_events_but_remain_uncertain(self):
        for day, status in (
            ("2026-04-01", "day_off"), ("2026-04-02", "attended"),
            ("2026-04-03", "day_off"), ("2026-04-04", "late"),
            ("2026-04-05", "day_off"), ("2026-04-06", "attended"),
        ):
            self.add_shift("emp-off", day, status, run_id="off-" + day)
        for day, status in (
            ("2026-04-01", "approved_leave"), ("2026-04-02", "attended"),
            ("2026-04-03", "sick"), ("2026-04-04", "late"),
            ("2026-04-05", "vacation"), ("2026-04-06", "attended"),
        ):
            self.add_shift("emp-leave", day, status, run_id="leave-" + day)

        report = self.admin.post(
            "/api/attendance/historical-reports",
            headers=self.admin_headers,
            json={"period": "month", "start": "2026-04-01"},
        ).get_json()["report"]
        day_off = report["patterns"]["postDayOff"]
        approved_leave = report["patterns"]["postApprovedTimeOff"]
        self.assertEqual(day_off["analysis"], "uncertain_first_scheduled_shift")
        self.assertEqual(day_off["sampleAnalysis"], "available")
        self.assertEqual(day_off["records"][0]["eligibleShifts"], 3)
        self.assertEqual(day_off["records"][0]["analysis"], "available")
        self.assertEqual(day_off["records"][0]["evidence"], "uncertain_first_scheduled_shift")
        self.assertEqual(day_off["records"][0]["lateDateValues"], ["2026-04-04"])
        self.assertEqual(day_off["records"][0]["absentDateValues"], [])
        self.assertEqual(day_off["records"][0]["lateShiftRate"], 33.33)
        self.assertEqual(day_off["records"][0]["absentShiftRate"], 0.0)
        self.assertEqual(approved_leave["analysis"], "uncertain_first_scheduled_shift")
        self.assertEqual(approved_leave["sampleAnalysis"], "available")
        self.assertEqual(approved_leave["records"][0]["eligibleShifts"], 3)
        self.assertEqual(approved_leave["records"][0]["analysis"], "available")
        self.assertEqual(approved_leave["records"][0]["evidence"], "uncertain_first_scheduled_shift")
        self.assertEqual(approved_leave["records"][0]["lateDateValues"], ["2026-04-04"])
        self.assertEqual(approved_leave["records"][0]["absentDateValues"], [])
        self.assertEqual(approved_leave["records"][0]["lateShiftRate"], 33.33)
        self.assertEqual(approved_leave["records"][0]["absentShiftRate"], 0.0)
        self.assertIn("cannot be verified", approved_leave["message"])

    def test_historical_score_override_is_dated_and_missing_audit_history_is_not_inferred(self):
        for day in ("2026-11-03", "2026-11-04"):
            self.add_shift("emp-a", day, "attended", run_id="override-" + day)
        for day in ("2026-10-26", "2026-10-27"):
            self.add_shift("emp-a", day, "attended", run_id="previous-" + day)
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO attendance_score_overrides
                    (tenant_id, employee_id, score, reason, updated_at)
                VALUES (?, 'emp-a', 80, 'latest value', '2026-11-10T12:00:00')
                """,
                (scheduler.DEFAULT_TENANT_ID,),
            )
            connection.executemany(
                """
                INSERT INTO attendance_score_audit_events
                    (id, tenant_id, employee_id, previous_score, score, reason, created_at)
                VALUES (?, ?, 'emp-a', ?, ?, 'recorded change', ?)
                """,
                [
                    ("override-before", scheduler.DEFAULT_TENANT_ID, None, 90, "2026-11-05T12:00:00"),
                    ("override-after", scheduler.DEFAULT_TENANT_ID, 90, 80, "2026-11-10T12:00:00"),
                ],
            )
        report = self.create_week(self.admin, self.admin_headers).get_json()["report"]
        employee = next(row for row in report["comparison"]["byEmployee"] if row["employeeId"] == "emp-a")
        self.assertEqual(employee["current"], 100)
        self.assertEqual(employee["currentEffective"], 90)
        self.assertEqual(employee["overrideEvidence"], "recorded_audit_history")
        self.assertEqual(employee["previousEffective"], None)
        self.assertEqual(employee["change"], None)
        self.assertEqual(employee["formulaChange"], 0)

    def test_selected_period_pattern_tables_and_workbook_include_late_absence_rates(self):
        for day, status in (
            ("2026-04-06", "attended"),
            ("2026-04-13", "late"),
            ("2026-04-20", "absent"),
        ):
            self.add_shift("emp-pattern", day, status, run_id="pattern-" + day)

        report_response = self.admin.post(
            "/api/attendance/historical-reports",
            headers=self.admin_headers,
            json={"period": "month", "start": "2026-04-01"},
        )
        self.assertEqual(report_response.status_code, 201, report_response.get_json())
        report = report_response.get_json()["report"]
        time_row = next(
            row for row in report["patterns"]["shiftTimes"]
            if row["employeeId"] == "emp-pattern"
        )
        day_row = next(
            row for row in report["patterns"]["daysOfWeek"]
            if row["employeeId"] == "emp-pattern"
        )
        for pattern in (time_row, day_row):
            self.assertEqual(pattern["eligibleShifts"], 3)
            self.assertEqual(pattern["lateShifts"], 1)
            self.assertEqual(pattern["lateDates"], 1)
            self.assertEqual(pattern["lateDateValues"], ["2026-04-13"])
            self.assertEqual(pattern["lateShiftRate"], 33.33)
            self.assertEqual(pattern["absentShifts"], 1)
            self.assertEqual(pattern["absentDates"], 1)
            self.assertEqual(pattern["absentDateValues"], ["2026-04-20"])
            self.assertEqual(pattern["absentShiftRate"], 33.33)
            self.assertEqual(pattern["analysis"], "available")

        pattern_sheet = next(
            rows for name, rows in historical._workbook_sheets(report)
            if name == "Patterns"
        )
        self.assertIn("Late shift rate %", pattern_sheet[0])
        self.assertIn("Absent shift rate %", pattern_sheet[0])
        self.assertIn("Late date values", pattern_sheet[0])
        self.assertIn("Absent date values", pattern_sheet[0])
        excel_pattern = next(row for row in pattern_sheet if row[2] == "emp-pattern")
        self.assertEqual(excel_pattern[9], "2026-04-13")
        self.assertEqual(excel_pattern[10], 33.33)
        self.assertEqual(excel_pattern[13], "2026-04-20")
        self.assertEqual(excel_pattern[14], 33.33)
        employee_sheet = next(
            rows for name, rows in historical._workbook_sheets(report)
            if name == "Employee trends"
        )
        self.assertIn("Late date values", employee_sheet[0])
        self.assertIn("Absent date values", employee_sheet[0])
        excel_employee = next(row for row in employee_sheet if row[1] == "emp-pattern")
        self.assertEqual(excel_employee[11], "2026-04-13")
        self.assertEqual(excel_employee[14], "2026-04-20")

        html_response = self.admin.get(
            f"/api/attendance/historical-reports/{report_response.get_json()['id']}/download?format=html"
        )
        self.assertEqual(html_response.status_code, 200)
        html = html_response.get_data(as_text=True)
        self.assertIn("Late-shift rate", html)
        self.assertIn("Absent-shift rate", html)
        self.assertIn("Late shifts", html)
        self.assertIn("Absent dates", html)
        self.assertIn("lateRate", html)
        self.assertIn("absentRate", html)
        self.assertIn("Late date values", html)
        self.assertIn("Absent date values", html)
        self.assertIn("2026-04-13", html)
        self.assertIn("2026-04-20", html)

    def test_manager_scope_uses_current_location_authority_and_dated_role_location(self):
        self.seed_week()
        self.add_shift("emp-a", "2026-11-04", "attended", role="Warehouse", run_id="unauthorized-role")
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute("UPDATE schedule_locations SET role_group='Cashier' WHERE id='loc1'")
        manager, _, _ = self.sign_in_manager()
        endpoint = "/api/access/manager/historical-reports"
        denied = self.create_week(manager, self.csrf, endpoint, location="Montego Bay")
        self.assertEqual(denied.status_code, 403, denied.get_json())
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE employees SET schedule_location_id='loc2', location='Montego Bay' WHERE employee_id='emp-a'"
            )
        response = self.create_week(manager, self.csrf, endpoint)
        self.assertEqual(response.status_code, 201, response.get_json())
        report = response.get_json()["report"]
        self.assertEqual({row["location"] for row in report["records"]}, {"Kingston"})
        self.assertEqual({row["employeeId"] for row in report["records"]}, {"emp-a"})
        self.assertNotIn("Warehouse", {row["role"] for row in report["records"]})
        report_id = response.get_json()["id"]
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE schedule_locations SET manager_email='other@acme.example' WHERE id='loc1'"
            )
        self.assertEqual(
            manager.get(f"{endpoint}/{report_id}/download?format=html").status_code,
            404,
        )

    def test_missing_dated_assignment_is_explicit_and_never_used_for_manager_scope(self):
        self.add_shift("emp-a", "2026-11-03", "attended", location="", role="", run_id="unknown-assignment")
        admin_report = self.create_week(self.admin, self.admin_headers).get_json()["report"]
        row = next(item for item in admin_report["records"] if item["runId"] == "unknown-assignment")
        self.assertEqual(row["assignmentEvidence"], "insufficient_evidence")
        self.assertIn("Insufficient evidence", admin_report["evidence"]["assignment"])

        manager, _, _ = self.sign_in_manager()
        manager_report = self.create_week(
            manager, self.csrf, "/api/access/manager/historical-reports"
        )
        self.assertEqual(manager_report.status_code, 201, manager_report.get_json())
        self.assertNotIn(
            "unknown-assignment",
            {item["runId"] for item in manager_report.get_json()["report"]["records"]},
        )

    def test_admin_filters_tenant_and_month_comparison(self):
        self.add_shift("emp-a", "2026-02-08", "absent", run_id="feb")
        self.add_shift("emp-a", "2026-03-08", "attended", run_id="mar")
        response = self.admin.post(
            "/api/attendance/historical-reports",
            headers=self.admin_headers,
            json={"period": "month", "start": "2026-03-15", "location": "Kingston", "role": "Cashier"},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        report = response.get_json()["report"]
        self.assertEqual((report["start"], report["end"]), ("2026-03-01", "2026-03-31"))
        self.assertEqual((report["comparison"]["start"], report["comparison"]["end"]), ("2026-02-01", "2026-02-28"))
        self.assertEqual(report["summary"]["score"], 100.0)
        self.assertEqual(report["comparison"]["previous"]["score"], 0.0)
        self.assertEqual(report["comparison"]["change"], 100.0)
        self.assertEqual({row["location"] for row in report["records"]}, {"Kingston"})
        self.assertEqual(self.admin.post(
            "/api/attendance/historical-reports", headers=self.admin_headers,
            json={"period": "week", "start": "2026-11-09"},
        ).status_code, 400)

    def test_saved_downloads_are_immutable_offline_and_workbook_parity(self):
        self.seed_week()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE attendance_shift_records SET employee_name=? WHERE employee_id='emp-a' AND shift_date='2026-11-03'",
                ("</script><img src=x>",),
            )
        response = self.create_week(self.admin, self.admin_headers, location="Kingston", role="Cashier")
        self.assertEqual(response.status_code, 201)
        report_id = response.get_json()["id"]
        history = self.admin.get("/api/attendance/historical-reports")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json()["reports"][0]["id"], report_id)

        html_path = f"/api/attendance/historical-reports/{report_id}/download?format=html"
        first_html = self.admin.get(html_path)
        self.assertEqual(first_html.status_code, 200)
        self.assertIn("default-src 'none'", first_html.headers["Content-Security-Policy"])
        self.assertIn(b"application/json", first_html.data)
        self.assertNotIn(b"https://", first_html.data)
        self.assertNotIn(b"</script><img", first_html.data)
        self.assertIn(b"\\u003c/script\\u003e", first_html.data)
        self.assertNotIn(b"<script src=", first_html.data)
        self.assertNotIn(b"<img src=", first_html.data)
        for marker in (
            b'id="centerChart"', b'id="employeeChart"', b'id="heatmap"',
            b'id="employeeFilter"', b'id="employeeSearch"', b'id="sortFilter"',
            b'Override not applied to partial team filter',
            b'dataset.selectionDetail', b'id="roleChart"', b'scope.id="scope"',
            b'employeeSelected||teamSelected',
        ):
            self.assertIn(marker, first_html.data)
        HTMLParser().feed(first_html.get_data(as_text=True))
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "DELETE FROM attendance_shift_records WHERE tenant_id=? AND shift_date >= '2026-11-02'",
                (scheduler.DEFAULT_TENANT_ID,),
            )
        again_html = self.admin.get(html_path)
        self.assertEqual(again_html.data, first_html.data)

        workbook_response = self.admin.get(
            f"/api/attendance/historical-reports/{report_id}/download?format=xlsx"
        )
        self.assertEqual(workbook_response.status_code, 200)
        self.assertIn("spreadsheetml", workbook_response.mimetype)
        with zipfile.ZipFile(io.BytesIO(workbook_response.data)) as archive:
            workbook_xml = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            names = [item.get("name") for item in workbook_xml.findall(".//s:sheet", namespace)]
            self.assertEqual(names, ["Summary", "Distribution centers", "Employee trends", "Patterns", "Shift records"])
            for name in archive.namelist():
                root = ElementTree.fromstring(archive.read(name))
                self.assertFalse(root.findall(".//s:f", namespace))
            summary_xml = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            values = [node.text for node in summary_xml.findall(".//s:t", namespace)]
            self.assertIn("Historical attendance trends", values)
            self.assertIn("75.0", values)

    def test_manager_cannot_view_admin_captures_or_other_tenants(self):
        self.seed_week()
        admin_report = self.create_week(self.admin, self.admin_headers).get_json()["id"]
        manager, _, _ = self.sign_in_manager()
        manager_endpoint = "/api/access/manager/historical-reports"
        denied = manager.get(f"{manager_endpoint}/{admin_report}/download?format=xlsx")
        self.assertEqual(denied.status_code, 404, denied.get_json())
        self.assertEqual(manager.get(manager_endpoint).get_json()["reports"], [])

    def test_period_boundaries_are_monday_and_calendar_month(self):
        self.assertEqual(
            historical.period_bounds("week", "2026-11-04"),
            (date(2026, 11, 2), date(2026, 11, 8), date(2026, 10, 26), date(2026, 11, 1)),
        )
        self.assertEqual(
            historical.period_bounds("month", "2024-03-17"),
            (date(2024, 3, 1), date(2024, 3, 31), date(2024, 2, 1), date(2024, 2, 29)),
        )

    def test_historical_ui_asset_is_available(self):
        with self.admin.get("/historical-attendance-reports.js") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"historical-report-form", response.data)
        manager, _, _ = self.sign_in_manager()
        with manager.get("/app/access") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"historicalAccessReports", response.data)
        with self.admin.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"historical-attendance-reports.js", response.data)
