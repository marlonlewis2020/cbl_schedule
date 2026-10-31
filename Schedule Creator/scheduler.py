from pathlib import Path
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import json
import os
import sqlite3
import base64
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, send_from_directory

from directory_seed import (
    EMPLOYEE_ASSIGNMENTS,
    EMPLOYEE_ROLE_OVERRIDES,
    SCHEDULE_LOCATIONS,
    UNMAPPED_ROSTER_EMPLOYEE,
)


APP_DIRECTORY = Path(__file__).resolve().parent
load_dotenv(APP_DIRECTORY / ".env")
DATABASE_PATH = APP_DIRECTORY / "data" / "schedule_creator.sqlite3"
MAX_ACCEPTED_SCHEDULE_BYTES = 16 * 1024 * 1024
BAMBOOHR_SCHEDULES_URL = "https://cbljm.bamboohr.com/api/v1/scheduling/shifts"
BAMBOOHR_TIME_OFF_URL = "https://cbljm.bamboohr.com/api/v1/time_off/whos_out"
STATIC_ASSETS = {
    "CBL-Scheduler2.css",
    "CBL-Scheduler2.config.js",
    "CBL-Scheduler2.js",
    "CBL-MicrosoftAuth.html",
}

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_ACCEPTED_SCHEDULE_BYTES


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS accepted_schedules (
                run_id TEXT PRIMARY KEY,
                accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                week_start TEXT NOT NULL,
                location TEXT NOT NULL,
                role TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schedule_locations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                bamboo_schedule_id TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL,
                role_group TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY,
                bamboohr_id TEXT UNIQUE,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                schedule_location_id TEXT REFERENCES schedule_locations(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS app_migrations (
                migration_id TEXT PRIMARY KEY
            );
            """
        )
        migration = connection.execute(
            "SELECT 1 FROM app_migrations WHERE migration_id = ?",
            ("seed-employee-schedule-locations-v1",),
        ).fetchone()
        if migration is None:
            connection.executemany(
                """
                INSERT OR IGNORE INTO schedule_locations
                    (id, name, bamboo_schedule_id, location, role_group)
                VALUES (?, ?, ?, ?, ?)
                """,
                SCHEDULE_LOCATIONS,
            )
            location_data = {
                location_id: (location, role_group)
                for location_id, _, _, location, role_group in SCHEDULE_LOCATIONS
            }
            group_to_role = {
                "Warehouse/Delivery": "Warehouse",
                "Supervisors": "Supervisor (Warehouse)",
                "Settlement": "Settlement",
            }
            seeded_employees = []
            for bamboohr_id, employee_id, name, schedule_location_id in EMPLOYEE_ASSIGNMENTS:
                location, role_group = location_data[schedule_location_id]
                seeded_employees.append(
                    (
                        employee_id,
                        bamboohr_id,
                        name,
                        location,
                        EMPLOYEE_ROLE_OVERRIDES.get(
                            employee_id, group_to_role[role_group]
                        ),
                        0 if employee_id in {"901333", "901443", "901442"} else 1,
                        schedule_location_id,
                    )
                )
            connection.executemany(
                """
                INSERT OR IGNORE INTO employees
                    (employee_id, bamboohr_id, name, location, role, active, schedule_location_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                seeded_employees,
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO employees
                    (employee_id, bamboohr_id, name, location, role, active, schedule_location_id)
                VALUES (?, NULL, ?, ?, ?, 0, NULL)
                """,
                UNMAPPED_ROSTER_EMPLOYEE,
            )
            connection.execute(
                "INSERT INTO app_migrations (migration_id) VALUES (?)",
                ("seed-employee-schedule-locations-v1",),
            )
        role_migration = connection.execute(
            "SELECT 1 FROM app_migrations WHERE migration_id = ?",
            ("correct-kidd-warehouse-role-v2",),
        ).fetchone()
        if role_migration is None:
            connection.execute(
                """
                UPDATE employees SET role = 'Warehouse'
                WHERE employee_id = '901405' AND role = 'DC Associate'
                    AND schedule_location_id = 'kidd-warehouse-delivery'
                """
            )
            connection.execute(
                "INSERT INTO app_migrations (migration_id) VALUES (?)",
                ("correct-kidd-warehouse-role-v2",),
            )


def valid_schedule(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("id"), str)
        and bool(payload["id"])
        and isinstance(payload.get("start"), str)
        and isinstance(payload.get("location"), str)
        and isinstance(payload.get("role"), str)
        and isinstance(payload.get("employees"), list)
        and all(isinstance(employee, dict) for employee in payload["employees"])
    )


@app.get("/")
def index():
    return send_from_directory(APP_DIRECTORY, "CBL-Scheduler2.html")


@app.get("/<path:asset_name>")
def serve_asset(asset_name):
    if asset_name not in STATIC_ASSETS:
        abort(404)
    return send_from_directory(APP_DIRECTORY, asset_name)


@app.get("/api/accepted-shifts")
def list_accepted_shifts():
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT run_id, accepted_at, payload
            FROM accepted_schedules
            ORDER BY week_start DESC, accepted_at DESC, location, role
            """
        ).fetchall()
    return jsonify(
        schedules=[
            {
                "id": run_id,
                "acceptedAt": accepted_at,
                "schedule": json.loads(payload),
            }
            for run_id, accepted_at, payload in rows
        ]
    )


@app.post("/api/accepted-shifts")
def accept_shifts():
    payload = request.get_json(silent=True)
    if not valid_schedule(payload):
        return jsonify(error="A valid weekly schedule is required."), 400

    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_ACCEPTED_SCHEDULE_BYTES:
        return jsonify(error="The schedule is too large to save."), 413

    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute(
            """
            INSERT INTO accepted_schedules (run_id, week_start, location, role, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                week_start = excluded.week_start,
                location = excluded.location,
                role = excluded.role,
                payload = excluded.payload
            """,
            (
                payload["id"],
                payload["start"],
                payload["location"],
                payload["role"],
                encoded,
            ),
        )
        row = connection.execute(
            "SELECT accepted_at FROM accepted_schedules WHERE run_id = ?",
            (payload["id"],),
        ).fetchone()
    return jsonify(id=payload["id"], acceptedAt=row[0])


@app.put("/api/accepted-shifts/<path:run_id>")
def update_accepted_shifts(run_id: str):
    payload = request.get_json(silent=True)
    if not valid_schedule(payload) or payload["id"] != run_id:
        return jsonify(error="The updated schedule does not match the accepted schedule."), 400

    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_ACCEPTED_SCHEDULE_BYTES:
        return jsonify(error="The schedule is too large to save."), 413

    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        cursor = connection.execute(
            """
            UPDATE accepted_schedules
            SET week_start = ?, location = ?, role = ?, payload = ?
            WHERE run_id = ?
            """,
            (payload["start"], payload["location"], payload["role"], encoded, run_id),
        )
        if cursor.rowcount == 0:
            return jsonify(error="Accepted schedule was not found."), 404
    return jsonify(id=run_id)


@app.delete("/api/accepted-shifts/<path:run_id>")
def delete_accepted_shifts(run_id: str):
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM accepted_schedules WHERE run_id = ?", (run_id,)
        )
        if cursor.rowcount == 0:
            return jsonify(error="Accepted schedule was not found."), 404
    return jsonify(id=run_id)


def directory_employee(row: tuple) -> dict:
    return {
        "id": row[0],
        "bamboohrId": row[1],
        "name": row[2],
        "location": row[3],
        "role": row[4],
        "active": bool(row[5]),
        "scheduleLocationId": row[6],
    }


@app.get("/api/employees")
def list_employees():
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT employee_id, bamboohr_id, name, location, role, active, schedule_location_id
            FROM employees
            ORDER BY active DESC, name COLLATE NOCASE
            """
        ).fetchall()
    return jsonify(employees=[directory_employee(row) for row in rows])


@app.put("/api/employees/status")
def update_employee_statuses():
    payload = request.get_json(silent=True)
    employee_ids = payload.get("employeeIds") if isinstance(payload, dict) else None
    active = payload.get("active") if isinstance(payload, dict) else None
    if (
        not isinstance(employee_ids, list)
        or not employee_ids
        or any(not isinstance(employee_id, str) or not employee_id.strip() for employee_id in employee_ids)
        or len(employee_ids) != len(set(employee_ids))
        or not isinstance(active, bool)
    ):
        return jsonify(error="A non-empty list of unique employee IDs and an active status are required."), 400
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        placeholders = ",".join("?" for _ in employee_ids)
        rows = connection.execute(
            f"SELECT employee_id FROM employees WHERE employee_id IN ({placeholders})",
            employee_ids,
        ).fetchall()
        if len(rows) != len(employee_ids):
            return jsonify(error="One or more selected employees were not found."), 404
        connection.executemany(
            "UPDATE employees SET active = ? WHERE employee_id = ?",
            [(int(active), employee_id) for employee_id in employee_ids],
        )
    return jsonify(employeeIds=employee_ids, active=active)


def valid_employee(payload: object, *, require_bamboo_id: bool = True) -> bool:
    if not isinstance(payload, dict):
        return False
    fields = ("id", "name", "location", "role")
    if any(not isinstance(payload.get(field), str) or not payload[field].strip() for field in fields):
        return False
    bamboohr_id = payload.get("bamboohrId")
    if require_bamboo_id and (
        not isinstance(bamboohr_id, str) or not bamboohr_id.strip().isdigit()
    ):
        return False
    return isinstance(payload.get("active"), bool) and (
        payload.get("scheduleLocationId") is None
        or isinstance(payload.get("scheduleLocationId"), str)
    )


def role_matches_schedule_group(role: str, role_group: str) -> bool:
    normalized_role = role.strip().casefold()
    normalized_group = role_group.strip().casefold()
    if not normalized_group:
        return True
    if normalized_group == "warehouse/delivery":
        return normalized_role in {"warehouse", "dc associate"}
    if "supervisor" in normalized_group:
        return "supervisor" in normalized_role
    if "settlement" in normalized_group:
        return "settlement" in normalized_role
    return normalized_role == normalized_group


def employee_location_exists(connection: sqlite3.Connection, payload: dict) -> bool:
    location_id = payload.get("scheduleLocationId")
    if location_id is None:
        return True
    row = connection.execute(
        "SELECT location, role_group FROM schedule_locations WHERE id = ?", (location_id,)
    ).fetchone()
    return (
        row is not None
        and row[0] == payload["location"]
        and role_matches_schedule_group(payload["role"], row[1])
    )


def directory_conflict(error: sqlite3.IntegrityError):
    return jsonify(error="Employee ID or BambooHR ID is already in use."), 409


@app.post("/api/employees")
def create_employee():
    payload = request.get_json(silent=True)
    if not valid_employee(payload):
        return jsonify(error="Employee ID, BambooHR ID, name, location, role, and active status are required."), 400
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        if not employee_location_exists(connection, payload):
            return jsonify(error="The assigned schedule location does not match the employee's location."), 400
        try:
            connection.execute(
                """
                INSERT INTO employees
                    (employee_id, bamboohr_id, name, location, role, active, schedule_location_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"].strip(),
                    payload["bamboohrId"].strip(),
                    payload["name"].strip(),
                    payload["location"].strip(),
                    payload["role"].strip(),
                    int(payload["active"]),
                    payload.get("scheduleLocationId"),
                ),
            )
        except sqlite3.IntegrityError as error:
            return directory_conflict(error)
    return jsonify(employee=payload), 201


