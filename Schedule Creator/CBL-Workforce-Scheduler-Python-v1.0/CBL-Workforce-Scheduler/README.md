# CBL Workforce Scheduler — Python Web App v1.0

Requires Python 3.9 or later and a current Edge, Chrome or Firefox browser. No pip packages, Node.js or Excel installation required.

## Start
1. Extract the entire ZIP into a folder you can write to.
2. Windows: double-click Start-Windows.cmd. macOS/Linux: run `sh start.sh`.
3. Your normal browser opens the app. Keep the terminal open; Ctrl+C stops it.

Alternative: `python server.py` (or `python3 server.py`). Options: `--port 8766`, `--no-browser`, `--data-dir /path/to/private-data`.
Use the complete session URL printed by the launcher. It changes each launch. The app runs at 127.0.0.1 only; it cannot be accessed by other computers.

When this launcher is run from the Schedule Creator project folder, it detects and serves the current split `CBL-Scheduler2.html` app and its CSS, JavaScript and configuration assets. If the launcher is extracted by itself without those project files, it continues to serve the older bundled standalone app.

## Included features
All current scheduler features are retained: workbook uploads, common weeks and week commencing controls, locked settings, random constrained generation, time-off workbook fallback and BambooHR retrieval, overtime estimates, shift trades, schedule import/template, Excel exports, email draft preparation, Workforce Links and aligned Settings.
Python serves the app, forwards BambooHR time-off requests and saves the workspace transactionally in SQLite. The scheduling calculation remains in the browser JavaScript engine. This is a Python-hosted web app, not a rewrite of the allocation algorithm in Python.

## Saving and moving your work
Settings, source workbook cell values, imported schedules, time-off records and generated results are stored in `data/workspace.sqlite3` beside server.py. Source XLSX files are parsed into workspace data; their original binary files are not archived. Existing standalone browser storage is not automatically imported: export its JSON workspace backup, then restore that file in Source & backups in this app. Alternatively upload your source workbook again.
Stop the app before copying the database as a backup. You can also use workspace JSON backup or Settings > Save Portable HTML. Keep the whole extracted folder (including data) to retain work between launches. A version check prevents one tab silently overwriting another tab's newer save; if notified, back up that tab before reloading.
Portable ZIP exports contain the split app assets and use browser saving as before. Source workbook imports can browse Microsoft 365 files after the Entra app is configured; they remain read-only and do not write files back to SharePoint.

## Microsoft 365 source workbooks
The current split scheduler supports personal Microsoft accounts and work or school accounts. Sign-in requires the Entra registration's account type to include both organizational directories and personal Microsoft accounts, a Single-page application redirect URI matching the URI shown in the upload dialog, and the delegated Microsoft Graph `Files.Read` permission. Set the public Application (client) ID in `CBL-Scheduler2.config.js`; never put a client secret in the browser app.

The local launcher uses a redirect URI like `http://localhost:8765/CBL-MicrosoftAuth.html` (the dialog displays the exact URI, including a custom port). From a hosted deployment, use its HTTPS callback URI instead. `file://` is not supported for Microsoft sign-in. Personal accounts can browse their own files. Work or school accounts can search SharePoint sites with `Sites.Read.All`; tenant administrator consent may be required. The app downloads and validates only the workbook selected by the user. Microsoft access tokens are held in memory and are not saved to the workspace.

## BambooHR and email
Enter optional BambooHR API credentials in Your profile. Python makes HTTPS requests to the fixed CBL BambooHR time-off endpoint, avoiding browser CORS restrictions. Access still depends on API permissions and network connectivity. Credentials are not stored in the SQLite workspace, logs, backups or portable exports. They may be saved separately in this browser's IndexedDB, as in the HTML edition; use Remove saved API credentials on shared computers. Time-off records and employee data are stored unencrypted in the workspace database; restrict the folder to authorized users and use your organization's approved device protection.
Email still prepares a draft in the default client and one downloadable workbook to attach manually. It does not send mail automatically.

## Deployment scope
This is a local single-user app, not a multi-user network service. It has a per-launch session token and Host/Origin checks, but no organizational sign-in, user roles or enterprise audit trail. Do not change the binding to expose it to a network. A shared deployment needs IT-managed HTTPS hosting, authentication, permissions and deployment review.

## Tests
Run `python -m unittest test_server.py` from this folder. Tests use synthetic data and mock BambooHR; no real API calls are made.
