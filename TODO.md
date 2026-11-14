# Tester TODOs

This checklist records integration and acceptance checks that still need tester
verification for the approved change requests. It is not a list of unimplemented
future roadmap features. Run PostgreSQL checks only against a disposable test
database, and do not use production employee or schedule data.

## Attendance snapshot actions - implemented, awaiting acceptance

- `attendance-snapshot-batch-deletion`: authorized admins select one or multiple
  snapshots and confirm atomic deletion of payloads/visible history. Preserve
  attendance/schedules, audit actor and IDs, block running/stale selections, and
  retain minimal run-key tombstones so scheduled cutoffs cannot regenerate.
- `attendance-snapshot-email-body`: executive subject, formatted preview and
  plain-text copy derived only from saved snapshot evidence. Include KPI
  highlights, location/role tables, follow-up call-outs and source warnings.
  Manual copying remains available when clipboard support is unavailable.
  Admins attach downloaded HTML themselves; no automatic sending.
- Previously downloaded/emailed copies cannot be revoked. Tenant/admin/tier
  authorization and CSRF are enforced server-side.

## Current walkthrough deferrals

User-directed on 2026-11-06: defer all outstanding PostgreSQL-related TODOs,
including migrations, imports, row-level security, permission/quota checks and
deployment acceptance. Keep them outstanding, not completed. Skip them during
the current one-by-one walkthrough, alongside the previously excluded HTTPS/
LAN-HTTP and PayPal TODOs. Completed PostgreSQL evidence remains unchanged.

## Temporary LAN HTTP option (must be removed)

- [ ] **Remove the temporary plain-HTTP option for PostgreSQL.** It is enabled by
  `SCHEDULE_CREATOR_TEMPORARY_ALLOW_LAN_HTTP=1` in `Schedule Creator\.env`. It
  permits HTTP only from loopback/private-network clients (never with
  `X-Forwarded-For`) and drops the Secure cookie flag. Delete the setting,
  `ALLOW_LAN_HTTP` and `http_allowed_for_client` in `scheduler.py`, and
  `TemporaryLanHttpTests`; restore HTTPS before any shared or production use.

## Temporary MFA bypass (removed)

- [x] **Remove the temporary authenticator bypass before any shared or
  production use.** Removed the runtime setting and bypass branches for
  business administrators, platform owners and managers. Unenrolled accounts
  must enroll before accessing protected pages; enrolled accounts require a
  valid authenticator code. The retired environment flag cannot enable bypass.
  Verified 47 targeted authentication/access/manual tests, including the retired
  environment flag being ignored and unchanged LAN HTTP behavior. No retired
  flag was present in the local `.env`. With user approval, incremented and
  verified auth versions for the configured SQLite database's administrator,
  platform owner and manager, revoking their existing sessions while preserving
  passwords, enrollment and other account fields. Employee sessions and
  schedules were not modified. Restart the app and worker to load the change.

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
  - **User-confirmed complete on 2026-11-06:** the mismatched-password prompt
    of `bootstrap-admin` and sign-in/sign-out in a real browser. The earlier
    automated checks above used Flask's test client; these remaining acceptance
    checks were confirmed by the user.

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
- Platform-owner sign-in requires MFA; the temporary bypass has been removed.

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

## Attendance setup and reports navigation (`attendance-page-setup-and-reports`) — implemented, awaiting acceptance

- [x] Group BambooHR attendance sync, shift source, filters and rules under
  Setup; group attendance snapshots and historical reports under Reports.
- [x] Preserve existing behavior, authorization, direct links, report history,
  report-script mount IDs, and always-visible attendance and score tables.
- [x] JavaScript syntax, editor diagnostics, whitespace validation, and the
  focused attendance-source regression test passed. The browser fixture could
  not start because its historical seed-metrics assertion fails before serving
  the page; no browser verification was completed.

## Source-specific attendance populations and history (`attendance-source-specific-populations-and-history`) — in progress

- Implemented: BambooHR mode fetches the provider's active employee directory
  independently of app active status and Employee #. Linked app-inactive people
  retain their app ID; unregistered BambooHR people use a namespaced provider
  ID and mapped Schedule Location metadata. App mode only includes currently
  active app employees.
- Implemented: clock events count regardless of BambooHR approval. Attendance
  and historical queries are source-filtered; syncing one source preserves the
  other source's rows. BambooHR-source local attendance/score overrides do not
  affect provider-source reports. Snapshots and historical HTML/XLSX identify
  the selected source. Existing confirmed, audited two-way shift reconciliation
  is unchanged.
- Verified: 27 attendance automation tests, 12 snapshot/report tests, and
  focused provider-only/app-inactive, source-switch retention, override
  exclusion, directory-fetch and snapshot-provenance checks pass.
- Still outstanding: BambooHR employment status is not retained as dated
  history, so a report cannot determine active status as of an arbitrary past
  date. BambooHR scheduled-shift API coverage for completed historical shifts
  also remains unverified; reports use only provider-source shifts previously
  captured and retained by the app. Do not silently substitute app schedules.
  The historical suite has two unrelated existing assertions failing: a
  429-versus-400 rate-limit expectation and a weekday/week-end date expectation.

## Attendance table manual clock actions (`attendance-manual-clock-actions`) — implemented, acceptance pending

- [x] Add audited, confirmed Clock in, Clock out, and Clock out at shift end
  actions. Enforce tenant-admin authorization, CSRF, employee mapping, leave
  state, existing open clocks, and unresolved-write protections server-side.
- [x] Clock out at shift end is unavailable until the scheduled end has passed
  in Jamaica time, then writes that shift's scheduled date and end time to the
  BambooHR clock-out endpoint. Require the open entry to belong to that shift;
  reject stale clocks from prior shifts.
- [x] Mocked attendance suite: 22 tests passed, including duplicate/unknown
  writes, authorization, shift-end timing, current-time clock-out, and stale
  prior-shift entries. JavaScript syntax and diff whitespace checks passed.
- [x] Disposable PostgreSQL schema on the local port-5433 clone: startup
  migrated an old `attendance_shift_records` table with `shift_end_at`, created
  the clock-action audit table and unresolved-claim index, and forced its RLS
  policy. Tenant reads were isolated, no-context reads were empty, and a
  cross-tenant insert was rejected. The temporary schema was dropped; existing
  clone schemas and data were not modified.
- [ ] Live BambooHR clock-event writes and real-browser acceptance remain
  unverified. No remote clock events were created during implementation.

## Manager and employee access (`manager-employee-access`) — complete

- [x] Admins create manager and employee accounts in Settings → Manager &
  employee access. A one-time temporary password (72-hour expiry) is shown to
  the admin; the user must replace it at first sign-in at `/access`. Admins can
  reset passwords (optionally MFA) and disable/enable accounts, which ends the
  account's sessions.
- [x] Sign in with BambooHR subdomain plus email or employee ID and password.
  Managers require MFA, enrolled at first sign-in; employees have no
  MFA.
- [x] Managers see attendance only for employees at schedule locations whose
  manager email matches theirs, and can mark a late shift absent with a reason
  (audited). Employees see only their own attendance. Employee accounts require
  the `employeeScheduleAccess` tier feature (Silver and above).
- [x] In-app notifications (bell with unread count, 30-second polling) are
  created once per late/absent transition, scoped per manager; admins have a
  bell covering the whole business. No email or push delivery.
- [x] Focused tests: `ManagerEmployeeAccessTests` (SQLite). User sessions are
  rejected from admin APIs.
- [x] Apply missing PostgreSQL tables `tenant_users`, `attendance_notifications`,
  and `attendance_notification_reads`, archive support and related attendance
  columns. Schema and notification RLS checks passed on 2026-11-04; synthetic
  verification writes were rolled back.
