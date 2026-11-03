"""Single source of truth for the CBL Schedule Creator user manual.

Edit this file whenever the app changes, add a REVISIONS entry, then run
`python build_user_manual.py` to regenerate docs/User-Manual.html and
docs/User-Manual.docx.

Block types: ("p", text) ("note", text) ("ul", [items]) ("ol", [items])
("table", [header...], [[row...], ...]) ("h3", text)
"""

MANUAL_TITLE = "CBL Schedule Creator User Manual"

REVISIONS = [
    ("2026-11-03", "Sidebar groups are collapsed by default and open one at a time when the group title is selected; Plan schedules is the second-to-last group."),
    ("2026-11-03", "Expanded notification details now include the shift time (start)."),
    ("2026-11-03", "Notification bell: the list pops up below the bell and can be closed; unread alerts are highlighted, selecting one expands its details and marks it read (shown pale)."),
    ("2026-11-03", "Removed the Print / PDF button; moved Upload source from the header to Settings; the temporary MFA bypass now also applies to manager accounts."),
    ("2026-11-03", "Manager and employee access: admin-created manager/employee accounts with temporary passwords, /access sign-in (MFA for managers), location-scoped manager attendance with mark-absent, employee own-attendance view, and in-app late/absent notification bells."),
    ("2026-11-03", "Attendance page: sections above the attendance tables are collapsible and start collapsed; both attendance tables sort by clicking a column heading; row actions use the same button style as the Employees table."),
    ("2026-11-03", "Attendance: BambooHR scheduled-shift read fix (numeric BambooHR IDs only, literal commas, whole-second end time) for HTTP 422 responses."),
    ("2026-11-03", "Attendance: shift source selection (app or BambooHR), discrepancy list and reasoned two-way reconciliation with audit records."),
    ("2026-11-03", "Initial user manual."),
]