@app.put("/api/employees/<path:employee_id>")
def update_employee(employee_id: str):
    payload = request.get_json(silent=True)
    if not valid_employee(payload):
        return jsonify(error="Employee ID, BambooHR ID, name, location, role, and active status are required."), 400
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        if not employee_location_exists(connection, payload):
            return jsonify(error="The assigned schedule location does not match the employee's location."), 400
        try:
            cursor = connection.execute(
                """
                UPDATE employees
                SET employee_id = ?, bamboohr_id = ?, name = ?, location = ?, role = ?,
                    active = ?, schedule_location_id = ?
                WHERE employee_id = ?
                """,
                (
                    payload["id"].strip(),
                    payload["bamboohrId"].strip(),
                    payload["name"].strip(),
                    payload["location"].strip(),
                    payload["role"].strip(),
                    int(payload["active"]),
                    payload.get("scheduleLocationId"),
                    employee_id,
                ),
            )
        except sqlite3.IntegrityError as error:
            return directory_conflict(error)
        if cursor.rowcount == 0:
            return jsonify(error="Employee was not found."), 404
    return jsonify(employee=payload)


@app.delete("/api/employees/<path:employee_id>")
def delete_employee(employee_id: str):
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM employees WHERE employee_id = ?", (employee_id,)
        )
        if cursor.rowcount == 0:
            return jsonify(error="Employee was not found."), 404
    return jsonify(id=employee_id)


