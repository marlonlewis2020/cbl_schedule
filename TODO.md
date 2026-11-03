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

## Business registration and SaaS hub (`business-hub`)

Automated results: 44-test SQLite suite passes; PostgreSQL harness
(`pg_hub_verify.py` in the session `files` folder, run in a disposable schema that
was dropped afterwards) passed 28 of 28 checks: two businesses registered and
pending, pending business blocked from the scheduler API, platform-owner sign-in
with MFA enrolment and approval, approved businesses working, per-business encrypted
BambooHR keys, row-level isolation of settings between businesses, suspend and
reactivate affecting only that business, and invalid transitions refused.

The `business-hub` change request was confirmed by the user and marked `done`
in both PostgreSQL and the tracked SQLite database. These deployment checks
remain for production use:

- [x] Create the platform owner: `python scheduler.py bootstrap-platform-owner --email <email> --name "<name>"`, then sign in at `/hub` and enrol the authenticator.
- [x] First start-up copies `BAMBOOHR_API_KEY` from `.env` into the encrypted store for `cbljm`; confirm the default business still loads employees, then remove the key from `.env`.
- [x] Register a real business at `/hub` (live BambooHR credential check), sign in as its admin, see the pending page, approve it as the owner, and confirm the scheduler opens with no locations or employees.
- [x] As the business's primary admin, add and remove an administrator from Settings, Business administrators.
- [x] Suspend and reactivate a business in a real browser.
- [x] Not covered: browser UI of `hub.html` and `business-status.html`, and the BambooHR credential check against a real account (mocked in tests).
- The temporary MFA bypass also applies to the platform-owner sign-in; remove it with the item above.

### Business admin and domain-ownership follow-up

- Main admin only: add, edit, remove, and reset another admin's password or MFA. Password reset generates a replacement password shown only once to the main admin. Admin list details show name/email to signed-in business admins, while joined date and MFA state are main-admin-only.
- Each admin's profile is populated from their account name; the first-login profile/test popup was removed. Name and email can be updated from the profile button; changing email requires the current password. BambooHR key testing remains in Settings.
- BambooHR subdomains are normalized and unique across registered businesses; duplicate registration directs the applicant to contact the existing owner or platform owner. Platform owners can permanently delete a business and its tenant data, except the original `cbljm` tenant; the deletion event remains in the hub audit log.
- [x] Python test suite: 48 tests passed. Browser opened the updated HTML pages; APIs could not be exercised through the `file:` pages.
- [x] PostgreSQL validation of these follow-up changes is pending: the configured server at `192.168.100.70:5432` did not accept a TCP connection during this run. The earlier 28-check business-hub result predates these changes.

## Membership tiers and entitlements (`tier-entitlements`)

- [x] Apply the confirmed tier limits: Bronze (2 admin seats, 2 teams, 20
  active employees, 2 locations); Silver (3, 4, 60, 4); Gold (4, unlimited
  teams/employees, 6 locations); Platinum (8, unlimited).
- [x] Keep schedule generation, sharing, BambooHR publishing, email,
  employee management, and settings in all tiers. Gate employee schedule
  access, shift trades, and history at Silver+; overtime forecasting at Gold+.
- [x] Enforce quotas on admin, employee, team, and location additions. Allow
  downgrades to grandfather existing usage without automatic deactivation.
- [x] Add platform-owner tier assignment and show plan usage/features in
  `/hub`.
- [x] Full SQLite suite: 57 tests passed, including tier boundaries,
  tenant-scoped quota checks, downgrade behavior, feature flags, and owner
  assignment.
- [x] Unit-test startup forces SQLite, preventing fixtures from using the
  deployment PostgreSQL URL loaded from `.env`.
- [x] Verify the tier selector and feature gates in a real browser.
- [x] Validate PostgreSQL quota enforcement only in a disposable schema.

## Business admin membership controls (`business-membership-controls`)

- [x] Let only the main business administrator change the tier, pause/resume,
  or cancel membership from the business status page.
- [x] Require explicit confirmation, show immediate access/plan-limit effects,
  and explain that billing is not processed by this app.
- [x] Preserve business data on pause/cancellation; pause can be resumed by the
  main admin and cancellation restoration is reserved for the platform owner.
- [x] Audit the acting admin and prior/new tier or membership state.
- [x] SQLite lifecycle regression test covers primary-admin permissions,
  confirmation, access gating, retained data, and audit records.