- [x] User verified manager sign-in, forced password change and MFA on
  2026-11-04.
- [x] User verified managers are restricted to assigned teams on 2026-11-04.
- [x] User verified notification reading and archiving are per user on
  2026-11-04.
- [x] User confirmed account disabling and session revocation checks passed
  on 2026-11-04.
- [x] User confirmed attendance actions and audit history checks passed
  on 2026-11-04.
- [x] Marked the request `done` in SQLite and PostgreSQL after the user
  confirmed all remaining checks passed on 2026-11-04. Also aligned PostgreSQL's
  stale `tier-entitlements` status to `done`, matching its completed checklist
  and SQLite status, before completing the dependent request.
- [x] The SQLite→PostgreSQL import does not copy the three new tables (they
  have no legacy data).

## Schedule portal (`schedule-portal`) — complete

- [x] Add tenant-scoped encrypted six-digit codes, unique across stored codes,
  per schedule location/role/period; expire at the period end in Jamaica time.
- [x] Add admin visibility settings (1–52 weeks, default current week plus three
  upcoming weeks) and accepted-schedule projection without workbook metadata.
- [x] Require individual employee sign-in, current location/role, actual period
  assignment and a valid code; throttle incorrect codes. Managers see all their
  assigned locations without codes.
- [x] Add `/access` schedule tables and a read-only, role/location-scoped
  employee team attendance summary; preserve the own-attendance view.
- [x] Add portal codes and expiry to opted-in manager confirmation drafts.
  Generated-only review emails remain supported without portal codes.
- [x] Full SQLite regression suite passed (94 tests); final focused access and
  manual checks passed (17 tests), including an additional shared-role isolation
  test. Editor diagnostics and Python/JavaScript syntax validation passed.
- [x] Applied `schedule_portal_codes` in PostgreSQL and SQLite. Verified
  PostgreSQL columns, indexes, unique code hashes and forced tenant RLS with
  own-tenant visibility, cross-tenant/no-context isolation and write rejection;
  all synthetic verification writes were rolled back.
- [x] Browser fixture checks verified employee code-entry flow, overnight
  next-day shift labels, refresh clearing, team counts and accepted-schedule
  codes/CSRF in manager email drafts. These are not live account acceptance tests.
- [x] User verified real-browser schedule access, codes in email drafts, expiry,
  role reassignment, visibility changes and next-day shift end times on 2026-11-04.
- [x] Marked `schedule-portal` done in SQLite and PostgreSQL after user acceptance
  on 2026-11-04; persisted statuses verified.

## Manager personal shifts (`manager-employee-dual-access`)

Implemented on 2026-11-05; user-confirmed live acceptance complete on
2026-11-06 for switching My shifts/Manage teams, personal-shift visibility
without expanded management access, retained MFA/access restrictions,
administrator-only self-attendance corrections, and access revocation after
reassignment or disabling. PostgreSQL verification remains deferred. Depends on
`manager-employee-access` and `schedule-portal`.

- Link a scheduled manager's account to their verified, same-business employee
  record; use one identity with **My shifts** and **Manage teams** views.
- Retain manager MFA in both views. Show own shifts and attendance by employee
  ID, including shifts at locations the manager does not manage.
- Preserve employee tier, team-code, assignment and visibility requirements.
  Personal assignments must not expand management permissions.
- Require an administrator for corrections to the manager's own attendance.
  Audit changes; explicitly resolve existing-account conflicts and revoke stale
  access after link/account changes.
- Test both views, out-of-scope personal shifts, self-correction rejection,
  MFA, tiers, reassignment and disabling.

## Current four-request batch: trades, publishing and sandbox billing

Implemented on 2026-11-05. Do not mark the requests accepted until live checks
below pass. All BambooHR/payment write validation uses mocks; no production
shifts or live payment endpoints were used.

- [x] Add authenticated trade records, participant confirmation, scoped manager
  acceptance, admin approval/rejection, withdrawal, per-reader unread inbox
  updates, and timestamped audit history.
- [x] Replace workspace-only trade confirmation with the server inbox; add
  accepted-schedule indicators and synchronize applied trades into workspace
  schedules when accepted copies load.
- [x] Add stale/version/assignment guards, non-admin past-shift blocking,
  scheduling-constraint checks and reasoned admin shift/day-off overrides.
- [x] Restore Shift trade as a shared modal with scoped location/team, period
  and employee dropdowns; lock employee 1 in personal mode and validate all
  selected checkbox days together, including balanced multi-day swaps.
- [x] Persist per-employee rest warnings and acknowledgements; enforce both
  affected employees' consent, including manager/admin proposals. Reject
  overlaps, other hard constraints and stale warnings. Publish/reconcile all
  selected dates, preserving legacy single-day/manual records.
- [x] Add explicit personal schedule selection and code-driven team selection,
  retaining identity scope, expiry and guessing lockout.
- [x] Align access and hub palette, headers, cards and responsive controls with
  the administrator application.
- [x] Restore the pre-redesign access/hub/inbox appearance at user request;
  scope shared styles to the trade popup so administrator light/dark colours
  remain unchanged. Retain the redesigned trade and schedule-selection flows.
  Verified 10 light/dark isolation checks, 16 trade modal checks, and original
  computed appearance on access, hub and inbox. Manual regeneration/test passed.
- [x] Subsequent trade redesign: themed cards and before/after shift previews;
  enforce at least five shifts per employee in the selected week. Treat other
  scheduling violations as warnings and require both employees, manager and
  admin to acknowledge exception trades. Preserve manual-override behaviour,
  tenant/team authorization, stale/version and pending-intersection safeguards.
  Validation: 125 Python regressions and 28 focused tests passed; the final
  warning-detail changes passed all 19 trade tests. Browser fixtures passed
  10 theme, 17 modal, 2 admin-entry and 13 inbox/consent checks. At 390px,
  both themes had no horizontal overflow and retained readable card colours.
  Rebuilt manuals, verified Python syntax and diff whitespace, and persisted
  the trade-policy migration with repeated local database initialization.
- [x] Verify the five-shift trade minimum and all exception acknowledgements
  with real employee/manager/admin sessions before marking trade requests done.
  User verified on 2026-11-05: below-five submission blocked; Employee 1
  required warning acknowledgement to submit; Employee 2 and manager cancelling
  warning consent preserved pending status, then acknowledged acceptance
  advanced to manager/admin review respectively. Admin notification opened
  the selected request within the admin site; cancelling preserved status,
  acknowledged approval made it ready to apply, and accepted shifts remained
  unchanged. Application/publishing and other trade acceptance items remain
  separate and unverified by this walkthrough.
- [x] Collapse inbox requests by default, showing week, actual initiator,
  status and unread indicator. Expanded requests retain role-appropriate
  accept/reject/withdraw controls, warnings and history; opening is not consent
  or a read acknowledgement. Rename the read action to Mark as read.
  Verified 21 Python tests (including manager/admin inbox progression), 25
  browser inbox checks and 8 mobile keyboard/overflow checks across both themes.
  Rebuilt the HTML/DOCX manuals.
- [x] Redesign validation: 121 Python regressions passed; 16 modal, 2 admin
  entry, 2 recipient consent, 7 access selection/mobile and 3 hub style/tab
  browser checks passed, along with 18 roster and 10 email checks. Five affected
  scripts parsed; Python syntax and tracked diff whitespace checks passed.
  Rebuilt HTML/DOCX manuals and verified repeated local schema initialization.