@app.get("/api/schedule-locations")
def list_schedule_locations():
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT s.id, s.name, s.bamboo_schedule_id, s.location, s.role_group,
                   COUNT(e.employee_id)
            FROM schedule_locations s
            LEFT JOIN employees e ON e.schedule_location_id = s.id
            GROUP BY s.id
            ORDER BY s.name COLLATE NOCASE
            """
        ).fetchall()
    return jsonify(
        scheduleLocations=[
            {
                "id": row[0],
                "name": row[1],
                "bambooScheduleId": row[2],
                "location": row[3],
                "roleGroup": row[4],
                "employeeCount": row[5],
            }
            for row in rows
        ]
    )


def valid_schedule_location(payload: object) -> bool:
    return isinstance(payload, dict) and all(
        isinstance(payload.get(field), str) and payload[field].strip()
        for field in ("name", "bambooScheduleId", "location")
    )


def schedule_location_conflict(error: sqlite3.IntegrityError):
    return jsonify(error="Schedule name or BambooHR schedule ID is already in use."), 409


@app.post("/api/schedule-locations")
def create_schedule_location():
    payload = request.get_json(silent=True)
    if not valid_schedule_location(payload):
        return jsonify(error="Schedule name, BambooHR schedule ID, and location are required."), 400
    location_id = os.urandom(16).hex()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        try:
            connection.execute(
                """
                INSERT INTO schedule_locations
                    (id, name, bamboo_schedule_id, location, role_group)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    location_id,
                    payload["name"].strip(),
                    payload["bambooScheduleId"].strip(),
                    payload["location"].strip(),
                    str(payload.get("roleGroup", "")).strip(),
                ),
            )
        except sqlite3.IntegrityError as error:
            return schedule_location_conflict(error)
    return jsonify(id=location_id), 201


