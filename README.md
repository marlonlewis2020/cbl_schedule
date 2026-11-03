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
owner to restore access. This deployment does not process membership billing.
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

Attendance uses accepted shifts in this app as its shift source. BambooHR
scheduled shifts cannot yet be selected: the existing integration's scheduling
POST adds shifts, and the BambooHR API operation for reading existing shifts
has not been verified. The Attendance page reports that comparison and
discrepancy resolution are unavailable rather than showing an empty
discrepancy list. The server rejects attempts to select BambooHR as the source,
so reconciliation cannot create duplicate shifts or imply an update succeeded.

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

Open **Developer change requests** from the app menu. On first use, create a
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
