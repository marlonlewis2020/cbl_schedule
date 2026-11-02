from pathlib import Path
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import argparse
import json
import os
import re
import secrets
import sqlite3
import base64
import hashlib
import io
import ipaddress
import hmac
import struct
import time as time_module
from getpass import getpass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from dotenv import dotenv_values, load_dotenv, set_key, unset_key
from flask import (
    Flask,
    abort,
    g,
    has_request_context,
    jsonify,
    make_response,
    redirect,
    request,
    send_from_directory,
    session,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from cryptography.fernet import Fernet, InvalidToken

from directory_seed import (
    EMPLOYEE_ASSIGNMENTS,
    EMPLOYEE_ROLE_OVERRIDES,
    SCHEDULE_LOCATIONS,
    UNMAPPED_ROSTER_EMPLOYEE,
)


APP_DIRECTORY = Path(__file__).resolve().parent
load_dotenv(APP_DIRECTORY / ".env")
DATABASE_PATH = APP_DIRECTORY / "data" / "schedule_creator.sqlite3"
DATABASE_URL = os.environ.get("SCHEDULE_CREATOR_DATABASE_URL", "").strip()
DEFAULT_TENANT_ID = os.environ.get("SCHEDULE_CREATOR_TENANT_ID", "cbljm").strip().lower()
if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", DEFAULT_TENANT_ID) is None:
    raise RuntimeError("SCHEDULE_CREATOR_TENANT_ID must be a valid tenant identifier.")
TRUSTED_PROXY_HOPS = int(os.environ.get("SCHEDULE_CREATOR_TRUSTED_PROXY_HOPS", "0"))
# TEMPORARY: allows PostgreSQL mode over plain HTTP, only for loopback/private-LAN
# clients. Not for internet exposure; remove later.
ALLOW_LAN_HTTP = (
    os.environ.get("SCHEDULE_CREATOR_TEMPORARY_ALLOW_LAN_HTTP", "").strip() == "1"
)


def http_allowed_for_client() -> bool:
    if not ALLOW_LAN_HTTP or request.headers.get("X-Forwarded-For"):
        return False
    try:
        address = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return False
    return address.is_loopback or address.is_private

# TEMPORARY: lets a correct password sign in without MFA (SQLite and PostgreSQL); remove later.
MFA_BYPASS = os.environ.get("SCHEDULE_CREATOR_TEMPORARY_MFA_BYPASS", "").strip() == "1"
if TRUSTED_PROXY_HOPS < 0:
    raise RuntimeError("SCHEDULE_CREATOR_TRUSTED_PROXY_HOPS cannot be negative.")
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
    (
        "attendance-automation",
        "Automatic attendance percentage from BambooHR time tracking",
        "Priority: Medium. Calculate each employee's attendance automatically as shifts attended (clocked in) divided by shifts scheduled, always averaged over the most recent 30-45 days (configurable within that range, default 30), replacing manual entry. Attendance calculation is included in every membership tier. First verify the tenant's BambooHR API key can read time-tracking clock-in data and that staff actually clock in through BambooHR. Match clock-ins to accepted schedule shifts by employee ID, with a configurable lateness tolerance, an overnight-shift day rule, and exclusion of shifts covered by approved time off. Write the result to each employee's attendance field on a schedule or on demand, keep a manual override, show the period and counts behind each percentage, and leave attendance blank when no data exists. The existing attendance priority bonus then uses the calculated value unchanged.",
        ("business-hub",),
    ),
    (
        "workforce-dashboards",
        "Interval snapshot and attendance dashboards",
        "Priority: Medium. Add two dashboards. (1) Daily interval snapshot dashboard: for a chosen day, show scheduled headcount against demand and shortfall by interval for each location x role team; included in Gold and Platinum only. (2) Attendance dashboard: per-team and per-employee attendance averaged over the last 30-45 days with scheduled vs attended counts; included in Silver, Gold and Platinum. Admins see every location x role team; managers see only teams for locations assigned to their verified manager email, enforced server-side. Finalize the interval length (hourly, 30-minute, or shift-start slots) and snapshot contents before building. Planned coverage comes from accepted schedules; actual attendance depends on the attendance-automation request.",
        ("attendance-automation", "manager-employee-access", "tier-entitlements"),
    ),
    (
        "snapshot-email-reports",
        "Scheduled snapshot report emails",
        "Priority: Low. Let the workforce admin choose how often snapshot reports are emailed (for example daily, weekly or custom) and who receives them: all scheduled employees, schedule-location managers, and a user-defined distribution list. Reuse the configured email client, respect each recipient's team scope so employees and managers only receive data they are entitled to see, include unsubscribe/opt-out handling for the distribution list, log delivery success and failure, and honor the tier of each report (interval snapshots Gold and Platinum, attendance Silver and above). Never include other teams' data in a recipient's report.",
        ("workforce-dashboards",),
    ),
)


def load_persistent_secret(environment_name: str, filename: str) -> str:
    configured = os.environ.get(environment_name, "").strip()
    if configured:
        if len(configured) < 32:
            raise RuntimeError(f"{environment_name} must contain at least 32 characters.")
        return configured
    if DATABASE_URL:
        raise RuntimeError(
            f"{environment_name} must be configured when PostgreSQL is enabled."
        )
    secret_path = APP_DIRECTORY / "data" / filename
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        secret = secret_path.read_text(encoding="utf-8").strip()
    else:
        secret = secrets.token_urlsafe(48)
        with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
            secret_file.write(secret)
    if len(secret) < 32:
        raise RuntimeError(f"Persistent secret file {secret_path} is invalid.")
    return secret


LOCAL_FLASK_SECRET = load_persistent_secret("FLASK_SECRET_KEY", "flask_secret.key")
MFA_ENCRYPTION_KEY = load_persistent_secret(
    "SCHEDULE_CREATOR_MFA_ENCRYPTION_KEY", "mfa_encryption.key"
)


app = Flask(__name__, static_folder=None)
if TRUSTED_PROXY_HOPS:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_proto=TRUSTED_PROXY_HOPS,
        x_host=TRUSTED_PROXY_HOPS,
    )
