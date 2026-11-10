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

-- Global opaque browser-session clocks; no account or tenant data is stored.
CREATE TABLE IF NOT EXISTS browser_sessions (
    id TEXT PRIMARY KEY,
    started_at BIGINT NOT NULL,
    last_activity BIGINT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS roster_configurations (
    tenant_id TEXT PRIMARY KEY DEFAULT current_setting('app.tenant_id', true),
    revision INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
    pools_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS roster_employee_settings (
    tenant_id TEXT NOT NULL DEFAULT current_setting('app.tenant_id', true),
    employee_id TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, employee_id)
);

CREATE TABLE IF NOT EXISTS meta_configurations (
    tenant_id TEXT NOT NULL DEFAULT current_setting('app.tenant_id', true) PRIMARY KEY,
    revision INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
    locations_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS attendance_reconciliation_audit_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT current_setting('app.tenant_id', true),
    discrepancy_id TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('app_to_bamboohr', 'bamboohr_to_app')),
    shift_date TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    before_json TEXT NOT NULL,
    after_json TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('succeeded', 'partial', 'failed')),
    actor_id TEXT,
    actor_email TEXT,
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
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    username_key TEXT UNIQUE,
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

ALTER TABLE roster_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE roster_configurations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON roster_configurations;
CREATE POLICY tenant_isolation ON roster_configurations
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE roster_employee_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE roster_employee_settings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON roster_employee_settings;
CREATE POLICY tenant_isolation ON roster_employee_settings
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE meta_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_configurations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON meta_configurations;
CREATE POLICY tenant_isolation ON meta_configurations
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

ALTER TABLE attendance_reconciliation_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_reconciliation_audit_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON attendance_reconciliation_audit_events;
CREATE POLICY tenant_isolation ON attendance_reconciliation_audit_events
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- Manager and employee sign-in accounts (looked up by BambooHR subdomain before
-- the tenant is known, so like tenant_admins this table has no row-level policy;
-- every query scopes by tenant_id explicitly).
CREATE TABLE IF NOT EXISTS tenant_users (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    role TEXT NOT NULL CHECK (role IN ('manager', 'employee')),
    email TEXT,
    employee_id TEXT,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 1 CHECK (must_change_password IN (0, 1)),
    temp_password_expires_at INTEGER NOT NULL DEFAULT 0,
    mfa_secret TEXT,
    mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1)),
    mfa_pending_secret TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    auth_version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS tenant_users_email_unique ON tenant_users (tenant_id, email);
CREATE UNIQUE INDEX IF NOT EXISTS tenant_users_employee_unique ON tenant_users (tenant_id, employee_id);

CREATE TABLE IF NOT EXISTS attendance_notifications (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    employee_name TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    shift_date TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, dedupe_key)
);
CREATE TABLE IF NOT EXISTS attendance_notification_reads (
    tenant_id TEXT NOT NULL,
    notification_id TEXT NOT NULL,
    reader_key TEXT NOT NULL,
    read_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, notification_id, reader_key)
);

ALTER TABLE attendance_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_notifications FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON attendance_notifications;
CREATE POLICY tenant_isolation ON attendance_notifications
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE attendance_notification_reads ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_notification_reads FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON attendance_notification_reads;
CREATE POLICY tenant_isolation ON attendance_notification_reads
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

CREATE TABLE IF NOT EXISTS schedule_portal_codes (
    tenant_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    role TEXT NOT NULL,
    period_start TEXT NOT NULL,
    code_hash TEXT NOT NULL UNIQUE,
    encrypted_code TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    PRIMARY KEY (tenant_id, location_id, role, period_start)
);
ALTER TABLE schedule_portal_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedule_portal_codes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON schedule_portal_codes;
CREATE POLICY tenant_isolation ON schedule_portal_codes
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

