# CBL Schedule Creator

The CBL Schedule Creator is a local Flask application for configuring workforce
requirements, creating and reviewing weekly employee schedules, managing
employees and BambooHR schedule locations, and publishing accepted shifts.

## Requirements

- Windows
- Python 3.9 or later
- Google Chrome

## Run the application

1. Open a terminal in `Schedule Creator`.
2. Install the dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Configure the BambooHR API key as described below.
4. Double-click `Start-Schedule-Creator.bat`, or start the Flask server
   directly:

   ```powershell
   python scheduler.py
   ```

The batch file starts the server on `127.0.0.1:5001`, checks that the
authentication API is responding, and opens the app in Chrome. If port 5001 is
already occupied, close the other server before starting this one. The app is
available at <http://127.0.0.1:5001/>.

## Administrator sign-in and storage

The app requires a business administrator to sign in before accessing scheduling
or business APIs. On first launch, create the initial administrator from the
local computer with a unique password of at least 14 characters. Enroll an
authenticator app using the displayed setup secret and verify its current
six-digit code. At each sign-in, enter the BambooHR subdomain for the business
you want to access, along with that business's administrator email and password.
The same email can be an administrator for multiple businesses; credentials and
MFA enrollment are managed separately for each business. Administrator MFA is
mandatory. Sign out from the application header when finished.

All authenticated browser roles (business administrators, platform owners,
managers, employees and developers) expire after 900 seconds without reported
user interaction, with an absolute eight-hour limit from successful sign-in.
Server-persisted opaque session clocks are shared across tabs. Notification/
attendance polling, page refresh and background jobs never renew activity.
The shared browser monitor reports trusted interaction at most every 30 seconds,
warns during the final minute and offers Stay signed in before idle expiry;
the absolute deadline cannot be extended. Expiry clears protected views and
requires normal sign-in/MFA, without deleting persisted workspace data.
Save form edits before expiry: unsaved edits may be lost.
Existing pre-upgrade sessions have no clock and must sign in again after
restart. Startup creates the clock table on SQLite/PostgreSQL; the PostgreSQL
reference schema includes it. It stores opaque IDs/timestamps only, not tenant
or account data. Previously expired cookies cannot recreate a clock.

Local development uses SQLite at
`Schedule Creator\data\schedule_creator.sqlite3`. Flask's session-signing key
and the independent MFA-encryption key are generated in
`Schedule Creator\data\flask_secret.key` and
`Schedule Creator\data\mfa_encryption.key`. Keep these files private and
preserve them with the database; losing the MFA-encryption key prevents existing
authenticator secrets from being decrypted. They are excluded from Git.

For a PostgreSQL-backed deployment, configure these values in
`Schedule Creator\.env` (or the process environment):

```dotenv
SCHEDULE_CREATOR_DATABASE_URL=postgresql://scheduler_app:password@db-host/scheduler
SCHEDULE_CREATOR_TENANT_ID=business-slug
FLASK_SECRET_KEY=at-least-32-random-characters
SCHEDULE_CREATOR_MFA_ENCRYPTION_KEY=another-independent-32-character-secret
SCHEDULE_CREATOR_TRUSTED_PROXY_HOPS=1
```

Provision the first PostgreSQL administrator from a trusted server shell
(passwords are prompted, not included in command history):

```powershell
python scheduler.py bootstrap-admin --email admin@example.com --name "Business Admin"
```

The administrator must enroll MFA at their first HTTPS sign-in. PostgreSQL
bootstrap is deliberately not exposed through the public web setup endpoint.

Use a dedicated PostgreSQL application role without `SUPERUSER` or
`BYPASSRLS`. The app enables and forces row-level security for schedule,
employee, configuration, and audit data. PostgreSQL mode requires HTTPS; set
the trusted-proxy count to the exact number of reverse proxies that set
`X-Forwarded-Proto` and `X-Forwarded-Host`, and terminate TLS at that trusted
proxy. Do not expose the Flask development server directly to the internet.
To install the tables on a new server ahead of time, run
[`Schedule Creator/schema_postgres.sql`](<Schedule Creator/schema_postgres.sql>)
as the application role (the file's header lists the role and database setup
steps). The app also creates the same schema itself on first start.
`SCHEDULE_CREATOR_TENANT_ID` identifies the app's business tenant and is
separate from the BambooHR tenant ID in Settings.

