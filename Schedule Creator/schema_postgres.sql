-- CBL Schedule Creator: PostgreSQL schema (PostgreSQL 13+).
--
-- Mirrors what scheduler.py creates on startup in PostgreSQL mode, so the app
-- finds a matching schema and its own migrations become no-ops.
--
-- STEP 1 - as a PostgreSQL administrator, once (edit names and password first):
--
--   CREATE ROLE schedule_app LOGIN PASSWORD 'CHANGE-ME-long-random-value'
--       NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
--   CREATE DATABASE schedule_creator OWNER schedule_app;
--
-- STEP 2 - run this file AS THE APPLICATION ROLE (it must own the tables
-- because the app alters policies and constraints at startup):
--
--   psql -U schedule_app -h <host> -d schedule_creator -f schema_postgres.sql
--
-- The app role must never be SUPERUSER or BYPASSRLS; the app refuses to start
-- otherwise. Row-level security is FORCED on tenant data tables, so even the
-- owner sees only the tenant set in app.tenant_id.
--
-- STEP 3 - set SCHEDULE_CREATOR_DATABASE_URL and the secrets (see README).

BEGIN;

-- Tenant data (row-level security, composite keys led by tenant_id) ----------

CREATE TABLE IF NOT EXISTS accepted_schedules (
    run_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT current_setting('app.tenant_id', true),
    accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    week_start TEXT NOT NULL,
    location TEXT NOT NULL,
    role TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (tenant_id, run_id)
);

CREATE TABLE IF NOT EXISTS schedule_locations (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT current_setting('app.tenant_id', true),
    name TEXT NOT NULL,
    bamboo_schedule_id TEXT NOT NULL,
    location TEXT NOT NULL,
    role_group TEXT NOT NULL DEFAULT '',
    manager_name TEXT NOT NULL DEFAULT '',
    manager_email TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, name),
    UNIQUE (tenant_id, bamboo_schedule_id)
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT current_setting('app.tenant_id', true),
    bamboohr_id TEXT,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    schedule_location_id TEXT,
    source_type TEXT NOT NULL DEFAULT 'bamboohr' CHECK (source_type IN ('bamboohr', 'manual')),
    bamboohr_location TEXT NOT NULL DEFAULT '',
    bamboohr_active INTEGER NOT NULL DEFAULT 1 CHECK (bamboohr_active IN (0, 1)),
    PRIMARY KEY (tenant_id, employee_id),
    UNIQUE (tenant_id, bamboohr_id)
);

ALTER TABLE employees DROP CONSTRAINT IF EXISTS employees_tenant_location_fkey;
ALTER TABLE employees
    ADD CONSTRAINT employees_tenant_location_fkey
    FOREIGN KEY (tenant_id, schedule_location_id)
    REFERENCES schedule_locations (tenant_id, id);

CREATE TABLE IF NOT EXISTS application_settings (
    setting_key TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT current_setting('app.tenant_id', true),
    setting_value TEXT NOT NULL,
    PRIMARY KEY (tenant_id, setting_key)
);

CREATE TABLE IF NOT EXISTS tenant_audit_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT current_setting('app.tenant_id', true),
    actor_id TEXT,
    actor_email TEXT,
    action TEXT NOT NULL,
    route TEXT NOT NULL,
    response_status INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Identity (looked up before a tenant is known, so no row-level security) ----

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id TEXT PRIMARY KEY,
    business_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tenant_admins (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants (tenant_id),
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
    admin_id TEXT PRIMARY KEY REFERENCES tenant_admins (id) ON DELETE CASCADE,
    encrypted_secret TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Application bookkeeping and developer change-request log -------------------

CREATE TABLE IF NOT EXISTS app_migrations (
    migration_id TEXT PRIMARY KEY
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
    request_id TEXT NOT NULL REFERENCES developer_change_requests (request_id) ON DELETE CASCADE,
    depends_on TEXT NOT NULL REFERENCES developer_change_requests (request_id) ON DELETE CASCADE,
    PRIMARY KEY (request_id, depends_on),
    CHECK (request_id <> depends_on)
);

-- Row-level security: each connection sets app.tenant_id; rows from any other
-- tenant are invisible and cannot be written. FORCE applies it to the owner too.

ALTER TABLE accepted_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE accepted_schedules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON accepted_schedules;
CREATE POLICY tenant_isolation ON accepted_schedules
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE schedule_locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedule_locations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON schedule_locations;
CREATE POLICY tenant_isolation ON schedule_locations
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON employees;
CREATE POLICY tenant_isolation ON employees
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE application_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_settings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON application_settings;
CREATE POLICY tenant_isolation ON application_settings
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE tenant_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_audit_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenant_audit_events;
CREATE POLICY tenant_isolation ON tenant_audit_events
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- Initial tenant (must match SCHEDULE_CREATOR_TENANT_ID, default 'cbljm').
-- Change the values here if you use a different tenant ID or business name.
INSERT INTO tenants (tenant_id, business_name)
VALUES ('cbljm', 'Celebration Brands Limited')
ON CONFLICT (tenant_id) DO NOTHING;

COMMIT;
