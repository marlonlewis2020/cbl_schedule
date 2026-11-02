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
  in `Schedule Creator\.env`, now applies to PostgreSQL as well as SQLite, and lets
  a correct administrator password sign in without a code. Delete that setting,
  the `MFA_BYPASS` code in `scheduler.py`, and its test, then re-run the MFA checks
  (the harness in the evidence section forces it off) with the setting absent.

## Secure tenant identity foundation

PostgreSQL checks have been run (see "Test evidence and handoff"). Items marked
done passed; the notes list what was not covered.

- [x] **Start the app against PostgreSQL.** *Passed.*
  - Configure `SCHEDULE_CREATOR_DATABASE_URL`, a stable `FLASK_SECRET_KEY`, and
    a stable `SCHEDULE_CREATOR_MFA_ENCRYPTION_KEY` (each secret must be at least
    32 characters). Preserve the secrets between restarts; losing the MFA
    encryption key makes enrolled MFA secrets unreadable.
  - Use a dedicated PostgreSQL application role that is neither `SUPERUSER` nor
    `BYPASSRLS`; verify startup refuses a role that has either privilege.
  - Start the app and confirm schema initialization/migrations complete and the
    login page and authentication-state endpoint respond. Restart it and confirm
    the schema remains usable without losing stored data.
  - Result: schema initialization is repeatable, stored data survived a process
    restart, the state endpoint and login page respond, and startup refuses
    a SUPERUSER or BYPASSRLS role. Role refusal was exercised by simulating the
    role flags, because no such role could be created on the server.

- [x] **Verify tenant row-level security.** *Passed.*
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
  - Result: with two tenants holding identical keys, each tenant read only its
    own rows in all five tables, updates to the other tenant's rows changed
    nothing, and inserts for another tenant were rejected. No tenant context and an
    unknown tenant saw no rows and could not write. RLS is enabled and forced,
    with one `tenant_isolation` policy, on all five tables.

- [x] **Exercise the SQLite-to-PostgreSQL import.** *Passed.*
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
  - Result: a copy of `data\schedule_creator.sqlite3` was imported into a
    disposable schema. A wrong confirmation cancelled with no changes. Locations,
    employees, accepted schedules, administrators and audit events matched the
    source counts; every source setting key and every change-request status was
    preserved; sample values matched. Imported admins have no MFA secret and must
    enroll again. A second import, an import into a target with an administrator,
    and an import into a target with an accepted schedule were all refused with no
    change to the target. The source copy's hash was unchanged.
  - Note: a freshly initialized database is seeded with 10 default schedule
    locations and 66 default employees before any import, and the import replaces
    them.

- [x] **Test administrator authentication and protected APIs on PostgreSQL.** *Passed, except the two manual items noted below.*
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
  - Result (run with the MFA bypass forced off): short passwords, bad emails
    and blank names were rejected, and only one account could be provisioned.
    Protected APIs returned 401 until sign-in completed. A missing CSRF token,
    wrong password, incorrect code and expired code were all rejected, and a valid
    code (including one typed with a space) signed in. A cross-origin mutation
    returned 403, an admin mutation wrote an audit event, and repeated failed
    logins returned 429. After logout the APIs returned 401 again. After a
    restart, the stored MFA secret decrypted and password plus a valid code signed
    in, while a password alone was refused.
  - **Not covered, still manual:** the mismatched-password prompt of
    `bootstrap-admin` (it reads the console, so it can't be scripted), and a
    sign-in and sign-out in a real browser. The checks above used Flask's test client.

## Test evidence and handoff

- [x] PostgreSQL 18.6, server on the local network. The tests ran in
  disposable schemas (`cbl_verify_*`, created and dropped by the run) in the
  `scheduler` database, using the app role, which is not a superuser, has no
  `BYPASSRLS`, `CREATEDB` or `CREATEROLE`, and can create schemas. Command:
  `python _pg_verify.py` (the harness is kept in the session `files` folder as
  `pg_verify.py`; copy it into `Schedule Creator` to re-run). Outcome: 114 checks,
  114 passed; no test schemas remain and the `public` tables were not touched.
  Secrets, URLs and codes are not recorded.
- [x] Failures found and fixed while getting here: the PostgreSQL adapter's
  `executemany` skipped SQL translation (`INSERT OR IGNORE` failed at startup), and
  the schedule-locations query had a `GROUP BY` PostgreSQL rejected (the Employees
  page returned 500). Both are fixed and the 33-test SQLite suite passes.
- [x] The `tenant-identity` change request is marked `done` (PostgreSQL and the
  tracked SQLite database). The temporary MFA bypass and LAN HTTP option (sections
  above) must still be removed before any shared or production use.