-- Authenticated trades and sandbox billing.
CREATE TABLE IF NOT EXISTS shift_trades (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, run_id TEXT NOT NULL,
    day INTEGER NOT NULL, employee_a TEXT NOT NULL, employee_b TEXT NOT NULL,
    slot_a TEXT NOT NULL, slot_b TEXT NOT NULL, location_id TEXT NOT NULL,
    state TEXT NOT NULL, reason TEXT NOT NULL, created_by TEXT NOT NULL,
    override_reason TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE shift_trades ADD COLUMN IF NOT EXISTS override_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE shift_trades ADD COLUMN IF NOT EXISTS days TEXT NOT NULL DEFAULT '[]';
ALTER TABLE shift_trades ADD COLUMN IF NOT EXISTS rest_warnings TEXT NOT NULL DEFAULT '{}';
ALTER TABLE shift_trades ADD COLUMN IF NOT EXISTS rest_acknowledged TEXT NOT NULL DEFAULT '[]';
ALTER TABLE shift_trades ADD COLUMN IF NOT EXISTS initiated_role TEXT NOT NULL DEFAULT 'employee';
ALTER TABLE shift_trades ADD COLUMN IF NOT EXISTS target_confirmed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE shift_trades ADD COLUMN IF NOT EXISTS constraint_policy TEXT NOT NULL DEFAULT 'legacy';
CREATE TABLE IF NOT EXISTS shift_trade_events (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, trade_id TEXT NOT NULL,
    state TEXT NOT NULL, actor_id TEXT NOT NULL, reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS shift_trade_reads (
    tenant_id TEXT NOT NULL, reader_id TEXT NOT NULL, trade_id TEXT NOT NULL,
    version INTEGER NOT NULL, PRIMARY KEY (tenant_id,reader_id,trade_id)
);
CREATE TABLE IF NOT EXISTS shift_trade_publish (
    trade_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
    before_payload TEXT NOT NULL, after_payload TEXT NOT NULL,
    operations TEXT NOT NULL, remote_mode TEXT NOT NULL, state TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS billing_configuration (
    id INTEGER PRIMARY KEY, payload TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS billing_accounts (
    tenant_id TEXT PRIMARY KEY, subscription_id TEXT UNIQUE, checkout_id TEXT NOT NULL,
    plan_id TEXT NOT NULL DEFAULT '', tier TEXT NOT NULL, period TEXT NOT NULL,
    auto_renew INTEGER NOT NULL, provider_status TEXT NOT NULL,
    access_state TEXT NOT NULL DEFAULT 'active', paid_until TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0, next_retry INTEGER,
    retry_state TEXT NOT NULL DEFAULT 'idle', last_error TEXT, last_payment TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE billing_accounts ADD COLUMN IF NOT EXISTS plan_id TEXT NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS billing_events (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, kind TEXT NOT NULL,
    detail TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS billing_webhook_receipts (
    id TEXT PRIMARY KEY, applied INTEGER NOT NULL DEFAULT 0
);
-- Opaque subscription-to-tenant routing, consulted before webhook tenant context.
CREATE TABLE IF NOT EXISTS attendance_reports (
    tenant_id TEXT NOT NULL, id TEXT NOT NULL, run_key TEXT NOT NULL,
    cutoff TEXT NOT NULL, created_at TEXT NOT NULL, state TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, id), UNIQUE (tenant_id, run_key)
);
CREATE TABLE IF NOT EXISTS attendance_report_settings (
    tenant_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
    checked_at TEXT NOT NULL, heartbeat TEXT
);
-- Contains no prices, payment details, credentials, employee or business names.
CREATE TABLE IF NOT EXISTS billing_subscription_index (
    subscription_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS billing_worker_status (
    id INTEGER PRIMARY KEY, heartbeat INTEGER NOT NULL
);
DO $$
DECLARE table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'shift_trades','shift_trade_events','shift_trade_reads','shift_trade_publish',
        'billing_accounts','billing_events','attendance_reports','attendance_report_settings'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', table_name);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I USING (tenant_id = current_setting(''app.tenant_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))',
            table_name
        );
    END LOOP;
END $$;

-- Initial tenant (must match SCHEDULE_CREATOR_TENANT_ID, default 'cbljm').
-- Change the values here if you use a different tenant ID or business name.
INSERT INTO tenants (tenant_id, business_name)
VALUES ('cbljm', 'Celebration Brands Limited')
ON CONFLICT (tenant_id) DO NOTHING;

COMMIT;