@app.put("/api/schedule-locations/<path:location_id>")
def update_schedule_location(location_id: str):
    payload = request.get_json(silent=True)
    if not valid_schedule_location(payload):
        return jsonify(error="Schedule name, BambooHR schedule ID, and location are required."), 400
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        assigned_roles = connection.execute(
            "SELECT role FROM employees WHERE schedule_location_id = ?",
            (location_id,),
        ).fetchall()
        if any(
            not role_matches_schedule_group(role[0], str(payload.get("roleGroup", "")))
            for role in assigned_roles
        ):
            return jsonify(error="The schedule role group must match every assigned employee role."), 400
        try:
            cursor = connection.execute(
                """
                UPDATE schedule_locations
                SET name = ?, bamboo_schedule_id = ?, location = ?, role_group = ?
                WHERE id = ?
                """,
                (
                    payload["name"].strip(),
                    payload["bambooScheduleId"].strip(),
                    payload["location"].strip(),
                    str(payload.get("roleGroup", "")).strip(),
                    location_id,
                ),
            )
        except sqlite3.IntegrityError as error:
            return schedule_location_conflict(error)
        if cursor.rowcount == 0:
            return jsonify(error="Schedule location was not found."), 404
        connection.execute(
            "UPDATE employees SET location = ? WHERE schedule_location_id = ?",
            (payload["location"].strip(), location_id),
        )
    return jsonify(id=location_id)


@app.delete("/api/schedule-locations/<path:location_id>")
def delete_schedule_location(location_id: str):
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        assigned = connection.execute(
            "SELECT COUNT(*) FROM employees WHERE schedule_location_id = ?",
            (location_id,),
        ).fetchone()[0]
        if assigned:
            return jsonify(error="Reassign employees before deleting this schedule location."), 409
        cursor = connection.execute(
            "DELETE FROM schedule_locations WHERE id = ?", (location_id,)
        )
        if cursor.rowcount == 0:
            return jsonify(error="Schedule location was not found."), 404
    return jsonify(id=location_id)


