from pathlib import Path
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import json
import os
import re
import secrets
import sqlite3
import base64
import time as time_module
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from dotenv import dotenv_values, load_dotenv, set_key, unset_key
from flask import Flask, abort, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

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
ENV_PATH = APP_DIRECTORY / ".env"
DEFAULT_APP_CONFIG = {
    "businessName": "Celebration Brands Limited",
    "teamName": "Schedule Management",
    "logoDataUrl": "",
    "primaryColor": "#159bd5",
    "accentColor": "#74bf16",
    "tenantId": "cbljm",
}
MAX_LOGO_BYTES = 2 * 1024 * 1024
_validated_bamboo_keys: dict[str, tuple[str, str, datetime]] = {}
STATIC_ASSETS = {
    "CBL-Scheduler2.css",
    "CBL-Scheduler2.config.js",
    "CBL-Scheduler2.js",
    "CBL-MicrosoftAuth.html",
}
DEVELOPER_REQUESTS = (
    (
        "developer-change-log",
        "Developer change-request log",
        "Provide a developer-only, password-protected change-request log with request statuses, filters, dependency/blocker display, secure credential updates, and approval before logging new requests. Do not use shared default credentials. The initial local developer account is established through a loopback-only setup flow.",
        (),
    ),
    (
        "tenant-identity",
        "Secure tenant identity foundation",
        "Move the current local single-business scheduler to a secure multi-tenant deployment with verified admin authentication, hashed credentials, tenant isolation, role checks, audit events, HTTPS, and a production database. Preserve the existing business as an explicitly migrated tenant.",
        (),
    ),
    (
        "business-hub",
        "Business registration and SaaS hub",
        "Create a separate SaaS hub for business registration, business details, BambooHR tenant/API credential validation and encrypted storage, the main business admin and additional admins, two-factor authentication enrollment, manual approval/rejection, and active/pending/suspended membership states. Pending businesses may sign in only to complete onboarding and view status; scheduling stays disabled until active. Decide whether two-factor authentication is mandatory for every admin.",
        ("tenant-identity",),
    ),
    (
        "tier-entitlements",
        "Membership tiers and feature entitlements",
        "Enforce Bronze (2 admins, 2 separately configured teams, 20 active employees), Silver (3 admins, 4 teams, 60 employees), Gold (4 admins, up to 6 schedule locations), and Platinum (8 admins, unlimited schedule locations). Gold and Platinum have unlimited active employees. All tiers include schedule generation, sharing, BambooHR publishing, email configuration, employee management, and settings. Higher-tier features include employee schedule access, shift trades, schedule history, overtime forecasting, and user licenses; finalize the exact feature-to-tier matrix.",
        ("business-hub",),
    ),
    (
        "manager-employee-access",
        "Manager and employee authentication",
        "Add verified individual sign-in for admins, schedule-location managers, and employees. Managers may manage/view locations assigned to their verified manager email. Employees authenticate individually and receive only the full schedule for their assigned location and role. Schedule codes are additional checks, not sole credentials.",
        ("tenant-identity", "business-hub", "tier-entitlements"),
    ),
    (
        "schedule-portal",
        "Employee schedule portal and access tokens",
        "Generate cryptographically random, unique, expiring six-digit access codes for each location/role schedule period and include them in manager confirmation messages. The employee portal validates identity, location, role, period, and schedule assignment before revealing the full location/role schedule. Add configurable schedule visibility cadence in weeks and manager access to all assigned locations.",
        ("manager-employee-access",),
    ),
    (
        "shift-trades",
        "Authenticated shift-trade workflow",
        "Add server-side trade records, inbox/notifications, schedule indicators, and an auditable status history: employee request, affected-employee confirmation, manager acceptance, workforce-admin approval, and applied/published, with rejection/withdrawal states. Managers may initiate on an employee's behalf with employee confirmation skipped but workforce approval retained. Employees cannot approve manager or workforce-admin trades. Block non-admin trades for started or past shifts.",
        ("manager-employee-access", "schedule-portal"),
    ),
    (
        "trade-publishing",
        "Approved trade and published-schedule reconciliation",
        "Apply workforce-admin-approved trades to accepted schedules. For already-published shifts, preview and confirm replacement/deletion actions, then update the app and BambooHR with visible success/failure states, retries/reconciliation, and audit history. Include admin overrides for past shifts and manual shift/day-off assignments. Verify BambooHR permissions and supported operations before implementation.",
        ("shift-trades",),
    ),
    (
        "recurring-billing",
        "Membership billing and payment providers",
        "As a later phase, add monthly/annual prices, optional auto-renew, PayPal first behind a provider abstraction, hosted/tokenized payment details, signed webhooks, reminders, daily retries up to seven attempts, suspension after repeated failure, and restoration after successful/manual payment. Never store raw payment credentials. Allow SaaS admins to configure tier features and prices with audit history.",
        ("business-hub", "tier-entitlements"),
    ),
    (
        "copilot-builder",
        "Copilot-reviewed request staging and implementation",
        "Integrate an explicitly authorized Copilot coding-agent/SDK service for drafting/reviewing requests, requiring user approval before logging, selecting the next dependency-ready request, and displaying isolated build progress/results. Run each build in a separate branch/workspace, test it, and require human review/merge; do not deploy or commit directly to the live app. This remains unavailable until a supported Copilot integration, credentials, and isolated runner are configured.",
        ("developer-change-log",),
    ),
)

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_ACCEPTED_SCHEDULE_BYTES
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"


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
                role_group TEXT NOT NULL DEFAULT '',
                manager_name TEXT NOT NULL DEFAULT '',
                manager_email TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY,
                bamboohr_id TEXT UNIQUE,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                schedule_location_id TEXT REFERENCES schedule_locations(id) ON DELETE SET NULL,
                source_type TEXT NOT NULL DEFAULT 'bamboohr' CHECK (source_type IN ('bamboohr', 'manual')),
                bamboohr_location TEXT NOT NULL DEFAULT '',
                bamboohr_active INTEGER NOT NULL DEFAULT 1 CHECK (bamboohr_active IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS app_migrations (
                migration_id TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS application_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS developer_users (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                auth_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS developer_login_attempts (
                client_key TEXT PRIMARY KEY,
                failures INTEGER NOT NULL DEFAULT 0,
                window_started_at INTEGER NOT NULL,
                locked_until INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS developer_change_requests (
                request_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'blocked', 'done', 'rejected')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS developer_change_request_dependencies (
                request_id TEXT NOT NULL REFERENCES developer_change_requests(request_id) ON DELETE CASCADE,
                depends_on TEXT NOT NULL REFERENCES developer_change_requests(request_id) ON DELETE CASCADE,
                PRIMARY KEY (request_id, depends_on),
                CHECK (request_id != depends_on)
            );
            """
        )
        for request_id, title, description, _ in DEVELOPER_REQUESTS:
            status = "done" if request_id == "developer-change-log" else "pending"
            connection.execute(
                """
                INSERT OR IGNORE INTO developer_change_requests
                    (request_id, title, description, status)
                VALUES (?, ?, ?, ?)
                """,
                (request_id, title, description, status),
            )
        for request_id, _, _, dependencies in DEVELOPER_REQUESTS:
            connection.executemany(
                """
                INSERT OR IGNORE INTO developer_change_request_dependencies
                    (request_id, depends_on)
                VALUES (?, ?)
                """,
                [(request_id, dependency) for dependency in dependencies],
            )
        connection.executemany(
            "INSERT OR IGNORE INTO application_settings (setting_key, setting_value) VALUES (?, ?)",
            DEFAULT_APP_CONFIG.items(),
        )
        location_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(schedule_locations)")
        }
        for column, definition in (
            ("manager_name", "TEXT NOT NULL DEFAULT ''"),
            ("manager_email", "TEXT NOT NULL DEFAULT ''"),
        ):
            if column not in location_columns:
                connection.execute(
                    f"ALTER TABLE schedule_locations ADD COLUMN {column} {definition}"
                )
        employee_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(employees)")
        }
        source_type_missing = "source_type" not in employee_columns
        for column, definition in (
            ("source_type", "TEXT NOT NULL DEFAULT 'bamboohr'"),
            ("bamboohr_location", "TEXT NOT NULL DEFAULT ''"),
            ("bamboohr_active", "INTEGER NOT NULL DEFAULT 1"),
        ):
            if column not in employee_columns:
                connection.execute(f"ALTER TABLE employees ADD COLUMN {column} {definition}")
        if source_type_missing:
            connection.execute(
                """
                UPDATE employees
                SET source_type = CASE WHEN bamboohr_id IS NULL THEN 'manual' ELSE 'bamboohr' END
                """
            )
            connection.execute(
                """
                UPDATE employees
                SET bamboohr_id = 'MANUAL-' || lower(hex(randomblob(12)))
                WHERE source_type = 'manual' AND (bamboohr_id IS NULL OR bamboohr_id = '')
                """
            )
        else:
            connection.execute(
                """
                UPDATE employees
                SET bamboohr_id = 'MANUAL-' || lower(hex(randomblob(12)))
                WHERE source_type = 'manual' AND (bamboohr_id IS NULL OR bamboohr_id = '')
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
                    (employee_id, bamboohr_id, name, location, role, active, schedule_location_id, source_type, bamboohr_active)
                VALUES (?, NULL, ?, ?, ?, 0, NULL, 'manual', 0)
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


def current_app_config() -> dict[str, str]:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        rows = connection.execute(
            "SELECT setting_key, setting_value FROM application_settings"
        ).fetchall()
    config = DEFAULT_APP_CONFIG | dict(rows)
    config["apiKeyConfigured"] = str(bool(os.environ.get("BAMBOOHR_API_KEY", "").strip())).lower()
    return config


def bamboohr_endpoint(path: str) -> str:
    tenant_id = current_app_config()["tenantId"]
    return f"https://{tenant_id}.bamboohr.com/api/v1/{path.lstrip('/')}"


def valid_tenant_id(value: object) -> bool:
    return isinstance(value, str) and len(value) <= 63 and re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9-]*", value
    ) is not None


def validate_logo_data_url(value: object) -> str | None:
    if value == "":
        return ""
    if not isinstance(value, str) or len(value) > (MAX_LOGO_BYTES * 4 // 3) + 128:
        return None
    match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", value)
    if not match:
        return None
    try:
        image_bytes = base64.b64decode(match.group(2), validate=True)
    except ValueError:
        return None
    if len(image_bytes) > MAX_LOGO_BYTES:
        return None
    image_type = match.group(1)
    valid_signature = (
        image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        if image_type == "png"
        else image_bytes.startswith(b"\xff\xd8\xff")
        if image_type == "jpeg"
        else image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP"
    )
    return value if valid_signature else None


def valid_app_config(payload: object) -> dict[str, str] | None:
    if not isinstance(payload, dict):
        return None
    business_name = payload.get("businessName")
    team_name = payload.get("teamName")
    tenant_id = payload.get("tenantId")
    primary_color = payload.get("primaryColor")
    accent_color = payload.get("accentColor")
    logo_data_url = validate_logo_data_url(payload.get("logoDataUrl", ""))
    if (
        not isinstance(business_name, str)
        or not business_name.strip()
        or len(business_name.strip()) > 120
        or not isinstance(team_name, str)
        or not team_name.strip()
        or len(team_name.strip()) > 120
        or not valid_tenant_id(tenant_id)
        or not isinstance(primary_color, str)
        or re.fullmatch(r"#[0-9a-fA-F]{6}", primary_color) is None
        or not isinstance(accent_color, str)
        or re.fullmatch(r"#[0-9a-fA-F]{6}", accent_color) is None
        or logo_data_url is None
    ):
        return None
    return {
        "businessName": business_name.strip(),
        "teamName": team_name.strip(),
        "logoDataUrl": logo_data_url,
        "primaryColor": primary_color.lower(),
        "accentColor": accent_color.lower(),
        "tenantId": tenant_id.lower(),
    }


def save_app_config(config: dict[str, str]) -> None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.executemany(
            """
            INSERT INTO application_settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
            """,
            config.items(),
        )


@app.get("/")
def index():
    return send_from_directory(APP_DIRECTORY, "CBL-Scheduler2.html")


@app.get("/<path:asset_name>")
def serve_asset(asset_name):
    if asset_name not in STATIC_ASSETS:
        abort(404)
    return send_from_directory(APP_DIRECTORY, asset_name)


def developer_csrf_valid() -> bool:
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("developer_csrf", "")
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


def developer_authenticated() -> bool:
    username = session.get("developer_username")
    auth_version = session.get("developer_auth_version")
    if not isinstance(username, str) or not isinstance(auth_version, int):
        return False
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        account = connection.execute(
            "SELECT username, auth_version FROM developer_users WHERE id = 1"
        ).fetchone()
    if (
        not account
        or account[0] != username
        or account[1] != auth_version
    ):
        session.clear()
        return False
    return True


def developer_local_request() -> bool:
    return request.remote_addr in {"127.0.0.1", "::1"}


def valid_developer_username(value: object) -> bool:
    return isinstance(value, str) and 3 <= len(value.strip()) <= 64


def valid_developer_password(value: object) -> bool:
    return isinstance(value, str) and len(value) >= 14 and len(value) <= 1024


@app.get("/developer/change-requests")
def developer_change_requests_page():
    return send_from_directory(APP_DIRECTORY, "developer-change-requests.html")


@app.get("/api/developer/auth-state")
def developer_auth_state():
    csrf_token = session.get("developer_csrf")
    if not isinstance(csrf_token, str):
        csrf_token = secrets.token_urlsafe(32)
        session["developer_csrf"] = csrf_token
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        configured = connection.execute(
            "SELECT 1 FROM developer_users WHERE id = 1"
        ).fetchone() is not None
    authenticated = developer_authenticated()
    return jsonify(
        configured=configured,
        authenticated=authenticated,
        username=session.get("developer_username") if authenticated else None,
        csrfToken=csrf_token,
        canBootstrap=not configured and developer_local_request(),
    )


@app.post("/api/developer/setup")
def setup_developer_account():
    if not developer_local_request():
        return jsonify(error="Initial developer setup is allowed only from this computer."), 403
    if not developer_csrf_valid():
        return jsonify(error="The setup session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not valid_developer_username(payload.get("username"))
        or not valid_developer_password(payload.get("password"))
    ):
        return jsonify(
            error="Enter a username of 3–64 characters and a password of at least 14 characters."
        ), 400
    username = payload["username"].strip()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        try:
            connection.execute(
                """
                INSERT INTO developer_users (id, username, password_hash)
                VALUES (1, ?, ?)
                """,
                (username, generate_password_hash(payload["password"])),
            )
        except sqlite3.IntegrityError:
            return jsonify(error="Developer access has already been initialized."), 409
    session.clear()
    session["developer_username"] = username
    session["developer_auth_version"] = 1
    session["developer_csrf"] = secrets.token_urlsafe(32)
    return jsonify(username=username, csrfToken=session["developer_csrf"])


@app.post("/api/developer/login")
def developer_login():
    if not developer_csrf_valid():
        return jsonify(error="The login session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Enter your developer username and password."), 400
    now = int(time_module.time())
    client_key = request.remote_addr or "unknown"
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        attempt = connection.execute(
            """
            SELECT failures, window_started_at, locked_until
            FROM developer_login_attempts WHERE client_key = ?
            """,
            (client_key,),
        ).fetchone()
        if attempt and attempt[2] > now:
            return jsonify(error="Too many failed sign-in attempts. Try again later."), 429
        if not attempt or now - attempt[1] >= 900:
            failures, window_started_at = 0, now
        else:
            failures, window_started_at = attempt[0], attempt[1]
        account = connection.execute(
            "SELECT username, password_hash, auth_version FROM developer_users WHERE id = 1"
        ).fetchone()
        valid = bool(
            account
            and isinstance(payload.get("username"), str)
            and account[0].casefold() == payload["username"].strip().casefold()
            and isinstance(payload.get("password"), str)
            and check_password_hash(account[1], payload["password"])
        )
        if not valid:
            failures += 1
            locked_until = now + 900 if failures >= 5 else 0
            connection.execute(
                """
                INSERT INTO developer_login_attempts
                    (client_key, failures, window_started_at, locked_until)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_key) DO UPDATE SET
                    failures = excluded.failures,
                    window_started_at = excluded.window_started_at,
                    locked_until = excluded.locked_until
                """,
                (client_key, failures, window_started_at, locked_until),
            )
            return jsonify(error="The developer username or password is incorrect."), 401
        connection.execute(
            "DELETE FROM developer_login_attempts WHERE client_key = ?",
            (client_key,),
        )
    session.clear()
    session["developer_username"] = account[0]
    session["developer_auth_version"] = account[2]
    session["developer_csrf"] = secrets.token_urlsafe(32)
    return jsonify(username=account[0], csrfToken=session["developer_csrf"])


@app.post("/api/developer/logout")
def developer_logout():
    if not developer_authenticated():
        return jsonify(error="Sign in to the developer area first."), 401
    if not developer_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    session.clear()
    return jsonify(loggedOut=True)


@app.post("/api/developer/credentials")
def update_developer_credentials():
    if not developer_authenticated():
        return jsonify(error="Sign in to the developer area first."), 401
    if not developer_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("currentPassword"), str)
        or not valid_developer_username(payload.get("username"))
        or not valid_developer_password(payload.get("newPassword"))
    ):
        return jsonify(
            error="Enter your current password, a username of 3–64 characters, and a new password of at least 14 characters."
        ), 400
    username = payload["username"].strip()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        account = connection.execute(
            "SELECT password_hash FROM developer_users WHERE id = 1"
        ).fetchone()
        if not account or not check_password_hash(account[0], payload["currentPassword"]):
            return jsonify(error="The current password is incorrect."), 403
        try:
            connection.execute(
                """
                UPDATE developer_users
                SET username = ?, password_hash = ?, auth_version = auth_version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (username, generate_password_hash(payload["newPassword"])),
            )
        except sqlite3.IntegrityError:
            return jsonify(error="That developer username is already in use."), 409
        auth_version = connection.execute(
            "SELECT auth_version FROM developer_users WHERE id = 1"
        ).fetchone()[0]
    session.clear()
    session["developer_username"] = username
    session["developer_auth_version"] = auth_version
    session["developer_csrf"] = secrets.token_urlsafe(32)
    return jsonify(username=username, csrfToken=session["developer_csrf"])


@app.get("/api/developer/change-requests")
def list_developer_change_requests():
    if not developer_authenticated():
        return jsonify(error="Sign in to the developer area first."), 401
    status = request.args.get("status", "all")
    statuses = {"pending", "in_progress", "blocked", "done", "rejected"}
    if status != "all" and status not in statuses:
        return jsonify(error="Choose a valid request status filter."), 400
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        query = """
            SELECT request_id, title, description, status, created_at, updated_at
            FROM developer_change_requests
        """
        parameters: tuple[str, ...] = ()
        if status != "all":
            query += " WHERE status = ?"
            parameters = (status,)
        query += " ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'pending' THEN 1 WHEN 'blocked' THEN 2 WHEN 'done' THEN 3 ELSE 4 END, developer_change_requests.rowid"
        rows = connection.execute(query, parameters).fetchall()
        dependencies = connection.execute(
            """
            SELECT dependency.request_id, prerequisite.request_id,
                   prerequisite.title, prerequisite.status
            FROM developer_change_request_dependencies AS dependency
            JOIN developer_change_requests AS prerequisite
              ON prerequisite.request_id = dependency.depends_on
            """
        ).fetchall()
        next_request = connection.execute(
            """
            SELECT request.request_id, request.title
            FROM developer_change_requests AS request
            WHERE request.status = 'pending'
              AND NOT EXISTS (
                  SELECT 1
                  FROM developer_change_request_dependencies AS dependency
                  JOIN developer_change_requests AS prerequisite
                    ON prerequisite.request_id = dependency.depends_on
                  WHERE dependency.request_id = request.request_id
                    AND prerequisite.status != 'done'
              )
            ORDER BY request.rowid
            LIMIT 1
            """
        ).fetchone()
        dependency_map: dict[str, list[dict[str, str]]] = {}
        for request_id, dependency_id, title, dependency_status in dependencies:
            dependency_map.setdefault(request_id, []).append(
                {"id": dependency_id, "title": title, "status": dependency_status}
            )
    requests = [
        {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "status": row[3],
            "createdAt": row[4],
            "updatedAt": row[5],
            "dependencies": dependency_map.get(row[0], []),
        }
        for row in rows
    ]
    eligible = (
        {"id": next_request[0], "title": next_request[1]}
        if next_request
        else None
    )
    return jsonify(requests=requests, nextEligible=eligible)


@app.put("/api/developer/change-requests/<path:request_id>")
def update_developer_change_request(request_id: str):
    if not developer_authenticated():
        return jsonify(error="Sign in to the developer area first."), 401
    if not developer_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    statuses = {"pending", "in_progress", "blocked", "done", "rejected"}
    if not isinstance(payload, dict) or payload.get("status") not in statuses:
        return jsonify(error="Choose a valid request status."), 400
    status = payload["status"]
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        request_row = connection.execute(
            "SELECT 1 FROM developer_change_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if not request_row:
            return jsonify(error="Change request was not found."), 404
        if status in {"in_progress", "done"}:
            incomplete = connection.execute(
                """
                SELECT prerequisite.title, prerequisite.status
                FROM developer_change_request_dependencies AS dependency
                JOIN developer_change_requests AS prerequisite
                  ON prerequisite.request_id = dependency.depends_on
                WHERE dependency.request_id = ? AND prerequisite.status != 'done'
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()
            if incomplete:
                return jsonify(
                    error=f"Complete blocking request “{incomplete[0]}” first."
                ), 409
        connection.execute(
            """
            UPDATE developer_change_requests
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE request_id = ?
            """,
            (status, request_id),
        )
    return jsonify(id=request_id, status=status)


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
        "source": row[7],
        "bamboohrLocation": row[8],
        "bamboohrActive": bool(row[9]) if row[7] == "bamboohr" else None,
    }


def normalized_employee_id(value: object) -> str:
    return str(value or "").strip().casefold()


def employee_id_in_use(
    connection: sqlite3.Connection, employee_id: str, exclude_employee_id: str | None = None
) -> bool:
    query = "SELECT 1 FROM employees WHERE lower(trim(employee_id)) = lower(trim(?))"
    parameters: tuple[str, ...] = (employee_id,)
    if exclude_employee_id is not None:
        query += " AND employee_id != ?"
        parameters += (exclude_employee_id,)
    return connection.execute(query, parameters).fetchone() is not None


def fetch_bamboohr_employees() -> list[dict[str, str]]:
    api_key = os.environ.get("BAMBOOHR_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BAMBOOHR_API_KEY is not configured on the app server.")
    authorization = base64.b64encode(f"{api_key}:x".encode("utf-8")).decode("ascii")
    cursor = None
    seen_cursors: set[str] = set()
    employees: list[dict[str, str]] = []
    expected_total = None

    while True:
        parameters = {
            "fields": "employeeNumber,location",
            "filter[status]": "active",
            "page[limit]": "2500",
        }
        if cursor:
            parameters["page[after]"] = cursor
        outbound = Request(
            f"{bamboohr_endpoint('employees')}?{urlencode(parameters)}",
            headers={"Accept": "application/json", "Authorization": f"Basic {authorization}"},
            method="GET",
        )
        try:
            with urlopen(outbound, timeout=30) as response:
                raw_data = response.read(10_000_001)
        except HTTPError as error:
            if error.code == 401:
                raise RuntimeError("BambooHR rejected the configured API key.") from error
            if error.code == 403:
                raise RuntimeError(
                    "BambooHR denied access to the employee list. Check the API key permissions."
                ) from error
            raise RuntimeError(f"BambooHR employee sync failed with HTTP {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise RuntimeError("The app server could not reach BambooHR for employee data.") from error
        if len(raw_data) > 10_000_000:
            raise RuntimeError("BambooHR employee response exceeds the allowed size.")
        try:
            page = json.loads(raw_data)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RuntimeError("BambooHR returned an invalid employee response.") from error
        if not isinstance(page, dict) or not isinstance(page.get("data"), list):
            raise RuntimeError("BambooHR returned an invalid employee list.")
        meta = page.get("meta")
        page_meta = meta.get("page") if isinstance(meta, dict) else None
        total = meta.get("total") if isinstance(meta, dict) else None
        if not isinstance(total, int) or total < 0 or not isinstance(page_meta, dict):
            raise RuntimeError("BambooHR returned incomplete employee pagination data.")
        if expected_total is None:
            expected_total = total
        elif expected_total != total:
            raise RuntimeError("The BambooHR employee list changed during synchronization; retry.")

        for item in page["data"]:
            if not isinstance(item, dict):
                raise RuntimeError("BambooHR returned an invalid employee record.")
            status = item.get("status")
            if status is not None and str(status).casefold() != "active":
                continue
            bamboohr_id = item.get("employeeId")
            employee_number = item.get("employeeNumber")
            if not isinstance(bamboohr_id, (str, int)) or not str(bamboohr_id).strip():
                raise RuntimeError("A BambooHR employee record is missing its BambooHR ID.")
            if not isinstance(employee_number, (str, int)) or not str(employee_number).strip():
                raise RuntimeError(
                    f"BambooHR employee {bamboohr_id} is missing Employee #. Complete it in BambooHR before syncing."
                )
            first_name = str(item.get("preferredName") or item.get("firstName") or "").strip()
            last_name = str(item.get("lastName") or "").strip()
            name = " ".join(part for part in (first_name, last_name) if part)
            if not name:
                name = str(item.get("displayName") or "").strip()
            if not name:
                raise RuntimeError(
                    f"BambooHR employee {bamboohr_id} is missing a display name."
                )
            employees.append(
                {
                    "bamboohrId": str(bamboohr_id).strip(),
                    "id": str(employee_number).strip(),
                    "name": name,
                    "bamboohrLocation": str(item.get("location") or "").strip(),
                }
            )
            if len(employees) > 100_000:
                raise RuntimeError("BambooHR employee list exceeds the supported size.")

        next_cursor = page_meta.get("nextCursor")
        if next_cursor is None:
            break
        if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
            raise RuntimeError("BambooHR returned an invalid employee page cursor.")
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    if expected_total != len(employees):
        raise RuntimeError(
            "BambooHR returned an incomplete active employee list; no changes were saved."
        )
    if len({employee["bamboohrId"] for employee in employees}) != len(employees):
        raise RuntimeError("BambooHR returned duplicate internal employee IDs; no changes were saved.")
    if len({normalized_employee_id(employee["id"]) for employee in employees}) != len(employees):
        raise RuntimeError("BambooHR returned duplicate Employee # values; no changes were saved.")
    return employees


def bamboo_employee_sync_conflicts(
    connection: sqlite3.Connection, remote_employees: list[dict[str, str]]
) -> list[dict]:
    records = connection.execute(
        """
        SELECT employee_id, bamboohr_id, name, location, role, active,
               schedule_location_id, source_type
        FROM employees
        """
    ).fetchall()
    if len({normalized_employee_id(row[0]) for row in records}) != len(records):
        raise RuntimeError(
            "The app contains duplicate Employee IDs ignoring case; resolve them before syncing."
        )
    by_id = {normalized_employee_id(row[0]): row for row in records}
    by_bamboo_id = {
        row[1]: row for row in records if row[1] and row[7] == "bamboohr"
    }
    conflicts = []
    for remote in remote_employees:
        employee = by_bamboo_id.get(remote["bamboohrId"])
        collision = by_id.get(normalized_employee_id(remote["id"]))
        if collision and collision[7] == "manual" and (
            employee is None or collision[0] != employee[0]
        ):
            conflicts.append(
                {
                    "bamboohrId": remote["bamboohrId"],
                    "employeeId": remote["id"],
                    "bamboohrName": remote["name"],
                    "existingBambooEmployeeId": employee[0] if employee else None,
                    "manualEmployee": {
                        "id": collision[0],
                        "name": collision[2],
                        "role": collision[4],
                        "location": collision[3],
                        "scheduleLocationId": collision[6],
                        "active": bool(collision[5]),
                    },
                }
            )
        elif collision and collision[7] == "bamboohr" and (
            employee is None or collision[0] != employee[0]
        ):
            raise RuntimeError(
                f"Employee # {remote['id']} is already assigned to another BambooHR record."
            )
    return conflicts


def mapped_bamboohr_location(connection: sqlite3.Connection, location: str) -> str:
    if not location:
        return ""
    rows = connection.execute(
        "SELECT DISTINCT location FROM schedule_locations"
    ).fetchall()
    matches = [
        row[0] for row in rows
        if normalized_employee_id(row[0]) == normalized_employee_id(location)
    ]
    return matches[0] if len(matches) == 1 else ""


@app.post("/api/bamboohr/employees/sync")
def sync_bamboohr_employees():
    payload = request.get_json(silent=True) or {}
    resolutions = payload.get("resolutions", []) if isinstance(payload, dict) else None
    if not isinstance(resolutions, list):
        return jsonify(error="Employee reconciliation choices must be a list."), 400
    try:
        remote_employees = fetch_bamboohr_employees()
    except RuntimeError as error:
        return jsonify(error=str(error)), 502 if "not configured" not in str(error) else 503

    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            conflicts = bamboo_employee_sync_conflicts(connection, remote_employees)
        except RuntimeError as error:
            return jsonify(error=str(error)), 409
        if conflicts and not resolutions:
            return jsonify(requiresReview=True, conflicts=conflicts)
        conflict_by_bamboo_id = {conflict["bamboohrId"]: conflict for conflict in conflicts}
        resolution_by_bamboo_id = {}
        for resolution in resolutions:
            if (
                not isinstance(resolution, dict)
                or not isinstance(resolution.get("bamboohrId"), str)
                or resolution.get("bamboohrId") in resolution_by_bamboo_id
                or not isinstance(resolution.get("samePerson"), bool)
            ):
                return jsonify(error="Each employee conflict needs one valid reconciliation choice."), 400
            resolution_by_bamboo_id[resolution["bamboohrId"]] = resolution
        if set(resolution_by_bamboo_id) != set(conflict_by_bamboo_id):
            if conflicts:
                return jsonify(requiresReview=True, conflicts=conflicts)
            return jsonify(error="The BambooHR list changed; refresh it and review again."), 409
        for bamboohr_id, resolution in resolution_by_bamboo_id.items():
            conflict = conflict_by_bamboo_id[bamboohr_id]
            if resolution.get("employeeId") != conflict["manualEmployee"]["id"]:
                return jsonify(error="A manual employee changed during reconciliation; refresh and review again."), 409
            if not resolution["samePerson"]:
                new_id = resolution.get("newManualEmployeeId")
                if (
                    not isinstance(new_id, str)
                    or not new_id.strip()
                    or normalized_employee_id(new_id) == normalized_employee_id(conflict["employeeId"])
                ):
                    return jsonify(error="Enter a new, unique Employee ID for the different manual employee."), 400
        if conflicts:
            existing_ids = {
                normalized_employee_id(row[0]): row[0]
                for row in connection.execute("SELECT employee_id FROM employees")
            }
            remote_ids = {
                normalized_employee_id(employee["id"]) for employee in remote_employees
            }
            proposed_ids = set()
            for bamboohr_id, resolution in resolution_by_bamboo_id.items():
                if resolution["samePerson"]:
                    continue
                replacement_id = resolution["newManualEmployeeId"].strip()
                normalized_replacement = normalized_employee_id(replacement_id)
                manual_id = conflict_by_bamboo_id[bamboohr_id]["manualEmployee"]["id"]
                if (
                    normalized_replacement in existing_ids
                    and existing_ids[normalized_replacement] != manual_id
                ):
                    return jsonify(error=f"Employee ID {replacement_id} is already in use."), 409
                if normalized_replacement in remote_ids or normalized_replacement in proposed_ids:
                    return jsonify(error=f"Employee ID {replacement_id} is already in use."), 409
                proposed_ids.add(normalized_replacement)

        by_bamboo_id = {
            row[1]: row
            for row in connection.execute(
                """
                SELECT employee_id, bamboohr_id, name, location, role, active,
                       schedule_location_id, source_type
                FROM employees WHERE source_type = 'bamboohr'
                """
            ).fetchall()
        }
        by_employee_id = {
            normalized_employee_id(row[0]): row
            for row in connection.execute(
                """
                SELECT employee_id, bamboohr_id, name, location, role, active,
                       schedule_location_id, source_type
                FROM employees
                """
            ).fetchall()
        }
        added = updated = inactivated = merged = rekeyed = 0
        employee_id_changes = []
        for remote in remote_employees:
            existing = by_bamboo_id.get(remote["bamboohrId"])
            resolution = resolution_by_bamboo_id.get(remote["bamboohrId"])
            collision = by_employee_id.get(normalized_employee_id(remote["id"]))
            if collision and collision[7] == "manual" and (
                existing is None or collision[0] != existing[0]
            ):
                if resolution["samePerson"]:
                    if existing and existing[0] != collision[0]:
                        connection.execute(
                            "DELETE FROM employees WHERE employee_id = ?",
                            (collision[0],),
                        )
                        if not existing[4]:
                            connection.execute(
                                """
                                UPDATE employees
                                SET location = ?, role = ?, active = ?, schedule_location_id = ?
                                WHERE employee_id = ?
                                """,
                                (
                                    collision[3], collision[4], collision[5],
                                    collision[6], existing[0],
                                ),
                            )
                        connection.execute(
                            "UPDATE employees SET employee_id = ? WHERE employee_id = ?",
                            (remote["id"], existing[0]),
                        )
                        employee_id_changes.append(
                            {
                                "oldId": existing[0],
                                "newId": remote["id"],
                                "source": "bamboohr",
                                "bamboohrId": remote["bamboohrId"],
                                "mergedManualId": collision[0],
                            }
                        )
                        rekeyed += 1
                        existing = (
                            remote["id"], existing[1], existing[2],
                            collision[3] if not existing[4] else existing[3],
                            collision[4] if not existing[4] else existing[4],
                            collision[5] if not existing[4] else existing[5],
                            collision[6] if not existing[4] else existing[6],
                            existing[7],
                        )
                    else:
                        connection.execute(
                            """
                            UPDATE employees
                            SET bamboohr_id = ?, name = ?, bamboohr_location = ?,
                                source_type = 'bamboohr', bamboohr_active = 1
                            WHERE employee_id = ? AND source_type = 'manual'
                            """,
                            (
                                remote["bamboohrId"], remote["name"],
                                remote["bamboohrLocation"], collision[0],
                            ),
                        )
                        existing = connection.execute(
                            """
                            SELECT employee_id, bamboohr_id, name, location, role, active,
                                   schedule_location_id, source_type
                            FROM employees WHERE employee_id = ?
                            """,
                            (collision[0],),
                        ).fetchone()
                    merged += 1
                else:
                    replacement_id = resolution["newManualEmployeeId"].strip()
                    connection.execute(
                        "UPDATE employees SET employee_id = ? WHERE employee_id = ?",
                        (replacement_id, collision[0]),
                    )
                    employee_id_changes.append(
                        {"oldId": collision[0], "newId": replacement_id, "source": "manual"}
                    )
                    rekeyed += 1
            if existing is None:
                mapped_location = mapped_bamboohr_location(
                    connection, remote["bamboohrLocation"]
                )
                connection.execute(
                    """
                    INSERT INTO employees
                        (employee_id, bamboohr_id, name, location, role, active,
                         schedule_location_id, source_type, bamboohr_location, bamboohr_active)
                    VALUES (?, ?, ?, ?, '', 0, NULL, 'bamboohr', ?, 1)
                    """,
                    (
                        remote["id"], remote["bamboohrId"], remote["name"],
                        mapped_location, remote["bamboohrLocation"],
                    ),
                )
                added += 1
            else:
                old_id = existing[0]
                if normalized_employee_id(old_id) != normalized_employee_id(remote["id"]):
                    connection.execute(
                        "UPDATE employees SET employee_id = ? WHERE employee_id = ?",
                        (remote["id"], old_id),
                    )
                    employee_id_changes.append(
                        {
                            "oldId": old_id,
                            "newId": remote["id"],
                            "source": "bamboohr",
                            "bamboohrId": remote["bamboohrId"],
                        }
                    )
                    rekeyed += 1
                connection.execute(
                    """
                    UPDATE employees
                    SET name = ?, bamboohr_id = ?, bamboohr_location = ?,
                        source_type = 'bamboohr', bamboohr_active = 1
                    WHERE employee_id = ?
                    """,
                    (
                        remote["name"], remote["bamboohrId"],
                        remote["bamboohrLocation"], remote["id"],
                    ),
                )
                updated += 1

        active_bamboo_ids = [employee["bamboohrId"] for employee in remote_employees]
        if active_bamboo_ids:
            placeholders = ",".join("?" for _ in active_bamboo_ids)
            inactive_cursor = connection.execute(
                f"""
                UPDATE employees SET active = 0, bamboohr_active = 0
                WHERE source_type = 'bamboohr' AND bamboohr_id NOT IN ({placeholders})
                  AND (active != 0 OR bamboohr_active != 0)
                """,
                active_bamboo_ids,
            )
        else:
            inactive_cursor = connection.execute(
                """
                UPDATE employees SET active = 0, bamboohr_active = 0
                WHERE source_type = 'bamboohr' AND (active != 0 OR bamboohr_active != 0)
                """
            )
        inactivated = inactive_cursor.rowcount
        return jsonify(
            synced=len(remote_employees),
            added=added,
            updated=updated,
            merged=merged,
            rekeyed=rekeyed,
            inactivated=inactivated,
            employeeIdChanges=employee_id_changes,
            syncedAt=datetime.now(timezone.utc).isoformat(),
        )


@app.get("/api/employees")
def list_employees():
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT employee_id, bamboohr_id, name, location, role, active, schedule_location_id,
                   source_type, bamboohr_location, bamboohr_active
            FROM employees
            ORDER BY name COLLATE NOCASE
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


@app.put("/api/employees/roles")
def update_employee_roles():
    payload = request.get_json(silent=True)
    employee_ids = payload.get("employeeIds") if isinstance(payload, dict) else None
    role = payload.get("role") if isinstance(payload, dict) else None
    if (
        not isinstance(employee_ids, list)
        or not employee_ids
        or any(not isinstance(employee_id, str) or not employee_id.strip() for employee_id in employee_ids)
        or len(employee_ids) != len(set(employee_ids))
        or not isinstance(role, str)
        or not role.strip()
    ):
        return jsonify(error="Select employees and provide one role to assign."), 400
    role = role.strip()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        rows = connection.execute(
            """
            SELECT employee_id, location, role, active, schedule_location_id
            FROM employees
            WHERE employee_id IN ({})
            """.format(",".join("?" for _ in employee_ids)),
            employee_ids,
        ).fetchall()
        if len(rows) != len(employee_ids):
            return jsonify(error="One or more selected employees were not found."), 404
        for employee in rows:
            if employee[4] and not role_matches_schedule_group(
                role,
                connection.execute(
                    "SELECT role_group FROM schedule_locations WHERE id = ?",
                    (employee[4],),
                ).fetchone()[0],
            ):
                return jsonify(
                    error=f"The role {role} does not match {employee[0]}'s schedule location. Change the schedule location first."
                ), 400
        changed_ids = [row[0] for row in rows if row[2] != role]
        if changed_ids:
            placeholders = ",".join("?" for _ in changed_ids)
            connection.execute(
                f"""
                UPDATE employees SET role = ?, active = 0
                WHERE employee_id IN ({placeholders})
                """,
                [role, *changed_ids],
            )
    return jsonify(role=role, employeeIds=employee_ids, deactivatedIds=changed_ids)


@app.put("/api/employees/import-review")
def confirm_imported_employee_mappings():
    payload = request.get_json(silent=True)
    mappings = payload.get("employees") if isinstance(payload, dict) else None
    if not isinstance(mappings, list) or not mappings:
        return jsonify(error="Approve at least one valid employee mapping."), 400
    seen_ids = set()
    normalized_mappings = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            return jsonify(error="The employee mapping review contains an invalid row."), 400
        employee_id = mapping.get("id")
        role = mapping.get("role")
        location = mapping.get("location")
        schedule_location_id = mapping.get("scheduleLocationId")
        if (
            not isinstance(employee_id, str)
            or not employee_id.strip()
            or not isinstance(mapping.get("name"), str)
            or not mapping["name"].strip()
            or not isinstance(location, str)
            or not location.strip()
            or not isinstance(role, str)
            or not role.strip()
            or not isinstance(mapping.get("addManual"), bool)
        ):
            return jsonify(error="Each mapping needs an Employee ID, name, location, role, and manual-add choice."), 400
        normalized_id = normalized_employee_id(employee_id)
        if normalized_id in seen_ids:
            return jsonify(error=f"Employee ID {employee_id} appears more than once in the review."), 400
        seen_ids.add(normalized_id)
        if schedule_location_id is not None and not isinstance(schedule_location_id, str):
            return jsonify(error="A schedule location selection is invalid."), 400
        normalized_mappings.append(
            {
                **mapping,
                "id": employee_id.strip(),
                "name": mapping["name"].strip(),
                "location": location.strip(),
                "role": role.strip(),
                "scheduleLocationId": schedule_location_id.strip() or None
                if isinstance(schedule_location_id, str)
                else None,
            }
        )
    updated = added = deactivated = 0
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        existing_rows = connection.execute(
            """
            SELECT employee_id, name, location, role, active,
                   schedule_location_id, source_type
            FROM employees
            """
        ).fetchall()
        if len({normalized_employee_id(row[0]) for row in existing_rows}) != len(existing_rows):
            return jsonify(error="Resolve duplicate Employee IDs before importing mappings."), 409
        current_by_id = {
            normalized_employee_id(row[0]): row for row in existing_rows
        }
        plans = []
        for mapping in normalized_mappings:
            current = current_by_id.get(normalized_employee_id(mapping["id"]))
            if current is None and not mapping["addManual"]:
                plans.append((mapping, None))
                continue
            schedule_location_id = mapping["scheduleLocationId"]
            if schedule_location_id:
                schedule = connection.execute(
                    "SELECT location, role_group FROM schedule_locations WHERE id = ?",
                    (schedule_location_id,),
                ).fetchone()
                if (
                    not schedule
                    or schedule[0] != mapping["location"]
                    or not role_matches_schedule_group(mapping["role"], schedule[1])
                ):
                    return jsonify(error=f"Schedule location does not match {mapping['name']}."), 400
            plans.append((mapping, current))

        for mapping, current in plans:
            employee_id = mapping["id"]
            role = mapping["role"]
            location_name = mapping["location"]
            schedule_location_id = mapping["scheduleLocationId"]
            if current is None:
                if not mapping["addManual"]:
                    continue
                connection.execute(
                    """
                    INSERT INTO employees
                        (employee_id, bamboohr_id, name, location, role, active,
                         schedule_location_id, source_type, bamboohr_location, bamboohr_active)
                    VALUES (?, ?, ?, ?, ?, 0, ?, 'manual', '', 0)
                    """,
                    (
                        employee_id,
                        "MANUAL-" + secrets.token_hex(12).upper(),
                        mapping["name"],
                        location_name,
                        role,
                        schedule_location_id,
                    ),
                )
                added += 1
                continue
            changed = current[2] != location_name or current[3] != role
            active = 0 if changed and current[4] else current[4]
            cursor = connection.execute(
                """
                UPDATE employees
                SET location = ?, role = ?, schedule_location_id = ?, active = ?
                WHERE employee_id = ?
                """,
                (location_name, role, schedule_location_id, active, current[0]),
            )
            updated += cursor.rowcount
            if changed and current[4]:
                deactivated += 1
    return jsonify(updated=updated, addedManual=added, deactivated=deactivated)


def valid_employee(payload: object, *, require_bamboo_id: bool = True) -> bool:
    if not isinstance(payload, dict):
        return False
    fields = ("id", "name", "location")
    if any(not isinstance(payload.get(field), str) or not payload[field].strip() for field in fields):
        return False
    role = payload.get("role")
    if not isinstance(role, str) or not role.strip():
        return False
    bamboohr_id = payload.get("bamboohrId")
    if require_bamboo_id and (
        not isinstance(bamboohr_id, str) or not bamboohr_id.strip()
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


def directory_conflict():
    return jsonify(error="Employee ID or BambooHR ID is already in use."), 409


@app.post("/api/employees")
def create_employee():
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or any(
            not isinstance(payload.get(field), str) or not payload[field].strip()
            for field in ("id", "name", "location")
        )
        or not isinstance(payload.get("role", ""), str)
        or not payload.get("role", "").strip()
        or payload.get("active", False) is not False
        or payload.get("scheduleLocationId") not in (None, "")
    ):
        return jsonify(error="A manual employee needs an Employee ID, name, and location and must start inactive."), 400
    employee_id = payload["id"].strip()
    role = payload.get("role", "").strip()
    bamboohr_id = "MANUAL-" + secrets.token_hex(12).upper()
    employee_payload = {
        "id": employee_id,
        "bamboohrId": bamboohr_id,
        "name": payload["name"].strip(),
        "location": payload["location"].strip(),
        "role": role,
        "active": False,
        "scheduleLocationId": None,
        "source": "manual",
    }
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        if employee_id_in_use(connection, employee_id):
            return directory_conflict()
        if not employee_location_exists(connection, employee_payload):
            return jsonify(error="The assigned schedule location does not match the employee's location."), 400
        try:
            connection.execute(
                """
                INSERT INTO employees
                    (employee_id, bamboohr_id, name, location, role, active, schedule_location_id,
                     source_type, bamboohr_location, bamboohr_active)
                VALUES (?, ?, ?, ?, ?, 0, NULL, 'manual', '', 0)
                """,
                (
                    employee_payload["id"],
                    bamboohr_id,
                    employee_payload["name"],
                    employee_payload["location"],
                    role,
                ),
            )
        except sqlite3.IntegrityError:
            return directory_conflict()
    return jsonify(employee=employee_payload), 201


@app.put("/api/employees/<path:employee_id>")
def update_employee(employee_id: str):
    payload = request.get_json(silent=True)
    if not valid_employee(payload):
        return jsonify(error="Employee ID, name, location, role, and active status are required."), 400
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        existing = connection.execute(
            """
            SELECT employee_id, bamboohr_id, name, location, role, active,
                   schedule_location_id, source_type
            FROM employees WHERE employee_id = ?
            """,
            (employee_id,),
        ).fetchone()
        if not existing:
            return jsonify(error="Employee was not found."), 404
        source_type = existing[7]
        if source_type == "bamboohr":
            payload = {
                **payload,
                "id": existing[0],
                "bamboohrId": existing[1],
                "name": existing[2],
            }
        else:
            payload = {
                **payload,
                "bamboohrId": existing[1],
                "active": bool(payload["active"]),
            }
        if employee_id_in_use(connection, payload["id"].strip(), employee_id):
            return directory_conflict()
        if not employee_location_exists(connection, payload):
            return jsonify(error="The assigned schedule location does not match the employee's location."), 400
        if payload["active"] and not payload["role"].strip():
            return jsonify(error="Assign a role before making the employee active."), 400
        if payload.get("scheduleLocationId") and not payload["role"].strip():
            return jsonify(error="Assign a role before mapping the employee to a schedule location."), 400
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
        except sqlite3.IntegrityError:
            return directory_conflict()
        if cursor.rowcount == 0:
            return jsonify(error="Employee was not found."), 404
    return jsonify(employee=payload)


@app.delete("/api/employees/<path:employee_id>")
def delete_employee(employee_id: str):
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        employee = connection.execute(
            "SELECT source_type FROM employees WHERE employee_id = ?", (employee_id,)
        ).fetchone()
        if not employee:
            return jsonify(error="Employee was not found."), 404
        if employee[0] != "manual":
            return jsonify(error="BambooHR employees cannot be deleted; make them inactive instead."), 409
        cursor = connection.execute(
            "DELETE FROM employees WHERE employee_id = ?", (employee_id,)
        )
    return jsonify(id=employee_id)


@app.get("/api/schedule-locations")
def list_schedule_locations():
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT s.id, s.name, s.bamboo_schedule_id, s.location, s.role_group,
                   s.manager_name, s.manager_email,
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
                "managerName": row[5],
                "managerEmail": row[6],
                "employeeCount": row[7],
            }
            for row in rows
        ]
    )