- [x] Verify the redesigned modal and both rest acknowledgement flows with real
  employee/linked-manager sessions; accept the UI and schedule/code selection.
  User verified on 2026-11-05: linked-manager personal mode fixed Employee 1
  to the linked employee and scoped trade choices to their personal assignment.
  Personal schedule selection and a valid team code worked; an incorrect code
  was rejected and management locations remained correctly scoped. A
  rest-warning trade required acknowledgement by the linked-manager initiator
  and the other employee before acceptance. No application/publishing was
  included in this check.
- [x] Add app-only / BambooHR preview and explicit application, durable
  operation journals, single-employee remote changes, partial-failure states,
  safe retries and read-only unknown-outcome reconciliation.
- [x] Add disabled-by-default sandbox hosted subscriptions, owner USD prices
  and feature settings, verified/deduplicated webhooks, manual credits, in-app
  reminders, daily seven-attempt ceiling, suspension/restoration, and a separate
  worker with heartbeat and retry claims.
- [x] Improve billing navigation and setup guidance; replace JSON feature entry
  with default/enabled/disabled dropdowns, group tier prices, add business and
  Jamaica date/time selectors, and show readable subscription details/history.
  Backend regressions passed (23 workforce/billing tests plus new feature
  metadata/override coverage); 14 billing browser form/status checks passed.
- [x] Preserve access identities, notification reader state, trade journals and
  billing records through the single-business SQLite importer. Revoke imported
  user sessions and disable destination billing; never run both source and
  destination workers. Import SQL is tested on a SQLite-backed harness, not a
  live PostgreSQL connection.
- [x] Full SQLite regression run: 113 tests passed. Browser regression fixtures:
  18 roster and 10 email checks passed; all six affected JavaScript/HTML scripts
  parsed successfully. Linked-manager switching/revoked sessions, trade preview
  and owner billing controls passed browser fixture checks.
- [x] Final targeted workflow run: 17 tests passed, including unknown remote
  results, safe reconciliation, partial-failure retries and import persistence.
  Repeated initialization preserved request statuses and disabled sandbox billing.
- Tracker: shift trades and trade publishing are now `done`; roster/META
  acceptance and recurring billing remain `in_progress` pending
  browser/PostgreSQL and provider/worker checks respectively.
- [x] Verify linked managers and both trade roles in real authenticated browser
  sessions; verify team restrictions, link disable/reassignment and own
  attendance correction rejection with MFA enabled.
- [x] Verify employee -> employee -> manager -> admin workflow, unread updates,
  cancellation/rejection, applied schedule/export/email data and manual overrides.
  User verified on 2026-11-05: full consent/approval progression (above);
  trade update stayed read without changing pending approval or clearing other
  attendance alerts; recipient rejection persisted for both users with a reason,
  no warning acceptance and no schedule change. App-only application changed
  only selected shifts, preserved at least five shifts each and prevented
  repeat application. Export and email schedule/preview reflected the applied
  swap. Initiator withdrawal persisted for both users with its reason,
  prevented recipient acceptance and left the schedule unchanged.
  The previously deferred manual-override check was authorized on 2026-11-06.
  Two isolated authenticated Flask tests passed: manual day-off application
  and audit, plus explicit constraint-override gating. No live browser session
  was used for this check.
- [x] In a test BambooHR environment, verify read permissions, single-employee
  writes, partial failures, unknown results, duplicates and reconciliation.
  Production writes require separate authorization.
  User confirmed dedicated test-account/employee/schedule mappings and a
  successful read-only preview with correct dates/times and no remote changes.
  Subsequent preview reported an integer-conversion error for a UUID schedule
  ID. Fixed trade payload construction to preserve nonnumeric BambooHR IDs;
  numeric IDs retain their existing representation. All 22 trade tests passed,
  including UUID preview (no writes) and mocked application. Live publishing
  remains unverified; restart and repeat the test-account preview first.
  Subsequent user application journal recorded the first POST failed with
  BambooHR HTTP 422; remaining DELETE/POST/DELETE operations stayed pending,
  with no recorded successful remote operations. Provider response details
  were discarded by the HTTP helper. Updated diagnostics to retain a bounded
  error response and show failed operation errors in the trade card/API.
  All 23 trade tests passed. The underlying provider validation cause remains
  identified by the user's test-account retry as overlap with existing remote
  shifts. Fixed replacement ordering: remove original shifts before creating
  replacements, including older saved retry plans. Completed operations remain
  skipped; unknown outcomes still require reconciliation; removal failures
  stop creation. Preview/retry warnings explain nontransactional recovery.
  Verified 26 trade/manual tests, including simulated overlap enforcement and
  old-plan recovery, and rebuilt manuals. No automated remote writes occurred;
  User confirmed the dedicated-test-account retry worked on 2026-11-05.
  User also verified Published status, matching app/BambooHR shifts, original
  assignments removed, no duplicates and unchanged unrelated records.
  At the user's request, recovery acceptance was completed separately with
  mocked BambooHR in isolated temporary SQLite databases using authenticated
  Flask clients, not live fault injection. Six targeted tests passed with
  external HTTP access explicitly blocked: partial-failure retry skipped
  successes; old overlap-failed plans removed originals before replacement;
  deletion failure stopped creation; multi-day reconciliation covered the full
  range; unknown writes blocked retry until read-only reconciliation; existing
  writes were not repeated; duplicate matches blocked recovery; absent writes
  required separate confirmed retry. Completion combines user-verified live
  test-account publishing with isolated mocked recovery, not live failure tests
  or production/PostgreSQL certification.
- [x] Configure PayPal sandbox credentials/webhook and all eight USD prices
  privately. Verified the registered webhook URL and event subscriptions,
  prepared and read back 16 active plans (eight single-period and eight
  auto-renewing), verified the worker heartbeat and enabled sandbox billing.
  Completed 2026-11-09. Live payments remain unsupported.
- [x] Hosted monthly checkout without auto-renew: user approved a USD 35 Bronze
  sandbox payment for CBL. PayPal verified the checkout association, amount,
  currency and zero outstanding balance. One cycle completed with no remaining
  cycles; provider status EXPIRED is expected for this single-period plan.
  At completion, app access was active through 2026-12-09 23:03:47
  America/Jamaica; later checkout tests may extend this date.
- [x] Receive and verify a real signed PAYMENT.SALE.COMPLETED webhook through
  the restricted HTTPS relay. The application recorded webhook verification
  and payment reconciliation, applied Bronze and recorded the paid-through
  date. No real money was charged.
- [x] Replay the same signed PayPal event and verify duplicate acknowledgement
  without another payment reconciliation, access extension or membership change.
  Verified 2026-11-09: PayPal accepted a resend of the already-applied payment
  event; the HTTPS relay received it at 23:10:29 Jamaica and returned HTTP 200.
  The complete billing/membership/receipt fingerprint stayed unchanged, with
  two applied receipts, one payment reconciliation and the same paid-through
  date. The isolated duplicate-response/manual-pause regression also passed
  with external HTTP blocked; that mocked test is separate from the real resend.
- [x] Reject missing, invalid and tampered webhook signatures without changing
  billing/access state; preserve original-body signature verification.
  Verified 2026-11-09 through the real public HTTPS endpoint: captured one
  genuine PayPal redelivery in memory and observed HTTP 200 with duplicate=true.
  Removing signature headers, changing the signature bytes and changing the
  payment amount while retaining the genuine signature each returned HTTP 400.
  The full billing/membership/receipt fingerprint stayed unchanged. Payloads
  and signature headers were not printed or saved; the normal relay was restored.
- [x] Hosted annual checkout without auto-renew: verify annual USD amount,
  one-cycle completion and the annual paid-through date.
  Verified 2026-11-09: user completed Bronze annual sandbox checkout; PayPal
  verified USD 400, zero outstanding balance, the matching business checkout
  and an annual plan with exactly one completed cycle and none remaining.
  The signed PAYMENT.SALE.COMPLETED webhook and payment reconciliation were
  recorded. Provider/app status EXPIRED is expected after the single cycle;
  membership and billing access remain active, auto-renew is off, and the
  paid-through date matches 2027-11-09 23:18:31 America/Jamaica. This does not
  establish recurring annual collection or renewal behavior.
