import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import patch

import scheduler


class AcceptedScheduleApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_path = scheduler.DATABASE_PATH
        scheduler.DATABASE_PATH = Path(self.temporary_directory.name) / "schedules.sqlite3"
        scheduler.initialize_database()
        scheduler.app.config["TESTING"] = True
        self.client = scheduler.app.test_client()
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


class DirectoryAndBambooApiTests(unittest.TestCase):
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
            "bamboohrId": "999",
            "name": "Test Employee",
            "location": "Kingston",
            "role": "Cashier",
            "active": False,
            "scheduleLocationId": None,
        }
        created = self.client.post("/api/employees", json=payload)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.client.post("/api/employees", json=payload).status_code, 409)
        payload["bamboohrId"] = ""
        self.assertEqual(self.client.post("/api/employees", json=payload).status_code, 400)

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
            },
        )
        self.assertEqual(created.status_code, 201)
        location_id = created.get_json()["id"]
        employee = {
            "id": "900998",
            "bamboohrId": "998",
            "name": "Temporary Employee",
            "location": "Kingston",
            "role": "Cashier",
            "active": False,
            "scheduleLocationId": location_id,
        }
        self.assertEqual(self.client.post("/api/employees", json=employee).status_code, 201)
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
            },
        )
        self.assertEqual(location_response.status_code, 201)
        location_id = location_response.get_json()["id"]
        employee_response = self.client.post(
            "/api/employees",
            json={
                "id": "990001",
                "bamboohrId": "9901",
                "name": "Publish Test",
                "location": "Kingston",
                "role": "Cashier",
                "active": True,
                "scheduleLocationId": location_id,
            },
        )
        self.assertEqual(employee_response.status_code, 201)
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

    def test_publish_requires_confirmation_and_reports_mocked_success(self):
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
        ):
            response = self.client.post(
                "/api/bamboohr/publish",
                json={"confirmed": True, "selections": selections},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["results"][0]["success"])


if __name__ == "__main__":
    unittest.main()