To import an existing local CBL database, configure PostgreSQL and the secrets
above, then run `python scheduler.py migrate-sqlite` from `Schedule Creator`.
The command defaults to the current SQLite database, prompts for confirmation,
and imports business schedules, employees, locations, settings, and developer
change-request data into the configured tenant. It refuses to overwrite a
target that already has an administrator, accepted schedules, or conflicting
developer credentials, runs as one transaction, and can be used only once. The
SQLite source is not modified.
Imported admin passwords are retained, but all admins must enroll MFA again
because encryption keys are deployment-specific.

The initial local setup creates one administrator for the configured tenant.
Multi-business registration, membership approval, and tenant account management
are available through the Business Hub. PostgreSQL schema support is included;
verify connection, backups, restore procedures, and deployment-specific
operations in the target environment before production use.

## Membership tiers and entitlements

New businesses start on Bronze. The platform owner assigns or changes a tier
from the Businesses panel at `/hub`. Admin seats are the user-license limit;
teams are distinct location/role groups, and the location limit counts distinct
locations.

| Tier | Admin seats | Teams | Active employees | Locations |
|---|---:|---:|---:|---:|
| Bronze | 2 | 2 | 20 | 2 |
| Silver | 3 | 4 | 60 | 4 |
| Gold | 4 | Unlimited | Unlimited | 6 |
| Platinum | 8 | Unlimited | Unlimited | Unlimited |

Schedule generation, sharing, BambooHR publishing, email configuration,
employee management, and settings are included in every tier. Employee schedule
access, shift trades, and schedule history are available with Silver and above;
overtime forecasting is available with Gold and above. The app returns
entitlements with the authenticated tenant state and hides unavailable UI
features. API additions that exceed an account's quotas are rejected.

Downgrades do not deactivate or delete existing data. Existing over-limit
usage is grandfathered, but new additions that exceed the selected tier are
blocked until usage falls within its limits. Removals, deactivations, and
changes that do not increase over-limit usage remain available.

The main business administrator can view the current tier and membership
status at `/business`, change tiers, pause, resume, or cancel membership. These
actions take effect immediately and require confirmation. Pausing disables
scheduler access but can be resumed by the main administrator. Cancellation
also disables access, retains all business data, and requires the platform
owner to restore access. Optional PayPal sandbox billing is disabled by default;
live payments are not supported. Enrolled sandbox subscriptions follow
membership pause/resume/cancel actions after provider verification.
Membership actions are recorded in the tenant audit log with the acting
administrator and the prior/new tier or status.

## BambooHR configuration

The Flask server reads `BAMBOOHR_API_KEY` from `Schedule Creator\.env`. Create
or edit that file with this setting:

```dotenv
BAMBOOHR_API_KEY=your_api_key
```

Keep the real API key private. `.env` is excluded from Git tracking; do not
paste the key into source files, screenshots, or commits. The app can test a
candidate key in Settings using a read-only BambooHR time-off request. A
successful test does not change the operational key; select **Use as app API
key** to explicitly save it to `.env` and update the running server.

Settings also supports the BambooHR tenant ID. Saving a tenant changes the
tenant used by all future time-off and schedule publishing requests. Existing
operational credentials remain in `.env` unless a successfully tested key is
explicitly promoted for the saved tenant. Business name, team name (default
**Schedule Management**), logo (PNG/JPEG/WebP, up to 2 MB), and primary/accent
colors are saved in the app database and applied throughout the interface and
schedule confirmation email signature.

The app fetches BambooHR time-off data when generating or refreshing schedules.
If the key is missing or BambooHR cannot be reached, scheduling continues
without that data and marks the schedule for review. Review schedules carefully
when the warning appears.

Publishing accepted shifts sends changes to BambooHR. Review the selected
shifts and payload preview, and explicitly confirm before posting.

