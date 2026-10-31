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
paste the key into source files, screenshots, or commits. Restart the Flask
server after changing the setting.

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

## Data and tests

Accepted schedules, employee records, and schedule locations are stored in
`Schedule Creator\data\schedule_creator.sqlite3`. Workspace settings and
generated schedules are saved in the browser when browser storage is available;
use the app's backup feature to retain or move a workspace.

Run the Flask API tests from `Schedule Creator`:

```powershell
python -m unittest -v test_scheduler.py
```