SECTIONS = [
    {
        "id": "introduction",
        "title": "1. Introduction",
        "blocks": [
            ("p", "The CBL Schedule Creator is a local web application for configuring workforce requirements, generating and reviewing weekly employee schedules, managing employees and BambooHR schedule locations, tracking attendance, and publishing accepted shifts to BambooHR."),
            ("h3", "Requirements"),
            ("ul", ["Windows", "Python 3.9 or later", "Google Chrome", "Network access to the configured database (PostgreSQL deployments) and to BambooHR for integration features"]),
        ],
    },
    {
        "id": "starting",
        "title": "2. Starting the app and signing in",
        "blocks": [
            ("h3", "Start the app"),
            ("ol", [
                "Install dependencies once: open a terminal in the Schedule Creator folder and run python -m pip install -r requirements.txt.",
                "Double-click Start-Schedule-Creator.bat. It starts the server on 127.0.0.1:5001, waits for the authentication API to respond, and opens the app in Chrome.",
                "If Chrome does not open, browse to http://127.0.0.1:5001/.",
            ]),
            ("note", "If the window reports that the API did not respond, read the server window for the startup error. A database connection timeout means the configured database host is unreachable. If port 5001 is already in use, close the other server first."),
            ("h3", "First-time administrator setup"),
            ("ol", [
                "On first launch, from the computer running the app, create the initial administrator with a unique password of at least 14 characters.",
                "Enroll an authenticator app using the displayed setup secret and verify the current six-digit code. Multi-factor authentication is mandatory.",
            ]),
            ("h3", "Signing in"),
            ("p", "At each sign-in, enter the BambooHR subdomain of the business, the administrator email, the password and the authenticator code. The same email can administer several businesses; passwords and MFA are managed separately for each business. Use Sign out in the application header when finished."),
        ],
    },
    {
        "id": "navigation",
        "title": "3. Finding your way around",
        "blocks": [
            ("p", "The sidebar groups the pages. All groups start collapsed; select a group title to show its pages, which collapses any other open group. Controls & lock, Weekly schedules and Settings are always available; other pages can be hidden or shown in Settings."),
            ("table", ["Group", "Pages"], [
                ["Workspace", "Overview"],
                ["People", "Employees, Schedule locations, Attendance"],
                ["Integrations", "Publish to BambooHR, Workforce Links"],
                ["Plan schedules", "Location roles, Roster settings, Controls & lock, META · operating days, Weekly schedules"],
                ["Data & settings", "Source & backups"],
            ]),
            ("note", "Features such as employee schedule access, shift trades, schedule history and overtime forecasting depend on the business membership tier (see section 8)."),
        ],
    },
    {
        "id": "workflow",
        "title": "4. Scheduling workflow at a glance",
        "blocks": [
            ("ol", [
                "Configure location × role pools, shift starts and demand shares (Location roles).",
                "Set each employee's availability for every shift start (Roster settings).",
                "Set the scheduling controls and lock the configuration (Controls & lock).",
                "Generate schedules, or upload completed schedules, then review coverage, constraints and time-off warnings (Weekly schedules).",
                "Accept schedules to save them in the app database. Accepted schedules can be reviewed later, and acceptance can be undone.",
                "Preview and publish selected accepted shifts to BambooHR (Publish to BambooHR).",
                "Track clock-ins against the accepted shifts (Attendance).",
            ]),
        ],
    },
    {
        "id": "pages",
        "title": "5. Page guide",
        "blocks": [],
        "subsections": [
            {
                "id": "overview",
                "title": "5.1 Overview",
                "blocks": [
                    ("p", "Shows configuration status, the latest saved schedule review, overtime and warehouse capacity planning (when your tier includes it) and model notes. Use it to see what still needs attention before generating schedules."),
                ],
            },
            {
                "id": "location-roles",
                "title": "5.2 Location roles",
                "blocks": [
                    ("p", "Choose which location × role pools are scheduled and add or remove possible shift start times for each pool."),
                    ("ul", [
                        "A new shift start begins with a 0% share. Allocate its share on this page.",
                        "The shift end is determined automatically from the shift duration set in Controls & lock.",
                        "After adding a start, set each employee's availability for it in Roster settings.",
                    ]),
                ],
            },
            {
                "id": "roster",
                "title": "5.3 Roster settings",
                "blocks": [
                    ("p", "Set each employee's constraints within their location-role pool: flexibility, reason if unavailable, preferred start, proximity and random rankings (1–3), attendance score (0–100), daily availability and availability for every configured shift start."),
                    ("note", "Inactive employees remain visible but are excluded from schedules."),
                ],
            },
            {
                "id": "controls",
                "title": "5.4 Controls & lock",
                "blocks": [
                    ("p", "Define the generation controls: the first Monday, paid hours per shift, elapsed shift span, minimum rest and related rules. Review the Resolved controls preview, then lock the configuration. Generation advances the week by seven days and selects each enabled pool automatically."),
                    ("ol", ["Review the configuration checks. Blocking issues must be fixed before you can lock.", "Lock the configuration.", "Select Generate schedules."]),
                ],
            },
            {
                "id": "meta",
                "title": "5.5 META · operating days",
                "blocks": [
                    ("p", "Define how each location works: daily operating intensity per location. Intensities are normalised across open days. A closed day receives no demand or make-up shifts; you may explicitly enter 0 for a closed day."),
                ],
            },
            {
                "id": "weekly",
                "title": "5.6 Weekly schedules",
                "blocks": [
                    ("p", "Lists every saved schedule, by pool and week, with demand coverage, supplemental shifts and employee target shortfalls."),
                    ("h3", "Common actions"),
                    ("ul", [
                        "Generate schedules or Refresh & shuffle all: each generation uses fresh randomness. Undo last shuffle restores the previous result.",
                        "Accept a schedule to save it to the database. Previously accepted shifts can be viewed later; Undo accept removes only the accepted copy.",
                        "Click a shift to change it manually using the options configured in Settings.",
                        "Upload schedules · XLSX imports completed schedules; Download schedule template provides the format. Empty shift cells are OFF.",
                        "View time-offs or Upload time-offs · XLSX to review leave that affects scheduling.",
                        "Trade shifts swaps shifts between employees (requires exactly five shifts each; Silver tier and above).",
                        "Email schedules creates confirmation drafts for each schedule location's manager. Attach the downloaded workbook before sending. The app never sends email itself.",
                        "Download filtered or all schedules (XLSX) or a combined CSV.",
                    ]),
                ],
            },
            {
                "id": "employees",
                "title": "5.7 Employees",
                "blocks": [
                    ("p", "A directory of BambooHR and manually added employees."),
                    ("ul", [
                        "Refresh BambooHR employees imports the active roster. New records start inactive until their app location, role and roster availability are reviewed. Existing mappings are kept; employees missing from BambooHR become locally inactive. Conflicts with manual records need an explicit same-person / different-people decision.",
                        "Filter by location and role. Select all selects only the employees currently shown.",
                        "Assign a role from the row or in a batch. Changing a role deactivates the employee until the roster profile is reviewed.",
                        "Add manual employee creates a record with a generated MANUAL-… ID. Manual employees are never published to BambooHR and are the only employees that can be deleted.",
                        "Row actions: Edit, Roster settings / Complete profile, Make active / Make inactive, and Delete (manual employees only).",
                    ]),
                    ("note", "Active/inactive status in this app is local and does not update BambooHR."),
                ],
            },
            {
                "id": "schedule-locations",
                "title": "5.8 Schedule locations",
                "blocks": [
                    ("p", "Map each app location to one BambooHR schedule ID, set the confirmation manager's name and email, and assign employees. An employee can belong to only one schedule location. A schedule location with employees assigned cannot be deleted. Confirmation emails are addressed to the location's manager and include only that site's schedules."),
                ],
            },
            {
                "id": "attendance",
                "title": "5.9 Attendance",
                "blocks": [
                    ("p", "Tracks BambooHR clock-ins against shifts. The page syncs BambooHR time tracking and approved time off while open and rechecks every five minutes. Absences are classified automatically four hours after shift start. Clock entries count as evidence even if awaiting BambooHR approval; approved leave is excluded from absence classification and the score denominator."),
                    ("h3", "Collapsible sections"),
                    ("p", "BambooHR attendance sync, Attendance shift source, Unresolved BambooHR shift discrepancies (BambooHR source only), Attendance filters and Attendance rules start collapsed. Click a section title to expand or collapse it. Your choices are remembered while you stay on the page. The two tables (Attendance and Attendance scores) are always visible."),
                    ("h3", "BambooHR attendance sync"),
                    ("p", "Select Sync selected period to fetch time tracking and leave for the selected period (historical selections fetch up to 365 inclusive days). Polling pauses while the browser tab is hidden or closed."),
                    ("h3", "Attendance shift source"),
                    ("ul", [
                        "Accepted shifts in this app (default): attendance is measured against accepted schedules saved here.",
                        "BambooHR shifts: the app reads BambooHR scheduled shifts for the selected period. You are asked to confirm the switch. BambooHR clock events remain the attendance evidence in both modes.",
                    ]),
                    ("h3", "Unresolved BambooHR shift discrepancies"),
                    ("p", "When BambooHR is the source, differences between BambooHR shifts and accepted app shifts are listed by date and employee. For each, an administrator can:"),
                    ("ul", [
                        "Use app shift: adds the app shift to BambooHR, then deletes the single-employee BambooHR shift it replaces.",
                        "Use BambooHR shift: updates the accepted app schedule to match BambooHR.",
                    ]),
                    ("p", "Each resolution requires confirmation and a reason (1–500 characters), is rechecked against live BambooHR data before any change, and is audited. BambooHR does not make add-then-delete transactional; if only one step succeeds, the app reports a partial result. Refresh before retrying. Shared multi-employee BambooHR shifts and shifts with a different duration, conflicting mapping or several shifts per employee-day cannot be resolved individually."),
                    ("h3", "Attendance filters"),
                    ("p", "Choose Single day or Month range, then optionally filter by location and role. Month ranges include all recorded shifts from the first month through the last; sync the period first if it has not been fetched."),
                    ("h3", "Attendance rules"),
                    ("p", "Set the lateness tolerance (minutes) and the attendance score period (30–45 days), then Save attendance rules."),
                    ("h3", "Attendance table"),
                    ("p", "Shows date, employee, location, role, shift start, clock-in, status, reason and actions. Click any column heading except Actions to sort; click again to reverse. ▲ means ascending and ▼ descending. Blank values always sort last."),
                    ("ul", ["Correct changes a shift's status (an auditable correction with a required reason)."]),
                    ("h3", "Attendance scores table"),
                    ("p", "Shows each active employee's attended / scheduled shifts, the Calculated score (attended ÷ scheduled), and the Effective score. All columns except Actions are sortable."),
                    ("ul", [
                        "Set override replaces the effective score with a value from 0 to 100 and requires a reason (1–500 characters). The row shows a Manual override badge.",
                        "Remove override (inside the same dialog) restores the calculated score.",
                        "Overrides apply per employee until removed, do not change shift records, and every change is audited with the previous value, new value, reason and administrator.",
                    ]),
                ],
            },
            {
                "id": "publish",
                "title": "5.10 Publish to BambooHR",
                "blocks": [
                    ("ol", [
                        "Check the BambooHR connection (Refresh server status).",
                        "Under Select accepted shifts, choose shifts from accepted schedules.",
                        "Select Preview BambooHR changes. Nothing is posted at this step.",
                        "Select Continue to publish confirmation, then Confirm and post to BambooHR.",
                        "Review Publishing results.",
                    ]),
                    ("note", "Publishing sends changes to BambooHR. Manual employees are never published. The API key stays on the server."),
                ],
            },
            {
                "id": "links",
                "title": "5.11 Workforce Links",
                "blocks": [("p", "A list of shared workbooks, HR tools and documentation links that open in a new browser tab.")],
            },
            {
                "id": "source",
                "title": "5.12 Source & backups",
                "blocks": [
                    ("ul", [
                        "Upload source replaces the configuration basis with a pre-filled workbook. During import the app pauses for a mapping review: confirm the app location, role and optional schedule location for every employee. Unknown employees are added only if you choose Add manually, and they start inactive.",
                        "Download workspace backup and Restore backup save and restore the workspace.",
                        "Download configured inputs · XLSX exports the current inputs.",
                    ]),
                    ("note", "Saved schedules retain the source settings they were generated with."),
                ],
            },
            {
                "id": "settings",
                "title": "5.13 Settings",
                "blocks": [
                    ("ul", [
                        "Business branding: business name, team name (default Schedule Management), logo (PNG/JPEG/WebP up to 2 MB), colours and the BambooHR tenant ID. Branding appears throughout the app and in the email signature.",
                        "BambooHR API key: Test key for saved tenant runs a read-only check. Use as app API key explicitly promotes a successfully tested key to the server.",
                        "Business membership & administrators: view the tier and manage administrators (see section 8).",
                        "Manager & employee access: create manager and employee sign-in accounts, reset passwords (optionally MFA) and disable or enable accounts (see section 5.14).",
                        "Upload source (also available here, no longer in the page header): replaces the configuration basis with a pre-filled workbook; see Source & backups for the mapping review.",
                        "Sidebar menu: show or hide pages. This is a preference, not a security boundary.",
                        "Schedule email: the fixed Cc to the workforce mailbox can be switched off, and additional non-working dates (one YYYY-MM-DD per line) can be added. Deadlines exclude the sending day, weekends and the listed dates (Jamaica time).",
                        "Workspace file: Download Portable ZIP Bundle exports configuration and saved schedules. API credentials are excluded; treat the bundle as confidential.",
                        "Overtime planning (Gold and above): overtime forecasting and warehouse FTE volume capacity.",
                    ]),
                ],
            },
            {
                "id": "access",
                "title": "5.14 Manager and employee access",
                "blocks": [
                    ("p", "Managers and employees sign in at /access (for example http://127.0.0.1:5001/access) with the BambooHR subdomain, their email (managers) or email/employee ID (employees) and password. Administrators keep signing in on the main page."),
                    ("h3", "Creating accounts (administrators)"),
                    ("ol", [
                        "Open Settings → Manager & employee access.",
                        "Choose Manager or Employee, enter the name, and an email (required for managers). For employees choose the active employee; employee accounts require the Silver tier or above.",
                        "Select Create account. A temporary password is shown once; share it securely. It expires after 72 hours.",
                        "Use Reset password (or Reset password & MFA) if it is lost, and Disable to end an account's access immediately.",
                    ]),
                    ("note", "A manager sees only employees at schedule locations whose manager email matches the manager's email (set on the Schedule locations page). An account with no matching location shows 'no matching schedule location'."),
                    ("h3", "Managers"),
                    ("ul", [
                        "At first sign-in the manager replaces the temporary password (at least 14 characters) and enrols an authenticator app. MFA is mandatory for managers; later sign-ins need the six-digit code (unless the temporary MFA bypass is enabled on the server).",
                        "The attendance table shows the last 30 days for the manager's own employees. Mark absent is offered for late shifts and needs a reason; it is audited.",
                        "The bell shows the unread count of late and absent alerts for the manager's employees and refreshes every 30 seconds. Select the bell to open a list below it and Close to hide it. Unread alerts are highlighted in amber; select one to expand its details (status, employee, location, shift date, time detected) and it turns pale as read. Mark all read clears the count for that manager only. Alerts appear only in the app; no email is sent.",
                    ]),
                    ("h3", "Employees"),
                    ("p", "Employees replace the temporary password at first sign-in (no MFA) and then see only their own attendance for the last 30 days with a status summary."),
                    ("h3", "Administrator bell"),
                    ("p", "The bell in the app header shows unread late and absent alerts for the whole business, with its own read state, and refreshes every 30 seconds. It works like the manager bell: the list opens below the bell, can be closed, highlights unread alerts, and expands an alert's details when selected, after which it shows pale."),
                ],
            },
        ],
    },
    {
        "id": "bamboohr",
        "title": "6. BambooHR integration notes",
        "blocks": [
            ("ul", [
                "The server reads BAMBOOHR_API_KEY from its environment configuration. Never paste the key into screenshots, chat or source files. If a key is exposed, revoke it in BambooHR and configure a replacement through the app's secured settings.",
                "Time-off data is fetched when generating or refreshing schedules. If the key is missing or BambooHR cannot be reached, scheduling continues without it and the schedule is marked for review.",
                "Saving a different tenant changes the tenant used by all future time-off, attendance and publishing requests.",
            ]),
        ],
    },
    {
        "id": "business",
        "title": "7. Business Hub and business account",
        "blocks": [
            ("p", "Multi-business registration, membership approval and tenant account management are available through the Business Hub (/hub). The main business administrator can view the membership at /business, change tier, and pause, resume or cancel membership. Actions take effect immediately, require confirmation and are audited. Cancellation retains data and requires the platform owner to restore access. No billing is processed by this deployment."),
        ],
    },
    {
        "id": "tiers",
        "title": "8. Membership tiers",
        "blocks": [
            ("table", ["Tier", "Admin seats", "Teams", "Active employees", "Locations"], [
                ["Bronze", "2", "2", "20", "2"],
                ["Silver", "3", "4", "60", "4"],
                ["Gold", "4", "Unlimited", "Unlimited", "6"],
                ["Platinum", "8", "Unlimited", "Unlimited", "Unlimited"],
            ]),
            ("ul", [
                "Included in every tier: schedule generation, sharing, BambooHR publishing, email configuration, employee management and settings.",
                "Silver and above: employee schedule access, shift trades and schedule history.",
                "Gold and above: overtime forecasting.",
                "Downgrades never delete data. Existing over-limit usage is kept, but new additions that exceed the tier are blocked until usage falls within limits.",
            ]),
        ],
    },
    {
        "id": "developer",
        "title": "9. Developer change requests",
        "blocks": [
            ("p", "The Developer change requests page records the product roadmap. First use creates a developer username and a unique password of at least 14 characters from the computer running the app. The page supports sign-in, credential updates, status filters and dependency checks. It does not launch agents or change code."),
        ],
    },
    {
        "id": "troubleshooting",
        "title": "10. Troubleshooting",
        "blocks": [
            ("table", ["Symptom", "What to check"], [
                ["\"The updated Schedule Creator API did not respond\" when starting", "Read the server window. A ConnectionTimeout means the PostgreSQL host is unreachable: restore network access. Do not switch to SQLite for production data."],
                ["Port 5001 already in use", "Close the other server or process using port 5001."],
                ["BambooHR scheduled-shifts request failed with HTTP 422", "Refresh the attendance page and retry. The app now queries only numeric BambooHR employee IDs and sends a valid time range. If it persists, report the exact message."],
                ["Time-off data missing from a schedule", "The BambooHR key is missing or BambooHR was unreachable. Check Settings > BambooHR API key and review the schedule carefully."],
                ["Attendance discrepancy cannot be resolved", "It may be stale (refresh), shared by several employees, or have a different duration or mapping than the app supports. Adjust in BambooHR or the app manually."],
                ["A page is missing from the sidebar", "It may be hidden in Settings > Sidebar menu, or the tier may not include it."],
            ]),
        ],
    },
    {
        "id": "testing",
        "title": "11. Running on SQLite for testing",
        "blocks": [
            ("p", "When SCHEDULE_CREATOR_DATABASE_URL is empty the app uses SQLite at data\\schedule_creator.sqlite3. This is suitable for testing, but it is a separate data set from PostgreSQL, has no row-level tenant isolation, and has no BambooHR credentials until you enter them. Do not use it for production data."),
        ],
    },
    {
        "id": "security",
        "title": "12. Security and data handling",
        "blocks": [
            ("ul", [
                "Keep the data folder, flask_secret.key and mfa_encryption.key private and back them up with the database. Losing the MFA key prevents existing authenticator secrets from being decrypted.",
                "Exported bundles and backups contain confidential workforce data.",
                "Sign out from the header when finished.",
            ]),
        ],
    },
    {
        "id": "maintaining",
        "title": "13. Keeping this manual current",
        "blocks": [
            ("p", "Every change to the app that affects what users see or do must update this manual in the same change:"),
            ("ol", [
                "Edit user_manual_content.py (relevant section, plus a new REVISIONS entry with the date and a one-line description).",
                "Run python build_user_manual.py to regenerate docs/User-Manual.html and docs/User-Manual.docx.",
                "Run the test suite; it fails if the committed HTML is out of date.",
            ]),
        ],
    },
]