app.config["MAX_CONTENT_LENGTH"] = MAX_ACCEPTED_SCHEDULE_BYTES
app.config["SECRET_KEY"] = LOCAL_FLASK_SECRET
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = bool(DATABASE_URL) and not ALLOW_LAN_HTTP
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback):
        return self.connection.__exit__(exception_type, exception, traceback)

    def close(self):
        self.connection.close()

    def execute(self, query, parameters=()):
        normalized = query.strip()
        if normalized.casefold().startswith("pragma foreign_keys"):
            return self.connection.execute("SELECT 1 WHERE FALSE")
        pragma = re.fullmatch(r"PRAGMA\s+table_info\((\w+)\)", normalized, re.IGNORECASE)
        if pragma:
            return self.connection.execute(
                """
                SELECT ordinal_position - 1, column_name, data_type,
                       CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END,
                       column_default, 0
                FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = %s
                ORDER BY ordinal_position
                """,
                (pragma.group(1),),
            )
        return self.connection.execute(self._translate(normalized), parameters)

    @classmethod
    def _translate(cls, query):
        normalized = query.strip()
        if re.match(r"INSERT\s+OR\s+IGNORE\s+INTO\s+", normalized, re.IGNORECASE):
            normalized = re.sub(
                r"INSERT\s+OR\s+IGNORE\s+INTO\s+",
                "INSERT INTO ",
                normalized,
                count=1,
                flags=re.IGNORECASE,
            )
            normalized = normalized.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        normalized = re.sub(r"\bCOLLATE\s+NOCASE\b", "", normalized, flags=re.IGNORECASE)
        normalized = normalized.replace(
            "lower(hex(randomblob(12)))",
            "substr(md5(random()::text || clock_timestamp()::text), 1, 24)",
        )
        return cls._postgres_placeholders(normalized)

    def executemany(self, query, parameters):
        cursor = self.connection.cursor()
        cursor.executemany(self._translate(query), parameters)
        return cursor

    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    @staticmethod
    def _postgres_placeholders(query: str) -> str:
        output = []
        quote = None
        index = 0
        while index < len(query):
            char = query[index]
            if quote:
                output.append(char)
                if char == quote:
                    if index + 1 < len(query) and query[index + 1] == quote:
                        output.append(query[index + 1])
                        index += 1
                    else:
                        quote = None
            elif char in {"'", '"'}:
                quote = char
                output.append(char)
            elif char == "?":
                output.append("%s")
            else:
                output.append(char)
            index += 1
        return "".join(output)


DatabaseConnection = sqlite3.Connection | PostgresConnection


def database_connect():
    if not DATABASE_URL:
        return sqlite3.connect(DATABASE_PATH)
    try:
        import psycopg
        from psycopg.rows import tuple_row
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL is configured but psycopg is not installed. Install requirements.txt."
        ) from error
    connection = psycopg.connect(DATABASE_URL, row_factory=tuple_row, connect_timeout=10)
    tenant_id = (
        getattr(g, "tenant_id", None)
        if has_request_context()
        else None
    ) or DEFAULT_TENANT_ID
    wrapped = PostgresConnection(connection)
    wrapped.execute("SELECT set_config('app.tenant_id', ?, false)", (tenant_id,))
    return wrapped


def database_integrity_errors() -> tuple[type[BaseException], ...]:
    if not DATABASE_URL:
        return (sqlite3.IntegrityError,)
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL is configured but psycopg is not installed. Install requirements.txt."
        ) from error
    return (sqlite3.IntegrityError, psycopg.IntegrityError)


def database_errors() -> tuple[type[BaseException], ...]:
    if not DATABASE_URL:
        return (sqlite3.Error,)
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL is configured but psycopg is not installed. Install requirements.txt."
        ) from error
    return (sqlite3.Error, psycopg.Error)


def mfa_cipher() -> Fernet:
    derived_key = hashlib.sha256(
        b"cbl-scheduler-admin-mfa-encryption\0" + MFA_ENCRYPTION_KEY.encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(derived_key))