def valid_schedule_location(payload: object) -> bool:
    if not isinstance(payload, dict) or not all(
        isinstance(payload.get(field), str) and payload[field].strip()
        for field in ("name", "bambooScheduleId", "location", "managerName", "managerEmail")
    ):
        return False
    manager_name = payload["managerName"].strip()
    manager_email = payload["managerEmail"].strip()
    return (
        not re.search(r"[\r\n<>]", manager_name)
        and re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+", manager_email)
        is not None
    )


def schedule_location_conflict(error: sqlite3.IntegrityError):
    return jsonify(error="Schedule name or BambooHR schedule ID is already in use."), 409


@app.post("/api/schedule-locations")
def create_schedule_location():
    payload = request.get_json(silent=True)
    if not valid_schedule_location(payload):
        return jsonify(
            error="Schedule name, BambooHR schedule ID, app location, manager name, and valid manager email are required."
        ), 400
    location_id = os.urandom(16).hex()
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        try:
            connection.execute(
                """
                INSERT INTO schedule_locations
                    (id, name, bamboo_schedule_id, location, role_group,
                     manager_name, manager_email)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    location_id,
                    payload["name"].strip(),
                    payload["bambooScheduleId"].strip(),
                    payload["location"].strip(),
                    str(payload.get("roleGroup", "")).strip(),
                    payload["managerName"].strip(),
                    payload["managerEmail"].strip(),
                ),
            )
        except sqlite3.IntegrityError as error:
            return schedule_location_conflict(error)
    return jsonify(id=location_id), 201


@app.put("/api/schedule-locations/<path:location_id>")
def update_schedule_location(location_id: str):
    payload = request.get_json(silent=True)
    if not valid_schedule_location(payload):
        return jsonify(
            error="Schedule name, BambooHR schedule ID, app location, manager name, and valid manager email are required."
        ), 400
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
                SET name = ?, bamboo_schedule_id = ?, location = ?, role_group = ?,
                    manager_name = ?, manager_email = ?
                WHERE id = ?
                """,
                (
                    payload["name"].strip(),
                    payload["bambooScheduleId"].strip(),
                    payload["location"].strip(),
                    str(payload.get("roleGroup", "")).strip(),
                    payload["managerName"].strip(),
                    payload["managerEmail"].strip(),
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


@app.get("/api/app-config")
def get_application_config():
    return jsonify(current_app_config())


@app.put("/api/app-config")
def update_application_config():
    config = valid_app_config(request.get_json(silent=True))
    if config is None:
        return jsonify(error="Provide valid business, team, logo, color, and BambooHR tenant settings."), 400
    save_app_config(config)
    return jsonify(current_app_config())


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
        SELECT employee_id, bamboohr_id, active, schedule_location_id, location, role,
               source_type
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
            if employee and employee[6] == "manual":
                continue
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
        raise ValueError(
            "The selected shifts have no BambooHR employees to publish; manually added employees are excluded."
        )
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


@app.post("/api/bamboohr/validate-key")
def validate_bamboohr_key():
    payload = request.get_json(silent=True)
    tenant_id = payload.get("tenantId") if isinstance(payload, dict) else None
    api_key = payload.get("apiKey") if isinstance(payload, dict) else None
    if (
        not valid_tenant_id(tenant_id)
        or not isinstance(api_key, str)
        or not api_key.strip()
        or len(api_key) > 4096
        or any(character in api_key for character in "\r\n:")
    ):
        return jsonify(error="Enter a valid BambooHR tenant ID and API key."), 400

    tenant_id = tenant_id.lower()
    authorization = base64.b64encode(f"{api_key.strip()}:x".encode("utf-8")).decode("ascii")
    outbound = Request(
        f"{bamboohr_endpoint_for_tenant(tenant_id, 'time_off/whos_out')}?"
        f"{urlencode({'start': date.today().isoformat(), 'end': date.today().isoformat()})}",
        headers={"Accept": "application/json", "Authorization": f"Basic {authorization}"},
        method="GET",
    )
    try:
        with urlopen(outbound, timeout=20) as response:
            response.read(2048)
    except HTTPError as error:
        if error.code == 401:
            return jsonify(error="BambooHR rejected this API key for the supplied tenant."), 401
        if error.code == 403:
            return jsonify(error="BambooHR denied this key access to the time-off endpoint."), 403
        return jsonify(error=f"BambooHR key validation failed with HTTP {error.code}."), 502
    except (URLError, TimeoutError, OSError):
        return jsonify(error="The app server could not reach BambooHR to validate the key."), 502

    now = datetime.now(timezone.utc)
    for token, (_, _, expires_at) in list(_validated_bamboo_keys.items()):
        if expires_at <= now:
            del _validated_bamboo_keys[token]
    promotion_token = secrets.token_urlsafe(32)
    _validated_bamboo_keys[promotion_token] = (
        tenant_id,
        api_key.strip(),
        now + timedelta(minutes=10),
    )
    return jsonify(valid=True, tenantId=tenant_id, promotionToken=promotion_token)


def bamboohr_endpoint_for_tenant(tenant_id: str, path: str) -> str:
    return f"https://{tenant_id}.bamboohr.com/api/v1/{path.lstrip('/')}"


@app.post("/api/bamboohr/promote-key")
def promote_bamboohr_key():
    payload = request.get_json(silent=True)
    token = payload.get("promotionToken") if isinstance(payload, dict) else None
    tenant_id = payload.get("tenantId") if isinstance(payload, dict) else None
    validation = _validated_bamboo_keys.get(token) if isinstance(token, str) else None
    now = datetime.now(timezone.utc)
    if (
        validation is None
        or validation[2] <= now
        or not valid_tenant_id(tenant_id)
        or tenant_id.lower() != validation[0]
        or current_app_config()["tenantId"] != validation[0]
    ):
        if isinstance(token, str):
            _validated_bamboo_keys.pop(token, None)
        return jsonify(error="Test the API key successfully for the currently saved tenant before promoting it."), 400

    key_path = ENV_PATH
    previous_dotenv_key = dotenv_values(key_path).get("BAMBOOHR_API_KEY")
    try:
        success, _, _ = set_key(key_path, "BAMBOOHR_API_KEY", validation[1])
        if not success:
            return jsonify(error="The API key could not be saved to the app server .env file."), 500
        try:
            save_app_config({"tenantId": validation[0]})
        except sqlite3.Error:
            if previous_dotenv_key is None:
                rollback_succeeded = unset_key(key_path, "BAMBOOHR_API_KEY")[0]
            else:
                rollback_succeeded = set_key(
                    key_path, "BAMBOOHR_API_KEY", previous_dotenv_key
                )[0]
            if not rollback_succeeded:
                return jsonify(
                    error="The app settings could not be saved and the API key rollback failed; review the server .env file."
                ), 500
            return jsonify(error="The app settings could not be saved; the API key change was rolled back."), 500
    except OSError:
        return jsonify(error="The API key could not be written to the app server .env file."), 500

    os.environ["BAMBOOHR_API_KEY"] = validation[1]
    del _validated_bamboo_keys[token]
    return jsonify(promoted=True, tenantId=validation[0])


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
        f"{bamboohr_endpoint('time_off/whos_out')}?{urlencode({'start': start_text, 'end': end_text})}",
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
            bamboohr_endpoint("scheduling/shifts"),
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