@app.put("/api/schedule-locations/<path:location_id>/employees")
def assign_schedule_location_employees(location_id: str):
    payload = request.get_json(silent=True)
    employee_ids = payload.get("employeeIds") if isinstance(payload, dict) else None
    if not isinstance(employee_ids, list) or any(
        not isinstance(employee_id, str) for employee_id in employee_ids
    ):
        return jsonify(error="A list of employee IDs is required."), 400
    if len(employee_ids) != len(set(employee_ids)):
        return jsonify(error="An employee can only be assigned once."), 400
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        location = connection.execute(
            "SELECT location, role_group FROM schedule_locations WHERE id = ?", (location_id,)
        ).fetchone()
        if not location:
            return jsonify(error="Schedule location was not found."), 404
        if employee_ids:
            placeholders = ",".join("?" for _ in employee_ids)
            employees = connection.execute(
                f"""
                SELECT employee_id, active, bamboohr_id, role
                FROM employees WHERE employee_id IN ({placeholders})
                """,
                employee_ids,
            ).fetchall()
            if len(employees) != len(employee_ids):
                return jsonify(error="One or more selected employees were not found."), 404
            if any(not active or not bamboo_id or not role for _, active, bamboo_id, role in employees):
                return jsonify(error="Only active employees with BambooHR IDs and roles can be assigned."), 400
            if any(not role_matches_schedule_group(role, location[1]) for _, _, _, role in employees):
                return jsonify(error="Selected employee roles do not match this schedule location's role group."), 400
        connection.execute(
            """
            UPDATE employees SET schedule_location_id = NULL
            WHERE schedule_location_id = ? AND active = 1
            """,
            (location_id,),
        )
        connection.executemany(
            """
            UPDATE employees
            SET schedule_location_id = ?, location = ?
            WHERE employee_id = ?
            """,
            [(location_id, location[0], employee_id) for employee_id in employee_ids],
        )
    return jsonify(id=location_id, employeeIds=employee_ids)


def accepted_schedule_selections(
    connection: sqlite3.Connection, selections: object
) -> list[dict]:
    if not isinstance(selections, list) or not selections:
        raise ValueError("Select at least one accepted shift.")
    if len(selections) > 500:
        raise ValueError("Select no more than 500 shifts per publish request.")
    lookup = {}
    for selection in selections:
        if not isinstance(selection, dict):
            raise ValueError("Each selected shift must specify a schedule, day, and start.")
        run_id = selection.get("runId")
        day = selection.get("day")
        start = selection.get("start")
        if (
            not isinstance(run_id, str)
            or not isinstance(day, int)
            or isinstance(day, bool)
            or not 0 <= day < 7
            or not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not 0 <= start < 24
        ):
            raise ValueError("A selected shift contains an invalid schedule, day, or start.")
        key = (run_id, day, float(start))
        if key in lookup:
            raise ValueError("The same accepted shift was selected more than once.")
        lookup[key] = None

    run_ids = list({run_id for run_id, _, _ in lookup})
    placeholders = ",".join("?" for _ in run_ids)
    rows = connection.execute(
        f"SELECT run_id, payload FROM accepted_schedules WHERE run_id IN ({placeholders})",
        run_ids,
    ).fetchall()
    schedules = {run_id: json.loads(payload) for run_id, payload in rows}
    for run_id, day, start in lookup:
        schedule = schedules.get(run_id)
        if not schedule:
            raise ValueError(f"Accepted schedule {run_id} was not found.")
        if start not in [float(value) for value in schedule.get("shiftStarts", [])]:
            raise ValueError(f"Shift start {start} is not configured in accepted schedule {run_id}.")
        lookup[(run_id, day, start)] = schedule
    return [
        {"runId": run_id, "day": day, "start": start, "schedule": schedule}
        for (run_id, day, start), schedule in lookup.items()
    ]


