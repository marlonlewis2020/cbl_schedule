"""Single source of truth for the CBL Schedule Creator user manual.

Edit this file whenever the app changes, add a REVISIONS entry, then run
`python build_user_manual.py` to regenerate docs/User-Manual.html and
docs/User-Manual.docx.

Block types: ("p", text) ("note", text) ("ul", [items]) ("ol", [items])
("table", [header...], [[row...], ...]) ("h3", text)
"""

MANUAL_TITLE = "CBL Schedule Creator User Manual"

REVISIONS = [
    ("2026-11-13", "Business branding now supports a report-only light/dark theme and two supporting images; new offline HTML captures freeze the saved name, logo, colors, theme and images."),
    ("2026-11-13", "Added role-scoped Help and knowledge base with searchable FAQs/glossary, manager location-scoped submissions, administrator review, feedback and published revision history."),
    ("2026-11-05", "Trade cards and before/after shift previews follow light/dark themes. Both employees must finish the selected week with at least five shifts; other scheduling violations become explicit warnings requiring both employees, manager and administrator acknowledgement. Manual assignment overrides remain separate."),
    ("2026-11-05", "Billing navigation and setup checklist; tier feature dropdowns replace JSON entry, business selectors and Jamaica date/time controls simplify manual credits, and subscription status/history are displayed in readable fields."),
    ("2026-11-05", "Restored the previous access/hub/inbox appearance and administrator light/dark palettes. Shared trade styles are scoped to the popup, which follows the administrator's selected theme; trade and schedule-selection functionality is unchanged."),
    ("2026-11-05", "Trade popup with scoped team/week/employee dropdowns, combined multi-day checkbox swaps, and both employees' reduced-rest acknowledgements. Employee schedule selection and code-driven selection; access and hub use administrator palette, cards and controls."),
    ("2026-11-05", "Linked manager personal views; authenticated, audited trade inbox and administrator publishing/overrides; disabled-by-default PayPal sandbox billing with hosted checkout, verified webhooks, reminders and a separate retry worker. Live payment and production BambooHR validation remain outstanding."),
    ("2026-11-04", "Manager confirmation email location dropdown populates on opening and updates with selected schedules; missing location/manager configuration errors are shown immediately."),
    ("2026-11-04", "Roster validation now checks availability for configured shift starts instead of stale legacy permissions. Missing values identify the shift time; configured-input exports include current permissions and custom-start tables."),
    ("2026-11-04", "Schedule portal: accepted team schedules at /access, expiring six-digit period codes in manager email drafts, configurable visibility (default four weeks), and employee read-only team attendance counts."),
    ("2026-11-03", "Notifications can be removed with ✕; removed items move to a per-user archive viewable with View archives at the bottom of the list (admin and manager)."),
    ("2026-11-03", "Attendance validation: a shift is attended only if the timesheet covers at least 60 minutes of it; early departures are recorded and notify the manager; overtime beyond the shift end is highlighted on the admin and manager attendance tables."),
    ("2026-11-03", "Manager and employee attendance tables now show a Shift time (start) column."),
    ("2026-11-03", "Manager attendance page: added From/To date filters that default to today."),
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
            ("p", "Use the shared sign-in page to choose Business administrator, Manager / employee or Platform owner. Enter the business subdomain for business/workforce accounts. Password replacement and authenticator enrollment/verification use the existing account rules; account identities are not merged. Initial local administrator setup remains linked from sign-in."),
            ("p", "At each sign-in, enter the BambooHR subdomain of the business, the administrator email, the password and the authenticator code. The same email can administer several businesses; passwords and MFA are managed separately for each business. Use Sign out in the application header when finished."),
        ],
    },
    {
        "id": "navigation",
        "title": "3. Finding your way around",
        "blocks": [
            ("p", "The sidebar groups the pages. All groups start collapsed; select a group title to show its pages, which collapses any other open group. Controls & lock, Weekly schedules and Settings are always available; other pages can be hidden or shown in Settings."),
            ("p", "Access, Shift Trades and Business now share application navigation, business branding, light/dark themes and scoped alerts. The administrator sidebar links to Trade approvals, Business and authorized Billing. Workforce users see My workspace and Shift trades; linked managers explicitly select Personal view or Management view. Platform owners keep their separate cross-business experience. Existing links remain valid and the administrator workspace stays at its original address, preserving saved browser data."),
            ("p", "All signed-in roles, including platform owners and developers, expire after 15 minutes without reported user interaction and at most eight hours after successful sign-in. The app warns during the final minute; Stay signed in renews an idle session but cannot extend the eight-hour limit. Genuine interaction is reported at most every 30 seconds. Activity in another tab shares the same server session clock; notification/attendance polling, refreshes and background tasks never count as activity. After expiry, protected views are cleared and normal sign-in/MFA is required. Save edits before the warning expires: unsaved forms may be lost, while persisted workspace data is retained. Sessions created before this upgrade require a new sign-in."),
            ("p", "Data & settings (Source & backups and META operating days) is available only to the designated primary business administrator. The separate Settings page remains available to other business administrators. Source uploads and portable-workspace exports duplicated in Settings follow the same primary-admin restriction. Ordinary scheduling, schedule downloads and sharing are unchanged."),
            ("table", ["Group", "Pages"], [
                ["Workspace", "Overview"],
                ["People", "Employees, Schedule locations, Attendance, Help & knowledge base"],
                ["Integrations", "Publish to BambooHR, Workforce Links"],
                ["Plan schedules", "Location roles, Roster settings, Controls & lock, Weekly schedules"],
                ["Data & settings", "Source & backups, META · operating days (primary administrator only)"],
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
                    ("p", "Each configured shift start must have availability 0 (No) or 1 (Yes). A Missing selection remains incomplete and the warning names the shift time. New shift starts default to No; completing the visible fields clears validation even when old workbook permission values were incomplete. Configured-input XLSX snapshots include Shift availability and Configured shift starts tables; use workspace JSON backups for exact reimport, including custom starts."),
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
                    ("p", "Open Data & settings → META operating days as the primary business administrator. Opening this page and editing a calendar require current server authorization; configuration must be unlocked before editing. Existing operating days and intensity values are preserved, and all administrators can continue generating schedules from those values. Like other workspace configuration, these calendars remain browser-resident; supported-workflow permissions do not prevent extraction or tampering through browser developer tools."),
                    ("p", "Define how each location works: daily operating intensity per location. Intensities are normalised across open days. A closed day receives no demand or make-up shifts; you may explicitly enter 0 for a closed day."),
                ],
            },
            {
                "id": "weekly",
                "title": "5.6 Weekly schedules",
                "blocks": [
                    ("p", "Lists every saved schedule, by pool and week, with demand coverage, supplemental shifts and employee target shortfalls."),
                    ("p", "The Saved schedule register scrolls vertically when it contains more than six records, with a sticky header and keyboard-focusable scrolling region. Administrators can select Delete on a record and confirm browser-workspace-only deletion. The selected workspace copy is removed only after browser storage succeeds; accepted database copies, BambooHR shifts and existing audit history are retained. Working persistent browser storage is required. The server audits authorization and the workspace records completed deletion. Related selectors and stale email preparation refresh, and shuffle undo is cleared so it cannot resurrect the deleted schedule. Backups exported earlier remain separate copies and restoring one can restore its schedules."),
                    ("h3", "Common actions"),
                    ("ul", [
                        "Generate schedules or Refresh & shuffle all: each generation uses fresh randomness. Undo last shuffle restores the previous result.",
                        "Accept a schedule to save it to the database. Previously accepted shifts can be viewed later; Undo accept removes only the accepted copy.",
                        "Click a shift to change it manually using the options configured in Settings.",
                        "Upload schedules · XLSX imports completed schedules; Download schedule template provides the format. Empty shift cells are OFF.",
                        "View time-offs or Upload time-offs · XLSX to review leave that affects scheduling.",
                        "Trade shifts opens the authenticated popup for accepted schedules (Silver and above by default). Use Open approvals inbox for approvals and publishing. Workspace-only trades cannot bypass approval.",
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
                    ("p", "Worked-time validation: a shift counts as attended only when the timesheet covers at least 60 minutes of the scheduled shift (or the whole shift if it is shorter). Overnight timesheets are compared against the real shift date and time, so time carried over from the previous night does not count toward the next shift. If the timesheet overlaps by less than 60 minutes, the shift is marked absent with the reason 'Timesheet covers only N minutes of the shift'. While someone is still clocked in and has not yet reached 60 minutes, the shift stays scheduled. Working at least 60 minutes but not the full shift still counts as attended and is noted as partial."),
                    ("p", "Early departure and overtime: when the last clock-out is more than 60 minutes before the shift end, the minutes left early are recorded, appear in the Reason column and the clock-in cell, and a 'Left early' notification is sent to the location manager and the admin. When the employee works more than 60 minutes past the shift end, the row is highlighted amber with '+N min past shift end' on both the admin Attendance page and the manager attendance page. A clock-out is treated as an early departure only once the shift has ended or the employee has been out for an hour, so short breaks are not reported."),
                    ("h3", "Collapsible sections"),
                    ("p", "Each table on the administrator Attendance page has a Download Excel button, including attendance records, scores, shift discrepancies and report histories. It exports the displayed rows in their current filtered/sorted order, omitting selection and action controls. Empty tables export their column headings."),
                    ("p", "BambooHR attendance sync, Attendance shift source, Unresolved BambooHR shift discrepancies (BambooHR source only), Attendance filters and Attendance rules start collapsed. Click a section title to expand or collapse it. Your choices are remembered while you stay on the page. The two tables (Attendance and Attendance scores) are always visible."),
                    ("h3", "BambooHR attendance sync"),
                    ("p", "Select Sync selected period to fetch time tracking and leave for the selected period (historical selections fetch up to 365 inclusive days). Polling pauses while the browser tab is hidden or closed."),
                    ("h3", "Historical weekly and monthly reports"),
                    ("p", "New historical HTML reports use the snapshot-style executive overview: four KPI cards with DC and role comparison charts/tables. Detailed employee comparisons, patterns and shift evidence remain hidden until an employee or both a Distribution Centre and role are selected. Select chart labels/table rows or filters to drill down; Clear filters restores the overview. The active scope is always displayed. Print / Save PDF respects the selected view. New HTML reports capture saved branding, report theme and supporting images; saved reports are unchanged and Excel retains full detail."),
                    ("p", "Administrators and managers can generate historical Excel and interactive HTML reports from their attendance views. Weeks start Monday in America/Jamaica; monthly reports cover previous months. Admins can restrict location and role; managers see only currently authorized teams and records attributed to those teams in the reporting period. Saved historical report history is separate from point-in-time snapshot history and is not removed by snapshot deletion."),
                    ("p", "Reports compare the selected period with the preceding week/month and list employee/DC attendance, incident counts and dates. Pattern analysis uses the selected period only and needs at least three eligible shifts per pattern. Missing history or assignment evidence is unavailable, not zero. Missing schedules never prove days off. Patterns are observed associations, not causes or automatic disciplinary recommendations. Share report copies only with authorized recipients."),
                    ("h3", "Attendance snapshot downloads"),
                    ("p", "Select individual snapshots or use Select all deletable snapshots, then Delete selected. Confirm the batch to remove saved HTML/XLSX and visible history; underlying attendance and schedules remain unchanged. Running captures cannot be deleted. Deletion is audited and minimal run keys remain to prevent regeneration of scheduled cutoffs. Downloaded or emailed copies cannot be recalled."),
                    ("p", "Generate email body creates an executive subject, formatted preview and plain-text body from the selected snapshot's saved evidence, with location/role summaries and source warnings. Copy the subject and desired body, or manually select/copy text if browser clipboard support is unavailable, then attach the downloaded HTML yourself. No email is sent."),
                    ("p", "On Silver and above, Capture now refreshes BambooHR and saves immutable HTML and XLSX snapshots. Refresh history lists ready, stale, failed and missed captures, with View HTML, Download HTML and Download XLSX for available reports. Stale source explicitly means the source refresh failed or overnight boundaries were unavailable; inspect the warning and freshness timestamp. Workbooks include blue location/role/shift summaries and employee clock details; late names are amber and absent names red. Future shifts are excluded; approved leave is excluded from the denominator. The reporting day's shifts include verified overnight carry-in."),
                    ("p", "The interactive HTML dashboard presents executive KPI cards first, location/role/shift charts and summaries next, then employee exceptions and operational attention. Filter by location, role, Jamaica shift-start time, attendance status or employee/reason search; select chart groups to drill down, sort employee columns, reset filters or use Print / Save PDF. Exceptions only changes the detail register, not executive metrics. Confirmed attendance distinguishes matching clock-ins from worked-time validation: a late record without a matching punch or the required worked time is not confirmed. No expected shifts shows N/A. Missing punches and absences overlap; do not add them. Counts are shift records, not unique people or demand forecasts."),
                    ("p", "New captures embed the saved business name, logo, colors, report theme and up to two supporting images, with all data, charts and image assets included for offline use. Later branding changes do not rewrite a captured report. Older snapshots show only their saved evidence, without adding current branding. Downloaded reports contain employee information: share only with authorized recipients. Offline copies cannot be revoked when your app session expires."),
                    ("p", "The primary administrator may enable captures at 7 AM, 3 PM and 11 PM Jamaica time. Run Run Attendance Reports Worker.bat separately with the same database/environment as the app and use a supervisor for continuous deployment. The worker runs without a browser, exposes a last-seen heartbeat and records missed cutoffs rather than backfilling later evidence. Wait one minute between on-demand requests. Automatic email, recipient lists and delivery are deferred; no messages are sent. Staffing-vs-demand interval analytics remain separate Gold/Platinum work."),
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
                    ("note", "Saved schedules retain the source settings they were generated with. Source imports and mapping approvals, restores, workspace backups, configured-input downloads and portable bundles require fresh online primary-administrator authorization for the current business; failed checks leave the workspace unchanged. These are restrictions on supported workflows, not protection against extracting configuration already available in your browser for ordinary scheduling. Existing browser data and previously exported backups are not removed or remotely secured."),
                ],
            },
            {
                "id": "settings",
                "title": "5.13 Settings",
                "blocks": [
                    ("ul", [
                        "Business branding: business name, team name (default Schedule Management), logo (PNG/JPEG/WebP up to 2 MB), primary/accent colours, BambooHR tenant ID, a light/dark theme for generated reports, and up to two supporting report images (PNG/JPEG/WebP up to 2 MB each). These report settings are separate from your personal app theme. New HTML reports embed the saved settings for offline use; changes apply to future reports only.",
                        "BambooHR API key: Test key for saved tenant runs a read-only check. Use as app API key explicitly promotes a successfully tested key to the server.",
                        "Business membership & administrators: view the tier and manage administrators (see section 8).",
                        "Manager & employee access: create manager and employee sign-in accounts, reset passwords (optionally MFA) and disable or enable accounts (see section 5.14).",
                        "Upload source (primary administrator only, also available here): replaces the configuration basis with a pre-filled workbook; see Source & backups for the mapping review.",
                        "Sidebar menu: show or hide pages. This is a preference, not a security boundary.",
                        "Schedule email: the fixed Cc to the workforce mailbox can be switched off, and additional non-working dates (one YYYY-MM-DD per line) can be added. Deadlines exclude the sending day, weekends and the listed dates (Jamaica time).",
                        "Workspace file (primary administrator only): Download Portable ZIP Bundle exports configuration and saved schedules. API credentials are excluded; treat the bundle as confidential.",
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
                        "To correct an account's role, select Change role in its Actions column. Choose Manager or Employee, provide a valid manager email or active employee link as required, then confirm Save role change. This preserves the account ID, password, name, history and enabled/disabled state and revokes existing sessions. Duplicate accounts are not merged. Managers must enroll/use MFA and only manage locations matching their email; employee access and manager personal links require an eligible membership. Existing enrolled MFA is retained for future manager use. Role correction does not change the employee's scheduling/job role or location assignment.",
                    ]),
                    ("note", "A manager sees only employees at schedule locations whose manager email matches the manager's email (set on the Schedule locations page). An account with no matching location shows 'no matching schedule location'."),
                    ("h3", "Scheduled managers: one account, two views"),
                    ("p", "When creating a manager account, optionally choose the manager's active employee record. For an existing account, use Settings → Schedule portal → Save manager employee link. Linking or unlinking revokes existing sessions. Conflicting employee accounts are rejected explicitly; accounts are never merged silently."),
                    ("p", "After signing in, a linked manager switches between My shifts / employee view and Manage teams. Personal shifts and attendance follow the employee ID even outside managed locations; team schedules still require employee assignment, visibility, tier and team-code checks. Manager MFA remains required in both views. Personal assignment never grants additional management rights, and administrators must correct the manager's own attendance."),
                    ("h3", "Managers"),
                    ("ul", [
                        "At first sign-in the manager replaces the temporary password (at least 14 characters) and enrols an authenticator app. MFA is mandatory for managers; later sign-ins need the six-digit code. The temporary server-side MFA bypass has been removed for managers, business administrators and platform owners.",
                        "The attendance page has From and To date filters that default to today (Jamaica time) when it opens; change the dates and select Apply, or Today to reset. The table lists the manager's own employees for that range, with each shift's date and start time. Mark absent is offered for late shifts and needs a reason; it is audited.",
                        "The bell shows the unread count of late and absent alerts for the manager's employees and refreshes every 30 seconds. Select the bell to open a list below it and Close to hide it. Unread alerts are highlighted in amber; select one to expand its details (status, employee, location, shift date, time detected) and it turns pale as read. Mark all read clears the count for that manager only. Select the ✕ beside an alert to remove it: it moves to the archives (for that manager only) and stops counting. Select View archives at the bottom of the list to see removed alerts, and Back to notifications to return. Alerts appear only in the app; no email is sent.",
                    ]),
                    ("h3", "Employees"),
                    ("p", "Employees replace the temporary password at first sign-in (no MFA) and then see only their own attendance for the last 30 days with a status summary."),
                    ("h3", "Schedule portal"),
                    ("ol", [
                        "Administrators accept schedules before making them available in the portal. In Settings → Schedule portal, set visibility from 1 to 52 weeks (default 4: current Monday-based week plus three upcoming weeks). Codes expire at midnight after the schedule period's last date, in Jamaica time.",
                        "In the manager confirmation email preview, select Include employee portal codes. It is selected by default when the selected schedule has already been accepted; generated-only review drafts remain available without portal codes. All included schedules must be accepted, correctly assigned and within the visibility window. The email contains the portal link, location/role/period code and expiry; share the code securely with the appropriate team. The app still prepares drafts, not automatic email delivery.",
                        "Employees sign in at /access and choose an assigned schedule from the Schedule dropdown to view only that period's own shifts, without a team code. View my shifts returns to the personal roster. To see the team roster, enter its six-digit code and select View team schedule. Leave Schedule unselected to let the code choose the eligible period; if the code matches multiple accepted versions, choose the desired version from the list. A code supplements individual login and never expands the employee's current location/exact-role scope or visibility. Five incorrect codes trigger a 15-minute lockout.",
                        "Managers see accepted schedules for all their assigned locations without entering codes. Tables show employee names/IDs, daily shifts, saved shift duration and next-day end times. Refresh schedules reloads the current accepted data and clears the displayed employee schedule.",
                    ]),
                    ("p", "Employees also see read-only attendance counts for today's shifts in their current location and role, with a Jamaica reporting timestamp. Future shifts are excluded; approved leave is excluded from the attendance denominator. No eligible shifts displays an unavailable percentage. Refresh schedules refreshes this summary; BambooHR data still comes from the existing attendance sync, not from the portal itself."),
                    ("h3", "Shift trade inbox and publishing"),
                    ("p", "BambooHR publishing removes the original single-employee shifts scheduled for replacement before creating replacement shifts, to avoid conflicts with the old assignments. These remote operations are not transactional: a failure after removal can leave replacement shifts missing until recovery. The app's accepted swap and durable remote journal remain saved. Failed operations show the provider's HTTP error/details; successful operations are skipped on retry, including saved older plans. Unknown outcomes require read-only reconciliation before any retry. Never reapply the app trade to recover remote publishing. BambooHR may still reject genuine overlaps with other shifts; app warning acknowledgement cannot override the provider's validation."),
                    ("p", "Administrators receive pending-manager-accepted trade requests in the main site's notification bell under Shift trade approvals. Click a notification to open the administrator trade inbox in a window within the admin site, with that request expanded. Viewing marks the current update read, not approved, and does not acknowledge warnings. Pending requests remain available until resolved; Mark all read includes their updates. Notifications refresh every 30 seconds while the admin tab is visible and when the trade window closes. Approval still requires explicit warning consent and a reason; preview/application remain separate."),
                    ("ol", [
                        "Click Trade shifts in the administrator app, Shift trade in the access portal, or Shift trade in the inbox. The popup uses validated Location × team and Week / period dropdowns. Personal mode fixes both Location × team and employee 1 to the current verified assignment, including linked managers using personal mode. Choose employee 2 and a period. Management-mode managers/admins retain authorized location choices and select both employees. Missing or changed assignments require administrator correction or reloading the choices. All choices come from visible accepted schedules and current same-location/exact-role assignments.",
                        "Select one or more swap-day checkboxes and review each employee's before-to-after shifts and resulting weekly count. Both employees must finish the selected schedule week with at least five assigned shifts. Five is a minimum, not an exact count or an hours threshold; six or seven are allowed. A single-day swap can be invalid while a balanced multi-day selection is valid. The minimum is rechecked at submission, confirmation, approval and application and cannot be overridden for trades.",
                        "Other scheduling rules (availability/operating days, shift-start permissions, fixed preference, approved leave, weekly maximum, overlaps and minimum rest) produce warnings rather than blocking swaps. Warnings identify the affected employee and dates or actual/required values where available. Approved leave is not cancelled by accepting a trade. Missing uploaded profile fields cannot establish availability. Permission, same-team/tenant, valid data, stale assignments and pending-trade intersection safeguards remain enforced; non-admin started/past trades remain blocked.",
                        "If there are warnings, the initiator must review and acknowledge all warnings at submission. Both employees must then consent to the full warning set, even if only one is affected. The recipient uses Accept trade; the offering employee uses Acknowledge & accept when someone else initiated. The location manager must explicitly acknowledge when accepting, then the administrator acknowledges when approving. Manager/admin exception proposals never skip these approvals. Warnings and acknowledgements are saved in the audit history; new or changed warnings require a new request and renewed consent.",
                        "Trades without warnings retain the ordinary employee-confirmation/manager/admin flow; manager initiation skips employee confirmation but retains admin approval. Older pending requests retain their original warning policy; withdraw and recreate to use the new exception workflow. The five-shift minimum also applies before older trades progress. Linked managers use My personal trades for employee consent and Manage team trades for manager acceptance.",
                        "Refresh the inbox for updates. Unread trade updates are separate from attendance alerts; Mark as read is per reader/version. Expanding a request does not mark it read or acknowledge warnings. History records states, actors, reasons and timestamps. Non-admin users cannot progress trades for started or past shifts. Changed assignments or stale versions are rejected.",
                        "For an approved trade, the administrator selects Preview application and explicitly chooses app-only or BambooHR. App-only does not touch BambooHR. Confirm the preview with an audit reason to update the accepted schedule; the administrator workspace synchronizes applied trades when accepted schedules load.",
                        "BambooHR previews validate directory mappings and scheduled-shift reads, show single-employee replacements/deletions, and reject shared/multiple remote shifts. Publishing is not remotely transactional. A failed publish leaves the app trade applied and shows its journal; retry sends only missing/failed operations. Unknown outcomes require read-only reconciliation and a separate confirmed retry; duplicate remote matches must be corrected manually. Interrupted running jobs cannot be reconciled for ten minutes.",
                        "Administrators may prepare manual shift/day-off overrides (including past shifts), preview and apply them through the same workflow. Availability, permissions, approved time off, weekly caps, overlaps and minimum rest are checked where supplied; explicitly overriding constraints requires a separate checkbox and audit reason. Missing uploaded profile fields cannot establish availability.",
                    ]),
                    ("p", "Trade requests are collapsed by default, showing the schedule week, initiator, status and unread indicator. Expand a request to review employee names, dated before/after shifts, weekly counts, warnings and approval history. Pending recipients can Accept trade or Reject trade; initiators can withdraw, and employees responding to management-initiated exception trades must also acknowledge and accept. After employee consent, managers use Open shift trade inbox in their portal to accept requests for their permitted teams. After manager acceptance, administrators review the same inbox at /trades for approval, preview and application. Its Dark mode / Light mode button uses the app palette; the popup follows the hosting page's selected theme without restyling other pages. Both employees must review all warnings before acceptance. The dialog supports keyboard focus, Escape/Close and scrolling."),
                    ("note", "Keep the server's MFA encryption key stable so stored portal codes remain readable. The SQLite-to-PostgreSQL importer does not copy portal codes; prepare new confirmation drafts in the destination to generate codes there."),
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
            ("p", "Multi-business registration, membership approval and tenant account management are available through the Business Hub (/hub). The main business administrator manages membership at /business. Actions require confirmation and audit history. Cancellation retains data and requires the platform owner to restore membership. An enrolled sandbox subscription is suspended/resumed/cancelled alongside membership; changing its tier requires cancelling/reconciling the current subscription first."),
            ("h3", "Optional PayPal sandbox billing"),
            ("ol", [
                "The platform owner opens /billing?view=owner from the hub. Privately configure PAYPAL_SANDBOX_CLIENT_ID, PAYPAL_SANDBOX_CLIENT_SECRET and PAYPAL_SANDBOX_WEBHOOK_ID on the server. No live provider URL is supported.",
                "Use the billing section links and Setup checklist to navigate. Set monthly/annual USD prices in the tier table with billing disabled. For each feature/tier, choose Default (showing whether it is normally enabled), Enabled or Disabled; Use defaults for all features clears overrides when saved. No JSON entry is required. Save prices and features, prepare sandbox product/plans, start the dedicated worker, then enable and save. Existing subscriptions retain their agreed price when prices change.",
                "Configure a PayPal sandbox webhook on your public HTTPS deployment at /api/payments/paypal/webhook, including subscription lifecycle and payment sale events. The app verifies signatures through PayPal, reads the authoritative subscription, and applies each verified event once. Never use a browser return URL as payment proof.",
                "The main business administrator opens /billing, chooses tier, monthly/annual billing and optional auto-renew, confirms the price and continues to hosted PayPal sandbox checkout. A non-renewing plan has one billing cycle. Payment details stay with PayPal. Verify subscription and payment reloads provider state; Cancel sandbox subscription cancels billing without issuing a refund or restoring suspended app access.",
                "A separate supervised billing_worker.py process checks payment state and retries failed outstanding payments once daily, up to seven payment attempts. Unknown outcomes are not charged again blindly. Seven failures suspend billing access; verified successful payment or an audited owner manual payment restores billing access without undoing a business suspension, membership pause or cancellation. Reminders/history are in-app; automatic email delivery is not configured.",
                "For manual credit, select the business by name/ID, choose a future date/time using Access paid through (Jamaica time, UTC−05:00), and enter an audit reason. It stops app retries but does not settle/cancel PayPal charges. For unknown checkout recovery, select a business and copy its sandbox subscription ID from PayPal; the saved checkout and plan must match. Current subscription details and billing history appear as readable fields instead of raw objects.",
            ]),
            ("note", "The server and dedicated worker must stay running. The owner page shows a worker heartbeat. Actual PayPal sandbox checkout/webhook/service acceptance and PostgreSQL migration/RLS verification are still required before deployment; no production BambooHR shifts were modified during implementation."),
            ("note", "For SQLite-to-PostgreSQL import, stop the source app and billing worker first and use a fresh destination for a single business. Access identities, notification read/archive state, trade approvals/journals and billing records are preserved; imported user sessions are revoked and billing is disabled at the destination. Keep encryption keys stable, verify sandbox credentials and subscription state, and start only the destination worker before reenabling billing. Portal codes are regenerated separately."),
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
            ("p", "The Developer change requests page records the product roadmap. First use creates a developer username and a unique password of at least 14 characters from the computer running the app. Signed-in developers can use Add a developer account, confirming their current password, to create another independent login with full developer access. Business administrator credentials cannot create developer accounts. Credential updates affect only the signed-in developer and invalidate that account's older sessions, not other developers. The page supports sign-in, credential updates, status filters and dependency checks. It does not launch agents or change code."),
            ("p", "Trusted server operators can run python scheduler.py add-developer --username new-developer from the application directory. Enter and confirm a unique password of at least 14 characters at the hidden terminal prompts; never put passwords in command arguments or chat. The command uses the configured database without unrelated initialization."),
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
    {
        "id": "help-knowledge",
        "title": "14. Help and knowledge base",
        "blocks": [
            ("p", "Open Help & knowledge base from shared application navigation. Search the FAQ, glossary and business-approved knowledge bites by topic, or open the full user manual for role-based page guidance and step-by-step procedures."),
            ("h3", "Manager submissions"),
            ("ol", [
                "Managers can submit a new FAQ, guide, tutorial, glossary entry or concise knowledge bite only for a Schedule Location assigned to their manager account.",
                "Choose the intended audience and provide the complete title and content. To suggest an edit, select the published article; the system records the version you based the edit on.",
                "A submission remains private and unpublished while pending. Check Your submissions for its status and administrator feedback.",
            ]),
            ("h3", "Administrator review"),
            ("ul", [
                "Business administrators review pending submissions and provide feedback when approving or rejecting them.",
                "Only approved submissions are published. Approving an edit creates a new revision and retains the previously published version.",
                "Submissions based on a superseded article revision cannot be published; ask the manager to refresh the article and resubmit.",
            ]),
            ("note", "Content is plain text. The application does not permit manager self-publication; tenant, role and Schedule Location scope are checked by the server."),
        ],
    },
]