- [x] Hosted monthly auto-renew checkout: verify first payment, ACTIVE provider
  status, renewal consent and next billing date. Distinguish plan scheduling
  from an actually observed subsequent recurring collection.
  Verified 2026-11-09: user approved Bronze monthly auto-renew; PayPal verified
  USD 35, zero outstanding balance, the matching checkout and a MONTH plan with
  unlimited cycles. Provider/app status is ACTIVE, with one cycle completed and
  the next billing date 2026-12-09 05:00 America/Jamaica. Signed payment and
  activation webhooks were recorded. Prior annual paid access was preserved
  through 2027-11-09 23:18:31 America/Jamaica. A subsequent recurring payment
  has not been observed.
- [x] Hosted annual auto-renew checkout: verify first payment, annual price,
  renewal consent and next billing date. A later real annual collection cannot
  be claimed merely from inspecting the plan or first payment.
  Verified 2026-11-09: user approved Bronze annual auto-renew; PayPal verified
  USD 400, zero outstanding balance, the matching checkout and a YEAR plan with
  unlimited cycles. Provider/app status is ACTIVE, with one cycle completed and
  next billing date 2027-11-09 05:00 America/Jamaica. Signed activation/payment
  webhooks and payment reconciliation were recorded; CBL remains Bronze/active
  with paid access through 2027-11-09 23:25:20 America/Jamaica. This verifies
  initial checkout and scheduling, not a subsequent real annual collection.
- [ ] Observe a subsequent real recurring collection separately from initial
  checkout and plan scheduling. Keep this outstanding if the test subscription
  is cancelled before renewal; do not claim a future monthly/annual charge was
  verified from its next billing date or from mocked worker tests.
- [x] Cancel an active sandbox subscription and verify provider/app status,
  preserved paid access/history and no unintended refund or membership change.
  Verified 2026-11-09: cancelled the active Bronze monthly auto-renew sandbox
  subscription through the authenticated business UI with user approval.
  PayPal and the app both report CANCELLED; retries are cancelled with no next
  retry. CBL remains Bronze/active with paid access through 2027-11-09 23:18:31
  America/Jamaica, the original last-payment value and all three reconciled
  payments unchanged. The cancellation audit is recorded; no refund was requested.
- [x] Verify business pause/resume against a sandbox subscription,
  preserving separate membership restrictions and billing access rules.
  Verified 2026-11-09 with user approval and the primary administrator's
  authenticated browser: pausing CBL set membership to paused and provider/app
  subscription status to SUSPENDED; the scheduling API returned HTTP 403 while
  membership controls remained available. Resume restored membership and
  provider/app status to ACTIVE and scheduling returned HTTP 200. Bronze tier,
  all four reconciled payments and paid access through 2027-11-09 23:25:20
  America/Jamaica were preserved. Provider and membership audit entries exist
  for both actions. This live check used the primary-admin role; broader
  billing-suspension role coverage remains in the recovery acceptance item.
- [x] Verify business membership cancellation against an active sandbox
  subscription, retained data/prepaid dates, blocked scheduling and explicit
  platform-owner restoration. Restoring app membership must not reactivate
  the cancelled PayPal subscription or issue a refund.
  Verified 2026-11-09: user approved cancelling CBL and restoring through
  owner login. Primary-admin cancellation set app/provider subscription status
  to CANCELLED and membership to cancelled; scheduling returned HTTP 403 and a
  primary-admin resume attempt was rejected with HTTP 409. Counts for employees,
  locations, accepted schedules, attendance entries/records, settings and admins
  were unchanged, as was the complete payment-history fingerprint. Bronze tier,
  four reconciled payments and the 2027-11-09 23:25:20 America/Jamaica prepaid
  date were retained; retries stopped and cancellation was audited. After the
  user signed in as platform owner, the authenticated owner UI restored app
  membership to active. Owner status confirmed an active business/membership
  with no billing suspension; PayPal and the app still reported CANCELLED and
  provider retries remained stopped. The same record counts, payment-history
  fingerprint, Bronze tier and prepaid date were preserved, with an owner
  restoration audit. No refund was requested. Restoration eligibility was
  checked through owner status and persisted state; a fresh primary-admin
  scheduling request was not part of this owner-only restoration check.
- [x] Verify owner manual credit, reason and audit; paid-through extension must
  not settle PayPal balances or reverse business/member suspension.
  Verified 2026-11-09: user approved an owner-UI test credit extending CBL to
  2027-11-10 23:26:00 America/Jamaica. Billing and owner audits retained the
  explicit sandbox reason; membership/tier and the complete four-payment
  history were unchanged. PayPal/app subscription remained CANCELLED, app retry
  state became manual with no next retry, and no provider payment/refund was
  requested. Separately, the strengthened disposable-data regression passed
  with external HTTP blocked: an empty reason was rejected; credit restored
  billing access without changing paused membership or suspended business
  status, scheduling stayed HTTP 403, provider subscription state was untouched,
  and both audit records were preserved. Mocked suspension evidence is not a
  live PayPal declined-payment test.
- [x] Verify isolated declined-payment handling, reminders, daily retry timing,
  seven-attempt ceiling, suspension, unknown-outcome recovery and restoration.
  Verified 2026-11-09 in disposable SQLite data with external billing HTTP
  blocked: non-due retries did not run; definitive declines scheduled the next
  attempt 86400 seconds later; the seventh attempt exhausted retries and
  suspended billing access. Unknown capture outcomes stopped further attempts;
  authoritative paid-state reconciliation restored access without another
  capture. Initial outstanding balances generated one reminder without an
  immediate charge; a due, verified retry restored access and recorded audit.
  Primary-admin, manager (including normal MFA enrollment/login) and employee
  workflows each returned HTTP 200 before suspension, HTTP 403 while suspended,
  and HTTP 200 after verified restoration. Provider failures were simulated;
  the working CBL business and its real sandbox subscription were not modified.
- [ ] Verify a deliberately declined payment against PayPal's real sandbox
  negative-testing facilities using a controlled test subscription. The isolated
  decline/retry tests above do not establish actual provider decline behavior;
  do not force failures against the working CBL business without fresh approval.
- [x] Verify isolated unknown-checkout recovery and duplicate-checkout prevention
  without repeated subscriptions; preserve the opaque checkout association.
  Verified 2026-11-09 with mocked provider reads and blocked external billing
  HTTP: wrong tenant, checkout and plan associations were rejected; a matching
  unknown checkout was recovered exactly once with routing and both audits.
  A repeated recovery and new checkout attempts against active or unresolved
  accounts were rejected without provider mutations. The owner guard was
  stubbed in the recovery test; actual owner authorization was exercised in the
  separately recorded live configuration, credit and membership tests. No real
  PayPal outage or ambiguous remote checkout was induced.