def bamboo_payloads(
    connection: sqlite3.Connection, selections: list[dict]
) -> list[dict]:
    payloads = {}
    employee_rows = connection.execute(
        """
        SELECT employee_id, bamboohr_id, active, schedule_location_id, location, role
        FROM employees
        """
    ).fetchall()
    employees = {row[0]: row for row in employee_rows}
    schedule_rows = connection.execute(
        "SELECT id, bamboo_schedule_id, location, name, role_group FROM schedule_locations"
    ).fetchall()
    locations = {row[0]: row for row in schedule_rows}

    for selection in selections:
        schedule = selection["schedule"]
        day, start = selection["day"], selection["start"]
        start_time = datetime.fromisoformat(schedule["start"]).date() + timedelta(days=day)
        minute_of_day = round(start * 60)
        local_start = datetime.combine(
            start_time,
            time(minute_of_day // 60, minute_of_day % 60),
            tzinfo=ZoneInfo("America/Jamaica"),
        )
        span = schedule.get("controls", {}).get("span")
        if not isinstance(span, (int, float)) or not 0 < span <= 24:
            raise ValueError(f"Accepted schedule {schedule['id']} has no valid shift duration.")
        local_end = local_start + timedelta(hours=span)

        for assigned in schedule.get("employees", []):
            if not isinstance(assigned, dict) or day >= len(assigned.get("slots", [])):
                continue
            if assigned["slots"][day] != start:
                continue
            employee = employees.get(str(assigned.get("id", "")))
            if not employee or not employee[2] or not employee[1]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned.get('id', ''))} is inactive "
                    "or has no BambooHR ID."
                )
            if "active" in assigned and not assigned["active"]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} was inactive when "
                    "the schedule was accepted."
                )
            if "bamboohrId" in assigned and str(assigned["bamboohrId"] or "") != str(employee[1]):
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has a different "
                    "BambooHR ID than when the schedule was accepted. Accept the updated schedule again."
                )
            if "scheduleLocationId" in assigned and assigned["scheduleLocationId"] != employee[3]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has a different "
                    "schedule location than when the schedule was accepted. Accept the updated schedule again."
                )
            if "directoryLocation" in assigned and assigned["directoryLocation"] != employee[4]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has a different "
                    "app location than when the schedule was accepted. Accept the updated schedule again."
                )
            if "directoryRole" in assigned and assigned["directoryRole"] != employee[5]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has a different "
                    "role than when the schedule was accepted. Accept the updated schedule again."
                )
            schedule_location_id = assigned.get("scheduleLocationId") or employee[3]
            location = locations.get(schedule_location_id)
            if not location:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has no valid BambooHR schedule location."
                )
            if "bambooScheduleId" in assigned and assigned["bambooScheduleId"] != location[1]:
                raise ValueError(
                    f"The BambooHR schedule mapping for {assigned.get('name', assigned['id'])} "
                    "changed after acceptance. Accept the updated schedule again."
                )
            if location[2] != schedule.get("location") or employee[4] != location[2]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} is not mapped to "
                    f"the accepted schedule's {schedule.get('location')} location."
                )
            if not role_matches_schedule_group(str(assigned.get("role", employee[5])), location[4]):
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} does not match "
                    f"the {location[3]} schedule role group."
                )
            group_key = (location[0], local_start.isoformat())
            payload = payloads.setdefault(
                group_key,
                {
                    "scheduleId": location[1],
                    "status": "published",
                    "color": "00FFAA",
                    "employeeIds": [],
                    "timezone": "America/Jamaica",
                    "start": local_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "end": local_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "scheduleName": location[3],
                    "employeeNames": [],
                },
            )
            bamboohr_id = int(employee[1]) if employee[1].isdigit() else employee[1]
            if bamboohr_id not in payload["employeeIds"]:
                payload["employeeIds"].append(bamboohr_id)
                payload["employeeNames"].append(assigned.get("name", assigned["id"]))

    if not payloads:
        raise ValueError("The selected shifts have no assigned employees.")
    return sorted(payloads.values(), key=lambda item: (item["start"], item["scheduleName"]))


def bamboo_preview_response(payloads: list[dict]) -> list[dict]:
    return [
        {
            "scheduleName": payload["scheduleName"],
            "scheduleId": payload["scheduleId"],
            "start": payload["start"],
            "end": payload["end"],
            "employeeIds": payload["employeeIds"],
            "employeeNames": payload["employeeNames"],
            "timezone": payload["timezone"],
        }
        for payload in payloads
    ]


@app.get("/api/bamboohr/status")
def bamboohr_status():
    return jsonify(configured=bool(os.environ.get("BAMBOOHR_API_KEY", "").strip()))