Attendance defaults to accepted shifts in this app, but an administrator can
select BambooHR scheduled shifts as the attendance shift source. BambooHR clock
events remain the source of attendance evidence in either mode. When BambooHR
is selected, the Attendance page reads its shifts, compares employee/date/time
and mapped location with accepted app shifts, and lists unresolved
discrepancies.

Admins can explicitly confirm a reasoned resolution in either direction.
Applying an app shift to BambooHR adds the replacement first and then deletes
the prior single-employee shift; BambooHR does not make these two operations
transactional, so a partial result is reported and audited. Applying BambooHR
to the app updates the accepted schedule and audits full before/after schedule
payloads. Stale discrepancies are rechecked before a write, and shared
BambooHR shifts or unsupported app mappings/durations are blocked from unsafe
individual resolution. These API operations were validated with mocked
responses; no production schedule writes were made during implementation.

## Scheduling workflow

1. Configure location-role pools, demand shares, shift starts, and employee
   availability.
2. Set scheduling controls and lock the configuration.
3. Generate or upload schedules, then review coverage, constraints, and any
   time-off warnings.
4. Accept schedules to save them in the app database. Previously accepted
   schedules can be reviewed, and acceptance can be undone without removing
   the generated workspace schedule.
5. In the BambooHR publishing view, select shifts from accepted schedules,
   preview the payload, and confirm to publish.

The app also includes employee and schedule-location management, employee
assignment, schedule exports, and workspace backup/restore.

## Employee directory

On the Employees page, select **Refresh BambooHR employees** to synchronize
the current active BambooHR roster. New BambooHR records are added inactive
for scheduling until their app location, role, and roster availability are
reviewed. Existing app mappings and roles are retained; BambooHR employees
missing from a later active-employee response remain in the directory but are
made inactive locally. Sync conflicts between a manual record and BambooHR
require an explicit same-person/different-people decision before any changes
are applied.

Use the Employees page's location and role filters to narrow the directory.
The select-all checkbox selects only the employees currently shown by those
filters; existing selections remain selected when changing filters.

Roles can be assigned from an employee row or in a batch. Changing a role
deactivates that employee until the roster profile is reviewed. Manual
employees receive a generated `MANUAL-...` BambooHR ID, are not sent when
publishing shifts, and are the only employee records that can be deleted.
Employee active status in this app does not update BambooHR.

When importing a source workbook, the app pauses for a mapping review. Confirm
the app location, role, and optional schedule location for every employee.
Unknown employees are not added to the app directory unless **Add manually**
is selected for them. Newly added manual employees start inactive.

Enter a manager name and email address for each schedule location in the
Schedule Locations directory. Confirmation emails are grouped by schedule
location: each draft is addressed to that location's manager and includes only
the selected schedules mapped to that site. Download the matching workbook and
attach it before sending. The app creates email drafts; it does not send them
automatically. Existing schedule locations need manager details added before
they can be included in a confirmation email.

## Developer change requests

Open **Developer change requests** from the app menu. Signed-in developers can
expand **Add a developer account** and confirm their current password to create
another independent developer login (unique username, password of at least 14
characters). All developer accounts have full change-request access; business
administrator credentials do not authorize account creation. Credential changes
affect only the signed-in developer and invalidate that account's older sessions,
not other developers. Existing accounts are preserved during schema migration.
An operator with trusted access to the server can also add an account locally:

```powershell
cd 'Schedule Creator'
python scheduler.py add-developer --username new-developer
```

Enter and confirm the password at the hidden terminal prompts, never as a command
argument or in chat. This command uses the configured database and performs only
the developer-account migration/creation, not unrelated initialization. Restrict
server/database access to trusted operators.

On first use, create a
developer username and a unique password with at least 14 characters. Initial
setup is restricted to the computer running the app; there is no built-in
`developer/developer` credential. The developer log supports sign-in, credential
updates, status filters, and dependency checks for starting or completing work.