- [ ] Install the worker under an always-on supervisor; verify restart/crash
  handling, heartbeat, single-instance claims, missed webhook polling, seven
  attempts and suspended membership access across all user roles.
  Read-only check on 2026-11-05 found no matching local worker process, Windows
  service or scheduled task by worker script/name. The configured local SQLite
  database had no billing worker heartbeat. No processes/settings were changed;
  another machine or a generically named wrapper was not ruled out.
  Verification was authorized on 2026-11-06, but at that time the environment had
  no PayPal sandbox client ID, client secret or webhook ID, billing is disabled,
  no plans are configured, and no worker heartbeat exists. The sandbox denied
  Windows process/service/task inspection. No external provider calls or
  service installation were made. Update 2026-11-09: a foreground worker is now
  running with a verified healthy heartbeat; credentials, plans, sandbox billing
  and a real sandbox payment/webhook have been verified as recorded above.
  Always-on supervision and the remaining recovery checks are still outstanding.
  Update 2026-11-09, isolated worker coverage: missed-webhook polling recovered
  an authoritative paid subscription without creating a payment or receipt,
  recorded one reconciliation and throttled the next poll by 600 seconds. A
  valid in-progress lease was not stolen; an expired in-progress claim became
  unknown once without repeating a read/capture. Provider read failures did not
  count as charge attempts. All 17 billing/relay regressions passed with external
  billing HTTP blocked. These checks cover app recovery logic, not Windows
  boot/logon execution, process-crash restart or a supervised service install.
  Supervision preparation 2026-11-09: added rotating 1 MB logs with three backups
  and a nonblocking filelock guard for one worker per installation. Four isolated
  lifecycle tests passed: normal startup/lock release, duplicate worker rejection,
  exceptional exit/lock release and app-context sweeps at the existing interval.
  The foreground worker was restarted with the new lock/logging and recorded a
  successful sweep. Added a least-privilege S4U Scheduled Task installer with
  boot/logon triggers, IgnoreNew instances and three one-minute failure restarts.
  PowerShell syntax/dependency probes passed, but Windows denied registration
  with Access is denied in this non-elevated session. No task exists; no elevation
  or registration workaround was attempted. User must run the installer in an
  elevated PowerShell window before scheduled start/crash/boot tests can proceed.
- [x] Apply/verify PostgreSQL startup or reference-schema migrations and forced
  tenant RLS for trade/billing tables in a disposable schema. The VS Code
  database connection was unavailable during this batch; no live migration
  success is claimed. The opaque subscription index is deliberately global
  for pre-tenant webhook routing.
  Read-only readiness check on 2026-11-05: this shell's app configuration
  selected SQLite, not PostgreSQL; psycopg was installed, but FLASK_SECRET_KEY
  and SCHEDULE_CREATOR_MFA_ENCRYPTION_KEY were not set in the loaded environment.
  No PostgreSQL connection, schema creation or migration was attempted. This
  does not establish the configuration of an app launched elsewhere.
  Completed on 2026-11-05 after the user corrected test-server access:
  71 checks passed in a uniquely named disposable schema using a restricted
  non-SUPERUSER/non-BYPASSRLS role. Verified current startup, repeat startup,
  legacy trade columns and billing plan-ID migrations with records preserved,
  forced RLS on all six tenant-scoped trade/billing tables, two-tenant read/
  update/insert isolation and missing/empty/unknown tenant-context reads.
  The opaque global webhook index remained separate. The schema was removed
  and the database user-table inventory returned to its original empty state.
  No normal app configuration changes, production migrations or provider calls.
  Harness: session files/pg_trade_billing_verify.py (private config separate).

## Implemented, awaiting user acceptance: saved schedule register (`saved-schedule-register-management`)

Recorded on 2026-11-04. Browser-workspace-only scope approved and implemented;
developer request remains in progress pending real-browser user acceptance.
Depends on `tenant-identity`.

- Allow administrators to delete schedules directly from the Saved schedule
  register, with confirmation, persistent deletion and consistent selection,
  filter, count and export/email updates.
- Explicitly distinguish workspace deletion from accepted database schedules
  and BambooHR-published shifts; do not silently delete accepted or remote data.
  Preserve unrelated schedules and audit history; report failures clearly.
- Limit the scrollable table viewport to at most six record rows plus its
  visible header, without excess empty space for shorter lists.
- Verify keyboard scrolling, variable row heights, deletion cancellation,
  persistence after reload and administrator-only access.
- Implemented strict IndexedDB deletion with online tenant/administrator/CSRF
  authorization, separate authorization/completion audit records, preserved
  accepted/provider copies, selection/filter refresh and stale email/undo
  invalidation. Six variable-height rows plus sticky header are shown.
- Automated checks cover cancellation, authorization/storage failures, reload
  persistence, final-record deletion, desktop/mobile light/dark presentation
  and access/manual regressions: 28 Python tests, 68 browser fixture checks
  and a real PageDown keyboard-scroll check passed. The deletion endpoint
  also preserved an existing accepted record byte-for-byte in an isolated test.
  Real-browser user acceptance remains.

## Attendance snapshots (`snapshot-email-reports`) - implemented, awaiting acceptance

Download-only scope implemented. Automatic email, recipient management and delivery
retries remain explicitly deferred until an authenticated sender is configured.
The `workforce-dashboards` acceptance prerequisite remains unchanged.

- Generate daily snapshots at **7 AM, 3 PM and 11 PM (Jamaica time)** and on
  demand from Attendance; save timestamped history for authorised downloads.
- Produce styled XLSX files and HTML email summaries similar to the supplied
  Oct 27 snapshot, with location/role/shift summaries and employee exceptions.
  Highlight late names in amber and absent names in red, with status labels.
- Support downloads, optional email distribution, or both. Automatic sending
  requires an authenticated sending integration; the current mail-client drafts
  do not send unattended or attach files automatically.
- Run independently of browser visibility; preserve attendance cutoff, leave,
  overnight and worked-time rules, show data freshness/failures, prevent duplicate
  generation/delivery, and enforce recipient scope and report-tier entitlements.

Implementation: Attendance now has Capture now, a timestamped history and immutable
XLSX downloads (Silver+). Primary administrators can opt into the three daily
captures; run `Schedule Creator\Run Attendance Reports Worker.bat` independently
of Flask, under a supervisor for continuous service. The workbook contains blue
summary headings, location/role/shift counts and employee attendance details,
with late names amber and absent names red. Captures include the reporting day's
shifts so far and verified overnight carry-in. Scheduled runs use an exact Jamaica
cutoff, unique tenant/run keys and explicit stale/failed/missed states. Cutoffs
missed by more than two minutes are recorded, not reconstructed from later data.
Worker heartbeat and BambooHR freshness failures remain visible. This does not
implement staffing-vs-demand interval analytics (Gold/Platinum).

## Interactive HTML attendance snapshot (`interactive-attendance-snapshot`) - implemented, awaiting acceptance

- Added View HTML and Download HTML alongside existing Silver+ XLSX downloads.
- Self-contained offline dashboard follows the supplied references: executive
  KPI cards, location/role/shift SVG charts and summary tables, followed by
  employee exceptions and evidence-based operational attention.
- Coordinated location/role/shift/status/search filters, chart drill-down,
  sortable employee details, responsive layout and Print / Save PDF.
- Each new capture embeds the business's saved company logo and name. Later
  branding changes do not alter captured HTML; older snapshots never borrow
  current branding or provider evidence retrospectively.
- Confirmed attendance separates matching punches from worked-time validation.
  Preserve four-hour absence rules, leave exclusion, overnight carry-in and
  source warnings; unavailable rates show N/A. No invented demand scores/trends.
- Retain tenant/administrator/tier authorization and existing XLSX compatibility.
  Downloaded employee information must be shared responsibly; offline copies
  cannot be revoked. Automatic email remains deferred.
- Depends on `snapshot-email-reports`; prerequisite and acceptance statuses
  remain unchanged.
- Validation: 29 Python report/register regressions and 74 interactive browser
  checks passed, including standalone HTML without network requests. Desktop/
  mobile layouts, print scope, empty/stale/legacy evidence and inert malicious
  names were checked. Real-business user acceptance remains.

## Planned requests accepted on 2026-11-05

### Account role correction implemented on 2026-11-05

