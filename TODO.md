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

## Manager and employee access (`manager-employee-access`) — complete

- [x] Admins create manager and employee accounts in Settings → Manager &
  employee access. A one-time temporary password (72-hour expiry) is shown to
  the admin; the user must replace it at first sign-in at `/access`. Admins can
  reset passwords (optionally MFA) and disable/enable accounts, which ends the
  account's sessions.
- [x] Sign in with BambooHR subdomain plus email or employee ID and password.
  MFA (enrolled at first sign-in, unless the temporary `MFA_BYPASS` is on, which
  now also applies to managers and must be removed with the admin bypass); employees have no
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

Implemented on 2026-11-05; live acceptance remains outstanding. Depends on
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
- [ ] Verify the five-shift trade minimum and all exception acknowledgements
  with real employee/manager/admin sessions before marking trade requests done.
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
- [ ] Verify the redesigned modal and both rest acknowledgement flows with real
  employee/linked-manager sessions; accept the UI and schedule/code selection.
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
- Tracker: dual access, trades and billing remain `in_progress` for live
  acceptance; trade publishing is `blocked` only by the unaccepted shift-trade
  prerequisite, not by missing application code.
- [ ] Verify linked managers and both trade roles in real authenticated browser
  sessions; verify team restrictions, link disable/reassignment and own
  attendance correction rejection with MFA enabled.
- [ ] Verify employee -> employee -> manager -> admin workflow, unread updates,
  cancellation/rejection, applied schedule/export/email data and manual overrides.
- [ ] In a test BambooHR environment, verify read permissions, single-employee
  writes, partial failures, unknown results, duplicates and reconciliation.
  Production writes require separate authorization.
- [ ] Configure PayPal sandbox credentials/webhook and prices privately. Verify
  real hosted monthly/annual checkout, one-cycle versus auto-renew plans,
  webhook signatures/replays, cancellation, failure retries and manual credits.
- [ ] Install the worker under an always-on supervisor; verify restart/crash
  handling, heartbeat, single-instance claims, missed webhook polling, seven
  attempts and suspended membership access across all user roles.
- [ ] Apply/verify PostgreSQL startup or reference-schema migrations and forced
  tenant RLS for trade/billing tables in a disposable schema. The VS Code
  database connection was unavailable during this batch; no live migration
  success is claimed. The opaque subscription index is deliberately global
  for pre-tenant webhook routing.

## Planned change request: saved schedule register (`saved-schedule-register-management`)

Recorded on 2026-11-04; not implemented. Depends on `tenant-identity`.

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

## Planned change request: attendance snapshots (`snapshot-email-reports`)

Recorded on 2026-11-04; not implemented. This extends the existing request and
retains its `workforce-dashboards` prerequisite.

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

These requests are recorded as pending; no feature behavior has changed.

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
- **Primary administrator access to Data & Settings**
  (`primary-admin-data-settings`): restrict the group to the designated primary
  business administrator. Enforce corresponding server permissions as well as
  navigation visibility, including direct requests and tenant isolation.
  Preserve ordinary scheduling/sharing. The separate Settings page is not
  automatically included; broader restrictions require an explicit scope decision.
- **Move META operating days into Data & Settings** (`meta-data-settings`):
  move it from Plan schedules, apply the primary-admin restriction, update
  shortcuts/visibility settings, and preserve operating days, intensity values,
  locks, saved snapshots and schedule-generation behavior.
  Depends on `primary-admin-data-settings`.
- **Fifteen-minute idle session expiry** (`session-idle-expiry`):
  cover business admins, managers, employees, platform owners and developers.
  Enforce expiry server-side at 900 idle seconds, across tabs; automatic polling
  and background refresh must not renew activity. Keep an absolute eight-hour
  maximum, warn before expiry, stop polling/clear protected views, and require
  normal sign-in/MFA again. Verify real activity renewal, polling-only expiry,
  cross-tab behavior, exact thresholds and all account types.
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
  Approved; implementation pending.

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
