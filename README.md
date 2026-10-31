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

The batch file starts the server on `127.0.0.1:5001`, checks that the current
app's employee API is responding, and opens the app in Chrome. If port 5001 is
already occupied, close the other server before starting this one. The app is
available at <http://127.0.0.1:5001/>.

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

## Data and tests

Accepted schedules, employee records, schedule locations, and business
configuration are stored in `Schedule Creator\data\schedule_creator.sqlite3`.
Scheduling workspace preferences and generated schedules are saved in the
browser when browser storage is available; use the app's backup feature to
retain or move a workspace.

Run the Flask API tests from `Schedule Creator`:

```powershell
python -m unittest -v test_scheduler.py
```