- [x] Add Settings account Change role between Employee and Manager, retaining
  the existing disable option rather than adding account deletion. Preserve
  account identity, password, name, history and active state. Require valid
  manager email/active employee links, reject duplicate or stale edits, revoke
  sessions, retain MFA enrollment and enforce manager MFA/location scope and
  employee-access membership checks. Audit the old/new role and administrator.
  Verified 43 access/trade/manual Python tests, 10 browser dialog checks and
  390px light/dark layout without horizontal overflow; editor checks passed.
  Rebuilt manuals. Live PostgreSQL validation remains outstanding.

- [x] Show manager-accepted trades pending administrator approval in the admin
  notification bell, alongside attendance alerts. Click opens a same-origin
  trade window within the admin site with the selected request expanded and
  the admin theme, even if an employee session also exists. Viewing/Mark all
  read uses existing per-reader/version read tracking, never approval or warning
  consent. Pending requests remain visible until resolved. Refresh every 30
  visible seconds and on window close; surface notification polling failures.
  Verified 44 Python tests, 12 notification and 25 inbox browser checks, and
  embedded admin selection/theme/mobile width with fixtures. Rebuilt manuals.

### Pending navigation and session requests

Requests below remain pending unless implementation evidence is explicitly noted.

- **Consistent Access, Hub and Business navigation and alerts**
  (`site-navigation-alerts`): give each site its own menu and top alerts icon.
  Align all three sites' layout/design with the admin hub and retain app
  branding, light/dark themes, existing functionality and responsive layouts.
  Place shift trades under Access, preserving administrator approval/publishing
  and employee/manager scopes. Alerts and navigation must remain authorized,
  site-specific and tenant-scoped, with accessible unread/read controls.
  Verify all sites, roles, keyboard/mobile navigation and both themes.
  Approved for recording only; implementation pending.
  Depends on `business-hub`, `manager-employee-access` and `shift-trades`.
  The separate-site shell approach is superseded by `unified-application-shell`
  below; its scoped alerts, accessibility and navigation requirements carry over.
- **Unified application shell and role-based navigation**
  (`unified-application-shell`): recorded at user request on 2026-11-05;
  implemented, awaiting acceptance. Integrate Access, Shift Trades and Business into
  the existing administrator shell instead of separate interfaces. Reuse the
  header/sidebar, branding, tables/dialogs, light/dark themes and mobile layout.
  Provide one sign-in entry point with account/business selection and role-based
  landing pages, without merging identities or weakening password/MFA rules.
  Employees get personal schedules/attendance/trades; managers get scoped team
  management with explicit linked personal mode; administrators retain scheduling,
  employee management and trade approvals/publishing; primary administrators
  additionally manage Data & Settings, membership and administrators. Platform
  owners retain a distinct cross-business experience with no implicit business
  permissions; developer authorization remains separate.
  Reuse existing backend workflows and preserve records/history. Enforce role,
  tenant, team, primary-admin and tier permissions server-side; scope alerts and
  read/unread state accordingly. Preserve old URLs through authorized redirects,
  selected-trade deep links and approval notifications. Apply shared idle expiry,
  the eight-hour limit, cross-tab activity and sign-out throughout.
  Verify all roles/modes, MFA, tenant isolation, direct/deep links, alerts,
  accessibility, mobile/themes and existing workflow regressions.
  Supersedes the separate-site shell approach of `site-navigation-alerts`.
  Prerequisites: `business-hub`, `manager-employee-access`, `shift-trades`,
  `business-membership-controls`, `primary-admin-data-settings`,
  `meta-data-settings` and `session-idle-expiry`.
  Implemented with `/signin`, role-aware shared navigation and `/app/...` views.
  The administrator workspace remains at `/` to preserve its pathname-scoped
  browser database. Existing Access/Trades/Business URLs and embedded trade
  approvals remain supported. Existing account and API guards remain authoritative.
- **Primary administrator access to Data & Settings**
  (`primary-admin-data-settings`): restrict the group to the designated primary
  business administrator. Enforce corresponding server permissions as well as
  navigation visibility, including direct requests and tenant isolation.
  Preserve ordinary scheduling/sharing. The separate Settings page is not
  automatically included; broader restrictions require an explicit scope decision.
  Implemented supported-workflow restrictions with user-approved browser-storage
  scope: hide Source & backups and its navigation group for additional admins;
  keep Settings separate. Source/SharePoint import, mapping approval, restore,
  backup, configured-input export and portable bundles (including duplicates in
  Settings) require current primary-admin authorization. The employee-import
  mutation also checks primary status and CSRF server-side. Authorization is
  tenant-scoped and audited; failed checks preserve the workspace.
  No server-side workspace migration: configuration already in a user's browser
  and older backups cannot be protected against local extraction. Ordinary
  scheduling/sharing and META placement remain unchanged. Awaiting user acceptance.
  Verified primary/additional administrator permissions, CSRF, tenant mismatch,
  reassignment, inactive/portal/owner denial, uncached permission checks and source
  import atomicity in isolated databases. Browser fixtures cover hidden groups/
  duplicate Settings actions, direct workflow denial, stale permissions and
  unchanged saved-register behavior at desktop/mobile sizes in both themes.
  57 distinct Python tests and 168 browser fixture checks passed. Manuals
  rebuilt; no real source, schedule or account assignments were changed.
- **Move META operating days into Data & Settings** (`meta-data-settings`):
  move it from Plan schedules, apply the primary-admin restriction, update
  shortcuts/visibility settings, and preserve operating days, intensity values,
  locks, saved snapshots and schedule-generation behavior.
  Depends on `primary-admin-data-settings`.
  Implemented: moved static/dynamic navigation and visibility preferences,
  hid META for non-primary administrators, authorized direct navigation and
  calendar edits with the existing tenant-scoped primary-admin endpoint.
  Edit authorization is audited and CSRF-protected; failures and locked/
  replaced workspaces retain prior calendar values. No migration of browser
  data or changes to schedule calculations/snapshots. The same browser-local
  supported-workflow limitation as Source & backups applies. Awaiting user
  acceptance.
  Verified seven targeted Python tests and 120 browser fixture checks across
  desktop/mobile light/dark: primary/non-primary access, stale permission denial,
  configuration locking, percentage/day values and IndexedDB round-trip
  persistence. Manuals rebuilt; no real calendar or schedule data was modified.
- **Fifteen-minute idle session expiry** (`session-idle-expiry`):
  cover business admins, managers, employees, platform owners and developers.
  Enforce expiry server-side at 900 idle seconds, across tabs; automatic polling
  and background refresh must not renew activity. Keep an absolute eight-hour
  maximum, warn before expiry, stop polling/clear protected views, and require
  normal sign-in/MFA again. Verify real activity renewal, polling-only expiry,
  cross-tab behavior, exact thresholds and all account types.
  Implemented server-persisted opaque session clocks shared across tabs for all
  five account types. Exact idle expiry is >=900 seconds; absolute expiry is
  >=28,800 seconds from completed sign-in. Only CSRF-protected, same-origin
  activity reports renew idle time; GETs, normal API traffic and worker/webhook
  jobs do not. Browser reports trusted user interactions at most every 30 seconds;
  server writes are bounded to once per 15 seconds. The final-minute warning
  offers explicit renewal except at the absolute deadline. Expiry clears
  protected UI and navigates to normal sign-in, stopping authenticated polling.
  Persisted workspaces remain; unsaved form edits may be lost. Pre-upgrade
  sessions fail closed and require sign-in after restart. SQLite/PostgreSQL
  startup and reference schema include the global opaque clock table.
  Awaiting user acceptance; live PostgreSQL validation not performed for this
  change. The unified-app shell discussed separately remains a proposal.
  Verified 98 targeted Python tests and 60 browser fixture checks across
  desktop/mobile light/dark, plus trusted browser Continue/typing checks.
  Covered exact idle/absolute boundaries, passive polling, shared-tab renewal,
  expired-cookie replay, logout revocation, all roles, partial sign-ins,
  CSRF/origin/input limits, repeat startup and webhook independence.
  Manuals rebuilt. No real user sessions or business records were modified;
  startup invalidates pre-upgrade sessions because their clock is absent.