- [x] Full SQLite test suite: 68 tests passed; the change-request tracker now
  marks this request complete.
- [x] Validate the new PostgreSQL column migration and row-level access path in
  a disposable schema. The configured PostgreSQL server was not available.

## Attendance automation (`attendance-automation`) — complete

- [x] Add tenant-scoped storage for BambooHR clock entries, shift statuses,
  correction history, and attendance-score overrides.
- [x] Sync BambooHR time-tracking and approved time-off data on app startup and
  every five minutes while the authenticated app tab is visible; no sync runs
  while the tab is hidden or closed.
- [x] Match clock entries to accepted shifts, classify late shifts and absences
  after four hours, exclude approved leave from scores, and audit reasoned admin
  corrections and score overrides.
- [x] Add attendance settings and a basic attendance/score view. The complete
  role-scoped workforce dashboards, manager notifications/actions, and employee
  dashboard remain tracked separately under `workforce-dashboards` and
  `manager-employee-access`.
- [x] Add location and role filters plus single-day or month-range reporting
  for recorded historical attendance. Summaries and attendance scores use the
  selected period; admins can sync a selected historical period from BambooHR
  (maximum 365 inclusive days).
- [x] Focused attendance/BambooHR/migration tests: 9 passed. Full SQLite suite:
  67 passed, including historical date and month-range queries.
- [x] Validate the configured API key and actual response shape against the
  configured BambooHR tenant using user-approved, read-only production access;
  no non-production tenant is available.
  - [x] Read-only live validation against the currently configured `cbljm`
    tenant on 2026-11-03: `time_tracking/timesheet_entries` returned 374
    records for 2026-10-26 through 2026-11-03; all 374 clock entries parsed.
    `time_off/whos_out` returned 93 records; all 93 leave entries parsed.
    The observed clock fields included `employeeId`, `date`, `start`, `end`,
    `timezone`, and `approved`; time-off fields included `employeeId`, `start`,
    and `end`. No employee values or credentials were displayed, and no
    records were persisted.
  - [x] Extended read-only validation over the maximum 365-day range
    (2025-11-04 through 2026-11-03): 6,743 clock entries and 2,688 leave
    entries parsed. The selected profile had 29 clock entries and 13 approved
    leave entries, but no accepted app shifts in that period.
  - [x] Exercised attendance matching in a disposable SQLite fixture with one
    real clock entry and a test-only accepted shift. It matched as attended
    with BambooHR as the source. The fixture and its pre-test backup were
    removed; no production app or BambooHR records were written.
- [x] Validate the new PostgreSQL schema, row-level security, and SQLite import
  in a disposable PostgreSQL schema. No attendance, schedule, or BambooHR
  records were written during live validation. Before completion, backed up all
  15 change-request rows and 20 dependencies, then marked this request `done`.

## Attendance shift-source selection and reconciliation (`attendance-shift-source-reconciliation`) — complete

- [x] Persist the selected attendance shift source per tenant. Attendance
  continues to use BambooHR clock events regardless of whether accepted app
  shifts or BambooHR shifts are selected for the schedule source.
- [x] Read paginated BambooHR scheduled shifts using the parameterized
  `start`, `end`, `employeeIds`, `statuses`, `page`, and `pageSize` contract
  supplied and confirmed by the user. Compare employee, date, start/end, and
  mapped location, and show unresolved discrepancies whenever BambooHR is
  selected.
- [x] Require CSRF protection, explicit confirmation, and a reason for either
  resolution direction. Re-read shifts and reject stale discrepancies before
  writing; prevent individual replacement of shared BambooHR shifts and reject
  unsupported app-schedule mappings/durations.
- [x] For app-to-BambooHR reconciliation, add the accepted shift and then
  delete the prior single-employee BambooHR shift using the confirmed
  `recurrenceEditOption=instance` contract. Report and audit partial outcomes;
  the two remote operations are not transactional.
- [x] For BambooHR-to-app reconciliation, update the accepted schedule and
  retain full before/after payloads in the tenant-scoped audit history.
- [x] Focused attendance tests cover source confirmation, read parsing and
  pagination, both resolution directions, and mocked partial BambooHR writes.
  No production schedule writes were made during implementation.

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
- [x] The `business-hub` change request is marked `done` (PostgreSQL and the
  tracked SQLite database). Production setup checks for the platform owner,
  BambooHR key migration, real business registration and browser flows remain
  listed in the section above.
