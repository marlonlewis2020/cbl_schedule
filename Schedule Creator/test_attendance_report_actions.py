import json
import unittest
from contextlib import closing
from datetime import datetime
from unittest.mock import patch

import attendance_email
import attendance_reports
import scheduler
from test_attendance_snapshot import SnapshotHtmlTests, example_payload


class ReportActionTests(unittest.TestCase):
    setUp = SnapshotHtmlTests.setUp
    tearDown = SnapshotHtmlTests.tearDown
    save = SnapshotHtmlTests.save
    headers = {"X-CSRF-Token": "test-csrf-token"}

    def test_confirmation_thresholds_and_unavailable_evidence(self):
        row = example_payload()["attendance"]["shifts"][1]
        self.assertFalse(attendance_email.confirmed(row | {"workedMinutes": 59}))
        self.assertTrue(attendance_email.confirmed(row | {"workedMinutes": 60}))
        shorter = row | {"shiftEnd": "2026-11-06T06:30:00-05:00", "workedMinutes": 30}
        self.assertTrue(attendance_email.confirmed(shorter))
        self.assertFalse(attendance_email.confirmed(shorter | {"workedMinutes": 29}))
        self.assertFalse(attendance_email.confirmed(row | {"clockIn": None}))
        self.assertFalse(attendance_email.confirmed(row | {"shiftEnd": None}))
        self.assertFalse(attendance_email.confirmed(row | {"workedMinutes": float("nan")}))
        self.assertFalse(attendance_email.confirmed(row | {"status": "absent"}))
        self.assertFalse(attendance_email.confirmed(row | {"status": "approved_leave"}))
        self.assertEqual(attendance_email.metrics([row | {"shiftEnd": None, "clockOut": None}], example_payload()["cutoff"])["missingOut"], 0)

    def test_email_matches_snapshot_and_is_inert_immutable(self):
        payload = self.save()
        with patch.object(scheduler, "current_app_config", side_effect=AssertionError("No live config")):
            response = self.admin.get("/api/attendance/reports/html-fixture/email")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        content = response.get_json()
        self.assertEqual(content["metrics"]["attendancePercent"], 57.1)
        self.assertEqual(content["metrics"]["confirmed"], 4)
        self.assertEqual(content["metrics"]["expected"], 7)
        self.assertEqual(content["metrics"]["late"], 1)
        self.assertEqual(content["metrics"]["missingOut"], 1)
        self.assertEqual(content["metrics"]["overtime"], 61)
        self.assertIn("Kingston", content["html"])
        self.assertIn("No email", content["text"].replace("This tool does not send email", "No email"))
        payload["businessName"] = '<img src=x onerror="alert(1)">'
        payload["attendance"]["shifts"][0]["location"] = "<script>bad()</script>"
        escaped = attendance_email.generate(payload)
        self.assertNotIn("<script>", escaped["html"])
        self.assertNotIn("<img", escaped["html"])
        payload["attendance"]["shifts"] = []
        self.assertIsNone(attendance_email.generate(payload)["metrics"]["attendancePercent"])
        payload["refreshError"] = "Provider unavailable"
        self.assertIn("SOURCE WARNING", attendance_email.generate(payload)["text"])

    def test_batch_delete_atomic_tombstone_and_audit(self):
        self.save()
        with closing(scheduler.database_connect()) as c, c:
            c.execute("INSERT INTO attendance_reports SELECT tenant_id,'second','scheduled:second',cutoff,created_at,state,payload,error FROM attendance_reports")
            original = c.execute("SELECT * FROM employees").fetchall()
        rejected = self.admin.delete("/api/attendance/reports", headers=self.headers,
                                     json={"ids": ["html-fixture", "unknown"], "confirm": True})
        self.assertEqual(rejected.status_code, 404)
        self.assertEqual(len(self.admin.get("/api/attendance/reports").get_json()["reports"]), 2)
        response = self.admin.delete("/api/attendance/reports", headers=self.headers,
                                    json={"ids": ["html-fixture", "second"], "confirm": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.admin.get("/api/attendance/reports").get_json()["reports"], [])
        for suffix in ("/html", "/download", "/email"):
            self.assertEqual(self.admin.get("/api/attendance/reports/html-fixture" + suffix).status_code, 409)
        with closing(scheduler.database_connect()) as c:
            self.assertTrue(all(state == "deleted" and data == "{}" for state, data in c.execute("SELECT state,payload FROM attendance_reports")))
            self.assertEqual(c.execute("SELECT * FROM employees").fetchall(), original)
            event = c.execute("SELECT action FROM tenant_audit_events WHERE route='delete_reports' AND action LIKE '{%'").fetchone()
            self.assertEqual(json.loads(event[0])["ids"], ["html-fixture", "second"])
        with scheduler.app.app_context():
            self.assertIsNone(attendance_reports.capture(scheduler, scheduler.DEFAULT_TENANT_ID, datetime.now(scheduler.ATTENDANCE_TIMEZONE), "scheduled:second"))

    def test_deletion_permissions_input_and_running_conflicts(self):
        self.save()
        path = "/api/attendance/reports"
        valid = {"ids": ["html-fixture"], "confirm": True}
        self.assertEqual(scheduler.app.test_client().delete(path, json=valid).status_code, 401)
        self.assertEqual(self.admin.delete(path, json=valid).status_code, 400)
        for body in ({"ids": []}, {"ids": ["html-fixture"]}, {"ids": ["html-fixture"] * 2, "confirm": True},
                     {"ids": [1], "confirm": True}, {"ids": ["x"] * 101, "confirm": True}):
            self.assertEqual(self.admin.delete(path, headers=self.headers, json=body).status_code, 400)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE attendance_reports SET state='running'")
        self.assertEqual(self.admin.delete(path, headers=self.headers, json=valid).status_code, 409)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE attendance_reports SET state='ready',tenant_id='other-tenant'")
        self.assertEqual(self.admin.delete(path, headers=self.headers, json=valid).status_code, 404)
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE tenants SET membership_tier='bronze'")
        self.assertEqual(self.admin.delete(path, headers=self.headers, json=valid).status_code, 403)

    def test_historical_captures_are_not_snapshot_actions(self):
        self.save()
        with closing(scheduler.database_connect()) as c, c:
            c.execute("UPDATE attendance_reports SET run_key='historical:fixture'")
        self.assertEqual(self.admin.get("/api/attendance/reports").get_json()["reports"], [])
        for suffix in ("/html", "/download", "/email"):
            self.assertEqual(self.admin.get("/api/attendance/reports/html-fixture" + suffix).status_code, 404)
        self.assertEqual(self.admin.delete("/api/attendance/reports", headers=self.headers,
                                          json={"ids": ["html-fixture"], "confirm": True}).status_code, 404)
        with closing(scheduler.database_connect()) as c:
            self.assertEqual(c.execute("SELECT state FROM attendance_reports").fetchone()[0], "ready")


if __name__ == "__main__":
    unittest.main()