- **Executive end-of-day download report** (`executive-end-of-day-report`):
  admins configure automatic generation 0–24 hours after the reporting day
  ends in Jamaica time. Reuse the interval snapshot's visual format for
  executive attendance/staffing/location summaries and significant exceptions.
  Retain dated authorized download history, show source freshness/incomplete
  overnight shifts, and attribute shifts to their start date without duplicates.
  Run without an open browser and surface failures. Download only, no automatic
  emailing. Verify exact timing limits and day boundaries.
  Depends on `snapshot-email-reports`. Approved; implementation pending.
- **Lock employee trade location** (`employee-trade-location-lock`):
  automatically populate the initiating employee's current verified location
  and make it uneditable; include linked managers in personal employee mode.
  Management-mode managers/admins retain authorized location choices. Enforce
  assignment/location restrictions on choices, options and submission server-side,
  preserve existing trade rules, and explain missing assignments/eligible schedules.
  Verify reassignment, tampered requests, all modes and tenant isolation.
  Depends on `shift-trades` and `manager-employee-dual-access`.
  Implemented, awaiting acceptance: personal choices expose a verified locked
  location/team, the picker preselects and disables it, and choices/options/
  submission recheck current assignments, including linked-manager personal mode.
  Management choices remain editable and scoped.

## Workspace readiness (`workspace-readiness`) - implemented, awaiting acceptance

- Startup uses a default-on, theme-aware readiness overlay. It shows a
  slow-load state after 20 seconds, fatal recovery with sign-in/support reference,
  or optional-integration recovery with explicitly read-only continuation.
- Retry reloads the app to avoid duplicate initialization listeners or writes.
  Limited mode makes `#content` inert and disables profile/notification actions;
  sign-out, navigation, theme and retry remain available.
- `SCHEDULE_CREATOR_WORKSPACE_READINESS_ENABLED` accepts documented boolean
  values, defaults on, and logs invalid values before safely defaulting on. It
  only controls presentation; authentication and authorization remain enforced.
  Restart the server after changing the environment setting.
- Verified the focused flag/auth test, syntax, whitespace and DOM-stub loading,
  optional, fatal and read-only transitions. Awaiting user acceptance;
  interactive browser/network-failure and viewport checks remain outstanding.

## Timed action-feedback toasts (`action-feedback-toasts`) - low priority, implemented, awaiting acceptance

- User-action feedback appears in a dismissible, nonblocking top-right toast for
  seven seconds. Rapid feedback is queued; the latest 20 messages are retained
  in tab session storage and are reviewable from the expanded header.
- New attendance and pending shift-trade alerts toast once after initial
  notification polling. Existing unread alerts are not replayed; bell read and
  archive behavior is unchanged. History and queued toasts clear on sign-out.
- Verified JavaScript syntax, seven-second duration, queue progression,
  dismissal, session history, accessible expansion state, sign-out cleanup and
  notification deduplication with Node checks. Awaiting user acceptance;
  interactive browser, keyboard and viewport verification remain outstanding.

## Change request visibility (`primary-admin-change-request-visibility`) - implemented, awaiting acceptance

- The current primary business administrator receives a separately guarded,
  read-only page and GET API; the scheduler link is hidden from other roles.
- The API exposes only business-facing titles and coarse statuses. It excludes
  request IDs, descriptions, dependencies, timestamps, private developer and
  identity requests, and all mutation controls. Status changes remain developer-only.
- Page/API requests recheck the current primary-admin designation and tenant.
  Anonymous users, other admins and platform-owner sessions without developer
  authentication are denied. Developer page and APIs are unchanged.
- Verified the focused access/sanitization test and all 11 developer
  change-request tests, including current primary-admin demotion and mutation
  denial. Syntax and whitespace checks passed. Awaiting user acceptance;
  interactive browser role/viewport verification remains outstanding.

## Historical attendance trends (`historical-attendance-trend-reports`) - implemented, awaiting acceptance

- Generate historical weekly and previous-month reports in Excel and offline
  interactive HTML. Admins select all/specific DCs; managers are restricted
  server-side to authorized teams for generation, history and downloads.
- Include executive/DC KPIs, employee attendance scores using the existing
  documented formula, expected/confirmed shifts, late/absence totals with dates
  and shift times, approved leave and detailed dated evidence.
- Compare employees and DCs week over week and month over month using counts,
  eligible-shift denominators, rates and percentage-point changes.
- Analyze late/absence patterns by shift-start time, weekday, first scheduled
  shift after a verified day off and first scheduled shift after approved time
  off. Separate leave types where evidence supports it; show incidents and
  eligible shifts for every pattern.
- HTML includes coordinated filters/search, sortable tables, drill-down, KPI
  cards, comparison/trend charts and heatmaps where supported. Excel provides
  matching summary, employee, comparison, pattern and evidence worksheets.
- Preserve Jamaica boundaries, overnight start-date attribution, leave,
  worked-time validation, corrections and verified late-arrival distinctions.
  Use historical assignment/schedule evidence, not today's teams/settings.
- Missing schedules are not verified days off. Missing history is unavailable,
  not zero. Distinguish observed patterns, insufficient evidence and no incidents;
  normalize comparisons and explicitly label partial periods.
- Confirmed policies: Monday weeks; selected-period-only pattern analysis;
  minimum three eligible shifts; current authorized manager teams with dated
  team attribution. Avoid cross-team
  disclosure after transfers, causal claims and automatic disciplinary actions.
- Reuse saved branding/report infrastructure; show freshness and incomplete
  evidence. Automatic email is outside scope.
- Verify access/transfers, period and score calculations, incident dates,
  all pattern categories, insufficient evidence, cross-format parity and offline
  interaction. Depends on `snapshot-email-reports`,
  `interactive-attendance-snapshot` and `manager-employee-access`.
- Implemented scoped generation, separate immutable history and Excel/offline
  interactive HTML with comparison charts, heatmap, coordinated filters/search/
  sorting/drill-down and dated overrides. Schedule-continuity gaps remain
  explicit uncertainty for first-shift-after-day-off/leave analysis.
- Validation: 45 combined historical/snapshot/action/register tests passed.
  Browser checks verified employee/pattern incident dates and rates, chart
  rendering, filtering/sorting/reset, desktop/mobile widths and standalone
  HTML with no network requests. Snapshot email preview and deletion
  cancellation/confirmation also passed. User acceptance remains outstanding;
  PostgreSQL validation is deferred.

## Workload and headcount planning (`workload-fte-headcount-planning`) - approved, implementation pending

- Separate workforce capacity/annual planning module. Managers primarily define
  required tasks, standard times, workload units/conversions, workload-to-task
  mappings and fixed work for their authorized locations/roles. Enforce scope
  server-side; workforce admins oversee models, review definitions and approve
  scheduling integration.
- Use dated manual/imported forecasts to calculate workload labour hours and
  required FTE from productive hours per FTE. Define working hours, breaks,
  leave/training/absence allowances, part-time capacity and shift coverage;
  avoid counting allowances already included in task standards twice.
- Distinguish fractional FTE from employee headcount, with explicit rounding and
  coverage assumptions. Show year-long weekly/monthly requirements by role and
  location, available/planned capacity, gaps, period changes and scenarios.