The approved SaaS roadmap is recorded there, but the Copilot builder is not
connected yet. The page does not launch agents or apply code changes. The
attendance roadmap now includes timely BambooHR clock-in tracking, a live
day-so-far dashboard with expected/attended counts and attendance percentages,
role/shift and location-to-team breakdowns, and named absence/late/leave
exceptions. Managers receive scoped in-app notifications and can record an
absence with a reason; a missing clock-in becomes absent four hours after
shift start unless approved leave applies. Admins see all business locations
by default, while managers and employees are restricted to their authorized
teams. Employees get a simplified read-only dashboard for their own team.
Attendance dashboards remain Silver+, and daily staffing interval snapshots
remain Gold/Platinum. Tenant registration and membership management,
manager/employee access, the employee portal, shift trades, payment, and
Copilot automation remain separate implementation phases.

## Manager and employee access

### Unified application and attendance downloads

Use `/signin` to choose Business administrator, Manager/employee or Platform owner.
Business/workforce sign-in includes the business subdomain; existing password
replacement and MFA enrollment/verification remain required. Initial local
administrator setup is available from the sign-in page. Shared navigation,
branding, themes, scoped alerts and sign-out wrap the existing workflows at
`/app/access`, `/app/trades`, `/app/business`, `/app/owner` and `/app/billing`.
Legacy URLs and selected-trade links still work. The administrator workspace
stays at `/`: its IndexedDB identity and accepted schedules are not migrated.
Platform owners do not receive business permissions. Linked managers explicitly
switch between personal and management views.

In personal trade mode the current verified location/team and offering employee
are preselected and cannot be changed. The server rechecks assignments when
loading options and submitting; a reassignment requires reloading the choices.
Authorized management users retain their scoped location choices.

Attendance snapshots are Silver+ and download-only for now. Attendance has
Capture now, Refresh history, View HTML, Download HTML and Download XLSX.
The interactive HTML dashboard shows executive KPI cards, location/role/
shift charts and summaries, then employee exceptions and evidence-based risks.
Location, role, shift, status and search filters coordinate the entire dashboard;
chart drill-down, sortable exception details and Print / Save PDF are available.
HTML contains its own data, charts and saved company logo, so downloaded files
work offline without external services. New captures freeze the business name
and logo from branding settings; later branding changes do not rewrite history.
Older captures use only saved evidence, without adding today's branding.
XLSX downloads remain available with exception colors and employee clock details.
The primary administrator may enable scheduled captures at 07:00, 15:00 and 23:00
America/Jamaica. Start the independent worker with:

```powershell
cd 'Schedule Creator'
python report_worker.py
```

Or use `Run Attendance Reports Worker.bat`. Keep it running with the same
environment/database as Flask; use a service supervisor for unattended
deployment. The browser does not schedule captures. Scheduling is opt-in,
requires an active Silver+ membership and exposes the worker's last heartbeat.
Scheduled cutoffs have unique per-tenant keys. Missed cutoffs older than two
minutes are recorded as missed rather than retrospectively reconstructed.
Abandoned running captures become explicit failures after 15 minutes; on-demand
capture provides recovery. Refresh failures produce clearly marked stale
downloads, not false successful refreshes. Snapshots preserve the exact cutoff,
existing worked-time/absence rules, approved-leave exclusion and verified
overnight carry-in. Both source freshness and actual capture time are recorded.
There is a one-minute on-demand cooldown.

Administrators can select individual snapshots or select all displayed deletable
captures and choose **Delete selected**. Confirmation removes HTML/XLSX payloads
and visible history atomically, without changing attendance or schedules.
Running captures cannot be deleted. Minimal run-key tombstones and deletion
audit entries remain so a deleted scheduled cutoff cannot be regenerated.
Previously downloaded or emailed copies cannot be recalled.

Each table on the administrator Attendance page offers **Download Excel**,
including attendance, scores, discrepancies and report histories. Exports follow
the displayed filters and sort order; action/selection/download controls are
excluded. Empty tables export column headings only.

**Generate email body** opens an executive subject, formatted preview and
plain-text alternative derived only from that saved snapshot. It includes
location/role tables, evidence-based call-outs and source warnings. Copy controls
require browser clipboard support; otherwise select/copy the subject and plain
text manually. Attach the downloaded HTML yourself; this does not send email.