@app.get("/api/bamboohr/time-offs")
def bamboohr_time_offs():
    start_text, end_text = request.args.get("start", ""), request.args.get("end", "")
    try:
        start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
    except ValueError:
        return jsonify(error="Provide valid start and end dates in YYYY-MM-DD format."), 400
    if start.isoformat() != start_text or end.isoformat() != end_text or end < start:
        return jsonify(error="Provide a valid inclusive time-off date range."), 400

    api_key = os.environ.get("BAMBOOHR_API_KEY", "").strip()
    if not api_key:
        return jsonify(error="BAMBOOHR_API_KEY is not configured on the app server."), 503

    authorization = base64.b64encode(f"{api_key}:x".encode("utf-8")).decode("ascii")
    outbound = Request(
        f"{BAMBOOHR_TIME_OFF_URL}?{urlencode({'start': start_text, 'end': end_text})}",
        headers={"Accept": "application/json", "Authorization": f"Basic {authorization}"},
        method="GET",
    )
    try:
        with urlopen(outbound, timeout=20) as response:
            raw_data = response.read(10_000_001)
        if len(raw_data) > 10_000_000:
            return jsonify(error="BambooHR time-off response exceeds the allowed size."), 502
        data = json.loads(raw_data)
        if not isinstance(data, list):
            return jsonify(error="BambooHR returned an invalid time-off response."), 502
        entries = []
        for item in data:
            if not isinstance(item, dict) or item.get("type") != "timeOff":
                continue
            if item.get("status") and str(item["status"]).casefold() != "approved":
                continue
            name, item_start, item_end = item.get("name"), item.get("start"), item.get("end")
            if not isinstance(name, str) or not name.strip():
                return jsonify(error="BambooHR returned a time-off record without an employee name."), 502
            try:
                leave_start, leave_end = date.fromisoformat(item_start), date.fromisoformat(item_end)
            except (TypeError, ValueError):
                return jsonify(error="BambooHR returned a time-off record with invalid dates."), 502
            if (
                leave_start.isoformat() != item_start
                or leave_end.isoformat() != item_end
                or leave_end < leave_start
            ):
                return jsonify(error="BambooHR returned a time-off record with invalid dates."), 502
            if leave_end >= start and leave_start <= end:
                entries.append(
                    {
                        "id": item.get("id", ""),
                        "type": "timeOff",
                        "employeeId": item.get("employeeId", ""),
                        "name": name.strip(),
                        "start": item_start,
                        "end": item_end,
                    }
                )
    except HTTPError as error:
        return jsonify(error=f"BambooHR time-off request failed with HTTP {error.code}."), 502
    except (URLError, TimeoutError, OSError):
        return jsonify(error="The app server could not reach BambooHR for time-off data."), 502
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify(error="BambooHR returned an invalid time-off response."), 502
    return jsonify(start=start_text, end=end_text, entries=entries)


@app.post("/api/bamboohr/preview")
def preview_bamboohr_publish():
    payload = request.get_json(silent=True)
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        try:
            selections = accepted_schedule_selections(
                connection, payload.get("selections") if isinstance(payload, dict) else None
            )
            prepared = bamboo_payloads(connection, selections)
        except (ValueError, KeyError, TypeError) as error:
            return jsonify(error=str(error)), 400
    return jsonify(payloads=bamboo_preview_response(prepared))


@app.post("/api/bamboohr/publish")
def publish_bamboohr_schedules():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        return jsonify(error="Explicit confirmation is required before publishing."), 400
    api_key = os.environ.get("BAMBOOHR_API_KEY", "").strip()
    if not api_key:
        return jsonify(error="Set BAMBOOHR_API_KEY on the app server before publishing."), 503
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        try:
            selections = accepted_schedule_selections(connection, payload.get("selections"))
            prepared = bamboo_payloads(connection, selections)
        except (ValueError, KeyError, TypeError) as error:
            return jsonify(error=str(error)), 400

    authorization = base64.b64encode(f"{api_key}:x".encode("utf-8")).decode("ascii")
    results = []
    for schedule_payload in prepared:
        request_payload = {
            key: value
            for key, value in schedule_payload.items()
            if key not in {"scheduleName", "employeeNames"}
        }
        outbound = Request(
            BAMBOOHR_SCHEDULES_URL,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Basic {authorization}",
            },
            method="POST",
        )
        result = {
            "scheduleName": schedule_payload["scheduleName"],
            "start": schedule_payload["start"],
            "employeeIds": schedule_payload["employeeIds"],
        }
        try:
            with urlopen(outbound, timeout=20) as response:
                result.update(status=response.status, success=200 <= response.status < 300)
                if not result["success"]:
                    result["error"] = response.read(2000).decode("utf-8", errors="replace")
        except HTTPError as error:
            result.update(
                status=error.code,
                success=False,
                error=error.read(2000).decode("utf-8", errors="replace"),
            )
        except URLError as error:
            result.update(status=None, success=False, error=str(error.reason))
        results.append(result)
    return jsonify(results=results), (200 if all(result["success"] for result in results) else 502)


def main() -> None:
    initialize_database()
    port = int(os.environ.get("SCHEDULE_CREATOR_PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