def active_tenant_id() -> str:
    tenant_id = getattr(g, "tenant_id", None) if has_request_context() else None
    return tenant_id or DEFAULT_TENANT_ID


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(database_connect()) as connection, connection:
        if DATABASE_URL:
            role = connection.execute(
                """
                SELECT rolsuper, rolbypassrls
                FROM pg_roles
                WHERE rolname = current_user
                """
            ).fetchone()
            if not role or role[0] or role[1]:
                raise RuntimeError(
                    "Use a dedicated PostgreSQL application role without SUPERUSER or BYPASSRLS."
                )
        tenant_default = (
            "current_setting('app.tenant_id', true)"
            if DATABASE_URL
            else f"'{DEFAULT_TENANT_ID}'"
        )
        accepted_schedule_keys = (
            "PRIMARY KEY (tenant_id, run_id)"
            if DATABASE_URL
            else "PRIMARY KEY (run_id)"
        )
        schedule_location_keys = (
            """
            PRIMARY KEY (tenant_id, id),
            UNIQUE (tenant_id, name),
            UNIQUE (tenant_id, bamboo_schedule_id)
            """
            if DATABASE_URL
            else """
            PRIMARY KEY (id),
            UNIQUE (name),
            UNIQUE (bamboo_schedule_id)
            """
        )
        employee_keys = (
            "PRIMARY KEY (tenant_id, employee_id), UNIQUE (tenant_id, bamboohr_id)"
            if DATABASE_URL
            else "PRIMARY KEY (employee_id), UNIQUE (bamboohr_id)"
        )
        employee_location_reference = (
            "FOREIGN KEY (tenant_id, schedule_location_id) "
            "REFERENCES schedule_locations (tenant_id, id)"
            if DATABASE_URL
            else "FOREIGN KEY (schedule_location_id) "
            "REFERENCES schedule_locations (id) ON DELETE SET NULL"
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS accepted_schedules (
                run_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                week_start TEXT NOT NULL,
                location TEXT NOT NULL,
                role TEXT NOT NULL,
                payload TEXT NOT NULL,
                {accepted_schedule_keys}
            )
            """
        )
        connection.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS schedule_locations (
                id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                name TEXT NOT NULL,
                bamboo_schedule_id TEXT NOT NULL,
                location TEXT NOT NULL,
                role_group TEXT NOT NULL DEFAULT '',
                manager_name TEXT NOT NULL DEFAULT '',
                manager_email TEXT NOT NULL DEFAULT '',
                {schedule_location_keys}
            );
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                bamboohr_id TEXT,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                schedule_location_id TEXT,
                source_type TEXT NOT NULL DEFAULT 'bamboohr' CHECK (source_type IN ('bamboohr', 'manual')),
                bamboohr_location TEXT NOT NULL DEFAULT '',
                bamboohr_active INTEGER NOT NULL DEFAULT 1 CHECK (bamboohr_active IN (0, 1)),
                {employee_keys},
                {employee_location_reference}
            );
            CREATE TABLE IF NOT EXISTS app_migrations (
                migration_id TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS application_settings (
                setting_key TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                setting_value TEXT NOT NULL,
                PRIMARY KEY (tenant_id, setting_key)
            );
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                business_name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tenant_admins (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                mfa_secret TEXT,
                mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1)),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                auth_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tenant_login_attempts (
                login_key TEXT PRIMARY KEY,
                failures INTEGER NOT NULL DEFAULT 0,
                window_started_at INTEGER NOT NULL,
                locked_until INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS tenant_mfa_enrollments (
                admin_id TEXT PRIMARY KEY REFERENCES tenant_admins(id) ON DELETE CASCADE,
                encrypted_secret TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tenant_audit_events (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                actor_id TEXT,
                actor_email TEXT,
                action TEXT NOT NULL,
                route TEXT NOT NULL,
                response_status INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS developer_users (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                username TEXT NOT NULL UNIQUE,
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
        connection.execute(
            "INSERT OR IGNORE INTO tenants (tenant_id, business_name) VALUES (?, ?)",
            (DEFAULT_TENANT_ID, DEFAULT_APP_CONFIG["businessName"]),
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
        if connection.execute(
            "INSERT OR IGNORE INTO app_migrations (migration_id) VALUES (?)",
            ("attendance-automation-tier-update",),
        ).rowcount:
            refreshed = next(
                row for row in DEVELOPER_REQUESTS if row[0] == "attendance-automation"
            )
            connection.execute(
                """
                UPDATE developer_change_requests
                SET description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE request_id = ? AND status = 'pending'
                """,
                (refreshed[2], refreshed[0]),
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
        for table_name in (
            "accepted_schedules",
            "schedule_locations",
            "employees",
            "application_settings",
            "tenant_audit_events",
        ):
            columns = {
                row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")
            }
            if "tenant_id" not in columns:
                connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN tenant_id TEXT NOT NULL DEFAULT {tenant_default}"
                )
        if DATABASE_URL:
            def constraints_for(table_name: str) -> dict[str, tuple[str, list[str]]]:
                rows = connection.execute(
                    """
                    SELECT tc.constraint_name, tc.constraint_type, kcu.column_name
                    FROM information_schema.table_constraints tc
                    LEFT JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                     AND tc.table_name = kcu.table_name
                    WHERE tc.table_schema = current_schema()
                      AND tc.table_name = ?
                    ORDER BY tc.constraint_name, kcu.ordinal_position
                    """,
                    (table_name,),
                ).fetchall()
                constraints = {}
                for name, kind, column in rows:
                    constraints.setdefault(name, (kind, []))
                    if column is not None:
                        constraints[name][1].append(column)
                return constraints

            def drop_constraints(table_name: str, kinds: set[str]) -> None:
                for name, (kind, _) in constraints_for(table_name).items():
                    if kind in kinds:
                        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                            raise RuntimeError(f"Unexpected constraint name on {table_name}.")
                        connection.execute(
                            f"ALTER TABLE {table_name} DROP CONSTRAINT {name}"
                        )

            def ensure_primary_key(
                table_name: str,
                columns: list[str],
                additional_unique: tuple[str, ...] = (),
            ) -> None:
                constraints = constraints_for(table_name)
                existing = next(
                    (
                        (name, value[1])
                        for name, value in constraints.items()
                        if value[0] == "PRIMARY KEY"
                    ),
                    None,
                )
                if existing and existing[1] == columns:
                    if additional_unique:
                        present = [
                            [column.strip() for column in value[1]]
                            for value in constraints.values()
                            if value[0] == "UNIQUE"
                        ]
                        if not all(
                            [column.strip() for column in item.split(",")] in present
                            for item in additional_unique
                        ):
                            drop_constraints(table_name, {"PRIMARY KEY", "UNIQUE"})
                            connection.execute(
                                f"ALTER TABLE {table_name} ADD PRIMARY KEY ({', '.join(columns)})"
                            )
                            for unique_columns in additional_unique:
                                connection.execute(
                                    f"ALTER TABLE {table_name} ADD UNIQUE ({unique_columns})"
                                )
                    return
                drop_constraints(table_name, {"PRIMARY KEY", "UNIQUE"})
                connection.execute(
                    f"ALTER TABLE {table_name} ADD PRIMARY KEY ({', '.join(columns)})"
                )
                for unique_columns in additional_unique:
                    connection.execute(
                        f"ALTER TABLE {table_name} ADD UNIQUE ({unique_columns})"
                    )

            foreign_keys = connection.execute(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'employees'::regclass
                  AND contype = 'f'
                  AND confrelid = 'schedule_locations'::regclass
                """
            ).fetchall()
            for (name,) in foreign_keys:
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                    raise RuntimeError("Unexpected employee-location foreign-key name.")
                connection.execute(
                    f"ALTER TABLE employees DROP CONSTRAINT {name}"
                )
            ensure_primary_key("accepted_schedules", ["tenant_id", "run_id"])
            ensure_primary_key(
                "schedule_locations",
                ["tenant_id", "id"],
                ("tenant_id, name", "tenant_id, bamboo_schedule_id"),
            )
            ensure_primary_key(
                "employees",
                ["tenant_id", "employee_id"],
                ("tenant_id, bamboohr_id",),
            )
            ensure_primary_key(
                "application_settings", ["tenant_id", "setting_key"]
            )
            connection.execute(
                """
                ALTER TABLE employees
                ADD CONSTRAINT employees_tenant_location_fkey
                FOREIGN KEY (tenant_id, schedule_location_id)
                REFERENCES schedule_locations (tenant_id, id)
                """
            )
        else:
            settings_info = connection.execute(
                "PRAGMA table_info(application_settings)"
            ).fetchall()
            settings_primary_key = [
                row[1]
                for row in sorted(
                    (row for row in settings_info if row[5]),
                    key=lambda row: row[5],
                )
            ]
            if settings_primary_key != ["tenant_id", "setting_key"]:
                connection.execute(
                    "ALTER TABLE application_settings RENAME TO application_settings_legacy"
                )
                connection.execute(
                    """
                    CREATE TABLE application_settings (
                        setting_key TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        setting_value TEXT NOT NULL,
                        PRIMARY KEY (tenant_id, setting_key)
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO application_settings
                        (setting_key, setting_value, tenant_id)
                    SELECT setting_key, setting_value, tenant_id
                    FROM application_settings_legacy
                    """
                )
                connection.execute("DROP TABLE application_settings_legacy")
        if DATABASE_URL:
            for table_name in (
                "accepted_schedules",
                "schedule_locations",
                "employees",
                "application_settings",
                "tenant_audit_events",
            ):
                connection.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
                connection.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
                connection.execute(
                    f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}"
                )
                connection.execute(
                    f"""
                    CREATE POLICY tenant_isolation ON {table_name}
                    USING (tenant_id = current_setting('app.tenant_id', true))
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
                    """
                )
        connection.executemany(
            """
            INSERT OR IGNORE INTO application_settings
                (setting_key, setting_value, tenant_id)
            VALUES (?, ?, ?)
            """,
            [(key, value, DEFAULT_TENANT_ID) for key, value in DEFAULT_APP_CONFIG.items()],
        )
        connection.execute(
            """
            UPDATE tenants
            SET business_name = (
                SELECT setting_value FROM application_settings
                WHERE tenant_id = ? AND setting_key = 'businessName'
            )
            WHERE tenant_id = ?
            """,
            (DEFAULT_TENANT_ID, DEFAULT_TENANT_ID),
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


def migrate_sqlite_business_data(source_path: Path) -> None:
    if not DATABASE_URL:
        raise RuntimeError("Set SCHEDULE_CREATOR_DATABASE_URL before migrating to PostgreSQL.")
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite migration source was not found: {source_path}")

    with closing(sqlite3.connect(source_path)) as source_connection:
        source_connection.row_factory = sqlite3.Row
        source_connection.execute("BEGIN")
        source_tables = {
            row[0]
            for row in source_connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

        def source_rows(table_name: str) -> list[dict]:
            if table_name not in source_tables:
                return []
            return [
                dict(row)
                for row in source_connection.execute(f"SELECT * FROM {table_name}")
            ]

        source_settings = {
            row["setting_key"]: row["setting_value"]
            for row in source_rows("application_settings")
        }
        settings = DEFAULT_APP_CONFIG | source_settings
        locations = source_rows("schedule_locations")
        employees = source_rows("employees")
        accepted = source_rows("accepted_schedules")
        admins = source_rows("tenant_admins")
        change_requests = source_rows("developer_change_requests")
        dependencies = source_rows("developer_change_request_dependencies")
        developer_users = source_rows("developer_users")
        migrations = source_rows("app_migrations")
        audit_events = source_rows("tenant_audit_events")

    def source_value(row: dict, column: str, default):
        value = row.get(column, default)
        return default if value is None else value

    with closing(database_connect()) as connection, connection:
        migrated = connection.execute(
            "SELECT 1 FROM app_migrations WHERE migration_id = ?",
            ("sqlite-business-import-v1",),
        ).fetchone()
        if migrated:
            raise RuntimeError("This SQLite database has already been imported.")
        admin_exists = connection.execute(
            "SELECT 1 FROM tenant_admins LIMIT 1"
        ).fetchone()
        schedules_exist = connection.execute(
            "SELECT 1 FROM accepted_schedules WHERE tenant_id = ? LIMIT 1",
            (DEFAULT_TENANT_ID,),
        ).fetchone()
        developer_exists = connection.execute(
            "SELECT 1 FROM developer_users WHERE id = 1"
        ).fetchone()
        if admin_exists or schedules_exist or (developer_exists and developer_users):
            raise RuntimeError(
                "Import before provisioning an administrator, creating PostgreSQL schedules, "
                "or setting up target developer credentials."
            )
        connection.execute(
            "DELETE FROM employees WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        connection.execute(
            "DELETE FROM schedule_locations WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        connection.execute(
            "DELETE FROM accepted_schedules WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        connection.execute(
            "DELETE FROM application_settings WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        connection.execute(
            "DELETE FROM tenant_audit_events WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        if locations:
            connection.executemany(
                """
                INSERT INTO schedule_locations
                    (id, tenant_id, name, bamboo_schedule_id, location, role_group,
                     manager_name, manager_email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, id) DO UPDATE SET
                    name = excluded.name,
                    bamboo_schedule_id = excluded.bamboo_schedule_id,
                    location = excluded.location,
                    role_group = excluded.role_group,
                    manager_name = excluded.manager_name,
                    manager_email = excluded.manager_email
                """,
                [
                    (
                        row["id"],
                        DEFAULT_TENANT_ID,
                        row["name"],
                        row["bamboo_schedule_id"],
                        row["location"],
                        source_value(row, "role_group", ""),
                        source_value(row, "manager_name", ""),
                        source_value(row, "manager_email", ""),
                    )
                    for row in locations
                ],
            )
        if employees:
            connection.executemany(
                """
                INSERT INTO employees
                    (employee_id, tenant_id, bamboohr_id, name, location, role, active,
                     schedule_location_id, source_type, bamboohr_location, bamboohr_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, employee_id) DO UPDATE SET
                    bamboohr_id = excluded.bamboohr_id,
                    name = excluded.name,
                    location = excluded.location,
                    role = excluded.role,
                    active = excluded.active,
                    schedule_location_id = excluded.schedule_location_id,
                    source_type = excluded.source_type,
                    bamboohr_location = excluded.bamboohr_location,
                    bamboohr_active = excluded.bamboohr_active
                """,
                [
                    (
                        row["employee_id"],
                        DEFAULT_TENANT_ID,
                        row.get("bamboohr_id"),
                        row["name"],
                        row["location"],
                        row["role"],
                        source_value(row, "active", 1),
                        row.get("schedule_location_id"),
                        source_value(
                            row,
                            "source_type",
                            "manual" if row.get("bamboohr_id") is None else "bamboohr",
                        ),
                        source_value(row, "bamboohr_location", ""),
                        source_value(row, "bamboohr_active", 1),
                    )
                    for row in employees
                ],
            )
        if accepted:
            connection.executemany(
                """
                INSERT INTO accepted_schedules
                    (run_id, tenant_id, accepted_at, week_start, location, role, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, run_id) DO UPDATE SET
                    accepted_at = excluded.accepted_at,
                    week_start = excluded.week_start,
                    location = excluded.location,
                    role = excluded.role,
                    payload = excluded.payload
                """,
                [
                    (
                        row["run_id"],
                        DEFAULT_TENANT_ID,
                        source_value(row, "accepted_at", datetime.now().isoformat()),
                        row["week_start"],
                        row["location"],
                        row["role"],
                        row["payload"],
                    )
                    for row in accepted
                ],
            )
        connection.executemany(
            """
            INSERT INTO application_settings (setting_key, setting_value, tenant_id)
            VALUES (?, ?, ?)
            ON CONFLICT (tenant_id, setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
            """,
            [(key, value, DEFAULT_TENANT_ID) for key, value in settings.items()],
        )
        connection.execute(
            "UPDATE tenants SET business_name = ? WHERE tenant_id = ?",
            (settings["businessName"], DEFAULT_TENANT_ID),
        )
        if admins:
            connection.executemany(
                """
                INSERT INTO tenant_admins
                    (id, tenant_id, email, display_name, password_hash,
                     mfa_secret, mfa_enabled, active, auth_version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, NULL, 0, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    email = excluded.email,
                    display_name = excluded.display_name,
                    password_hash = excluded.password_hash,
                    mfa_secret = NULL,
                    mfa_enabled = 0,
                    active = excluded.active,
                    auth_version = excluded.auth_version,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        row["id"],
                        DEFAULT_TENANT_ID,
                        row["email"],
                        row["display_name"],
                        row["password_hash"],
                        source_value(row, "active", 1),
                        source_value(row, "auth_version", 1),
                        source_value(row, "created_at", datetime.now().isoformat()),
                        source_value(row, "updated_at", datetime.now().isoformat()),
                    )
                    for row in admins
                ],
            )
        if developer_users:
            connection.executemany(
                """
                INSERT INTO developer_users
                    (id, username, password_hash, auth_version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    username = excluded.username,
                    password_hash = excluded.password_hash,
                    auth_version = excluded.auth_version,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        row["id"],
                        row["username"],
                        row["password_hash"],
                        source_value(row, "auth_version", 1),
                        source_value(row, "created_at", datetime.now().isoformat()),
                        source_value(row, "updated_at", datetime.now().isoformat()),
                    )
                    for row in developer_users
                ],
            )
        if change_requests:
            connection.executemany(
                """
                INSERT INTO developer_change_requests
                    (request_id, title, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (request_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        row["request_id"],
                        row["title"],
                        row["description"],
                        row["status"],
                        source_value(row, "created_at", datetime.now().isoformat()),
                        source_value(row, "updated_at", datetime.now().isoformat()),
                    )
                    for row in change_requests
                ],
            )
        if dependencies:
            connection.execute("DELETE FROM developer_change_request_dependencies")
            connection.executemany(
                """
                INSERT OR IGNORE INTO developer_change_request_dependencies
                    (request_id, depends_on)
                VALUES (?, ?)
                """,
                [(row["request_id"], row["depends_on"]) for row in dependencies],
            )
        if migrations:
            connection.executemany(
                "INSERT OR IGNORE INTO app_migrations (migration_id) VALUES (?)",
                [(row["migration_id"],) for row in migrations],
            )
        if audit_events:
            connection.executemany(
                """
                INSERT INTO tenant_audit_events
                    (id, tenant_id, actor_id, actor_email, action, route,
                     response_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["id"],
                        DEFAULT_TENANT_ID,
                        row.get("actor_id"),
                        row.get("actor_email"),
                        row["action"],
                        row["route"],
                        row["response_status"],
                        source_value(row, "created_at", datetime.now().isoformat()),
                    )
                    for row in audit_events
                ],
            )
        connection.execute(
            "INSERT INTO app_migrations (migration_id) VALUES (?)",
            ("sqlite-business-import-v1",),
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
    with closing(database_connect()) as connection:
        rows = connection.execute(
            "SELECT setting_key, setting_value FROM application_settings WHERE tenant_id = ?",
            (active_tenant_id(),),
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
    with closing(database_connect()) as connection, connection:
        connection.executemany(
            """
            INSERT INTO application_settings (setting_key, setting_value, tenant_id)
            VALUES (?, ?, ?)
            ON CONFLICT(tenant_id, setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
            """,
            [(key, value, active_tenant_id()) for key, value in config.items()],
        )
        if "businessName" in config:
            connection.execute(
                "UPDATE tenants SET business_name = ? WHERE tenant_id = ?",
                (config["businessName"], active_tenant_id()),
            )


def valid_admin_email(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= 254
        and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()) is not None
    )


def provision_tenant_admin(name: str, email: str, password: str) -> str:
    if (
        not valid_admin_email(email)
        or not name.strip()
        or len(name.strip()) > 120
        or not 14 <= len(password) <= 1024
    ):
        raise ValueError("Provide a valid name, email, and password of at least 14 characters.")
    admin_id = secrets.token_urlsafe(18)
    with closing(database_connect()) as connection, connection:
        existing = connection.execute(
            "SELECT 1 FROM tenant_admins WHERE tenant_id = ? LIMIT 1",
            (DEFAULT_TENANT_ID,),
        ).fetchone()
        if existing:
            raise RuntimeError("An administrator has already been initialized for this tenant.")
        created = connection.execute(
            """
            INSERT OR IGNORE INTO tenant_admins
                (id, tenant_id, email, display_name, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                admin_id,
                DEFAULT_TENANT_ID,
                email.strip().casefold(),
                name.strip(),
                generate_password_hash(password),
            ),
        )
        if created.rowcount == 0:
            raise RuntimeError("An administrator already uses that email address.")
    return admin_id


def reset_tenant_admin_password(email: str, password: str) -> None:
    if not valid_admin_email(email) or not 14 <= len(password) <= 1024:
        raise ValueError("Provide a valid email and a password of at least 14 characters.")
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE tenant_admins
            SET password_hash = ?, auth_version = auth_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND email = ?
            """,
            (generate_password_hash(password), DEFAULT_TENANT_ID, email.strip().casefold()),
        )
        if updated.rowcount == 0:
            raise RuntimeError("No administrator uses that email address.")
        connection.execute("DELETE FROM tenant_login_attempts")


def reset_tenant_admin_mfa(email: str) -> None:
    if not valid_admin_email(email):
        raise ValueError("Provide a valid administrator email.")
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE tenant_admins
            SET mfa_secret = NULL, mfa_enabled = 0, auth_version = auth_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND email = ?
            """,
            (DEFAULT_TENANT_ID, email.strip().casefold()),
        )
        if updated.rowcount == 0:
            raise RuntimeError("No administrator uses that email address.")
        connection.execute("DELETE FROM tenant_login_attempts")


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_value(secret: str, counter: int) -> str:
    padded_secret = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded_secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{number:06d}"


def verify_totp(secret: str, supplied: object) -> bool:
    if not isinstance(supplied, str):
        return False
    # Authenticator apps often display codes as "123 456".
    supplied = re.sub(r"[\s-]", "", supplied)
    if re.fullmatch(r"\d{6}", supplied) is None:
        return False
    counter = int(time_module.time() // 30)
    return any(
        hmac.compare_digest(totp_value(secret, counter + offset), supplied)
        for offset in (-1, 0, 1)
    )


def tenant_authenticated() -> bool:
    admin_id = session.get("tenant_admin_id")
    tenant_id = session.get("tenant_id")
    auth_version = session.get("tenant_auth_version")
    if (
        not isinstance(admin_id, str)
        or not isinstance(tenant_id, str)
        or not isinstance(auth_version, int)
    ):
        return False
    g.tenant_id = tenant_id
    with closing(database_connect()) as connection:
        account = connection.execute(
            """
            SELECT a.auth_version, a.active, a.mfa_enabled
            FROM tenant_admins a
            JOIN tenants t ON t.tenant_id = a.tenant_id
            WHERE a.id = ? AND a.tenant_id = ? AND t.active = 1
            """,
            (admin_id, tenant_id),
        ).fetchone()
    if not account or account[0] != auth_version or not account[1] or not (
        account[2] or MFA_BYPASS
    ):
        session.clear()
        g.tenant_id = DEFAULT_TENANT_ID
        return False
    return True


def tenant_auth_csrf_valid() -> bool:
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("tenant_auth_csrf", "")
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


def tenant_auth_attempt_key(email: str) -> str:
    return hmac.new(
        app.config["SECRET_KEY"].encode("utf-8"),
        f"{request.remote_addr or 'unknown'}\0{email}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def tenant_auth_attempt_state(
    connection: DatabaseConnection, login_key: str, now: int
) -> tuple[int, int] | None:
    attempt = connection.execute(
        """
        SELECT failures, window_started_at, locked_until
        FROM tenant_login_attempts WHERE login_key = ?
        """,
        (login_key,),
    ).fetchone()
    if attempt and attempt[2] > now:
        return None
    if not attempt or now - attempt[1] >= 900:
        return 0, now
    return attempt[0], attempt[1]


def record_tenant_auth_failure(
    connection: DatabaseConnection,
    login_key: str,
    failures: int,
    window_started_at: int,
    now: int,
) -> None:
    failures += 1
    locked_until = now + 900 if failures >= 5 else 0
    connection.execute(
        """
        INSERT INTO tenant_login_attempts
            (login_key, failures, window_started_at, locked_until)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(login_key) DO UPDATE SET
            failures = excluded.failures,
            window_started_at = excluded.window_started_at,
            locked_until = excluded.locked_until
        """,
        (login_key, failures, window_started_at, locked_until),
    )


def otp_qr_data_uri(otp_uri: str) -> str:
    import segno

    buffer = io.BytesIO()
    segno.make(otp_uri, error="m").save(
        buffer, kind="svg", scale=6, border=4, dark="#000000", light="#ffffff"
    )
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def start_mfa_enrollment(connection, admin_id: str, email: str) -> tuple[str, str]:
    secret = new_totp_secret()
    connection.execute(
        """
        INSERT INTO tenant_mfa_enrollments (admin_id, encrypted_secret)
        VALUES (?, ?)
        ON CONFLICT(admin_id) DO UPDATE
        SET encrypted_secret = excluded.encrypted_secret,
            created_at = CURRENT_TIMESTAMP
        """,
        (admin_id, mfa_cipher().encrypt(secret.encode("ascii")).decode("ascii")),
    )
    label = quote(f"CBL Schedule:{email}")
    return secret, f"otpauth://totp/{label}?secret={secret}&issuer=CBL%20Schedule"


@app.before_request
def enforce_tenant_authentication():
    g.tenant_id = session.get("tenant_id") or DEFAULT_TENANT_ID
    if DATABASE_URL and not request.is_secure and not http_allowed_for_client():
        return (
            "HTTPS is required for PostgreSQL-backed deployments. Configure the app's trusted HTTPS reverse proxy.",
            400,
        )
    if request.path.startswith("/api/developer/") or request.path.startswith(
        "/api/tenant-auth/"
    ):
        return None
    if request.path.startswith("/api/"):
        if not tenant_authenticated():
            return jsonify(error="Sign in as a business administrator to continue."), 401
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            if origin:
                parsed_origin = urlsplit(origin)
                if (
                    parsed_origin.scheme not in {"http", "https"}
                    or parsed_origin.netloc.casefold() != request.host.casefold()
                ):
                    return jsonify(error="Cross-origin requests are not allowed."), 403
    return None


@app.after_request
def audit_tenant_mutation(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if DATABASE_URL and request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    if request.path == "/" or request.path.startswith("/api/tenant-auth/"):
        response.headers["Cache-Control"] = "no-store"
    actor_id = session.get("tenant_admin_id") or session.get("pending_tenant_admin_id")
    auth_success = (
        request.path.startswith("/api/tenant-auth/")
        and response.status_code < 400
    )
    if (
        request.path.startswith("/api/")
        and not request.path.startswith("/api/developer/")
        and request.method not in {"GET", "HEAD", "OPTIONS"}
        and response.status_code < 500
        and (isinstance(actor_id, str) or auth_success)
    ):
        with closing(database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO tenant_audit_events
                    (id, tenant_id, actor_id, actor_email, action, route, response_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    secrets.token_urlsafe(18),
                    active_tenant_id(),
                    actor_id,
                    session.get("tenant_admin_email"),
                    request.method,
                    request.endpoint or "unknown",
                    response.status_code,
                ),
            )
    return response


@app.get("/api/tenant-auth/state")
def tenant_auth_state():
    authenticated = tenant_authenticated()
    csrf_token = session.get("tenant_auth_csrf")
    if not isinstance(csrf_token, str):
        csrf_token = secrets.token_urlsafe(32)
        session["tenant_auth_csrf"] = csrf_token
    with closing(database_connect()) as connection:
        configured = connection.execute(
            "SELECT 1 FROM tenant_admins WHERE tenant_id = ? LIMIT 1",
            (DEFAULT_TENANT_ID,),
        ).fetchone() is not None
    return jsonify(
        configured=configured,
        authenticated=authenticated,
        email=session.get("tenant_admin_email") if authenticated else None,
        csrfToken=csrf_token,
        canBootstrap=(
            not DATABASE_URL
            and not configured
            and request.remote_addr in {"127.0.0.1", "::1"}
        ),
    )


@app.post("/api/tenant-auth/bootstrap")
def bootstrap_tenant_admin():
    if DATABASE_URL:
        return jsonify(error="Use the server-side bootstrap-admin command for PostgreSQL."), 403
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return jsonify(error="Initial administrator setup is allowed only from this computer."), 403
    if not tenant_auth_csrf_valid():
        return jsonify(error="The setup session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not valid_admin_email(payload.get("email"))
        or not isinstance(payload.get("name"), str)
        or not payload["name"].strip()
        or len(payload["name"].strip()) > 120
        or not isinstance(payload.get("password"), str)
        or not 14 <= len(payload["password"]) <= 1024
    ):
        return jsonify(error="Enter a valid name, email, and password of at least 14 characters."), 400
    admin_id = secrets.token_urlsafe(18)
    with closing(database_connect()) as connection, connection:
        existing = connection.execute(
            "SELECT 1 FROM tenant_admins WHERE tenant_id = ? LIMIT 1",
            (DEFAULT_TENANT_ID,),
        ).fetchone()
        if existing:
            return jsonify(error="An administrator has already been initialized."), 409
        created = connection.execute(
            """
            INSERT OR IGNORE INTO tenant_admins
                (id, tenant_id, email, display_name, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                admin_id,
                DEFAULT_TENANT_ID,
                payload["email"].strip().casefold(),
                payload["name"].strip(),
                generate_password_hash(payload["password"]),
            ),
        )
        if created.rowcount == 0:
            return jsonify(error="An administrator already uses that email address."), 409
        secret, otp_uri = start_mfa_enrollment(
            connection, admin_id, payload["email"].strip().casefold()
        )
    session.clear()
    session["pending_tenant_admin_id"] = admin_id
    session["pending_tenant_id"] = DEFAULT_TENANT_ID
    session["tenant_auth_csrf"] = secrets.token_urlsafe(32)
    return jsonify(
        mfaEnrollmentRequired=True,
        secret=secret,
        otpAuthUri=otp_uri,
        qrCode=otp_qr_data_uri(otp_uri),
        csrfToken=session["tenant_auth_csrf"],
    ), 201


@app.post("/api/tenant-auth/login")
def tenant_admin_login():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The sign-in session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not valid_admin_email(payload.get("email"))
        or not isinstance(payload.get("password"), str)
    ):
        return jsonify(error="Enter your administrator email and password."), 400
    email = payload["email"].strip().casefold()
    login_key = tenant_auth_attempt_key(email)
    now = int(time_module.time())
    with closing(database_connect()) as connection, connection:
        attempt_state = tenant_auth_attempt_state(connection, login_key, now)
        if attempt_state is None:
            return jsonify(error="Too many failed sign-in attempts. Try again later."), 429
        failures, window_started_at = attempt_state
        account = connection.execute(
            """
            SELECT a.id, a.tenant_id, a.email, a.password_hash, a.mfa_secret,
                   a.mfa_enabled, a.auth_version, a.active
            FROM tenant_admins a
            JOIN tenants t ON t.tenant_id = a.tenant_id AND t.active = 1
            WHERE a.email = ?
            """,
            (email,),
        ).fetchone()
        password_valid = bool(
            account
            and account[7]
            and check_password_hash(account[3], payload["password"])
        )
        if not password_valid:
            record_tenant_auth_failure(
                connection, login_key, failures, window_started_at, now
            )
            return jsonify(error="The email or password is incorrect."), 401
        if MFA_BYPASS:
            connection.execute(
                "DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,)
            )
        elif not account[5]:
            g.tenant_id = account[1]
            secret, otp_uri = start_mfa_enrollment(
                connection, account[0], account[2]
            )
            session.clear()
            session["pending_tenant_admin_id"] = account[0]
            session["pending_tenant_id"] = account[1]
            session["tenant_auth_csrf"] = secrets.token_urlsafe(32)
            return jsonify(
                mfaEnrollmentRequired=True,
                secret=secret,
                otpAuthUri=otp_uri,
                qrCode=otp_qr_data_uri(otp_uri),
                csrfToken=session["tenant_auth_csrf"],
            ), 200
        else:
            try:
                secret = mfa_cipher().decrypt(account[4].encode("ascii")).decode("ascii")
            except (AttributeError, InvalidToken, UnicodeDecodeError):
                return jsonify(error="Administrator MFA data is unavailable; contact support."), 503
            if not verify_totp(secret, payload.get("code")):
                record_tenant_auth_failure(
                    connection, login_key, failures, window_started_at, now
                )
                return jsonify(error="The email, password, or verification code is incorrect."), 401
            connection.execute("DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,))
        tenant_admin = account
    session.clear()
    session.permanent = True
    session["tenant_admin_id"] = tenant_admin[0]
    session["tenant_id"] = tenant_admin[1]
    session["tenant_admin_email"] = tenant_admin[2]
    session["tenant_auth_version"] = tenant_admin[6]
    session["tenant_auth_csrf"] = secrets.token_urlsafe(32)
    g.tenant_id = tenant_admin[1]
    return jsonify(authenticated=True, csrfToken=session["tenant_auth_csrf"])


@app.post("/api/tenant-auth/verify-mfa")
def verify_tenant_admin_mfa():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The setup session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    admin_id = session.get("pending_tenant_admin_id")
    tenant_id = session.get("pending_tenant_id")
    if (
        not isinstance(payload, dict)
        or not isinstance(admin_id, str)
        or not isinstance(tenant_id, str)
    ):
        return jsonify(error="Restart administrator sign-in to continue MFA setup."), 401
    g.tenant_id = tenant_id
    with closing(database_connect()) as connection, connection:
        enrollment = connection.execute(
            """
            SELECT e.encrypted_secret, a.email, a.auth_version, a.active
            FROM tenant_mfa_enrollments e
            JOIN tenant_admins a ON a.id = e.admin_id
            WHERE e.admin_id = ? AND a.tenant_id = ?
            """,
            (admin_id, tenant_id),
        ).fetchone()
        if not enrollment or not enrollment[3]:
            return jsonify(error="The MFA enrollment session is no longer valid."), 401
        now = int(time_module.time())
        login_key = tenant_auth_attempt_key(enrollment[1])
        attempt_state = tenant_auth_attempt_state(connection, login_key, now)
        if attempt_state is None:
            return jsonify(error="Too many failed verification attempts. Try again later."), 429
        try:
            secret = mfa_cipher().decrypt(enrollment[0].encode("ascii")).decode("ascii")
        except (InvalidToken, UnicodeDecodeError):
            return jsonify(error="MFA enrollment data is unavailable; contact support."), 503
        if not verify_totp(secret, payload.get("code")):
            record_tenant_auth_failure(
                connection, login_key, attempt_state[0], attempt_state[1], now
            )
            return jsonify(error="Enter the current six-digit code from your authenticator."), 400
        connection.execute(
            """
            UPDATE tenant_admins
            SET mfa_secret = ?, mfa_enabled = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (mfa_cipher().encrypt(secret.encode("ascii")).decode("ascii"), admin_id, tenant_id),
        )
        connection.execute(
            "DELETE FROM tenant_mfa_enrollments WHERE admin_id = ?", (admin_id,)
        )
        connection.execute(
            "DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,)
        )
    session.clear()
    session.permanent = True
    session["tenant_admin_id"] = admin_id
    session["tenant_id"] = tenant_id
    session["tenant_admin_email"] = enrollment[1]
    session["tenant_auth_version"] = enrollment[2]
    session["tenant_auth_csrf"] = secrets.token_urlsafe(32)
    g.tenant_id = tenant_id
    return jsonify(authenticated=True, csrfToken=session["tenant_auth_csrf"])


@app.post("/api/tenant-auth/logout")
def tenant_admin_logout():
    if not tenant_authenticated():
        return jsonify(error="Sign in first."), 401
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    session.clear()
    return jsonify(loggedOut=True)


@app.get("/")
def index():
    if not tenant_authenticated():
        return send_from_directory(APP_DIRECTORY, "tenant-login.html")
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
    with closing(database_connect()) as connection:
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
    with closing(database_connect()) as connection:
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
    with closing(database_connect()) as connection, connection:
        try:
            connection.execute(
                """
                INSERT INTO developer_users (id, username, password_hash)
                VALUES (1, ?, ?)
                """,
                (username, generate_password_hash(payload["password"])),
            )
        except database_integrity_errors():
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
    with closing(database_connect()) as connection, connection:
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
    with closing(database_connect()) as connection, connection:
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
        except database_integrity_errors():
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
    with closing(database_connect()) as connection:
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
    with closing(database_connect()) as connection, connection:
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
    with closing(database_connect()) as connection:
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

    with closing(database_connect()) as connection, connection:
        conflict_key = "tenant_id, run_id" if DATABASE_URL else "run_id"
        connection.execute(
            f"""
            INSERT INTO accepted_schedules (run_id, week_start, location, role, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT({conflict_key}) DO UPDATE SET
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

    with closing(database_connect()) as connection, connection:
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
    with closing(database_connect()) as connection, connection:
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
    connection: DatabaseConnection, employee_id: str, exclude_employee_id: str | None = None
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
    connection: DatabaseConnection, remote_employees: list[dict[str, str]]
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


def mapped_bamboohr_location(connection: DatabaseConnection, location: str) -> str:
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

    with closing(database_connect()) as connection, connection:
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
    with closing(database_connect()) as connection:
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
    with closing(database_connect()) as connection, connection:
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
    with closing(database_connect()) as connection, connection:
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
    with closing(database_connect()) as connection, connection:
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


def employee_location_exists(connection: DatabaseConnection, payload: dict) -> bool:
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
    with closing(database_connect()) as connection, connection:
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
        except database_integrity_errors():
            return directory_conflict()
    return jsonify(employee=employee_payload), 201


@app.put("/api/employees/<path:employee_id>")
def update_employee(employee_id: str):
    payload = request.get_json(silent=True)
    if not valid_employee(payload):
        return jsonify(error="Employee ID, name, location, role, and active status are required."), 400
    with closing(database_connect()) as connection, connection:
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
        except database_integrity_errors():
            return directory_conflict()
        if cursor.rowcount == 0:
            return jsonify(error="Employee was not found."), 404
    return jsonify(employee=payload)


@app.delete("/api/employees/<path:employee_id>")
def delete_employee(employee_id: str):
    with closing(database_connect()) as connection, connection:
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
    with closing(database_connect()) as connection:
        rows = connection.execute(
            """
            SELECT s.id, s.name, s.bamboo_schedule_id, s.location, s.role_group,
                   s.manager_name, s.manager_email,
                   COUNT(e.employee_id)
            FROM schedule_locations s
            LEFT JOIN employees e ON e.schedule_location_id = s.id
            GROUP BY s.id, s.name, s.bamboo_schedule_id, s.location, s.role_group,
                     s.manager_name, s.manager_email
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


def schedule_location_conflict(error: BaseException):
    return jsonify(error="Schedule name or BambooHR schedule ID is already in use."), 409


@app.post("/api/schedule-locations")
def create_schedule_location():
    payload = request.get_json(silent=True)
    if not valid_schedule_location(payload):
        return jsonify(
            error="Schedule name, BambooHR schedule ID, app location, manager name, and valid manager email are required."
        ), 400
    location_id = os.urandom(16).hex()
    with closing(database_connect()) as connection, connection:
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
        except database_integrity_errors() as error:
            return schedule_location_conflict(error)
    return jsonify(id=location_id), 201


@app.put("/api/schedule-locations/<path:location_id>")
def update_schedule_location(location_id: str):
    payload = request.get_json(silent=True)
    if not valid_schedule_location(payload):
        return jsonify(
            error="Schedule name, BambooHR schedule ID, app location, manager name, and valid manager email are required."
        ), 400
    with closing(database_connect()) as connection, connection:
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
        except database_integrity_errors() as error:
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
    with closing(database_connect()) as connection, connection:
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
    with closing(database_connect()) as connection, connection:
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
    connection: DatabaseConnection, selections: object
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
    connection: DatabaseConnection, selections: list[dict]
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
        except database_errors():
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
    with closing(database_connect()) as connection:
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
    with closing(database_connect()) as connection:
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
    parser = argparse.ArgumentParser(description="Run the CBL Schedule Creator.")
    commands = parser.add_subparsers(dest="command")
    bootstrap_command = commands.add_parser(
        "bootstrap-admin",
        help="Create the first administrator for the configured tenant.",
    )
    bootstrap_command.add_argument("--email", required=True)
    bootstrap_command.add_argument("--name", required=True)
    reset_command = commands.add_parser(
        "reset-admin-password",
        help="Set a new password for an existing administrator.",
    )
    reset_command.add_argument("--email", required=True)
    mfa_reset_command = commands.add_parser(
        "reset-admin-mfa",
        help="Remove an administrator's authenticator so it can be enrolled again.",
    )
    mfa_reset_command.add_argument("--email", required=True)
    migration_command = commands.add_parser(
        "migrate-sqlite",
        help="Import the current SQLite business data into PostgreSQL once.",
    )
    migration_command.add_argument(
        "--source",
        type=Path,
        default=DATABASE_PATH,
        help="SQLite database to import (defaults to the app's local database).",
    )
    arguments = parser.parse_args()
    initialize_database()
    if arguments.command == "migrate-sqlite":
        confirmation = input(
            "This imports SQLite data and replaces the target tenant's initial "
            "locations, employees, and settings. Type IMPORT to continue: "
        )
        if confirmation != "IMPORT":
            parser.error("SQLite migration cancelled.")
        try:
            migrate_sqlite_business_data(arguments.source)
        except (FileNotFoundError, RuntimeError) as error:
            parser.error(str(error))
        except database_errors() as error:
            parser.error(str(error))
        print("SQLite business data imported into the configured PostgreSQL tenant.")
        return
    if arguments.command == "reset-admin-mfa":
        try:
            reset_tenant_admin_mfa(arguments.email)
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))
        print("MFA reset. Sign in with the password to scan a new QR code.")
        return
    if arguments.command == "reset-admin-password":
        password = getpass("New administrator password (14+ characters): ")
        if password != getpass("Confirm new password: "):
            parser.error("The passwords do not match.")
        try:
            reset_tenant_admin_password(arguments.email, password)
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))
        print("Password reset. Existing sessions are signed out.")
        return
    if arguments.command == "bootstrap-admin":
        password = getpass("Administrator password (14+ characters): ")
        confirmation = getpass("Confirm administrator password: ")
        if password != confirmation:
            parser.error("The passwords do not match.")
        try:
            provision_tenant_admin(
                arguments.name,
                arguments.email,
                password,
            )
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))
        print(
            "Administrator created. Sign in through HTTPS to enroll mandatory MFA."
        )
        return
    port = int(os.environ.get("SCHEDULE_CREATOR_PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