HTML distinguishes confirmed attendance from clock-in evidence: late records
without a matching punch or the required worked-time validation are not counted
as confirmed. Approved leave is excluded; zero expected shifts show N/A.
Missing punches and saved absences overlap and must not be added together.
All counts represent shift records, not unique employees or future staffing
demand. Downloaded reports contain employee information; share only with
authorized recipients. Offline copies cannot be revoked when a session expires.

Automatic email and email-only/both modes remain deferred by agreement. No email
is sent by this worker. Staffing-vs-demand interval analytics are not part of
these attendance downloads and retain their separate Gold/Platinum entitlement.
SQLite tests and browser checks cover this implementation; the new PostgreSQL
table policies still require disposable-database deployment acceptance.

Historical attendance reports are available in administrator Attendance and
manager team attendance. Select a week or previous month; weeks use Monday
boundaries and dates are interpreted in America/Jamaica. Administrators may
limit scope using the Distribution Centre and Role dropdowns (or All locations/
All roles); managers are limited to currently authorized teams
and dated records attributed to those teams, including role restrictions.
Saved historical reports provide separate immutable Excel/HTML history.
They are not deleted through the point-in-time snapshot deletion controls.

Reports compare the selected period with the preceding week/month and show
employee/DC counts, rates, scores and incident dates. Pattern analysis uses
only the selected period, with at least three eligible shifts per pattern.
Missing history/assignment evidence is unavailable, not zero; gaps in recorded
schedules do not prove days off. Comparisons describe observed associations,
not causes or disciplinary recommendations. Report copies contain employee
information and must be shared only with authorized recipients.

New historical HTML reports use a snapshot-style executive overview with four
KPI cards and DC/role comparisons. Employee registers, pattern analysis and shift
details stay hidden until an employee or both a DC and role are selected.
Select chart labels or table rows to drill down, or use the filters; Clear
filters restores the overview. The active scope is displayed and Print / Save
PDF respects the selected detail visibility. New reports freeze the business
name/logo at generation; existing saved HTML and detailed Excel sheets are
unchanged. Comparisons cover selected/preceding periods, not invented long-term
trend lines.

Data & settings / Source & backups is restricted to the designated primary
business administrator. Source import and mapping approval, restore, workspace
backup, configured-input export and portable bundles require fresh server
authorization; mutation authorization uses CSRF and the current tenant.
Duplicate source/portable actions in Settings have the same restriction.
The separate Settings page, ordinary scheduling, schedule exports and sharing
remain available to other administrators. META operating days is now in
Data & settings and follows the same primary-admin permission: opening it and
editing a calendar require current server authorization. Locked configurations
remain uneditable; operating-day/intensity data and schedule calculations are
unchanged.
These are supported-workflow permissions: browser-resident configuration used
for scheduling and previously exported backups cannot be secured retroactively.
No server-side workspace migration or local-data removal is performed.

On Weekly schedules, the Saved schedule register has a six-record scrolling
viewport and sticky header. Its administrator-only Delete action removes only
the selected browser-workspace copy after confirmation and successful IndexedDB
storage. Accepted database copies, BambooHR shifts and existing audit history
are retained. Deletion requires online administrator authorization and working
browser storage; shuffle undo is cleared and stale email preparation invalidated.
Previously exported backups remain unchanged.

Trade publishing removes original single-employee shifts before creating
replacements, including on retries of older saved plans. Remote operations are
not transactional; missing replacements after a failure require reconciliation
and retry, not reapplication of the accepted app trade. Completed operations
are skipped, unknown outcomes require read-only reconciliation, and provider
validation errors are shown on failed trade operations. App acknowledgements
cannot override BambooHR's own overlap validation.

The administrator notification bell includes **Shift trade approvals** for
manager-accepted requests awaiting administrator approval. Clicking an alert
opens an embedded administrator inbox with the selected trade expanded, in the
admin site's theme. Viewing marks that update read, not approved or acknowledged.
Pending requests remain listed until resolved; unread counts are per reader and
version. Notifications refresh every 30 seconds while visible and on window
close. Approval and application still require their existing explicit steps.

