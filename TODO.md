# Tester TODOs

This checklist records integration and acceptance checks that still need tester
verification for the approved change requests. It is not a list of unimplemented
future roadmap features. Run PostgreSQL checks only against a disposable test
database, and do not use production employee or schedule data.

## Temporary LAN HTTP option (must be removed)

- [ ] **Remove the temporary plain-HTTP option for PostgreSQL.** It is enabled by
  `SCHEDULE_CREATOR_TEMPORARY_ALLOW_LAN_HTTP=1` in `Schedule Creator\.env`. It
  permits HTTP only from loopback/private-network clients (never with
  `X-Forwarded-For`) and drops the Secure cookie flag. Delete the setting,
  `ALLOW_LAN_HTTP` and `http_allowed_for_client` in `scheduler.py`, and
  `TemporaryLanHttpTests`; restore HTTPS before any shared or production use.

## Temporary MFA bypass (must be removed)

- [ ] **Remove the temporary authenticator bypass before any shared or
  production use.** It is enabled by `SCHEDULE_CREATOR_TEMPORARY_MFA_BYPASS=1`
  in `Schedule Creator\.env`, is ignored when PostgreSQL is configured, and lets
  a correct administrator password sign in without a code. Delete that setting,
  the `MFA_BYPASS` code in `scheduler.py`, and its test, then re-run the MFA checks
  below with the setting absent.

## Secure tenant identity foundation

The SQLite automated suite passed during implementation, but it does not exercise
PostgreSQL. Record the test environment, commands, results, and any logs with
secrets or personal data removed.

- [ ] **Start the app against PostgreSQL.**
  - Configure `SCHEDULE_CREATOR_DATABASE_URL`, a stable `FLASK_SECRET_KEY`, and
    a stable `SCHEDULE_CREATOR_MFA_ENCRYPTION_KEY` (each secret must be at least
    32 characters). Preserve the secrets between restarts; losing the MFA
    encryption key makes enrolled MFA secrets unreadable.
  - Use a dedicated PostgreSQL application role that is neither `SUPERUSER` nor
    `BYPASSRLS`; verify startup refuses a role that has either privilege.
  - Start the app and confirm schema initialization/migrations complete and the
    login page and authentication-state endpoint respond. Restart it and confirm
    the schema remains usable without losing stored data.

- [ ] **Verify tenant row-level security.**
  - In a disposable PostgreSQL database, create representative records in
    accepted schedules, employees, schedule locations, application settings,
    and audit events for two distinct tenant IDs.
  - Connect with the application role and set each tenant context in turn.
    Confirm a tenant can read and modify only its own rows; inserts or updates
    with another tenant ID must be rejected or remain invisible.
  - Repeat with no tenant context and with an unknown tenant ID. Confirm no
    tenant's records are exposed or writable.
  - Verify the policies are enabled and forced on every table listed in the
    application’s PostgreSQL setup. Save the SQL/results used to establish this.

- [ ] **Exercise the SQLite-to-PostgreSQL import.**
  - Make a copy of the current SQLite database and import that copy into a fresh,
    disposable PostgreSQL tenant using `python scheduler.py migrate-sqlite`.
    Confirm the command requires the exact `IMPORT` confirmation.
  - Compare source and destination counts and representative values for
    locations, employees, accepted schedules, settings, administrator records,
    developer change requests/dependencies, and audit events.
  - Confirm imported administrator accounts are required to enroll in MFA
    again, and that the source SQLite file is unchanged.
  - Run the import a second time and against a target with existing data.
    Confirm safeguards refuse both cases without partially changing target data.

- [ ] **Test administrator authentication and protected APIs on PostgreSQL.**
  - Bootstrap the first admin from a trusted shell with
    `python scheduler.py bootstrap-admin --email ... --name ...`; verify invalid
    and mismatched passwords are rejected and valid credentials provision only
    the intended account.
  - Sign in and complete mandatory TOTP enrollment. Verify login cannot finish
    without MFA, incorrect/expired codes fail, and a valid code opens the app.
  - Confirm unauthenticated requests cannot access protected business APIs;
    same-origin/CSRF checks reject invalid mutations; repeated failed logins are
    rate-limited; and successful admin mutations create audit events.
  - Sign out in the browser and verify the session is cleared and protected APIs
    again return an authentication-required response. Repeat after restarting
    the app to confirm configured secrets and MFA remain usable.

## Test evidence and handoff

- [ ] Record PostgreSQL version, test database setup, application role
  privileges, exact commands, test outcomes, and any failures. Redact database
  URLs, passwords, MFA codes/secrets, API keys, and personal data.
- [ ] Report any failed or blocked check with reproduction steps and sanitized
  logs. Do not mark the `tenant-identity` change request done until the
  PostgreSQL checks above pass and the implementation issues are resolved.