- Approved, versioned, effective-dated plans automatically update only agreed
  scheduling demand/capacity settings. Preview changes/conflicts; derive daily/
  shift distribution before translating weekly requirements into scheduling.
- Preserve availability, contracts, safety rules, configuration locks and
  accepted schedules. Audit changes and support rollback; do not silently
  overwrite settings on forecast edits or rewrite accepted schedules.
- Agree models, forecast inputs, approval authority, definition/review workflow
  and permitted scheduling-setting updates before implementation. Label results
  as model-based requirements, not guarantees.
- Verify conversions, fixed work, allowances, FTE/headcount, year/period
  boundaries, scenarios, scoped access, approval/effective dates, conflicts,
  rollback and saved-data preservation. Depends on `manager-employee-access`.
- Recording only; implementation pending.

## Help and knowledge base (`faq-guides-knowledge-base`) - implemented, awaiting acceptance

- Added role-aware Help navigation/page with searchable built-in FAQs, glossary,
  a step-by-step tutorial, and a plain-text index of the generated user manual.
- Managers submit new/edit content only for their assigned Schedule Locations,
  choose an audience, save drafts, and resubmit drafts/rejections. Server-side
  role, tenant, location, CSRF, stale-revision and reviewer checks are enforced.
- Business admins approve/reject with required feedback. Only approval publishes;
  previous versions remain in immutable revision history. Content renders as
  plain text, so submitted markup is never executed. PostgreSQL RLS is enabled.
- Notification policy: no email/push notifications. Admin pending queue and
  manager submission status/feedback appear in the Help page.
- Five workflow tests, manual freshness, shared route test, syntax and whitespace
  checks passed. Awaiting user acceptance; interactive browser/mobile checks
  remain outstanding.

## Shared HTML report branding (`shared-html-report-branding`) - implemented, awaiting acceptance

- Business Settings supports a report-only light/dark theme and up to two
  supporting PNG/JPEG/WebP images, each limited to 2 MB, with preview, replace
  and remove controls. Existing server-side logo signature/type validation is
  reused; app personal theme remains separate.
- New snapshot and historical HTML/XLSX captures freeze business name, logo,
  primary/accent colors, report theme and validated support images. Offline HTML
  embeds the assets; saved captures are not rewritten after branding changes.
- Existing report entitlements are unchanged. Snapshot/historical capture and
  config tests, manual freshness, syntax and whitespace checks passed. Awaiting
  user acceptance; interactive browser/mobile/print verification remains open.

## Historical report dashboard redesign (`historical-report-progressive-dashboard`) - implemented, awaiting acceptance

- Match the snapshot's branded style with spacious panels, concise executive
  KPI cards and clear DC/role attendance, lateness and absence comparisons.
- Initially hide full employee registers, detailed evidence and pattern tables.
  Selecting a DC x role reveals its dedicated trend graph and summary table;
  selecting an employee reveals their graph, score, incident dates and
  shift/day/post-day-off/approved-time-off patterns.
- Coordinate filters/chart drill-down, show active scope and restore the
  uncluttered overview when selections clear. Keep detail hidden until selected.
- Preserve saved evidence, calculations, source/sample warnings, manager
  authorization, detailed Excel worksheets and historical capture immutability.
- Label two-period comparisons accurately; no invented multi-period trend lines.
  Retain offline use, accessibility and responsive/print-friendly presentation.
- Verify overview/detail visibility, team/employee selection, reset, metric
  consistency, unavailable evidence, Excel parity and desktop/mobile/print.
- Depends on `historical-attendance-trend-reports` and
  `interactive-attendance-snapshot`. Implemented for newly generated HTML;
  previously saved reports and detailed Excel sheets remain unchanged.

## Role-scoped roster settings (`role-scoped-roster-settings`) - implemented, acceptance verification pending

- Managers see roster settings for their currently authorized teams and may
  edit roster fields except Random 1-3 and Attendance 0-100, which are read-only.
  Proximity, daily availability and allowed shift starts remain editable.
- Employees see only their own record and may edit only Flexible, Reason if no
  and Preferred start. All other fields are clearly read-only.
- Preserve administrator permissions. Enforce tenant, current team/employee
  scope and field-level write allowlists server-side, including tampered requests.
- Preferred starts use configured location x role choices and existing
  availability validation; require a reason when Flexible is No and reject
  incompatible choices with explicit feedback.
- Preserve MFA, roster locking and existing access/membership restrictions.
  Revoke stale access after reassignment, disabling or account/link changes.
- Linked managers use employee permissions for their own record in My shifts;
  do not expand management scope or bypass administrator-only self-attendance
  corrections.
- Audit edits, prevent stale concurrent overwrites and surface save failures.
  Changes affect future scheduling, not accepted shifts or historical attendance.
- Verify role/scoped visibility, permitted and forbidden updates, own-record
  isolation, linked-manager views, start validation, locks, access revocation,
  concurrent edits, audit history and accepted-schedule preservation.
- Depends on `manager-employee-access` and `manager-employee-dual-access`.
- Implementation adds tenant-scoped shared configuration and employee settings,
  an explicit primary-admin preview/import flow, incremental employee and shift
  start synchronization, manager and personal roster views, field-level server
  validation, audit events and revision conflict handling.
- SQLite verification: all 34 combined manager/access tests passed, including
  roster scope, field permissions, locking, import safeguards, new-start
  availability, audit, reassignment and transaction rollback. The linked-manager
  personal-roster test is included.
- Browser verification and PostgreSQL execution remain outstanding. PostgreSQL
  validation stays deferred under the existing user instruction; do not mark
  production acceptance complete based on SQLite results.

## Manager-scoped META settings (`manager-scoped-meta-settings`) - implemented, acceptance verification pending

- Managers view only their currently authorized locations on META. Permit
  changes only when configuration is unlocked; locked settings are read-only.
  Managers cannot unlock configuration themselves.
- Preserve administrator permissions; employees and linked managers in their
  personal employee view receive no META access.
- Enforce tenant/location scope, permitted fields and current lock state
  server-side on reads and writes, including tampered requests and stale pages.
  Preserve MFA, membership/access restrictions and operating-setting validation.
- Revoke stale access after reassignment or disabling. Audit edits, reject stale
  concurrent overwrites and explicitly report validation/save failures.
- Affect future scheduling only; preserve accepted shifts and saved
  configuration snapshots.
- **Scope confirmed:** managers may edit both operating days and workload
  intensity percentages. Any assignment to a team at a physical location grants
  location-wide META access across roles at that location.
- META values were browser-local. The primary administrator now previews and
  explicitly imports the current browser values once into tenant-scoped server
  storage; existing server settings are never overwritten by another import.
  New workspace locations can be explicitly added without replacing saved
  location values.
- Verify scoped visibility, unlocked edits, locked/unlock denials, location and
  shared-role boundaries, validation, revocation, concurrency, audit history
  and saved-schedule preservation. SQLite verification passed for the combined
  34-test manager/access suite, including shared-role location scope, read/write
  permissions, lock synchronization, revision conflicts, audit and preservation
  of an accepted schedule.
- Browser verification and PostgreSQL execution remain outstanding. PostgreSQL
  validation remains deferred under the existing user instruction.
- Depends on `manager-employee-access`. Scope is confirmed and the feature is
  implemented; browser verification and deferred PostgreSQL validation remain
  outstanding.

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
  tracked SQLite database). The temporary MFA bypass has been removed; the LAN
  HTTP option (section above) must still be removed before shared or production use.
- [x] The `business-hub` change request is marked `done` (PostgreSQL and the
  tracked SQLite database). Production setup checks for the platform owner,
  BambooHR key migration, real business registration and browser flows remain
  listed in the section above.