Settings → Manager & employee access → **Change role** corrects an existing
account between Employee and Manager. Supply a valid manager email or an active
employee link as required. Confirmation preserves the account ID, password,
name, history and enabled/disabled state, audits the role change and revokes
existing sessions. Manager MFA, email-based location scope and personal-access
membership checks still apply. Existing enrolled MFA is retained; conflicting
accounts and stale edits are rejected rather than merged or overwritten.
This changes the sign-in role, not the employee's scheduling/job role.

Admins create manager and employee accounts in Settings → Manager & employee
access and share the one-time temporary password (72-hour expiry). Users sign
in at `/access` with the BambooHR subdomain, email or employee ID and password,
and must replace the temporary password at first sign-in. Managers must enrol
an authenticator app and provide its verification code at sign-in; employees have no
MFA and need the Silver tier or above (`employeeScheduleAccess`). Managers see
attendance only for employees at schedule locations whose manager email matches
theirs and can mark late shifts absent with a reason; employees see only their
own attendance. Late/absent transitions create in-app notifications (bell,
30-second polling) for the matching managers and for admins. Manager/employee
sessions are rejected by all administrator APIs. Accounts live in
`tenant_users`; notifications in `attendance_notifications` and
`attendance_notification_reads`.

Scheduled managers can link one active same-business employee record to their
existing manager account. My shifts uses that employee ID independently of
managed locations; Manage teams retains the original manager scope and MFA.
Link changes revoke sessions, and self-attendance corrections require an admin.

## Authenticated trades

`/trades` is the shared trade inbox for accepted schedules. Employee requests
need affected-employee confirmation, manager acceptance and admin approval.
Manager-initiated requests skip employee confirmation, not admin approval.
The administrator and access-page Shift trade buttons open a shared modal:
location/team, accepted period and employees are scoped dropdowns; employee 1
is locked for employee/personal views. Checkbox days are validated together,
including combinations that balance weekly caps. Pending intersections are
blocked across every selected day. Legacy single-day trades/overrides remain
readable and publishing journals cover all selected dates.

Both employees must finish the selected accepted schedule week with at least
five assigned shifts (not exactly five); this is enforced at every progression
and application and cannot be overridden for trades. Other scheduling
violations, including overlaps, availability, approved leave, weekly maximum
and rest, are warnings requiring both employees' consent plus explicit manager
acceptance and admin approval. Exception proposals never skip these stages,
even when initiated by management. Changed warnings require a new request.
Authorization, data validity, stale/version checks, pending intersections and
non-admin past-shift guards remain enforced. Manual assignments are separate
and retain their existing override workflow.
Linked managers use `/trades?view=employee` for personal actions. Status history
and unread updates are persisted per tenant/reader.

Admins preview and explicitly apply approved trades or manual shift/day-off
overrides. App-only mode leaves BambooHR unchanged. Remote mode reads and
validates mappings first, journals single-employee replacement/deletion
operations, and exposes partial failures. Successful operations are not repeated.
Unknown writes require read-only reconciliation and separate retry confirmation;
shared shifts and duplicate matches require manual correction. Validation used
mocked BambooHR only, not production writes.

Employees explicitly choose an accepted period for their own shifts without a
code. Team codes may identify a visible assigned period without selecting it
first; shared codes return eligible versions only. Existing expiry, throttling,
CSRF and team/tenant checks are retained. Access, hub and the trade inbox retain
their previous appearance, except the redesigned trade inbox cards.
`workforce-ui.css` scopes theme styling to the trade popup and inbox, preserving
the surrounding administrator palette. Trade cards show names, dated
before/after shifts, weekly counts and grouped warnings with approval status.

## PayPal sandbox billing and dedicated worker

The billing page provides section navigation, a setup checklist, tier price
tables and per-feature Default/Enabled/Disabled dropdowns (no JSON input).
Manual credits and recovery use business selectors; paid-through date/time
entry is explicitly Jamaica time. Subscription details and history are readable
fields, while all existing server validation and sandbox-only safeguards remain.

The provider is hard-coded to PayPal's **sandbox**, never the live API. Billing
starts disabled and is optional for existing memberships. Privately configure
`PAYPAL_SANDBOX_CLIENT_ID`, `PAYPAL_SANDBOX_CLIENT_SECRET`, and
`PAYPAL_SANDBOX_WEBHOOK_ID` in the server environment. Do not enter credentials
in chat, screenshots, source code or owner price forms.

The owner opens `/billing?view=owner`, saves eight USD monthly/annual prices and
optional boolean tier feature overrides, prepares sandbox plans, starts the
worker, then enables billing. The main business administrator uses `/billing`
for hosted checkout, optional auto-renew, reconciliation and cancellation.
Non-renewing plans have one cycle; existing subscriptions retain agreed prices.
Checkout/payment credentials stay with PayPal.

Configure subscription lifecycle/payment sale webhooks in the PayPal sandbox
dashboard with the public HTTPS URL `/api/payments/paypal/webhook`. Signature
verification uses PayPal's verification endpoint, followed by an authoritative
subscription read; event IDs are deduplicated transactionally. The opaque
`billing_subscription_index` resolves tenant context before applying forced RLS
to billing accounts/events. It contains no payment details or business names.

Run the worker **separately** from Flask, using the same database/environment:

```powershell
Set-Location 'Schedule Creator'
python billing_worker.py
```

`Run Billing Worker.bat` is a foreground convenience launcher, not a service
installer. For unattended operation, use Windows Task Scheduler or a service
supervisor: start at system boot, run whether or not a user is logged in, prevent
duplicate instances, restart on failure, and retain process error output. Do not
tie its lifetime to Chrome or the Flask development reloader. The owner page
reports heartbeat health, and enabling billing requires a current heartbeat.

The worker checks payment state and retries a failed outstanding balance daily,
up to seven payment attempts; definitive failures suspend billing access after
the seventh attempt. Unknown outcomes stop retries for reconciliation. Verified
payments/manual owner credits restore billing access without reversing an
administrator's membership/business suspension. Manual credits stop app retries
but do not settle/cancel provider charges. Reminders are in-app, not email.

Startup/reference-schema migrations include trade/billing tables. Live
PostgreSQL migration/RLS checks and PayPal sandbox checkout/webhook/supervised
worker acceptance remain outstanding; billing stays disabled until configured.
The SQLite importer preserves access identities, attendance notification
read/archive state, trade approvals/journals, billing history and subscription
routing, revokes imported user sessions, and disables billing at the destination.
It accepts a single business and a fresh destination only. Stop the source app
and worker before exporting/importing; preserve encryption keys, verify sandbox
credentials and payment state, then start only the destination worker before
reenabling billing. Do not run billing workers against both databases.
API contracts: [PayPal Subscriptions](https://developer.paypal.com/docs/api/subscriptions/v1/)
and [official OpenAPI specification](https://github.com/paypal/paypal-rest-api-specifications/blob/main/openapi/billing_subscriptions_v1.json).

## User manual

The user manual is in `Schedule Creator\docs\User-Manual.html` and
`Schedule Creator\docs\User-Manual.docx`. **Update it with every change that
affects what users see or do.** Edit `Schedule Creator\user_manual_content.py`
(the relevant section plus a new `REVISIONS` entry), then regenerate both files:

```powershell
python -m pip install -r requirements-docs.txt
python build_user_manual.py
```

`UserManualTests` fails when the committed HTML does not match the content file.

## Data and tests

In local development, accepted schedules, employee records, schedule locations,
and business configuration are stored in
`Schedule Creator\data\schedule_creator.sqlite3`. PostgreSQL is selected by
`SCHEDULE_CREATOR_DATABASE_URL`; tenant-owned tables use PostgreSQL row-level
security. Scheduling workspace preferences and generated schedules are saved
in the browser when browser storage is available; use the app's backup feature
to retain or move a workspace.

Run the Flask API tests from `Schedule Creator`:

```powershell
python -m unittest -v test_scheduler.py
```

The test module forces SQLite before running fixtures so the suite cannot
connect to the deployment PostgreSQL database loaded from `.env`. Run
PostgreSQL integration checks only with a disposable schema and an explicitly
isolated test harness.
