from pathlib import Path
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import argparse
import json
import math
import os
import re
import secrets
import sqlite3
import sys
import base64
import hashlib
import io
import ipaddress
import hmac
import struct
import time as time_module
from getpass import getpass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values, load_dotenv, set_key, unset_key
from flask import (
    Flask,
    abort,
    g,
    has_request_context,
    jsonify,
    make_response,
    redirect,
    request,
    send_from_directory,
    session,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from cryptography.fernet import Fernet, InvalidToken

from directory_seed import (
    EMPLOYEE_ASSIGNMENTS,
    EMPLOYEE_ROLE_OVERRIDES,
    SCHEDULE_LOCATIONS,
    UNMAPPED_ROSTER_EMPLOYEE,
)
import workforce_trades
import membership_billing
import session_idle
import attendance_reports
import historical_attendance_reports
import application_shell
import knowledge_base
import meta_settings
import roster_settings


APP_DIRECTORY = Path(__file__).resolve().parent
load_dotenv(APP_DIRECTORY / ".env")
DATABASE_PATH = APP_DIRECTORY / "data" / "schedule_creator.sqlite3"
DATABASE_URL = os.environ.get("SCHEDULE_CREATOR_DATABASE_URL", "").strip()
DEFAULT_TENANT_ID = os.environ.get("SCHEDULE_CREATOR_TENANT_ID", "cbljm").strip().lower()
if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", DEFAULT_TENANT_ID) is None:
    raise RuntimeError("SCHEDULE_CREATOR_TENANT_ID must be a valid tenant identifier.")
TRUSTED_PROXY_HOPS = int(os.environ.get("SCHEDULE_CREATOR_TRUSTED_PROXY_HOPS", "0"))
# TEMPORARY: allows PostgreSQL mode over plain HTTP, only for loopback/private-LAN
# clients. Not for internet exposure; remove later.
ALLOW_LAN_HTTP = (
    os.environ.get("SCHEDULE_CREATOR_TEMPORARY_ALLOW_LAN_HTTP", "").strip() == "1"
)


def http_allowed_for_client() -> bool:
    if not ALLOW_LAN_HTTP or request.headers.get("X-Forwarded-For"):
        return False
    try:
        address = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return False
    return address.is_loopback or address.is_private

if TRUSTED_PROXY_HOPS < 0:
    raise RuntimeError("SCHEDULE_CREATOR_TRUSTED_PROXY_HOPS cannot be negative.")
MAX_ACCEPTED_SCHEDULE_BYTES = 16 * 1024 * 1024
ENV_PATH = APP_DIRECTORY / ".env"
DEFAULT_APP_CONFIG = {
    "businessName": "Celebration Brands Limited",
    "teamName": "Schedule Management",
    "logoDataUrl": "",
    "supportingImages": [],
    "reportTheme": "light",
    "primaryColor": "#159bd5",
    "accentColor": "#74bf16",
    "tenantId": "cbljm",
}
MAX_LOGO_BYTES = 2 * 1024 * 1024
_validated_bamboo_keys: dict[str, tuple[str, str, datetime, str]] = {}
STATIC_ASSETS = {
    "CBL-Scheduler2.css",
    "CBL-Scheduler2.config.js",
    "CBL-Scheduler2.js",
    "CBL-MicrosoftAuth.html",
    "workforce-ui.css",
    "trade-picker.js",
    "session-idle.js",
    "application-shell.js",
    "application-shell.css",
    "attendance-reports.js",
    "historical-attendance-reports.js",
}
DEVELOPER_REQUESTS = (
    (
        "developer-change-log",
        "Developer change-request log",
        "Provide a developer-only, password-protected change-request log with request statuses, filters, dependency/blocker display, secure credential updates, and approval before logging new requests. Do not use shared default credentials. The initial local developer account is established through a loopback-only setup flow.",
        (),
    ),
    (
        "tenant-identity",
        "Secure tenant identity foundation",
        "Move the current local single-business scheduler to a secure multi-tenant deployment with verified admin authentication, hashed credentials, tenant isolation, role checks, audit events, HTTPS, and a production database. Preserve the existing business as an explicitly migrated tenant.",
        (),
    ),
    (
        "business-hub",
        "Business registration and SaaS hub",
        "Create a separate SaaS hub for business registration, business details, BambooHR tenant/API credential validation and encrypted storage, the main business admin and additional admins, two-factor authentication enrollment, manual approval/rejection, and active/pending/suspended membership states. Pending businesses may sign in only to complete onboarding and view status; scheduling stays disabled until active. Decide whether two-factor authentication is mandatory for every admin.",
        ("tenant-identity",),
    ),
    (
        "tier-entitlements",
        "Membership tiers and feature entitlements",
        "Enforce Bronze (2 admin seats, 2 teams, 20 active employees, 2 locations), Silver (3 admin seats, 4 teams, 60 active employees, 4 locations), Gold (4 admin seats, unlimited teams and employees, 6 locations), and Platinum (8 admin seats, unlimited teams, employees, and locations). All tiers include schedule generation, sharing, BambooHR publishing, email configuration, employee management, and settings. Employee schedule access, shift trades, and schedule history are Silver and above; overtime forecasting is Gold and above. User licenses are admin seats. Downgrades retain existing over-limit records but block additions; never deactivate records automatically.",
        ("business-hub",),
    ),
    (
        "business-membership-controls",
        "Business admin membership controls",
        "Allow only the designated main business admin to change the business membership tier, pause membership, or cancel membership from the hub. Show the current tier and status, explain the action's access and billing effects when applicable, and require confirmation. Apply existing membership status and tier-entitlement rules consistently, audit each action with its actor and prior/new value, and never delete tenant data as a side effect of cancellation.",
        ("business-hub", "tier-entitlements"),
    ),
    (
        "manager-employee-access",
        "Manager/employee authentication and attendance actions",
        "Add verified individual sign-in for admins, schedule-location managers, and employees. Managers may manage/view only locations assigned to their verified manager email; employees authenticate individually and receive only information for their assigned location and role. Schedule codes are additional checks, not sole credentials. Add an expandable attendance-notifications control beside the app inbox icon. Notify each scoped manager in real time when a team member is late or absent. A manager may mark a late employee absent before automatic classification, with a required absence reason; record who made the change, when, and the reason. Automatically flag a scheduled employee absent four hours after shift start if no valid clock-in has been recorded, excluding approved leave and retaining an auditable correction path. Admins can manage attendance exceptions across their business; managers can act only for assigned teams.",
        ("tenant-identity", "business-hub", "tier-entitlements"),
    ),
    (
        "schedule-portal",
        "Employee schedule portal and access tokens",
        "Generate cryptographically random, unique, expiring six-digit access codes for each location/role schedule period and include them in manager confirmation messages. The employee portal validates identity, location, role, period, and schedule assignment before revealing the full location/role schedule. Add configurable schedule visibility cadence in weeks and manager access to all assigned locations. Include a simplified, read-only attendance dashboard for each signed-in employee, restricted to that employee's own location × role team and the employee attendance/dashboard entitlements.",
        ("manager-employee-access",),
    ),
    (
        "manager-employee-dual-access",
        "Manager personal shifts and employee view",
        "Link a scheduled manager's existing account to their verified employee record within the same business. Use one identity and password with separate My shifts and Manage teams views; retain manager MFA in both views. Show personal accepted shifts and own attendance by linked employee ID, even when the manager works at a location they do not manage. Apply the existing employee schedule visibility, assignment, team-code and membership-tier checks when accessing employee team schedules or dashboards. Keep employee-view permissions separate from management permissions: personal assignment must not grant management access to another location. Prevent manager attendance corrections to their own employee record; require an authorised administrator and preserve audit history. Validate active, same-tenant employee links, handle existing employee-account conflicts explicitly without duplicate/ambiguous sign-ins or silent account merging, and revoke stale access after account/link changes. Test a manager scheduled outside their management scope, both views, MFA, tier restrictions, reassignment, disabling and rejection of self-corrections.",
        ("manager-employee-access", "schedule-portal"),
    ),
    (
        "role-scoped-roster-settings",
        "Manager team roster settings and employee self-service preferences",
        "Give managers access to the roster settings page for employees in their currently authorized teams. Managers may edit roster settings including proximity, daily availability and allowed shift starts, but Random 1-3 and Attendance 0-100 remain read-only. Employees see only their own roster record and may edit only Flexible, Reason if no and Preferred start; all other settings remain read-only. Preserve existing administrator permissions. Use a tenant-scoped shared server source, initialized only through a primary-admin preview and explicitly confirmed one-time import; never silently overwrite existing shared settings. Enforce tenant, current team/employee scope and field-level write allowlists server-side, including direct URLs and tampered requests. Preferred starts must come from the employee's configured location x role and comply with existing availability validation; require a reason when Flexible is No and explicitly reject incompatible choices. Preserve MFA, roster locking and existing access and membership restrictions. Reassignment, disabling and account/link changes revoke stale access. Linked managers use employee permissions for their own record in My shifts, without gaining extra management scope or bypassing the administrator-only self-attendance correction rule. Audit changes and prevent stale concurrent updates from silently overwriting newer edits. Changes affect future scheduling only, not accepted shifts or historical attendance. Clearly label read-only values and report validation or save failures. Verify scoped visibility, allowed and forbidden field updates, own-record isolation, linked-manager views, configured starts and validation, locks, transfers/disabling, concurrent edits, audit history and accepted-schedule preservation. Implemented; browser and deferred PostgreSQL acceptance remain outstanding.",
        ("manager-employee-access", "manager-employee-dual-access"),
    ),
    (
        "manager-scoped-meta-settings",
        "Manager-scoped META operating days and workload settings",
        "Allow managers to view the META operating settings page for only their currently authorized locations. When configuration is unlocked, managers may change permitted operating settings for those locations; when locked, settings remain visible and read-only. Managers cannot unlock configuration themselves. Preserve administrator permissions and grant no META access to employees or a linked manager's personal employee view. Enforce tenant/location authorization, permitted fields and the current lock state server-side on every read and write, including direct URLs, tampered requests and pages opened before a configuration lock. Preserve MFA, membership/access restrictions and existing operating-day/intensity validation; revoke stale access after reassignment or disabling. Audit edits, reject stale concurrent overwrites and surface validation/save failures. Changes affect future scheduling only; preserve accepted shifts and saved configuration snapshots. META currently shares open/closed days and daily workload intensity percentages across all roles at a physical location: before implementation, agree whether managers may edit both fields or operating days only, and define explicit physical-location authorization where a manager is assigned to only one location x role. Do not infer authority over other teams from a single role assignment. Verify scoped visibility, unlocked edits, locked and unlock denials, cross-location isolation, shared-location role boundaries, validation, revocation, concurrent edits, audit history and saved-schedule preservation. Approved for recording only; implementation pending scope agreement.",
        ("manager-employee-access",),
    ),
    (
        "shift-trades",
        "Authenticated shift-trade workflow",
        "Add authenticated, auditable trades with employee consent, manager acceptance, admin approval, application/publishing, rejection and withdrawal. Use themed, readable popup/inbox cards with scoped location x exact-role team, accepted week/period and employee dropdowns; employee 1 is fixed in personal mode. Show dated before/after shifts, selected checkbox days and combined weekly counts. Enforce at least five assigned shifts per employee in the selected schedule week at submission and every approval/application, not exactly five. All other scheduling violations, including overlaps, availability, leave, weekly caps and rest, become explicit warnings requiring both employees' consent, manager acceptance and admin approval, including management-initiated exception trades. Persist warnings and actor acknowledgements; changed warnings require renewed consent through a new request. Retain tenant/team authorization, valid assignments, stale/version and pending-intersection safeguards, non-admin past-shift blocking and the separate manual-override workflow.",
        ("manager-employee-access", "schedule-portal"),
    ),
    (
        "trade-publishing",
        "Approved trade and published-schedule reconciliation",
        "Apply workforce-admin-approved trades to accepted schedules. For already-published shifts, preview and confirm replacement/deletion actions, then update the app and BambooHR with visible success/failure states, retries/reconciliation, and audit history. Include admin overrides for past shifts and manual shift/day-off assignments. Verify BambooHR permissions and supported operations before implementation.",
        ("shift-trades",),
    ),
    (
        "recurring-billing",
        "Membership billing and payment providers",
        "As a later phase, add monthly/annual prices, optional auto-renew, PayPal first behind a provider abstraction, hosted/tokenized payment details, signed webhooks, reminders, daily retries up to seven attempts, suspension after repeated failure, and restoration after successful/manual payment. Never store raw payment credentials. Allow SaaS admins to configure tier features and prices with audit history.",
        ("business-hub", "tier-entitlements"),
    ),
    (
        "copilot-builder",
        "Copilot-reviewed request staging and implementation",
        "Integrate an explicitly authorized Copilot coding-agent/SDK service for drafting/reviewing requests, requiring user approval before logging, selecting the next dependency-ready request, and displaying isolated build progress/results. Run each build in a separate branch/workspace, test it, and require human review/merge; do not deploy or commit directly to the live app. This remains unavailable until a supported Copilot integration, credentials, and isolated runner are configured.",
        ("developer-change-log",),
    ),
    (
        "attendance-automation",
        "Real-time attendance tracking and automation",
        "Priority: Medium. Verify that each tenant's BambooHR API key can read both time-tracking clock-in data and approved time off. Read recent timesheet entries within BambooHR's 365-day API limit and match clock entries to accepted shifts by employee ID and timestamp, including overnight shifts in the scheduler's Jamaica time zone. Clock starts count as evidence even before BambooHR approval; exclude approved leave and never infer sick leave from a missing punch. Use a configurable lateness tolerance (0–120 minutes, default 15). Mark a shift late after the tolerance when no clock start exists; if no valid clock-in exists four hours after shift start, flag the employee absent. Keep tenant-scoped, idempotent time entries, shift statuses, and audit history. Allow an authorized administrator to correct a shift with a required reason; manager actions become available after manager authentication is implemented. Refresh on app open and every five minutes while the authenticated app tab is visible; no sync runs while it is closed or hidden. Calculate each employee's attendance as attended (including late) shifts divided by scheduled shifts, excluding approved leave, over a configurable 30–45-day period (default 30). Show period and counts, leave the calculated percentage blank when no eligible data exists, and allow a reasoned, audited score override or removal. Attendance calculation and operational tracking are included in every tier. The existing attendance priority bonus consumes the effective calculated or overridden score unchanged.",
        ("business-hub",),
    ),
    (
        "attendance-manual-clock-actions",
        "Attendance table manual clock-in and clock-out actions",
        "Add Clock in, Clock out and Clock out at shift end actions to the Actions column of the Attendance page's employee attendance table. Offer Clock in only when the employee has no active clock-in; offer Clock out only when a valid open clock-in exists. Clock out at shift end must close that same open attendance entry using the scheduled end date and time of the shift the employee is still clocked in for, not the current time or another shift's end; preserve overnight shifts and America/Jamaica time-zone handling. Confirm the employee, shift and resulting timestamp before saving, require an audit reason, and record the actor and before/after clock values. Enforce existing tenant, role and team scope server-side, including manager self-correction restrictions; do not grant new employee permissions. Recheck the open-clock state when saving and prevent duplicate clock-ins, repeated clock-outs, invalid time ordering and stale concurrent updates. Agree the policy for a scheduled end time that is still in the future before implementation. Decide whether actions write BambooHR clock events or are explicitly labelled local attendance corrections, and verify provider write support and permissions before enabling remote changes; never imply that a local correction updated BambooHR. Refresh affected rows, attendance totals and notifications after success, and report unavailable actions or save failures clearly. Verify not-clocked-in and clocked-in states, the correct still-open shift, overnight dates, missing or ambiguous shift ends, authorization, duplicate requests, concurrency and audit history. User approved recording this request only; implementation pending.",
        ("attendance-automation", "manager-employee-access"),
    ),
    (
        "attendance-shift-source-reconciliation",
        "Attendance shift-source selection and reconciliation",
        "Add an administrator-controlled Attendance page switch to use accepted app shifts or BambooHR scheduled shifts as the shift source, while always using BambooHR clock events to verify attendance. When BambooHR is selected, notify the administrator of unresolved differences between app and BambooHR shifts. Compare shifts by employee, date, start/end time, and location; let an administrator explicitly choose to update the app shift data from BambooHR or publish the app shift data to BambooHR. Require confirmation and audit every resolution, preserve accepted-schedule history, and never modify clock events. First verify the tenant's BambooHR Scheduling API supports reading and updating shifts and that the configured key has the required permissions; report unsupported operations clearly rather than implying reconciliation succeeded.",
        ("attendance-automation",),
    ),
    (
        "attendance-source-specific-populations-and-history",
        "Source-specific attendance populations and historical evidence",
        "Make the Attendance source selection govern employee eligibility, shift expectations, attendance calculations, snapshots, and historical reports consistently. When BambooHR is selected, include every active BambooHR employee with BambooHR scheduled shifts for the reporting period, regardless of app-active status; do not require an app employee row to include the employee. Base BambooHR-mode schedules and historical references only on BambooHR records, including schedules, clock activities, timesheets, and approved leave, with source and period provenance retained. Continue showing differences from accepted app shifts and retain the existing confirmed, audited choice to reconcile either direction. Count all BambooHR clock activities regardless of their approval flag; timesheet/clock approval and correction are handled by managers outside this app, with no in-app approval gate or workflow. When accepted app shifts are selected, include only active app employees and use accepted app schedules as expected shifts, with BambooHR clock activities/timesheets and approved leave as attendance evidence. Ensure the live attendance table and rate, scores, HTML/XLSX snapshots, and historical trend reports all use the same selected-source population and evidence. Do not silently substitute or mix sources when historical BambooHR evidence is unavailable; disclose missing or incomplete provider history. Define how active BambooHR status is established for historical periods and retain dated provider evidence where needed. Verify unlinked and app-inactive BambooHR employees, inactive app employees, source switching, approval-independent clock matching, snapshots, reports, historical boundaries, missing mappings, provider failures, and source provenance.",
        (),
    ),
    (
        "workforce-dashboards",
        "Live attendance and staffing dashboards",
        "Priority: Medium. Build a live attendance dashboard from timely attendance events and accepted schedules. Show the selected day's snapshot so far: people expected to have started by now, people who clocked in, attendance percentage, and exception counts and employee names/statuses (including sick, absent, late, and vacation when supported by verified leave data). Break down the live attendance percentage and exceptions by role and shift; preserve the reporting hierarchy location → role → location × role team → shift. Admins have full business-wide access, default to All locations, and see groups by location; filters must not hide the location grouping. Managers see and act only on their assigned locations/teams, and employees see a simplified read-only dashboard for their own location × role team. Show the reporting timestamp/time zone and distinguish approved leave, open/current shifts, and genuine exceptions so live percentages use only employees expected so far. Define the refresh/update mechanism and finalize the interval length (hourly, 30-minute, or shift-start slots) and snapshot contents before building the separate daily staffing-vs-demand interval snapshot. Attendance dashboard access remains Silver+; daily interval staffing snapshots remain Gold and Platinum. Planned coverage comes from accepted schedules; actual attendance and four-hour absence classification depend on attendance-automation.",
        ("attendance-automation", "manager-employee-access", "tier-entitlements"),
    ),
    (
        "snapshot-email-reports",
        "Scheduled and on-demand attendance snapshots and report emails",
        "Priority: Low. Generate attendance snapshot files automatically every day at 7 AM, 3 PM and 11 PM in America/Jamaica, and upon authorised request from the Attendance page. Persist timestamped, immutable snapshots with a history list and authorised downloads. Produce a styled XLSX workbook and HTML email summary closely resembling the supplied Oct 27, 2026 Automated Workforce Interval Snapshot message and workbook: blue headings, location summaries of scheduled/present/absent/attendance percentage, role and shift breakdowns, and employee-level attendance exceptions with shift times and clock-in/out. Highlight late employees' names in amber and absent employees' names in red, with explicit status labels. Report attendance as of each cutoff, distinguish future/pending shifts and approved leave, preserve overnight matching, minimum worked-time validation, lateness tolerance and four-hour absence rules, and record source-data freshness. Use a reliable background scheduler independent of an open browser tab, refresh BambooHR before capture, clearly flag refresh failures, prevent duplicate scheduled runs, and record generation failures and missed runs. Allow download only, email only, or both. Let the workforce admin configure email cadence (including these three daily times, daily, weekly or custom) and recipients: scheduled employees, schedule-location managers and a user-defined distribution list. Reuse the configured email profile where supported; the existing default-mail-client draft flow cannot send unattended or attach files automatically, so require an authenticated server-side sending integration such as Microsoft Graph or supported SMTP for automatic dissemination. Include the formatted summary and XLSX attachment, respect each recipient's team scope, include distribution-list unsubscribe/opt-out handling, and log delivery success, failures and retries without duplicate sends. Honor each report's tier (interval staffing-vs-demand snapshots Gold and Platinum, attendance reports Silver and above). Never include other teams' data in a recipient's report. Full reproduction of unrelated workbook analytics is outside this request.",
        ("workforce-dashboards",),
    ),
    (
        "saved-schedule-register-management",
        "Saved schedule register deletion and six-record scrolling",
        "Allow authenticated business administrators to delete schedules directly from the Saved schedule register on Weekly schedules, with explicit confirmation and tenant-scoped authorisation. Persist the deletion and refresh the register, selected schedule, filters, counts and export/email selections consistently. Clearly distinguish saved workspace schedules from accepted database copies and BambooHR-published shifts; explicitly confirm the intended deletion scope rather than silently deleting accepted or remote records. Preserve unrelated schedules and audit history, and surface deletion failures. Make the register vertically scrollable with a viewport no taller than six record rows plus its header; shorter lists should not leave unnecessary empty space. Keep the header visible, support keyboard scrolling and existing action styling, and verify with more than six records, variable row heights, cancellation, reload persistence and non-admin access rejection. This request records planned work only.",
        ("tenant-identity",),
    ),
    (
        "primary-admin-data-settings",
        "Primary administrator access to Data & Settings",
        "Restrict the Data & Settings navigation group and its pages/actions to the business's designated primary administrator (is_primary), not every administrator or the platform owner by default. Hide the group for other accounts and enforce tenant-scoped server-side authorization on the corresponding data/configuration operations; hiding navigation or browser preferences alone is insufficient. Cover direct URLs/API requests, source imports/restores, backups/exports and configuration changes exposed by this group without accidentally blocking ordinary schedule generation or approved schedule sharing. Preserve existing data and reject unauthorized operations explicitly. The separate Settings page is not included automatically merely because of its name; any broader restriction requires an explicit scope decision. Verify primary versus additional administrators, manager/employee denial, tenant isolation, account reassignment and reload persistence. Planned work only.",
        ("business-membership-controls",),
    ),
    (
        "meta-data-settings",
        "Move META operating days into Data & Settings",
        "Move META operating days from Plan schedules into Data & Settings and apply that group's primary-administrator access restriction. Update sidebar ordering, navigation shortcuts, page visibility settings and manual guidance consistently. Preserve existing operating-day/intensity values, configuration locking rules, saved schedule snapshots and scheduling behavior; this is a navigation/access change, not a change to demand calculations. Verify that the primary administrator can view/edit META, other users cannot reach its configuration through direct navigation or mutation paths, and generation continues to consume the preserved configuration. Planned work only.",
        ("primary-admin-data-settings",),
    ),
    (
        "site-navigation-alerts",
        "Consistent Access, Hub and Business navigation and alerts",
        "Add a navigation menu to each Access, Hub and Business site, with similar layout and design to the admin hub and consistent app branding, light/dark themes and responsive behavior. Put a site-specific alerts icon at the top of each site, with authorized site-scoped alerts and unread indicators; do not expose other sites', users' or tenants' protected alerts. Place shift trades and their inbox under Access navigation, retaining employee/personal-manager/team-manager permissions and administrator review, approval and publishing access. Preserve each site's existing functions, content organization and workflows while aligning its navigation and visual shell with the admin hub; do not remove functionality or alter permissions as a styling side effect. Support accessible keyboard navigation and mobile menus. Reuse existing alert/read behavior where available and surface failures explicitly. Verify navigation, alert scope, unread/read behavior, role permissions and light/dark mobile layouts on all three sites. User approved recording this request only; implementation remains pending.",
        ("business-hub", "manager-employee-access", "shift-trades"),
    ),
    (
        "unified-application-shell",
        "Unified application shell and role-based navigation",
        "Unify Access, Shift Trades and Business management within the existing administrator application's visual shell, rather than maintaining separate site interfaces. Supersedes the separate-site shell approach in site-navigation-alerts while retaining its authorized alerts, navigation and accessibility requirements. Reuse the administrator header, sidebar, branding, dialogs, tables, responsive layouts and light/dark themes. Provide one sign-in entry point that identifies the account and business without merging identities or granting implicit access; preserve password-change, MFA and tenant-selection requirements. Route employees to personal schedules, attendance, trade requests and notifications; managers to authorized team attendance and trade approvals with an explicit linked personal-employee mode; business administrators to scheduling, employee management, trade approval/publishing and business information; primary administrators additionally to Data & Settings and membership/administrator management; platform owners to an explicitly separated cross-business administration experience without implicit business-user permissions. Keep developer access separately authorized. Build role-aware navigation and landing pages, reusing existing backend workflows and account identities. Enforce role, tenant, team, primary-admin and membership-entitlement permissions server-side on every protected endpoint; hidden menus are not authorization. Integrate authorized alerts with unread/read behavior without leaking other users' or tenants' data. Preserve schedule data, trade history, approvals, publishing journals and existing workflows. Retain old Access, Trades and Business URLs as authorized redirects to integrated views, preserving selected-trade deep links and administrator approval notifications. Apply the shared 15-minute idle warning/expiry, eight-hour absolute deadline, cross-tab activity and sign-out consistently. Verify every role and personal/management mode, tenant isolation, direct/deep-link access, MFA, notifications, keyboard/mobile navigation, both themes and existing scheduling/trade/business regressions. Approved for recording only; implementation pending.",
        ("business-hub", "manager-employee-access", "shift-trades", "business-membership-controls",
         "primary-admin-data-settings", "meta-data-settings", "session-idle-expiry"),
    ),
    (
        "executive-end-of-day-report",
        "Configurable executive end-of-day download report",
        "Let an authorized business administrator configure automatic report generation from 0 through 24 hours after the reporting day ends in America/Jamaica. For example, Monday's report may be generated Tuesday at 8 AM. Generate a downloadable executive-focused report using a visual format similar to the interval snapshot workbook, emphasizing attendance rates, scheduled versus actual staffing, location performance and significant exceptions rather than detailed employee listings by default. Reuse the snapshot reporting infrastructure and preserve dated report/download history with tenant-scoped authorization and existing report entitlements. Run independently of an open browser, prevent duplicate runs, persist the generation setting and surface generation/data-refresh failures. Clearly show the reporting date, generation timestamp, source freshness and incomplete overnight shifts; attribute shifts to their start date to avoid double-counting. Download only for this request; automatic emailing is not included. Verify the exact 0-hour and 24-hour limits, invalid offsets, day boundaries, overnight attribution, automatic generation, history and authorized downloads. Approved for recording only; implementation pending.",
        ("snapshot-email-reports",),
    ),
    (
        "employee-trade-location-lock",
        "Automatically populate and lock employee trade location",
        "When an employee initiates a shift trade, automatically populate the location from their current verified active employee assignment and make the location field uneditable. Apply the same restriction to linked managers in personal employee mode; managers and administrators in management mode retain their authorized location choices. Enforce the assignment and location restriction server-side on trade choices, options and submission, not just through a disabled dropdown or browser-supplied value. Preserve exact-role team scope, accepted-schedule visibility and all existing trade approval, warning and minimum-shift rules. Show an explicit explanation if the employee lacks a valid assignment or eligible schedule; do not silently select an unrelated location. Revalidate reassignment and stale choices, including direct/tampered API requests. Verify employee, linked-manager personal mode, management mode, reassignment, missing assignments and tenant isolation. Approved for recording only; implementation pending.",
        ("shift-trades", "manager-employee-dual-access"),
    ),
    (
        "interactive-attendance-snapshot",
        "Interactive branded HTML attendance snapshot dashboard",
        "Generate a self-contained interactive HTML dashboard alongside each attendance snapshot XLSX. Use the supplied intraday snapshot for reporting structure and operations dashboard for visual inspiration: company logo saved in business branding, executive KPI cards first, location/role/shift charts and summaries next, then employee exceptions and evidence-based risks. Include confirmed attendance percentage, expected shifts so far, matching clock-ins, late arrivals, missing punches, absences, approved leave, early departures, overtime and missing clock-outs when verified by saved evidence. Provide coordinated location/role/shift/status/search filters, chart drill-down, sortable exception details, accessible labels/tables, responsive layout and print/PDF support. Embed assets/data for offline use without external services. Capture the business logo/name with the report; later branding changes must not rewrite history. Preserve tenant/role/tier download authorization, immutable saved cutoffs and source freshness, overnight/leave/worked-time/absence rules, and XLSX compatibility. Do not copy the sample's two-hour absence rule, invent trends/demand scores, or enable automatic email. Existing snapshots may render only their saved evidence; do not attach current branding retrospectively. Implemented; awaiting user acceptance.",
        ("snapshot-email-reports",),
    ),
    (
        "attendance-snapshot-batch-deletion",
        "Administrator batch deletion of saved attendance snapshots",
        "Allow authorized administrators to select individual or multiple attendance snapshots in history and confirm batch deletion. Remove saved HTML/XLSX payloads and visible history without changing underlying attendance, schedules, employees or provider data. Keep minimal deleted run-key tombstones to prevent scheduled cutoffs regenerating, and audit actor and snapshot IDs. Enforce tenant/admin/tier/CSRF authorization server-side, reject running captures and stale selections, and make batches atomic. Clearly warn that downloaded or emailed copies cannot be recalled. Implemented; awaiting user acceptance.",
        ("snapshot-email-reports",),
    ),
    (
        "attendance-snapshot-email-body",
        "Generate executive email bodies accompanying saved attendance snapshots",
        "Let authorized administrators generate a suggested subject, formatted email body and plain-text alternative from the selected snapshot's saved evidence. Include confirmed attendance, expected shifts, clock-ins, verified late arrivals, absences, missing punches, leave, early departures, overtime, ended missing clock-outs, compact location/role tables and evidence-based highlights. Match HTML snapshot metric definitions and display source warnings, overlap/validation definitions and saved reporting cutoff. Provide preview and copying with manual-copy fallback, without sending email; the administrator attaches the downloaded HTML themselves. Preserve tenant/admin/tier authorization, inert safe rendering and historical branding/evidence. Implemented; awaiting user acceptance.",
        ("interactive-attendance-snapshot",),
    ),
    (
        "workspace-readiness",
        "Workspace readiness loading and recovery experience with environment toggle",
        "Hide the scheduling workspace body behind a clean, branded, theme-aware loading screen with a centered spinner and accessible loading message until essential initialization, authentication, permissions and core scheduling data are verified ready. Prevent interaction with partially loaded controls, respect reduced-motion preferences, and provide bounded waiting with meaningful status and recovery options instead of an indefinite spinner. On application-level loading failures, show an engaging branded error/recovery page with a plain-language explanation, explicitly available and unavailable functions, Retry loading, Continue with limited functionality only when safe, and Contact support/helpdesk with a non-sensitive reference or timestamp. Essential authentication, permission or core-data failures must block workspace access; optional integration failures may allow explicitly described degraded operation without presenting missing data as empty or stale evidence as current. Preserve saved/local workspace data and avoid duplicate writes on retry. Do not require every optional background integration to respond before essential workspace readiness. Provide a documented server-side environment-file flag SCHEDULE_CREATOR_WORKSPACE_READINESS_ENABLED, default enabled, allowing operators to disable only this loading/recovery presentation and retain the existing startup experience; disabling must never bypass authentication, authorization, validation or other safety guards. Validate flag values using repository configuration conventions and document restart requirements. Complete network/server outages may still use browser errors unless separately supported by an offline fallback. Verify successful and slow loading, essential and optional failures, safe continuation, retry, accessibility, desktop/mobile themes, disabled behavior and preservation of saved records. Approved for recording only; implementation pending.",
        (),
    ),
    (
        "primary-admin-change-request-visibility",
        "Primary administrator read-only change requests and developer-only editing",
        "Restrict business-user visibility of the developer change requests link and read-only register to the business's designated primary administrator, not all administrators. Preserve separately authenticated developer access and make the developer the only actor allowed to create, edit, delete or change request statuses and dependencies. Primary administrators can view business-appropriate completed, in-progress and planned changes to understand what has happened and what is expected next, without editing controls or mutation permissions. Other administrators, managers, employees and platform-owner sessions without explicit developer authentication must not gain register access. Enforce page, read API and mutation authorization server-side, including direct URLs and tampered requests, rather than relying on hidden navigation or disabled buttons. Recheck current primary-administrator designation and tenant scope; preserve developer authentication, CSRF, audit and existing prerequisite/status rules. Exclude secrets, sensitive internal implementation notes and other businesses' information from the primary-administrator view while retaining the developer's authorized full register. Verify developer read/write access, primary-administrator read-only access, denial for other roles and anonymous users, direct mutation rejection, reassignment, tenant isolation and navigation visibility. Approved for recording only; implementation pending.",
        ("developer-change-log", "primary-admin-data-settings"),
    ),
    (
        "schedule-locations-plan-schedules-category",
        "Move Schedule Locations into Plan Schedules",
        "Move the Schedule Locations page link from People into the Plan Schedules navigation category. Preserve the existing page, URL, access rules, and all current scheduling and location-management behavior. This is a navigation-placement request only; do not rename or remove the page.",
        ("unified-application-shell",),
    ),
    (
        "schedule-location-role-management",
        "Create roles for a schedule location",
        "Allow authorized business administrators to create roles for a selected schedule location from the Schedule Locations page. Store roles scoped to the tenant and location, validate role names, and prevent duplicate roles for the same location. Keep existing role assignments and do not grant role creation to managers or employees. Clarify role editing/deletion and whether a role may be shared across locations during implementation.",
        ("business-hub",),
    ),
    (
        "bamboohr-location-lifecycle-and-retirement",
        "BambooHR location synchronization, mapping, and safe retirement",
        "Treat the BambooHR employee directory as the source of truth for BambooHR employees' locations. After a complete successful directory sync, compare its distinct active employee locations with accepted app locations and prompt the authorized business administrator to accept all or a selected subset. For every accepted location, let the administrator choose existing roles or create roles for that location; add the accepted location-role pools to Location × Role and the location to META with blank operating-day/intensity values. Show a corresponding Schedule Locations item as pending configuration, but do not invent a BambooHR schedule ID or manager details. On every sync, update BambooHR employees to their matching accepted BambooHR location, replacing an app location when BambooHR has a valid accepted location assignment. Admin reassignment is only a fallback when the employee has no matching accepted BambooHR location; warn that a later sync will replace that fallback if BambooHR supplies a matching location. Automatically assign the Schedule Location only when exactly one configured mapping matches the employee's app location and role; when multiple mappings match, require an administrator choice, and when none match leave it unset. After a complete successful sync, detect app locations no longer represented among active BambooHR directory employees and ask the administrator to map each deprecated location to a current BambooHR location or retire it. A bulk mapping applies only to employees without their own matching accepted BambooHR location; employees with a valid BambooHR match follow that individual location. If a location is retired instead, automatically map employees with valid accepted BambooHR locations and leave the rest unmapped for an explicit bulk-to-one or individual reassignment. Allow administrators to delete an app location or a location-role pool from Location Roles only after reviewing all affected employees and references; support assigning everyone to one destination or assigning employees individually in the same operation. Resolve employee, pool, META, and pending Schedule Location references before removal; preserve accepted schedules, attendance history, and saved reports. Make changes tenant-scoped, authorized, quota-aware, transactional, revision-checked, and audited. Verify complete versus failed sync behavior, all/subset acceptance, new/existing role choices, BambooHR precedence over app fallback, unique/ambiguous/missing Schedule Location matches, deprecated-location mapping/retirement, employee batch reassignment, pool/location deletion safety, tier limits, concurrency, and historical-data preservation.",
        ("schedule-location-role-management",),
    ),
    (
        "historical-attendance-trend-reports",
        "Historical weekly and monthly attendance reports with employee and DC trends",
        "Allow administrators and managers to generate attendance reports for a selected historical week or previous month, downloadable as matching Excel and self-contained interactive HTML. Administrators may select all or specific distribution centres (DCs)/locations; managers may report only on authorized teams, with tenant/team scope enforced server-side during generation, history access and downloads. Include branded executive/DC summaries of expected shifts, confirmed attendance, attendance percentage, approved leave, verified late arrivals and absences; an employee register with the existing documented attendance-score calculation, expected/confirmed shifts, late and absence counts with dates and shift times; and dated attendance evidence and exception details. Add week-over-week and month-over-month comparisons per employee and DC, showing counts, eligible-shift denominators, rates and percentage-point changes across comparable completed periods. Analyze employee late/absence patterns by shift-start time, weekday, first scheduled shift after a verified day off, and first scheduled shift after dated approved time off; separate leave types where reliable evidence exists. Show incidents and eligible shifts for every pattern, not raw counts alone. Provide coordinated DC/team/employee/period filters, search, sortable tables and evidence drill-down, with KPI cards, comparison charts, trend lines and heatmaps where evidence supports them. Excel must include corresponding summary, employee, comparison, pattern-analysis and detailed-evidence worksheets using identical calculations. Reuse reporting infrastructure and saved branding; show Jamaica-time reporting boundaries, source freshness and incomplete evidence. Preserve attendance-score rules, worked-time validation, approved-leave exclusions, corrections and overnight attribution to shift start date; distinguish verified late arrivals from missing-punch late statuses. Use dated schedule, attendance and assignment evidence rather than reconstructing history from current settings or employee teams. Define historical manager access without exposing other teams after transfers. Missing schedule records are not proof of a day off. Comparisons require evidence for both periods; unavailable history must remain unavailable, not zero. Agree the week boundary, comparison/history window, minimum eligible-shift sample and historical manager-access policy before implementation. Clearly distinguish observed patterns, insufficient evidence and no recorded incidents; label partial periods and avoid misleading full-period comparisons. Describe association, not cause or predictions; post-leave patterns must not automatically trigger disciplinary action. Verify authorization and transfers, period boundaries, denominators/scores, late/absence dates, overnight/leave/correction rules, shift/day/post-day-off/post-time-off analysis, insufficient history/sample cases, cross-format parity and offline HTML interaction. Automatic email is not included. Approved for recording only; implementation pending.",
        ("snapshot-email-reports", "interactive-attendance-snapshot", "manager-employee-access"),
    ),
    (
        "attendance-page-setup-and-reports",
        "Attendance setup and reports navigation",
        "Reorganize the Attendance page into two clear sections without changing existing features or permissions. Put BambooHR attendance sync, Attendance shift source, Attendance filters, and Attendance rules together in one Setup section. Put Attendance snapshots and Historical attendance trend reports together in a Reports section. Preserve current behavior, tenant/role authorization, report history, and direct links. This request is for navigation and grouping only.",
        (
            "attendance-automation",
            "attendance-shift-source-reconciliation",
            "interactive-attendance-snapshot",
            "historical-attendance-trend-reports",
        ),
    ),
    (
        "workload-fte-headcount-planning",
        "Manager-defined workload FTE modelling and annual headcount planning with approved scheduling integration",
        "Create a workforce capacity and annual headcount planning module separate from day-to-day scheduling. Managers are primarily responsible for defining work within their authorized locations and roles: required tasks, standard completion times, workload units such as cases/orders/pallets/transactions, explicit unit definitions and conversions, workload-to-task mappings, and fixed work independent of volume. Enforce manager tenant/team/location permissions server-side. Workforce administrators oversee staffing-model assumptions, review work definitions and approve plans for scheduling integration. Accept dated manual or imported workload forecasts for a full year; translate workload and fixed work into required labour hours, then required FTE using productive hours available per FTE. Staffing models must explicitly account for working hours, breaks, leave, training, absence allowances, part-time capacity and shift coverage, identifying allowances already included in task standards to avoid double-counting. Show FTE separately from employee headcount and explain rounding/coverage assumptions. Present weekly and monthly workload, labour hours, required FTE/headcount, available/planned capacity, staffing gaps and week-over-week/month-over-month changes by role and location, with alternative scenarios and visible model assumptions. Use approved, versioned, effective-dated plans to automatically update only agreed scheduling demand/capacity settings; calculate proposed changes rather than silently overwriting settings whenever a forecast changes. Define daily/shift distribution before translating weekly requirements into scheduling inputs. Preserve employee availability, contractual limits, safety rules, configuration locks and accepted schedules; never rewrite accepted schedules. Show proposed settings changes, conflicts and effective dates, maintain an audit trail and support rollback. Results are model-based requirements, not guaranteed staffing outcomes. Agree staffing models, forecast inputs, approval authority, manager definition/review workflow and the exact scheduling settings permitted for automatic updates before implementation. Verify task/unit conversions, fixed work, allowance accounting, productive-hour/FTE/headcount calculations, year and period boundaries, weekly/monthly comparisons, scenario isolation, manager/admin/tenant access, approval/effective dates, locked-setting conflicts, rollback and preservation of saved schedules and employee records. Approved for recording only; implementation pending.",
        ("manager-employee-access",),
    ),
    (
        "faq-guides-knowledge-base",
        "FAQ, user guide, tutorials, glossary and administrator-approved knowledge base",
        "Add a dedicated help/FAQ page containing frequently asked questions, a user guide, full step-by-step tutorials, glossaries and a searchable knowledge base of concise knowledge bites. Reuse and keep directly related existing user-manual content consistent with implemented workflows; organize content by topic and user role, with accessible navigation, search and responsive presentation. Managers may submit new knowledge bites or proposed changes to existing bites within their authorized business scope. An authorized business administrator reviews submissions and approves or rejects them with feedback; only approved versions become published and visible to the intended audience. Preserve the previous published version while edits await review. Track draft/submitted/approved/rejected states, authorship, reviewers, revision history and review timestamps; support resubmission and guard against conflicting/stale edits. Enforce tenant, role, audience and review permissions server-side for reads, submissions and publication, not only through hidden controls. Managers must not self-publish or approve their own submissions using manager permissions. Keep platform-wide application documentation separate from tenant-specific operational knowledge; business approvals must not overwrite shared product guidance or expose another business's content. Sanitize rendered content, validate inputs and preserve CSRF/audit protections. Define permitted content formats, audience visibility, ownership of shared documentation and notification workflow before implementation. Verify FAQ/guide/tutorial/glossary navigation and search, manager submission, administrator approval/rejection and feedback, pending-edit publication isolation, revision conflicts/resubmission, tenant/role boundaries and safe content rendering. Approved for recording only; implementation pending.",
        ("manager-employee-access",),
    ),
    (
        "shared-html-report-branding",
        "Shared business branding and supporting images for all generated HTML reports",
        "Allow every business to upload up to two supporting images in addition to its logo, managed by authorized business administrators with preview, replacement and removal. Apply business name, logo, configured colors, supporting images and business-configured report theme consistently to all generated HTML report types through a shared report-branding mechanism. Supporting images enhance headers or decorative sections without obscuring charts, tables, warnings or employee information. Validate upload type, size and dimensions using documented limits and safe supported image formats; enforce tenant/admin permissions server-side and retain CSRF/audit protections. Embed validated assets and branding in downloaded HTML for offline operation without external URLs. Freeze branding when each report is generated; later edits affect new reports only and must not rewrite saved reports or retrospectively attach current branding to historical captures. Preserve accessible contrast, meaningful absence/lateness/warning colors, responsive layouts and print-friendly output, with attractive defaults when images or custom branding are absent. The business's configured report theme, not the generating user's personal light/dark preference, determines report styling. Branding availability is for all businesses while existing report-generation entitlements remain unchanged. Reuse existing logo validation and snapshot branding capture where suitable; wire every current HTML report generator and provide the same mechanism for future report types. Agree image limits, placement and report-theme options before implementation. Verify two-image limit, invalid/oversized uploads, preview/replacement/removal, tenant/admin isolation, all HTML report surfaces, saved-branding immutability, offline assets, default styling, contrast/status semantics and mobile/print layouts. Approved for recording only; implementation pending.",
        ("interactive-attendance-snapshot",),
    ),
    (
        "historical-report-progressive-dashboard",
        "Snapshot-style historical attendance dashboard with selection-driven trend detail",
        "Redesign the weekly/monthly interactive HTML report to match the attendance snapshot's attractive branded visual style: spacious panels, concise executive KPI cards and clear charts rather than crowded tables. Initially show only general attendance, lateness and absence trends/comparisons by distribution centre (DC) and role. Hide full employee registers, detailed shift evidence and employee pattern tables from the initial overview. Selecting a location x role reveals a dedicated trend graph and summary table for that team; selecting an employee reveals their dedicated trend graph and table, attendance score, late/absence dates and shift-time/day/post-day-off/approved-time-off patterns. Keep detailed panels hidden until a relevant selection is made, coordinate filters and chart drill-down across the view, show an explicit scope label and let clearing selections restore the uncluttered overview. Preserve all underlying saved evidence and detailed Excel worksheets, existing calculations, source warnings, insufficient-evidence/minimum-sample safeguards, tenant/tier authorization and manager team restrictions. Distinguish selected-versus-previous-period comparisons from genuine multi-period trends; do not fabricate longer trend lines when only two periods exist. Retain offline interaction, accessibility, responsive layouts and print-friendly output. Preserve historical capture immutability; do not silently rewrite previously generated reports. Verify initial overview visibility, team and employee selection/drill-down, reset, coordinated metrics, unavailable evidence, Excel parity and desktop/mobile/print presentation. Approved for recording only; implementation pending.",
        ("historical-attendance-trend-reports", "interactive-attendance-snapshot"),
    ),
    (
        "session-idle-expiry",
        "Fifteen-minute idle session expiry",
        "Expire authenticated business administrator, manager, employee, platform-owner and developer sessions after 15 minutes without genuine user activity. Enforce the deadline server-side across browser tabs and direct API requests; automatic attendance/notification polling, background refresh, worker jobs and passive open tabs must not extend the idle deadline. Retain the existing eight-hour session lifetime as an absolute maximum that user activity cannot extend. Provide a warning before expiry, preserve unsaved-work warnings where applicable, stop authenticated polling on expiry, clear protected displays, and require normal sign-in/MFA again. Define a bounded, validated user-activity reporting mechanism rather than treating every HTTP request as activity. Test the exact 900-second boundary, activity renewal before expiry, expiry despite continuous polling, cross-tab behavior, absolute maximum, all account types and rejection of stale sessions. Planned work only.",
        ("tenant-identity", "manager-employee-access", "developer-change-log", "business-hub"),
    ),
    (
        "action-feedback-toasts",
        "Timed action-feedback toasts and recent feedback history",
        "Priority: Low. Show transient user-action feedback in a nonblocking top-right toast for seven seconds, with a close button and accessible status announcements. Ensure rapid messages are queued or stacked rather than silently overwriting one another. Keep expired or dismissed feedback in a recent-feedback history accessible by expanding the header, so users can review messages they missed; retain a bounded history for the current browser session. Also toast newly received header alert events once, but do not replay existing alerts during notification polling or change their durable read/archive state. Keep the notification bell as the source for persistent alerts. Verify timing, dismissal, rapid actions, missed-feedback history, new-alert deduplication, accessibility, keyboard use and responsive layouts.",
        (),
    ),
)
WORKFORCE_IMPLEMENTATION_NOTES = {
    "shared-html-report-branding": "Implemented: Business Settings now validates/saves a report-only light/dark theme and up to two PNG/JPEG/WebP supporting images (each <=2 MB) alongside existing name/logo/colors. Snapshot and historical report captures freeze name, logo, colors, theme and supporting images; both offline HTML templates embed images safely and apply the captured theme/brand colors. Existing saved reports are unchanged. Branding config, snapshot and historical capture tests, manual freshness, syntax and whitespace checks passed. Awaiting user acceptance; interactive browser/mobile/print verification remains outstanding.",
    "faq-guides-knowledge-base": "Implemented: added a shared role-aware Help page with searchable built-in FAQs, glossary, step-by-step tutorial and plain-text index of the user manual. Tenant knowledge articles publish only after business-admin approval; manager submissions are location-scoped, audience-filtered, auditable, editable as drafts/resubmissions, and guarded against stale revisions. Published versions are immutable history; admin review and manager feedback/status are surfaced in Help. Notification policy is page-based only (no email/push): admins see the pending queue on Help and managers see status/feedback there. Added PostgreSQL RLS, tenant-scoped schema, safe text rendering, manual navigation and role/page tests. Five knowledge workflow tests, manual freshness, shared route test, syntax and whitespace checks passed. Awaiting user acceptance; interactive browser/mobile verification remains outstanding.",
    "workspace-readiness": "Implemented: startup now has a default-on readiness overlay with a 20-second slow-load message, fatal recovery/sign-in path, optional-degraded read-only continuation, Retry via reload, and a validated SCHEDULE_CREATOR_WORKSPACE_READINESS_ENABLED presentation-only flag. Limited mode inerts workspace content and disables profile/notification actions while preserving sign-out, navigation, theme and retry. Focused flag/auth test, Python/JavaScript syntax and DOM-stub optional/fatal/read-only transitions passed. Awaiting user acceptance; interactive browser/network-failure and viewport verification remain outstanding.",
    "attendance-source-specific-populations-and-history": "In progress: BambooHR attendance fetch now uses the provider's active employee directory, includes app-inactive and unregistered employees via BambooHR-namespaced IDs, and counts clock activity independent of approval. App mode filters to active app employees. Attendance/history queries are source-filtered; switching sources preserves the other source's rows. HTML/XLSX snapshots and historical reports identify their shift source; app overrides do not affect BambooHR-source history. Verified 27 attendance, 12 snapshot/report, source-population and provenance checks. Historical BambooHR active-status snapshots and provider historical schedule coverage remain unresolved; the historical suite retains two unrelated date/rate-limit assertion failures.",
    "primary-admin-change-request-visibility": "Implemented: the current primary business administrator receives a no-store read-only page and GET API with only business-facing titles and coarse status labels; developer IDs, descriptions, dependencies, timestamps, and private developer/identity requests are excluded. Current primary designation is checked for each request; anonymous and other-role sessions are denied. Developer routes and mutation controls are unchanged. The focused authorization/sanitization test and all 11 developer change-request tests passed. Awaiting user acceptance; browser role/viewport verification remains outstanding.",
    "action-feedback-toasts": "Implemented: user action feedback now shows in a dismissible seven-second toast queue. The latest 20 items are retained in tab session storage and shown from the expanded header; new attendance and pending trade alerts toast once after initial polling without changing bell read/archive state. History and active toasts clear on sign-out. Node syntax, mocked queue/timer/history/sign-out checks, and mocked notification deduplication passed. Awaiting user acceptance; interactive browser and keyboard verification remain outstanding.",
    "attendance-page-setup-and-reports": "Implemented: grouped BambooHR attendance sync, shift source, filters and rules under Setup, and snapshot/historical report mounts under Reports. Preserved report mount IDs, existing workflows and the always-visible live attendance/score tables. Awaiting user acceptance; browser fixture verification is blocked by its pre-existing historical seed-metrics assertion.",
    "historical-report-progressive-dashboard": "Implemented: new historical HTML uses snapshot-style cards and DC/role overview charts/tables, with employee/team comparisons, patterns and shift evidence hidden until employee or DC plus role selection. Coordinated keyboard/chart/table drill-down, scope labels, reset and print layouts; new reports capture business name/logo. Excel detail and previously saved HTML remain unchanged. Awaiting user acceptance; PostgreSQL checks deferred.",
    "historical-attendance-trend-reports": "Implemented: scoped historical weekly/monthly Excel and offline interactive HTML, saved history, employee/DC comparisons, charts and coordinated filters, incident dates, dated score overrides and conservative shift/day/post-day-off/leave pattern analysis. Confirmed policies: Monday weeks, selected-period patterns, minimum three eligible shifts, managers' current authorized teams with dated record attribution. Missing schedule continuity and history remain explicitly unavailable. Awaiting user acceptance; PostgreSQL validation deferred.",
    "unified-application-shell": "Implemented: shared /signin account/business selection and role-aware Access/Trades/Business/owner navigation, branding/themes, scoped alerts and preserved legacy/deep links. Administrator browser workspace remains at /. Existing MFA, role, tenant, team and idle-session guards are retained. Awaiting acceptance; prerequisite statuses are unchanged.",
    "employee-trade-location-lock": "Implemented: personal trade location/team and Employee 1 are preselected and locked, including linked-manager personal mode. Choices/options/submission recheck current verified assignments; management choices retain authorized scope. Awaiting acceptance; prerequisite statuses are unchanged.",
    "snapshot-email-reports": "Implemented download-only scope: immutable Silver+ attendance XLSX/history, on-demand capture, opt-in 07:00/15:00/23:00 Jamaica worker captures, exact cutoff/verified overnight context, source freshness and explicit stale/failed/missed states with deduplication. Run report_worker.py independently with the app database/environment. Automatic email/recipient/delivery work is deferred by agreement; no email is sent. Staffing-vs-demand interval analytics are separate Gold/Platinum work. Awaiting acceptance and disposable PostgreSQL policy verification; prerequisite statuses are unchanged.",
}
MEMBERSHIP_TIERS = {
    "bronze": {
        "name": "Bronze",
        "limits": {"admins": 2, "teams": 2, "employees": 20, "locations": 2},
        "features": {
            "scheduleGeneration": True,
            "scheduleSharing": True,
            "bamboohrPublishing": True,
            "emailConfiguration": True,
            "employeeManagement": True,
            "settings": True,
            "employeeScheduleAccess": False,
            "shiftTrades": False,
            "scheduleHistory": False,
            "overtimeForecasting": False,
        },
    },
    "silver": {
        "name": "Silver",
        "limits": {"admins": 3, "teams": 4, "employees": 60, "locations": 4},
        "features": {
            "scheduleGeneration": True,
            "scheduleSharing": True,
            "bamboohrPublishing": True,
            "emailConfiguration": True,
            "employeeManagement": True,
            "settings": True,
            "employeeScheduleAccess": True,
            "shiftTrades": True,
            "scheduleHistory": True,
            "overtimeForecasting": False,
        },
    },
    "gold": {
        "name": "Gold",
        "limits": {"admins": 4, "teams": None, "employees": None, "locations": 6},
        "features": {
            "scheduleGeneration": True,
            "scheduleSharing": True,
            "bamboohrPublishing": True,
            "emailConfiguration": True,
            "employeeManagement": True,
            "settings": True,
            "employeeScheduleAccess": True,
            "shiftTrades": True,
            "scheduleHistory": True,
            "overtimeForecasting": True,
        },
    },
    "platinum": {
        "name": "Platinum",
        "limits": {"admins": 8, "teams": None, "employees": None, "locations": None},
        "features": {
            "scheduleGeneration": True,
            "scheduleSharing": True,
            "bamboohrPublishing": True,
            "emailConfiguration": True,
            "employeeManagement": True,
            "settings": True,
            "employeeScheduleAccess": True,
            "shiftTrades": True,
            "scheduleHistory": True,
            "overtimeForecasting": True,
        },
    },
}


def load_persistent_secret(environment_name: str, filename: str) -> str:
    configured = os.environ.get(environment_name, "").strip()
    if configured:
        if len(configured) < 32:
            raise RuntimeError(f"{environment_name} must contain at least 32 characters.")
        return configured
    if DATABASE_URL:
        raise RuntimeError(
            f"{environment_name} must be configured when PostgreSQL is enabled."
        )
    secret_path = APP_DIRECTORY / "data" / filename
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        secret = secret_path.read_text(encoding="utf-8").strip()
    else:
        secret = secrets.token_urlsafe(48)
        with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
            secret_file.write(secret)
    if len(secret) < 32:
        raise RuntimeError(f"Persistent secret file {secret_path} is invalid.")
    return secret


LOCAL_FLASK_SECRET = load_persistent_secret("FLASK_SECRET_KEY", "flask_secret.key")
MFA_ENCRYPTION_KEY = load_persistent_secret(
    "SCHEDULE_CREATOR_MFA_ENCRYPTION_KEY", "mfa_encryption.key"
)


app = Flask(__name__, static_folder=None)
if TRUSTED_PROXY_HOPS:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_proto=TRUSTED_PROXY_HOPS,
        x_host=TRUSTED_PROXY_HOPS,
    )
app.config["MAX_CONTENT_LENGTH"] = MAX_ACCEPTED_SCHEDULE_BYTES
app.config["SECRET_KEY"] = LOCAL_FLASK_SECRET
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = bool(DATABASE_URL) and not ALLOW_LAN_HTTP
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback):
        return self.connection.__exit__(exception_type, exception, traceback)

    def close(self):
        self.connection.close()

    def rollback(self):
        self.connection.rollback()

    def execute(self, query, parameters=()):
        normalized = query.strip()
        if normalized.casefold().startswith("pragma foreign_keys"):
            return self.connection.execute("SELECT 1 WHERE FALSE")
        pragma = re.fullmatch(r"PRAGMA\s+table_info\((\w+)\)", normalized, re.IGNORECASE)
        if pragma:
            return self.connection.execute(
                """
                SELECT ordinal_position - 1, column_name, data_type,
                       CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END,
                       column_default, 0
                FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = %s
                ORDER BY ordinal_position
                """,
                (pragma.group(1),),
            )
        return self.connection.execute(self._translate(normalized), parameters)

    @classmethod
    def _translate(cls, query):
        normalized = query.strip()
        if re.match(r"INSERT\s+OR\s+IGNORE\s+INTO\s+", normalized, re.IGNORECASE):
            normalized = re.sub(
                r"INSERT\s+OR\s+IGNORE\s+INTO\s+",
                "INSERT INTO ",
                normalized,
                count=1,
                flags=re.IGNORECASE,
            )
            normalized = normalized.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        normalized = re.sub(r"\bCOLLATE\s+NOCASE\b", "", normalized, flags=re.IGNORECASE)
        normalized = normalized.replace(
            "lower(hex(randomblob(12)))",
            "substr(md5(random()::text || clock_timestamp()::text), 1, 24)",
        )
        return cls._postgres_placeholders(normalized)

    def executemany(self, query, parameters):
        cursor = self.connection.cursor()
        cursor.executemany(self._translate(query), parameters)
        return cursor

    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    @staticmethod
    def _postgres_placeholders(query: str) -> str:
        output = []
        quote = None
        index = 0
        while index < len(query):
            char = query[index]
            if quote:
                output.append(char)
                if char == quote:
                    if index + 1 < len(query) and query[index + 1] == quote:
                        output.append(query[index + 1])
                        index += 1
                    else:
                        quote = None
            elif char in {"'", '"'}:
                quote = char
                output.append(char)
            elif char == "?":
                output.append("%s")
            else:
                output.append(char)
            index += 1
        return "".join(output)


DatabaseConnection = sqlite3.Connection | PostgresConnection


def database_connect():
    if not DATABASE_URL:
        return sqlite3.connect(DATABASE_PATH)
    try:
        import psycopg
        from psycopg.rows import tuple_row
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL is configured but psycopg is not installed. Install requirements.txt."
        ) from error
    connection = psycopg.connect(DATABASE_URL, row_factory=tuple_row, connect_timeout=10)
    tenant_id = (
        getattr(g, "tenant_id", None)
        if has_request_context()
        else None
    ) or DEFAULT_TENANT_ID
    wrapped = PostgresConnection(connection)
    wrapped.execute("SELECT set_config('app.tenant_id', ?, false)", (tenant_id,))
    return wrapped


def database_integrity_errors() -> tuple[type[BaseException], ...]:
    if not DATABASE_URL:
        return (sqlite3.IntegrityError,)
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL is configured but psycopg is not installed. Install requirements.txt."
        ) from error
    return (sqlite3.IntegrityError, psycopg.IntegrityError)


def database_errors() -> tuple[type[BaseException], ...]:
    if not DATABASE_URL:
        return (sqlite3.Error,)
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL is configured but psycopg is not installed. Install requirements.txt."
        ) from error
    return (sqlite3.Error, psycopg.Error)


def mfa_cipher() -> Fernet:
    derived_key = hashlib.sha256(
        b"cbl-scheduler-admin-mfa-encryption\0" + MFA_ENCRYPTION_KEY.encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(derived_key))


def active_tenant_id() -> str:
    tenant_id = getattr(g, "tenant_id", None) if has_request_context() else None
    return tenant_id or DEFAULT_TENANT_ID


def tenant_membership_tier(
    connection: DatabaseConnection, tenant_id: str | None = None
) -> str:
    row = connection.execute(
        "SELECT membership_tier FROM tenants WHERE tenant_id = ?",
        (tenant_id or active_tenant_id(),),
    ).fetchone()
    tier = row[0] if row else "bronze"
    return tier if tier in MEMBERSHIP_TIERS else "bronze"


def membership_usage(
    connection: DatabaseConnection, tenant_id: str | None = None
) -> dict[str, int]:
    selected_tenant = tenant_id or active_tenant_id()
    counts = {}
    for key, table, condition in (
        ("admins", "tenant_admins", "active = 1"),
        ("employees", "employees", "active = 1"),
    ):
        counts[key] = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE tenant_id = ? AND {condition}",
            (selected_tenant,),
        ).fetchone()[0]
    counts["locations"] = connection.execute(
        """
        SELECT COUNT(DISTINCT LOWER(location))
        FROM schedule_locations WHERE tenant_id = ?
        """,
        (selected_tenant,),
    ).fetchone()[0]
    if DATABASE_URL:
        connection.execute(
            "SELECT set_config('app.tenant_id', ?, false)", (selected_tenant,)
        )
    team_rows = connection.execute(
        """
        SELECT DISTINCT LOWER(location), LOWER(role_group)
        FROM schedule_locations
        WHERE tenant_id = ?
        """,
        (selected_tenant,),
    ).fetchall()
    counts["teams"] = len(team_rows)
    if DATABASE_URL:
        connection.execute(
            "SELECT set_config('app.tenant_id', ?, false)", (active_tenant_id(),)
        )
    return counts


def membership_summary(
    connection: DatabaseConnection, tenant_id: str | None = None
) -> dict:
    selected_tenant = tenant_id or active_tenant_id()
    tier = tenant_membership_tier(connection, tenant_id)
    policy = MEMBERSHIP_TIERS[tier]
    status = connection.execute(
        "SELECT membership_status FROM tenants WHERE tenant_id = ?",
        (selected_tenant,),
    ).fetchone()
    return {
        "tier": tier,
        "tierName": policy["name"],
        "status": status[0] if status else "active",
        "limits": policy["limits"],
        "features": membership_billing.features(connection, tier, policy["features"]),
        "billingSuspended": membership_billing.access_suspended(connection, selected_tenant),
        "usage": membership_usage(connection, selected_tenant),
        "userLicenses": policy["limits"]["admins"],
    }


def membership_limit_error(tier: str, resource: str, usage: int, limit: int):
    labels = {
        "admins": "active administrator",
        "employees": "active employee",
        "locations": "location",
        "teams": "configured location/role team",
    }
    return jsonify(
        error=(
            f"The {MEMBERSHIP_TIERS[tier]['name']} "
            f"plan allows {limit} {labels[resource]}(s); {usage} are already in use. "
            "Remove or deactivate existing items, or ask the platform owner to change the plan."
        ),
        limit=limit,
        usage=usage,
        resource=resource,
    ), 409


def membership_quota_response(
    connection: DatabaseConnection,
    resource: str,
    *,
    additions: int = 1,
    tenant_id: str | None = None,
):
    if additions <= 0:
        return None
    selected_tenant = tenant_id or active_tenant_id()
    tier = tenant_membership_tier(connection, selected_tenant)
    limit = MEMBERSHIP_TIERS[tier]["limits"][resource]
    if limit is None:
        return None
    usage = membership_usage(connection, selected_tenant)[resource]
    if usage + additions <= limit:
        return None
    return membership_limit_error(tier, resource, usage, limit)


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(database_connect()) as connection, connection:
        if DATABASE_URL:
            role = connection.execute(
                """
                SELECT rolsuper, rolbypassrls
                FROM pg_roles
                WHERE rolname = current_user
                """
            ).fetchone()
            if not role or role[0] or role[1]:
                raise RuntimeError(
                    "Use a dedicated PostgreSQL application role without SUPERUSER or BYPASSRLS."
                )
        connection.executescript(workforce_trades.SCHEMA)
        if "override_reason" not in {row[1] for row in connection.execute("PRAGMA table_info(shift_trades)")}:
            connection.execute("ALTER TABLE shift_trades ADD COLUMN override_reason TEXT NOT NULL DEFAULT ''")
        trade_columns = {row[1] for row in connection.execute("PRAGMA table_info(shift_trades)")}
        for column, definition in (
            ("days", "TEXT NOT NULL DEFAULT '[]'"),
            ("rest_warnings", "TEXT NOT NULL DEFAULT '{}'"),
            ("rest_acknowledged", "TEXT NOT NULL DEFAULT '[]'"),
            ("initiated_role", "TEXT NOT NULL DEFAULT 'employee'"),
            ("target_confirmed", "INTEGER NOT NULL DEFAULT 0"),
            ("constraint_policy", "TEXT NOT NULL DEFAULT 'legacy'"),
        ):
            if column not in trade_columns:
                connection.execute(f"ALTER TABLE shift_trades ADD COLUMN {column} {definition}")
        connection.executescript(membership_billing.SCHEMA)
        connection.executescript(attendance_reports.SCHEMA)
        connection.executescript(roster_settings.SCHEMA)
        connection.executescript(meta_settings.SCHEMA)
        connection.executescript(knowledge_base.SCHEMA)
        if "plan_id" not in {row[1] for row in connection.execute("PRAGMA table_info(billing_accounts)")}:
            connection.execute("ALTER TABLE billing_accounts ADD COLUMN plan_id TEXT NOT NULL DEFAULT ''")
        tenant_default = (
            "current_setting('app.tenant_id', true)"
            if DATABASE_URL
            else f"'{DEFAULT_TENANT_ID}'"
        )
        accepted_schedule_keys = (
            "PRIMARY KEY (tenant_id, run_id)"
            if DATABASE_URL
            else "PRIMARY KEY (run_id)"
        )
        schedule_location_keys = (
            """
            PRIMARY KEY (tenant_id, id),
            UNIQUE (tenant_id, name),
            UNIQUE (tenant_id, bamboo_schedule_id)
            """
            if DATABASE_URL
            else """
            PRIMARY KEY (id),
            UNIQUE (name),
            UNIQUE (bamboo_schedule_id)
            """
        )
        employee_keys = (
            "PRIMARY KEY (tenant_id, employee_id), UNIQUE (tenant_id, bamboohr_id)"
            if DATABASE_URL
            else "PRIMARY KEY (employee_id), UNIQUE (bamboohr_id)"
        )
        employee_location_reference = (
            "FOREIGN KEY (tenant_id, schedule_location_id) "
            "REFERENCES schedule_locations (tenant_id, id)"
            if DATABASE_URL
            else "FOREIGN KEY (schedule_location_id) "
            "REFERENCES schedule_locations (id) ON DELETE SET NULL"
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS accepted_schedules (
                run_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                week_start TEXT NOT NULL,
                location TEXT NOT NULL,
                role TEXT NOT NULL,
                payload TEXT NOT NULL,
                {accepted_schedule_keys}
            )
            """
        )
        connection.executescript(
            f"""
            {session_idle.SCHEMA}
            CREATE TABLE IF NOT EXISTS schedule_locations (
                id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                name TEXT NOT NULL,
                bamboo_schedule_id TEXT NOT NULL,
                location TEXT NOT NULL,
                role_group TEXT NOT NULL DEFAULT '',
                manager_name TEXT NOT NULL DEFAULT '',
                manager_email TEXT NOT NULL DEFAULT '',
                {schedule_location_keys}
            );
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                bamboohr_id TEXT,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                schedule_location_id TEXT,
                source_type TEXT NOT NULL DEFAULT 'bamboohr' CHECK (source_type IN ('bamboohr', 'manual')),
                bamboohr_location TEXT NOT NULL DEFAULT '',
                bamboohr_active INTEGER NOT NULL DEFAULT 1 CHECK (bamboohr_active IN (0, 1)),
                {employee_keys},
                {employee_location_reference}
            );
            CREATE TABLE IF NOT EXISTS roster_configurations (
                tenant_id TEXT PRIMARY KEY,
                revision INTEGER NOT NULL DEFAULT 1,
                locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
                pools_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS roster_employee_settings (
                tenant_id TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                settings_json TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tenant_id, employee_id)
            );
            CREATE TABLE IF NOT EXISTS app_migrations (
                migration_id TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS application_settings (
                setting_key TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                setting_value TEXT NOT NULL,
                PRIMARY KEY (tenant_id, setting_key)
            );
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                business_name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                bamboohr_subdomain TEXT
            );
            CREATE TABLE IF NOT EXISTS tenant_admins (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                email TEXT NOT NULL,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                mfa_secret TEXT,
                mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1)),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                auth_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tenant_login_attempts (
                login_key TEXT PRIMARY KEY,
                failures INTEGER NOT NULL DEFAULT 0,
                window_started_at INTEGER NOT NULL,
                locked_until INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS tenant_mfa_enrollments (
                admin_id TEXT PRIMARY KEY REFERENCES tenant_admins(id) ON DELETE CASCADE,
                encrypted_secret TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tenant_users (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                role TEXT NOT NULL CHECK (role IN ('manager', 'employee')),
                email TEXT,
                employee_id TEXT,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                must_change_password INTEGER NOT NULL DEFAULT 1 CHECK (must_change_password IN (0, 1)),
                temp_password_expires_at INTEGER NOT NULL DEFAULT 0,
                mfa_secret TEXT,
                mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1)),
                mfa_pending_secret TEXT,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                auth_version INTEGER NOT NULL DEFAULT 1,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS tenant_users_email_unique
            ON tenant_users (tenant_id, email);
            CREATE UNIQUE INDEX IF NOT EXISTS tenant_users_employee_unique
            ON tenant_users (tenant_id, employee_id);
            CREATE TABLE IF NOT EXISTS attendance_notifications (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                dedupe_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                employee_name TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                shift_date TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (tenant_id, dedupe_key)
            );
            CREATE TABLE IF NOT EXISTS attendance_notification_reads (
                tenant_id TEXT NOT NULL,
                notification_id TEXT NOT NULL,
                reader_key TEXT NOT NULL,
                read_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                archived INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (tenant_id, notification_id, reader_key)
            );
            CREATE TABLE IF NOT EXISTS schedule_portal_codes (
                tenant_id TEXT NOT NULL,
                location_id TEXT NOT NULL,
                role TEXT NOT NULL,
                period_start TEXT NOT NULL,
                code_hash TEXT NOT NULL UNIQUE,
                encrypted_code TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, location_id, role, period_start)
            );
            CREATE TABLE IF NOT EXISTS tenant_audit_events (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT {tenant_default},
                actor_id TEXT,
                actor_email TEXT,
                action TEXT NOT NULL,
                route TEXT NOT NULL,
                response_status INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS attendance_time_entries (
                tenant_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                bamboohr_id TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                timezone TEXT NOT NULL,
                approved INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (tenant_id, entry_id)
            );
            CREATE TABLE IF NOT EXISTS attendance_shift_records (
                tenant_id TEXT NOT NULL,
                schedule_run_id TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                shift_date TEXT NOT NULL,
                shift_start REAL NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                employee_name TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT '',
                clock_in_at TEXT,
                clock_in_timezone TEXT NOT NULL DEFAULT '',
                clock_out_at TEXT,
                shift_end_at TEXT,
                worked_minutes INTEGER,
                early_minutes INTEGER NOT NULL DEFAULT 0,
                overtime_minutes INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tenant_id, schedule_run_id, employee_id, shift_date)
            );
            CREATE TABLE IF NOT EXISTS attendance_shift_audit_events (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                schedule_run_id TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                shift_date TEXT NOT NULL,
                previous_status TEXT,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                actor_id TEXT,
                actor_email TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS attendance_reconciliation_audit_events (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                discrepancy_id TEXT NOT NULL,
                direction TEXT NOT NULL CHECK (direction IN ('app_to_bamboohr', 'bamboohr_to_app')),
                shift_date TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                before_json TEXT NOT NULL,
                after_json TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK (outcome IN ('succeeded', 'partial', 'failed')),
                actor_id TEXT,
                actor_email TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS attendance_clock_action_audit_events (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                bamboohr_id TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                schedule_run_id TEXT NOT NULL,
                shift_date TEXT NOT NULL,
                action TEXT NOT NULL CHECK (action IN ('clock_in', 'clock_out', 'clock_out_shift_end')),
                outcome TEXT NOT NULL CHECK (outcome IN ('pending', 'succeeded', 'failed', 'unknown', 'rejected')),
                reason TEXT NOT NULL,
                requested_date TEXT NOT NULL,
                requested_time TEXT NOT NULL,
                before_json TEXT NOT NULL DEFAULT '{{}}',
                after_json TEXT NOT NULL DEFAULT '{{}}',
                detail TEXT NOT NULL DEFAULT '',
                actor_id TEXT,
                actor_email TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (tenant_id, request_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS attendance_clock_action_claim_idx
                ON attendance_clock_action_audit_events (tenant_id, bamboohr_id)
                WHERE outcome IN ('pending', 'unknown');
            CREATE TABLE IF NOT EXISTS attendance_score_overrides (
                tenant_id TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
                reason TEXT NOT NULL,
                actor_id TEXT,
                actor_email TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tenant_id, employee_id)
            );
            CREATE TABLE IF NOT EXISTS attendance_score_audit_events (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                previous_score REAL,
                score REAL,
                reason TEXT NOT NULL,
                actor_id TEXT,
                actor_email TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS platform_owners (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                mfa_secret TEXT,
                mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1)),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                auth_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS platform_mfa_enrollments (
                owner_id TEXT PRIMARY KEY REFERENCES platform_owners(id) ON DELETE CASCADE,
                encrypted_secret TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS hub_audit_events (
                id TEXT PRIMARY KEY,
                actor_email TEXT,
                action TEXT NOT NULL,
                tenant_id TEXT,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS developer_users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                auth_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS developer_login_attempts (
                client_key TEXT PRIMARY KEY,
                failures INTEGER NOT NULL DEFAULT 0,
                window_started_at INTEGER NOT NULL,
                locked_until INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS developer_change_requests (
                request_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'blocked', 'done', 'rejected')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS developer_change_request_dependencies (
                request_id TEXT NOT NULL REFERENCES developer_change_requests(request_id) ON DELETE CASCADE,
                depends_on TEXT NOT NULL REFERENCES developer_change_requests(request_id) ON DELETE CASCADE,
                PRIMARY KEY (request_id, depends_on),
                CHECK (request_id != depends_on)
            );
            """
        )
        tenant_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tenants)")
        }
        status_missing = "status" not in tenant_columns
        for column, definition in (
            (
                "status",
                "TEXT NOT NULL DEFAULT 'active' CHECK "
                "(status IN ('pending', 'active', 'suspended', 'rejected'))",
            ),
            ("status_note", "TEXT NOT NULL DEFAULT ''"),
            ("contact_email", "TEXT NOT NULL DEFAULT ''"),
            ("bamboohr_api_key_encrypted", "TEXT"),
            ("reviewed_at", "TEXT"),
            ("bamboohr_subdomain", "TEXT"),
            ("membership_tier", "TEXT NOT NULL DEFAULT 'bronze'"),
            (
                "membership_status",
                "TEXT NOT NULL DEFAULT 'active' CHECK "
                "(membership_status IN ('active', 'paused', 'cancelled'))",
            ),
        ):
            if column not in tenant_columns:
                connection.execute(f"ALTER TABLE tenants ADD COLUMN {column} {definition}")
        if status_missing:
            connection.execute("UPDATE tenants SET status = 'suspended' WHERE active = 0")
        admin_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tenant_admins)")
        }
        if "is_primary" not in admin_columns:
            connection.execute(
                "ALTER TABLE tenant_admins ADD COLUMN is_primary INTEGER NOT NULL DEFAULT 0"
            )
            connection.execute(
                """
                UPDATE tenant_admins SET is_primary = 1
                WHERE id IN (
                    SELECT (
                        SELECT b.id FROM tenant_admins b
                        WHERE b.tenant_id = t.tenant_id
                        ORDER BY b.created_at, b.id LIMIT 1
                    )
                    FROM tenants t
                )
                """
            )
        if DATABASE_URL:
            unique_constraints = connection.execute(
                """
                SELECT conname, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'tenant_admins'::regclass AND contype = 'u'
                """
            ).fetchall()
            for name, definition in unique_constraints:
                if definition.casefold() == "unique (email)":
                    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                        raise RuntimeError("Unexpected administrator email constraint name.")
                    connection.execute(
                        f'ALTER TABLE tenant_admins DROP CONSTRAINT "{name}"'
                    )
        else:
            legacy_email_unique = False
            for index in connection.execute(
                "PRAGMA index_list(tenant_admins)"
            ).fetchall():
                if not index[2]:
                    continue
                escaped_name = index[1].replace('"', '""')
                indexed_columns = [
                    row[2]
                    for row in connection.execute(
                        f'PRAGMA index_info("{escaped_name}")'
                    ).fetchall()
                ]
                if indexed_columns == ["email"]:
                    legacy_email_unique = True
                    break
            if legacy_email_unique:
                connection.execute(
                    """
                    CREATE TEMP TABLE tenant_mfa_enrollments_email_migration AS
                    SELECT admin_id, encrypted_secret, created_at
                    FROM tenant_mfa_enrollments
                    """
                )
                connection.execute("DROP TABLE tenant_mfa_enrollments")
                connection.execute(
                    """
                    CREATE TABLE tenant_admins_new (
                        id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                        email TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        mfa_secret TEXT,
                        mfa_enabled INTEGER NOT NULL DEFAULT 0
                            CHECK (mfa_enabled IN (0, 1)),
                        active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                        auth_version INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        is_primary INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO tenant_admins_new
                    SELECT id, tenant_id, email, display_name, password_hash,
                           mfa_secret, mfa_enabled, active, auth_version,
                           created_at, updated_at, is_primary
                    FROM tenant_admins
                    """
                )
                connection.execute("DROP TABLE tenant_admins")
                connection.execute(
                    "ALTER TABLE tenant_admins_new RENAME TO tenant_admins"
                )
                connection.execute(
                    """
                    CREATE TABLE tenant_mfa_enrollments (
                        admin_id TEXT PRIMARY KEY
                            REFERENCES tenant_admins(id) ON DELETE CASCADE,
                        encrypted_secret TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO tenant_mfa_enrollments
                        (admin_id, encrypted_secret, created_at)
                    SELECT admin_id, encrypted_secret, created_at
                    FROM tenant_mfa_enrollments_email_migration
                    """
                )
                connection.execute(
                    "DROP TABLE tenant_mfa_enrollments_email_migration"
                )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS tenant_admins_tenant_email_unique
            ON tenant_admins (tenant_id, email)
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO tenants (tenant_id, business_name) VALUES (?, ?)",
            (DEFAULT_TENANT_ID, DEFAULT_APP_CONFIG["businessName"]),
        )
        migrate_developer_accounts(connection)
        for request_id, title, description, _ in DEVELOPER_REQUESTS:
            status = "done" if request_id == "developer-change-log" else "pending"
            connection.execute(
                """
                INSERT OR IGNORE INTO developer_change_requests
                    (request_id, title, description, status)
                VALUES (?, ?, ?, ?)
                """,
                (request_id, title, description, status),
            )
        for request_id, note in WORKFORCE_IMPLEMENTATION_NOTES.items():
            if connection.execute(
                "INSERT OR IGNORE INTO app_migrations(migration_id) VALUES (?)",
                ("workforce-download-shell-v1:" + request_id,),
            ).rowcount:
                connection.execute(
                    "UPDATE developer_change_requests SET description=description || ?,"
                    "updated_at=CURRENT_TIMESTAMP WHERE request_id=?",
                    ("\n\nImplementation update: " + note, request_id),
                )
        if connection.execute(
            "INSERT OR IGNORE INTO app_migrations (migration_id) VALUES (?)",
            ("attendance-automation-tier-update",),
        ).rowcount:
            refreshed = next(
                row for row in DEVELOPER_REQUESTS if row[0] == "attendance-automation"
            )
            connection.execute(
                """
                UPDATE developer_change_requests
                SET description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE request_id = ? AND status = 'pending'
                """,
                (refreshed[2], refreshed[0]),
            )
        if connection.execute(
            "INSERT OR IGNORE INTO app_migrations (migration_id) VALUES (?)",
            ("live-attendance-dashboard-requests-v1",),
        ).rowcount:
            refreshed_requests = {
                row[0]: row
                for row in DEVELOPER_REQUESTS
                if row[0]
                in {
                    "manager-employee-access",
                    "schedule-portal",
                    "attendance-automation",
                    "workforce-dashboards",
                }
            }
            for request_id, request in refreshed_requests.items():
                connection.execute(
                    """
                    UPDATE developer_change_requests
                    SET title = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE request_id = ? AND status IN ('pending', 'in_progress', 'blocked')
                    """,
                    (request[1], request[2], request_id),
                )
        if connection.execute(
            "INSERT OR IGNORE INTO app_migrations (migration_id) VALUES (?)",
            ("attendance-automation-implementation-v1",),
        ).rowcount:
            request = next(
                row for row in DEVELOPER_REQUESTS if row[0] == "attendance-automation"
            )
            connection.execute(
                """
                UPDATE developer_change_requests
                SET title = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE request_id = ? AND status IN ('pending', 'in_progress', 'blocked')
                """,
                (request[1], request[2], request[0]),
            )
        if connection.execute(
            "INSERT OR IGNORE INTO app_migrations (migration_id) VALUES (?)",
            ("scheduled-attendance-snapshot-request-v1",),
        ).rowcount:
            request = next(
                row for row in DEVELOPER_REQUESTS if row[0] == "snapshot-email-reports"
            )
            connection.execute(
                """
                UPDATE developer_change_requests
                SET title = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE request_id = ? AND status IN ('pending', 'in_progress', 'blocked')
                """,
                (request[1], request[2], request[0]),
            )
        if connection.execute(
            "INSERT OR IGNORE INTO app_migrations (migration_id) VALUES (?)",
            ("manager-personal-view-implementation-v1",),
        ).rowcount:
            definition = next(row for row in DEVELOPER_REQUESTS if row[0] == "manager-employee-dual-access")
            connection.execute(
                "UPDATE developer_change_requests SET description=?,updated_at=CURRENT_TIMESTAMP "
                "WHERE request_id=? AND status IN ('pending','in_progress','blocked')",
                (definition[2], definition[0]),
            )
        for request_id, _, _, dependencies in DEVELOPER_REQUESTS:
            connection.executemany(
                """
                INSERT OR IGNORE INTO developer_change_request_dependencies
                    (request_id, depends_on)
                VALUES (?, ?)
                """,
                [(request_id, dependency) for dependency in dependencies],
            )
        for table_name in (
            "accepted_schedules",
            "schedule_locations",
            "employees",
            "roster_configurations",
            "roster_employee_settings",
            "meta_configurations",
            "application_settings",
            "tenant_audit_events",
            "attendance_time_entries",
            "attendance_shift_records",
            "attendance_shift_audit_events",
            "attendance_reconciliation_audit_events",
            "attendance_clock_action_audit_events",
            "attendance_score_overrides",
            "attendance_score_audit_events",
        ):
            columns = {
                row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")
            }
            if "tenant_id" not in columns:
                connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN tenant_id TEXT NOT NULL DEFAULT {tenant_default}"
                )
        if DATABASE_URL:
            def constraints_for(table_name: str) -> dict[str, tuple[str, list[str]]]:
                rows = connection.execute(
                    """
                    SELECT tc.constraint_name, tc.constraint_type, kcu.column_name
                    FROM information_schema.table_constraints tc
                    LEFT JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                     AND tc.table_name = kcu.table_name
                    WHERE tc.table_schema = current_schema()
                      AND tc.table_name = ?
                    ORDER BY tc.constraint_name, kcu.ordinal_position
                    """,
                    (table_name,),
                ).fetchall()
                constraints = {}
                for name, kind, column in rows:
                    constraints.setdefault(name, (kind, []))
                    if column is not None:
                        constraints[name][1].append(column)
                return constraints

            def drop_constraints(table_name: str, kinds: set[str]) -> None:
                for name, (kind, _) in constraints_for(table_name).items():
                    if kind in kinds:
                        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                            raise RuntimeError(f"Unexpected constraint name on {table_name}.")
                        connection.execute(
                            f"ALTER TABLE {table_name} DROP CONSTRAINT {name}"
                        )

            def ensure_primary_key(
                table_name: str,
                columns: list[str],
                additional_unique: tuple[str, ...] = (),
            ) -> None:
                constraints = constraints_for(table_name)
                existing = next(
                    (
                        (name, value[1])
                        for name, value in constraints.items()
                        if value[0] == "PRIMARY KEY"
                    ),
                    None,
                )
                if existing and existing[1] == columns:
                    if additional_unique:
                        present = [
                            [column.strip() for column in value[1]]
                            for value in constraints.values()
                            if value[0] == "UNIQUE"
                        ]
                        if not all(
                            [column.strip() for column in item.split(",")] in present
                            for item in additional_unique
                        ):
                            drop_constraints(table_name, {"PRIMARY KEY", "UNIQUE"})
                            connection.execute(
                                f"ALTER TABLE {table_name} ADD PRIMARY KEY ({', '.join(columns)})"
                            )
                            for unique_columns in additional_unique:
                                connection.execute(
                                    f"ALTER TABLE {table_name} ADD UNIQUE ({unique_columns})"
                                )
                    return
                drop_constraints(table_name, {"PRIMARY KEY", "UNIQUE"})
                connection.execute(
                    f"ALTER TABLE {table_name} ADD PRIMARY KEY ({', '.join(columns)})"
                )
                for unique_columns in additional_unique:
                    connection.execute(
                        f"ALTER TABLE {table_name} ADD UNIQUE ({unique_columns})"
                    )

            foreign_keys = connection.execute(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'employees'::regclass
                  AND contype = 'f'
                  AND confrelid = 'schedule_locations'::regclass
                """
            ).fetchall()
            for (name,) in foreign_keys:
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                    raise RuntimeError("Unexpected employee-location foreign-key name.")
                connection.execute(
                    f"ALTER TABLE employees DROP CONSTRAINT {name}"
                )
            ensure_primary_key("accepted_schedules", ["tenant_id", "run_id"])
            ensure_primary_key(
                "schedule_locations",
                ["tenant_id", "id"],
                ("tenant_id, name", "tenant_id, bamboo_schedule_id"),
            )
            ensure_primary_key(
                "employees",
                ["tenant_id", "employee_id"],
                ("tenant_id, bamboohr_id",),
            )
            ensure_primary_key(
                "application_settings", ["tenant_id", "setting_key"]
            )
            connection.execute(
                """
                ALTER TABLE employees
                ADD CONSTRAINT employees_tenant_location_fkey
                FOREIGN KEY (tenant_id, schedule_location_id)
                REFERENCES schedule_locations (tenant_id, id)
                """
            )
        else:
            settings_info = connection.execute(
                "PRAGMA table_info(application_settings)"
            ).fetchall()
            settings_primary_key = [
                row[1]
                for row in sorted(
                    (row for row in settings_info if row[5]),
                    key=lambda row: row[5],
                )
            ]
            if settings_primary_key != ["tenant_id", "setting_key"]:
                connection.execute(
                    "ALTER TABLE application_settings RENAME TO application_settings_legacy"
                )
                connection.execute(
                    """
                    CREATE TABLE application_settings (
                        setting_key TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        setting_value TEXT NOT NULL,
                        PRIMARY KEY (tenant_id, setting_key)
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO application_settings
                        (setting_key, setting_value, tenant_id)
                    SELECT setting_key, setting_value, tenant_id
                    FROM application_settings_legacy
                    """
                )
                connection.execute("DROP TABLE application_settings_legacy")
        if DATABASE_URL:
            for table_name in (
                "accepted_schedules",
                "schedule_locations",
                "employees",
                "roster_configurations",
                "roster_employee_settings",
                "meta_configurations",
                "application_settings",
                "tenant_audit_events",
                "attendance_time_entries",
                "attendance_shift_records",
                "attendance_shift_audit_events",
                "attendance_reconciliation_audit_events",
                "attendance_clock_action_audit_events",
                "attendance_score_overrides",
                "attendance_score_audit_events",
                "attendance_notifications",
                "attendance_notification_reads",
                "schedule_portal_codes",
                "shift_trades",
                "shift_trade_events",
                "shift_trade_publish",
                "shift_trade_reads",
                "billing_accounts",
                "attendance_reports",
                "attendance_report_settings",
                "billing_events",
                "business_knowledge_articles",
                "business_knowledge_submissions",
                "business_knowledge_revisions",
            ):
                connection.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
                connection.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
                connection.execute(
                    f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}"
                )
                connection.execute(
                    f"""
                    CREATE POLICY tenant_isolation ON {table_name}
                    USING (tenant_id = current_setting('app.tenant_id', true))
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
                    """
                )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS attendance_shift_records_period_idx
            ON attendance_shift_records (tenant_id, shift_date, employee_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS attendance_time_entries_employee_idx
            ON attendance_time_entries (tenant_id, bamboohr_id, entry_date)
            """
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO application_settings
                (setting_key, setting_value, tenant_id)
            VALUES (?, ?, ?)
            """,
            [
                (key, json.dumps(value, ensure_ascii=False) if isinstance(value, list) else str(value), DEFAULT_TENANT_ID)
                for key, value in DEFAULT_APP_CONFIG.items()
            ],
        )
        if DATABASE_URL:
            tenant_rows = connection.execute(
                """
                SELECT tenant_id, bamboohr_subdomain
                FROM tenants
                ORDER BY created_at, tenant_id
                """
            ).fetchall()
            claimed_domains: dict[str, str] = {}
            for tenant_id, claimed_domain in tenant_rows:
                if not claimed_domain:
                    continue
                normalized_domain = claimed_domain.strip().lower()
                existing_owner = claimed_domains.get(normalized_domain)
                if existing_owner and existing_owner != tenant_id:
                    raise RuntimeError(
                        f"BambooHR domain '{normalized_domain}' is already claimed by "
                        f"multiple tenants ({existing_owner} and {tenant_id}). "
                        "Resolve domain ownership before starting the scheduler."
                    )
                claimed_domains[normalized_domain] = tenant_id
            conflicting_domains: list[tuple[str, str, str]] = []
            for tenant_id, claimed_domain in tenant_rows:
                if claimed_domain:
                    continue
                connection.execute(
                    "SELECT set_config('app.tenant_id', ?, false)", (tenant_id,)
                )
                domain = connection.execute(
                    """
                    SELECT setting_value FROM application_settings
                    WHERE tenant_id = ? AND setting_key = 'tenantId'
                    """,
                    (tenant_id,),
                ).fetchone()
                if domain and valid_tenant_id(domain[0]):
                    normalized_domain = domain[0].strip().lower()
                    existing_owner = claimed_domains.get(normalized_domain)
                    if existing_owner and existing_owner != tenant_id:
                        conflicting_domains.append(
                            (normalized_domain, existing_owner, tenant_id)
                        )
                    else:
                        connection.execute(
                            """
                            UPDATE tenants SET bamboohr_subdomain = ?
                            WHERE tenant_id = ? AND bamboohr_subdomain IS NULL
                            """,
                            (normalized_domain, tenant_id),
                        )
                        claimed_domains[normalized_domain] = tenant_id
            connection.execute(
                "SELECT set_config('app.tenant_id', ?, false)", (DEFAULT_TENANT_ID,)
            )
            for domain, owner, conflicting_tenant in conflicting_domains:
                print(
                    f"Warning: BambooHR domain '{domain}' is claimed by tenant "
                    f"'{owner}'; tenant '{conflicting_tenant}' has the same legacy "
                    "setting. That setting was left unchanged and must be resolved."
                )
        else:
            domain = connection.execute(
                """
                SELECT setting_value FROM application_settings
                WHERE tenant_id = ? AND setting_key = 'tenantId'
                """,
                (DEFAULT_TENANT_ID,),
            ).fetchone()
            if domain and valid_tenant_id(domain[0]):
                connection.execute(
                    """
                    UPDATE tenants SET bamboohr_subdomain = ?
                    WHERE tenant_id = ? AND bamboohr_subdomain IS NULL
                    """,
                    (domain[0].lower(), DEFAULT_TENANT_ID),
                )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS tenants_bamboohr_subdomain_unique
            ON tenants (LOWER(bamboohr_subdomain))
            WHERE bamboohr_subdomain IS NOT NULL AND bamboohr_subdomain != ''
            """
        )
        connection.execute(
            """
            UPDATE tenants
            SET business_name = (
                SELECT setting_value FROM application_settings
                WHERE tenant_id = ? AND setting_key = 'businessName'
            )
            WHERE tenant_id = ?
            """,
            (DEFAULT_TENANT_ID, DEFAULT_TENANT_ID),
        )
        location_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(schedule_locations)")
        }
        for column, definition in (
            ("manager_name", "TEXT NOT NULL DEFAULT ''"),
            ("manager_email", "TEXT NOT NULL DEFAULT ''"),
        ):
            if column not in location_columns:
                connection.execute(
                    f"ALTER TABLE schedule_locations ADD COLUMN {column} {definition}"
                )
        notification_read_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(attendance_notification_reads)"
            )
        }
        if "archived" not in notification_read_columns:
            connection.execute(
                "ALTER TABLE attendance_notification_reads "
                "ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
            )
        shift_record_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(attendance_shift_records)")
        }
        for column, definition in (
            ("clock_out_at", "TEXT"),
            ("shift_end_at", "TEXT"),
            ("worked_minutes", "INTEGER"),
            ("early_minutes", "INTEGER NOT NULL DEFAULT 0"),
            ("overtime_minutes", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if column not in shift_record_columns:
                connection.execute(
                    f"ALTER TABLE attendance_shift_records ADD COLUMN {column} {definition}"
                )
        employee_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(employees)")
        }
        source_type_missing = "source_type" not in employee_columns
        for column, definition in (
            ("source_type", "TEXT NOT NULL DEFAULT 'bamboohr'"),
            ("bamboohr_location", "TEXT NOT NULL DEFAULT ''"),
            ("bamboohr_active", "INTEGER NOT NULL DEFAULT 1"),
        ):
            if column not in employee_columns:
                connection.execute(f"ALTER TABLE employees ADD COLUMN {column} {definition}")
        if source_type_missing:
            connection.execute(
                """
                UPDATE employees
                SET source_type = CASE WHEN bamboohr_id IS NULL THEN 'manual' ELSE 'bamboohr' END
                """
            )
            connection.execute(
                """
                UPDATE employees
                SET bamboohr_id = 'MANUAL-' || lower(hex(randomblob(12)))
                WHERE source_type = 'manual' AND (bamboohr_id IS NULL OR bamboohr_id = '')
                """
            )
        else:
            connection.execute(
                """
                UPDATE employees
                SET bamboohr_id = 'MANUAL-' || lower(hex(randomblob(12)))
                WHERE source_type = 'manual' AND (bamboohr_id IS NULL OR bamboohr_id = '')
                """
            )
        migration = connection.execute(
            "SELECT 1 FROM app_migrations WHERE migration_id = ?",
            ("seed-employee-schedule-locations-v1",),
        ).fetchone()
        if migration is None:
            connection.executemany(
                """
                INSERT OR IGNORE INTO schedule_locations
                    (id, name, bamboo_schedule_id, location, role_group)
                VALUES (?, ?, ?, ?, ?)
                """,
                SCHEDULE_LOCATIONS,
            )
            location_data = {
                location_id: (location, role_group)
                for location_id, _, _, location, role_group in SCHEDULE_LOCATIONS
            }
            group_to_role = {
                "Warehouse/Delivery": "Warehouse",
                "Supervisors": "Supervisor (Warehouse)",
                "Settlement": "Settlement",
            }
            seeded_employees = []
            for bamboohr_id, employee_id, name, schedule_location_id in EMPLOYEE_ASSIGNMENTS:
                location, role_group = location_data[schedule_location_id]
                seeded_employees.append(
                    (
                        employee_id,
                        bamboohr_id,
                        name,
                        location,
                        EMPLOYEE_ROLE_OVERRIDES.get(
                            employee_id, group_to_role[role_group]
                        ),
                        0 if employee_id in {"901333", "901443", "901442"} else 1,
                        schedule_location_id,
                    )
                )
            connection.executemany(
                """
                INSERT OR IGNORE INTO employees
                    (employee_id, bamboohr_id, name, location, role, active, schedule_location_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                seeded_employees,
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO employees
                    (employee_id, bamboohr_id, name, location, role, active, schedule_location_id, source_type, bamboohr_active)
                VALUES (?, NULL, ?, ?, ?, 0, NULL, 'manual', 0)
                """,
                UNMAPPED_ROSTER_EMPLOYEE,
            )
            connection.execute(
                "INSERT INTO app_migrations (migration_id) VALUES (?)",
                ("seed-employee-schedule-locations-v1",),
            )
        role_migration = connection.execute(
            "SELECT 1 FROM app_migrations WHERE migration_id = ?",
            ("correct-kidd-warehouse-role-v2",),
        ).fetchone()
        if role_migration is None:
            connection.execute(
                """
                UPDATE employees SET role = 'Warehouse'
                WHERE employee_id = '901405' AND role = 'DC Associate'
                    AND schedule_location_id = 'kidd-warehouse-delivery'
                """
            )
            connection.execute(
                "INSERT INTO app_migrations (migration_id) VALUES (?)",
                ("correct-kidd-warehouse-role-v2",),
            )


def migrate_sqlite_business_data(source_path: Path) -> None:
    if not DATABASE_URL:
        raise RuntimeError("Set SCHEDULE_CREATOR_DATABASE_URL before migrating to PostgreSQL.")
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite migration source was not found: {source_path}")

    with closing(sqlite3.connect(source_path)) as source_connection:
        source_connection.row_factory = sqlite3.Row
        source_connection.execute("BEGIN")
        source_tables = {
            row[0]
            for row in source_connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

        def source_rows(table_name: str) -> list[dict]:
            if table_name not in source_tables:
                return []
            return [
                dict(row)
                for row in source_connection.execute(f"SELECT * FROM {table_name}")
            ]

        setting_rows = source_rows("application_settings")
        source_settings = {
            row["setting_key"]: row["setting_value"]
            for row in setting_rows
        }
        settings = DEFAULT_APP_CONFIG | source_settings
        locations = source_rows("schedule_locations")
        employees = source_rows("employees")
        accepted = source_rows("accepted_schedules")
        admins = source_rows("tenant_admins")
        change_requests = source_rows("developer_change_requests")
        dependencies = source_rows("developer_change_request_dependencies")
        developer_users = source_rows("developer_users")
        migrations = source_rows("app_migrations")
        audit_events = source_rows("tenant_audit_events")
        attendance_time_entries = source_rows("attendance_time_entries")
        attendance_shift_records = source_rows("attendance_shift_records")
        attendance_shift_audit_events = source_rows("attendance_shift_audit_events")
        attendance_reconciliation_audit_events = source_rows(
            "attendance_reconciliation_audit_events"
        )
        attendance_clock_action_audit_events = source_rows(
            "attendance_clock_action_audit_events"
        )
        attendance_score_overrides = source_rows("attendance_score_overrides")
        attendance_score_audit_events = source_rows("attendance_score_audit_events")
        workflow_rows = {
            name: source_rows(name) for name in (
                "tenant_users", "shift_trades", "shift_trade_events", "shift_trade_reads",
                "shift_trade_publish", "billing_accounts", "billing_events",
                "attendance_reports", "attendance_report_settings",
                "billing_subscription_index", "billing_webhook_receipts",
                "attendance_notifications", "attendance_notification_reads",
            )
        }
        billing_configuration = source_rows("billing_configuration")
        source_businesses = source_rows("tenants")
        source_tenants = {
            row["tenant_id"] for rows in [setting_rows, source_businesses, locations, employees, accepted, admins, audit_events,
                                          *workflow_rows.values()]
            for row in rows if row.get("tenant_id")
        }
        if len(source_tenants) > 1:
            raise RuntimeError("The SQLite importer accepts one business only. Do not combine multiple businesses in one import.")

    def source_value(row: dict, column: str, default):
        value = row.get(column, default)
        return default if value is None else value

    with closing(database_connect()) as connection, connection:
        migrated = connection.execute(
            "SELECT 1 FROM app_migrations WHERE migration_id = ?",
            ("sqlite-business-import-v1",),
        ).fetchone()
        if migrated:
            raise RuntimeError("This SQLite database has already been imported.")
        admin_exists = connection.execute(
            "SELECT 1 FROM tenant_admins LIMIT 1"
        ).fetchone()
        schedules_exist = connection.execute(
            "SELECT 1 FROM accepted_schedules WHERE tenant_id = ? LIMIT 1",
            (DEFAULT_TENANT_ID,),
        ).fetchone()
        developer_exists = connection.execute(
            "SELECT 1 FROM developer_users LIMIT 1"
        ).fetchone()
        if admin_exists or schedules_exist or (developer_exists and developer_users):
            raise RuntimeError(
                "Import before provisioning an administrator, creating PostgreSQL schedules, "
                "or setting up target developer credentials."
            )
        if connection.execute("SELECT 1 FROM tenant_users LIMIT 1").fetchone() or (
            billing_configuration and connection.execute("SELECT 1 FROM billing_configuration LIMIT 1").fetchone()
        ):
            raise RuntimeError("Import before creating target access accounts or configuring platform billing.")
        connection.execute(
            "DELETE FROM employees WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        connection.execute(
            "DELETE FROM schedule_locations WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        connection.execute(
            "DELETE FROM accepted_schedules WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        connection.execute(
            "DELETE FROM application_settings WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        connection.execute(
            "DELETE FROM tenant_audit_events WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
        )
        for table_name in (
            "attendance_time_entries",
            "attendance_shift_records",
            "attendance_shift_audit_events",
            "attendance_reconciliation_audit_events",
            "attendance_clock_action_audit_events",
            "attendance_score_overrides",
            "attendance_score_audit_events",
        ):
            connection.execute(
                f"DELETE FROM {table_name} WHERE tenant_id = ?", (DEFAULT_TENANT_ID,)
            )
        if locations:
            connection.executemany(
                """
                INSERT INTO schedule_locations
                    (id, tenant_id, name, bamboo_schedule_id, location, role_group,
                     manager_name, manager_email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, id) DO UPDATE SET
                    name = excluded.name,
                    bamboo_schedule_id = excluded.bamboo_schedule_id,
                    location = excluded.location,
                    role_group = excluded.role_group,
                    manager_name = excluded.manager_name,
                    manager_email = excluded.manager_email
                """,
                [
                    (
                        row["id"],
                        DEFAULT_TENANT_ID,
                        row["name"],
                        row["bamboo_schedule_id"],
                        row["location"],
                        source_value(row, "role_group", ""),
                        source_value(row, "manager_name", ""),
                        source_value(row, "manager_email", ""),
                    )
                    for row in locations
                ],
            )
        if employees:
            connection.executemany(
                """
                INSERT INTO employees
                    (employee_id, tenant_id, bamboohr_id, name, location, role, active,
                     schedule_location_id, source_type, bamboohr_location, bamboohr_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, employee_id) DO UPDATE SET
                    bamboohr_id = excluded.bamboohr_id,
                    name = excluded.name,
                    location = excluded.location,
                    role = excluded.role,
                    active = excluded.active,
                    schedule_location_id = excluded.schedule_location_id,
                    source_type = excluded.source_type,
                    bamboohr_location = excluded.bamboohr_location,
                    bamboohr_active = excluded.bamboohr_active
                """,
                [
                    (
                        row["employee_id"],
                        DEFAULT_TENANT_ID,
                        row.get("bamboohr_id"),
                        row["name"],
                        row["location"],
                        row["role"],
                        source_value(row, "active", 1),
                        row.get("schedule_location_id"),
                        source_value(
                            row,
                            "source_type",
                            "manual" if row.get("bamboohr_id") is None else "bamboohr",
                        ),
                        source_value(row, "bamboohr_location", ""),
                        source_value(row, "bamboohr_active", 1),
                    )
                    for row in employees
                ],
            )
        if accepted:
            connection.executemany(
                """
                INSERT INTO accepted_schedules
                    (run_id, tenant_id, accepted_at, week_start, location, role, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, run_id) DO UPDATE SET
                    accepted_at = excluded.accepted_at,
                    week_start = excluded.week_start,
                    location = excluded.location,
                    role = excluded.role,
                    payload = excluded.payload
                """,
                [
                    (
                        row["run_id"],
                        DEFAULT_TENANT_ID,
                        source_value(row, "accepted_at", datetime.now().isoformat()),
                        row["week_start"],
                        row["location"],
                        row["role"],
                        row["payload"],
                    )
                    for row in accepted
                ],
            )
        if attendance_time_entries:
            connection.executemany(
                """
                INSERT INTO attendance_time_entries
                    (tenant_id, entry_id, bamboohr_id, entry_date, started_at,
                     ended_at, timezone, approved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, entry_id) DO UPDATE SET
                    bamboohr_id = excluded.bamboohr_id,
                    entry_date = excluded.entry_date, started_at = excluded.started_at,
                    ended_at = excluded.ended_at, timezone = excluded.timezone,
                    approved = excluded.approved
                """,
                [
                    (
                        DEFAULT_TENANT_ID, row["entry_id"], row["bamboohr_id"],
                        row["entry_date"], row["started_at"], row["ended_at"],
                        row["timezone"], row["approved"],
                    )
                    for row in attendance_time_entries
                ],
            )
        if attendance_shift_records:
            connection.executemany(
                """
                INSERT INTO attendance_shift_records
                    (tenant_id, schedule_run_id, employee_id, shift_date, shift_start,
                     status, source, reason, employee_name, location, role, clock_in_at,
                     clock_in_timezone, shift_end_at, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, schedule_run_id, employee_id, shift_date)
                DO UPDATE SET shift_start = excluded.shift_start, status = excluded.status,
                    source = excluded.source, reason = excluded.reason,
                    employee_name = excluded.employee_name, location = excluded.location,
                    role = excluded.role, clock_in_at = excluded.clock_in_at,
                    clock_in_timezone = excluded.clock_in_timezone,
                    shift_end_at = excluded.shift_end_at,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        DEFAULT_TENANT_ID, row["schedule_run_id"], row["employee_id"],
                        row["shift_date"], row["shift_start"], row["status"],
                        row["source"], row["reason"], row["employee_name"],
                        row["location"], row["role"], row["clock_in_at"],
                        row["clock_in_timezone"], row.get("shift_end_at"), row["updated_at"],
                    )
                    for row in attendance_shift_records
                ],
            )
        if attendance_shift_audit_events:
            connection.executemany(
                """
                INSERT INTO attendance_shift_audit_events
                    (id, tenant_id, schedule_run_id, employee_id, shift_date,
                     previous_status, status, source, reason, actor_id, actor_email, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    (
                        row["id"], DEFAULT_TENANT_ID, row["schedule_run_id"],
                        row["employee_id"], row["shift_date"], row["previous_status"],
                        row["status"], row["source"], row["reason"], row["actor_id"],
                        row["actor_email"], row["created_at"],
                    )
                    for row in attendance_shift_audit_events
                ],
            )
        if attendance_reconciliation_audit_events:
            connection.executemany(
                """
                INSERT INTO attendance_reconciliation_audit_events
                    (id, tenant_id, discrepancy_id, direction, shift_date,
                     employee_id, reason, before_json, after_json, outcome,
                     actor_id, actor_email, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    (
                        row["id"], DEFAULT_TENANT_ID, row["discrepancy_id"],
                        row["direction"], row["shift_date"], row["employee_id"],
                        row["reason"], row["before_json"], row["after_json"],
                        row["outcome"], row.get("actor_id"), row.get("actor_email"),
                        source_value(row, "created_at", datetime.now().isoformat()),
                    )
                    for row in attendance_reconciliation_audit_events
                ],
            )
        if attendance_clock_action_audit_events:
            connection.executemany(
                """INSERT OR IGNORE INTO attendance_clock_action_audit_events
                   (id,tenant_id,request_id,bamboohr_id,employee_id,schedule_run_id,
                    shift_date,action,outcome,reason,requested_date,requested_time,
                    before_json,after_json,detail,actor_id,actor_email,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    tuple(row[column] for column in (
                        "id", "tenant_id", "request_id", "bamboohr_id", "employee_id",
                        "schedule_run_id", "shift_date", "action", "outcome", "reason",
                        "requested_date", "requested_time", "before_json", "after_json",
                        "detail", "actor_id", "actor_email", "created_at", "updated_at",
                    ))
                    for row in attendance_clock_action_audit_events
                ],
            )
        if attendance_score_overrides:
            connection.executemany(
                """
                INSERT INTO attendance_score_overrides
                    (tenant_id, employee_id, score, reason, actor_id, actor_email, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, employee_id) DO UPDATE SET
                    score = excluded.score, reason = excluded.reason,
                    actor_id = excluded.actor_id, actor_email = excluded.actor_email,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        DEFAULT_TENANT_ID, row["employee_id"], row["score"],
                        row["reason"], row["actor_id"], row["actor_email"],
                        row["updated_at"],
                    )
                    for row in attendance_score_overrides
                ],
            )
        if attendance_score_audit_events:
            connection.executemany(
                """
                INSERT INTO attendance_score_audit_events
                    (id, tenant_id, employee_id, previous_score, score, reason,
                     actor_id, actor_email, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    (
                        row["id"], DEFAULT_TENANT_ID, row["employee_id"],
                        row["previous_score"], row["score"], row["reason"],
                        row["actor_id"], row["actor_email"], row["created_at"],
                    )
                    for row in attendance_score_audit_events
                ],
            )
        connection.executemany(
            """
            INSERT INTO application_settings (setting_key, setting_value, tenant_id)
            VALUES (?, ?, ?)
            ON CONFLICT (tenant_id, setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
            """,
            [(key, value, DEFAULT_TENANT_ID) for key, value in settings.items()],
        )
        connection.execute(
            "UPDATE tenants SET business_name = ? WHERE tenant_id = ?",
            (settings["businessName"], DEFAULT_TENANT_ID),
        )
        if source_businesses:
            business = source_businesses[0]
            connection.execute(
                "UPDATE tenants SET membership_tier=?,membership_status=? WHERE tenant_id=?",
                (business.get("membership_tier", "bronze"), business.get("membership_status", "active"),
                 DEFAULT_TENANT_ID),
            )
        if admins:
            connection.executemany(
                """
                INSERT INTO tenant_admins
                    (id, tenant_id, email, display_name, password_hash,
                     mfa_secret, mfa_enabled, active, auth_version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, NULL, 0, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    email = excluded.email,
                    display_name = excluded.display_name,
                    password_hash = excluded.password_hash,
                    mfa_secret = NULL,
                    mfa_enabled = 0,
                    active = excluded.active,
                    auth_version = excluded.auth_version,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        row["id"],
                        DEFAULT_TENANT_ID,
                        row["email"],
                        row["display_name"],
                        row["password_hash"],
                        source_value(row, "active", 1),
                        source_value(row, "auth_version", 1),
                        source_value(row, "created_at", datetime.now().isoformat()),
                        source_value(row, "updated_at", datetime.now().isoformat()),
                    )
                    for row in admins
                ],
            )
        if developer_users:
            connection.executemany(
                """
                INSERT INTO developer_users
                    (id, username, password_hash, auth_version, created_at, updated_at, username_key)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    username = excluded.username,
                    password_hash = excluded.password_hash,
                    auth_version = excluded.auth_version,
                    username_key = excluded.username_key,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        row["id"],
                        row["username"],
                        row["password_hash"],
                        source_value(row, "auth_version", 1),
                        source_value(row, "created_at", datetime.now().isoformat()),
                        source_value(row, "updated_at", datetime.now().isoformat()),
                        row["username"].casefold(),
                    )
                    for row in developer_users
                ],
            )
        if change_requests:
            connection.executemany(
                """
                INSERT INTO developer_change_requests
                    (request_id, title, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (request_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        row["request_id"],
                        row["title"],
                        row["description"],
                        row["status"],
                        source_value(row, "created_at", datetime.now().isoformat()),
                        source_value(row, "updated_at", datetime.now().isoformat()),
                    )
                    for row in change_requests
                ],
            )
        if dependencies:
            connection.execute("DELETE FROM developer_change_request_dependencies")
            connection.executemany(
                """
                INSERT OR IGNORE INTO developer_change_request_dependencies
                    (request_id, depends_on)
                VALUES (?, ?)
                """,
                [(row["request_id"], row["depends_on"]) for row in dependencies],
            )
        if migrations:
            connection.executemany(
                "INSERT OR IGNORE INTO app_migrations (migration_id) VALUES (?)",
                [(row["migration_id"],) for row in migrations],
            )
        if audit_events:
            connection.executemany(
                """
                INSERT INTO tenant_audit_events
                    (id, tenant_id, actor_id, actor_email, action, route,
                     response_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["id"],
                        DEFAULT_TENANT_ID,
                        row.get("actor_id"),
                        row.get("actor_email"),
                        row["action"],
                        row["route"],
                        row["response_status"],
                        source_value(row, "created_at", datetime.now().isoformat()),
                    )
                    for row in audit_events
                ],
            )
        for table_name, rows in workflow_rows.items():
            target_columns = {column[1] for column in connection.execute(f"PRAGMA table_info({table_name})")}
            for row in rows:
                values = {key: value for key, value in row.items() if key in target_columns}
                if "tenant_id" in target_columns:
                    values["tenant_id"] = DEFAULT_TENANT_ID
                if table_name == "tenant_users":
                    values["auth_version"] = values.get("auth_version", 1) + 1
                columns = ",".join('"' + key.replace('"', '""') + '"' for key in values)
                placeholders = ",".join("?" for _ in values)
                connection.execute(
                    f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
                    tuple(values.values()),
                )
        for row in billing_configuration:
            configuration = json.loads(row["payload"])
            configuration["enabled"] = False
            connection.execute("INSERT INTO billing_configuration(id,payload) VALUES(?,?)",
                               (row["id"], json.dumps(configuration)))
        connection.execute(
            "INSERT INTO app_migrations (migration_id) VALUES (?)",
            ("sqlite-business-import-v1",),
        )


def valid_schedule(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("id"), str)
        and bool(payload["id"])
        and isinstance(payload.get("start"), str)
        and isinstance(payload.get("location"), str)
        and isinstance(payload.get("role"), str)
        and isinstance(payload.get("employees"), list)
        and all(isinstance(employee, dict) for employee in payload["employees"])
    )


def current_app_config() -> dict[str, object]:
    with closing(database_connect()) as connection:
        rows = connection.execute(
            "SELECT setting_key, setting_value FROM application_settings WHERE tenant_id = ?",
            (active_tenant_id(),),
        ).fetchall()
    config = DEFAULT_APP_CONFIG | dict(rows)
    if isinstance(config.get("supportingImages"), str):
        try:
            parsed_images = json.loads(config["supportingImages"])
            config["supportingImages"] = parsed_images if isinstance(parsed_images, list) else []
        except (TypeError, ValueError):
            config["supportingImages"] = []
    if config.get("reportTheme") not in {"light", "dark"}:
        config["reportTheme"] = "light"
    config["apiKeyConfigured"] = str(bool(bamboohr_api_key())).lower()
    return config


def bamboohr_cipher() -> Fernet:
    derived_key = hashlib.sha256(
        b"cbl-scheduler-bamboohr-credentials\0" + MFA_ENCRYPTION_KEY.encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(derived_key))


def encrypt_bamboohr_api_key(api_key: str) -> str:
    return bamboohr_cipher().encrypt(api_key.encode("utf-8")).decode("ascii")


def bamboohr_api_key() -> str:
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection:
        row = connection.execute(
            "SELECT bamboohr_api_key_encrypted FROM tenants WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
    if row and row[0]:
        try:
            return bamboohr_cipher().decrypt(row[0].encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError):
            return ""
    # Only the original business may still fall back to the server environment.
    return os.environ.get("BAMBOOHR_API_KEY", "").strip() if tenant_id == DEFAULT_TENANT_ID else ""


def migrate_environment_bamboohr_key() -> bool:
    api_key = os.environ.get("BAMBOOHR_API_KEY", "").strip()
    if not api_key:
        return False
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE tenants SET bamboohr_api_key_encrypted = ?
            WHERE tenant_id = ? AND bamboohr_api_key_encrypted IS NULL
            """,
            (encrypt_bamboohr_api_key(api_key), DEFAULT_TENANT_ID),
        )
    return updated.rowcount > 0


def bamboohr_endpoint(path: str) -> str:
    tenant_id = current_app_config()["tenantId"]
    return f"https://{tenant_id}.bamboohr.com/api/v1/{path.lstrip('/')}"


def valid_tenant_id(value: object) -> bool:
    return isinstance(value, str) and len(value) <= 63 and re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9-]*", value
    ) is not None


def validate_logo_data_url(value: object) -> str | None:
    if value == "":
        return ""
    if not isinstance(value, str) or len(value) > (MAX_LOGO_BYTES * 4 // 3) + 128:
        return None
    match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", value)
    if not match:
        return None
    try:
        image_bytes = base64.b64decode(match.group(2), validate=True)
    except ValueError:
        return None
    if len(image_bytes) > MAX_LOGO_BYTES:
        return None
    image_type = match.group(1)
    valid_signature = (
        image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        if image_type == "png"
        else image_bytes.startswith(b"\xff\xd8\xff")
        if image_type == "jpeg"
        else image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP"
    )
    return value if valid_signature else None


def valid_app_config(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    business_name = payload.get("businessName")
    team_name = payload.get("teamName")
    tenant_id = payload.get("tenantId")
    primary_color = payload.get("primaryColor")
    accent_color = payload.get("accentColor")
    logo_data_url = validate_logo_data_url(payload.get("logoDataUrl", ""))
    supporting_images = payload.get("supportingImages", [])
    report_theme = payload.get("reportTheme", "light")
    if (
        not isinstance(supporting_images, list)
        or len(supporting_images) > 2
        or any(validate_logo_data_url(image) is None for image in supporting_images)
        or not isinstance(report_theme, str)
        or report_theme not in {"light", "dark"}
    ):
        return None
    if (
        not isinstance(business_name, str)
        or not business_name.strip()
        or len(business_name.strip()) > 120
        or not isinstance(team_name, str)
        or not team_name.strip()
        or len(team_name.strip()) > 120
        or not valid_tenant_id(tenant_id)
        or not isinstance(primary_color, str)
        or re.fullmatch(r"#[0-9a-fA-F]{6}", primary_color) is None
        or not isinstance(accent_color, str)
        or re.fullmatch(r"#[0-9a-fA-F]{6}", accent_color) is None
        or logo_data_url is None
    ):
        return None
    return {
        "businessName": business_name.strip(),
        "teamName": team_name.strip(),
        "logoDataUrl": logo_data_url,
        "supportingImages": supporting_images,
        "reportTheme": report_theme,
        "primaryColor": primary_color.lower(),
        "accentColor": accent_color.lower(),
        "tenantId": tenant_id.lower(),
    }


class BambooDomainConflict(Exception):
    pass


def save_app_config(config: dict[str, object]) -> None:
    with closing(database_connect()) as connection, connection:
        tenant_id = active_tenant_id()
        if "tenantId" in config:
            claimed = connection.execute(
                """
                SELECT tenant_id FROM tenants
                WHERE LOWER(bamboohr_subdomain) = ? AND tenant_id != ?
                """,
                (config["tenantId"].lower(), tenant_id),
            ).fetchone()
            if claimed:
                raise BambooDomainConflict
        connection.executemany(
            """
            INSERT INTO application_settings (setting_key, setting_value, tenant_id)
            VALUES (?, ?, ?)
            ON CONFLICT(tenant_id, setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
            """,
            [
                (key, json.dumps(value, ensure_ascii=False) if isinstance(value, list) else str(value), active_tenant_id())
                for key, value in config.items()
            ],
        )
        if "businessName" in config or "tenantId" in config:
            fields = []
            parameters = []
            if "businessName" in config:
                fields.append("business_name = ?")
                parameters.append(config["businessName"])
            if "tenantId" in config:
                fields.append("bamboohr_subdomain = ?")
                parameters.append(config["tenantId"].lower())
            parameters.append(tenant_id)
            connection.execute(
                f"UPDATE tenants SET {', '.join(fields)} WHERE tenant_id = ?",
                parameters,
            )


def valid_admin_email(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= 254
        and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()) is not None
    )


def provision_tenant_admin(name: str, email: str, password: str) -> str:
    if (
        not valid_admin_email(email)
        or not name.strip()
        or len(name.strip()) > 120
        or not 14 <= len(password) <= 1024
    ):
        raise ValueError("Provide a valid name, email, and password of at least 14 characters.")
    admin_id = secrets.token_urlsafe(18)
    with closing(database_connect()) as connection, connection:
        existing = connection.execute(
            "SELECT 1 FROM tenant_admins WHERE tenant_id = ? LIMIT 1",
            (DEFAULT_TENANT_ID,),
        ).fetchone()
        if existing:
            raise RuntimeError("An administrator has already been initialized for this tenant.")
        created = connection.execute(
            """
            INSERT OR IGNORE INTO tenant_admins
                (id, tenant_id, email, display_name, password_hash, is_primary)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                admin_id,
                DEFAULT_TENANT_ID,
                email.strip().casefold(),
                name.strip(),
                generate_password_hash(password),
            ),
        )
        if created.rowcount == 0:
            raise RuntimeError("An administrator already uses that email address.")
    return admin_id


def reset_tenant_admin_password(email: str, password: str) -> None:
    if not valid_admin_email(email) or not 14 <= len(password) <= 1024:
        raise ValueError("Provide a valid email and a password of at least 14 characters.")
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE tenant_admins
            SET password_hash = ?, auth_version = auth_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND email = ?
            """,
            (generate_password_hash(password), DEFAULT_TENANT_ID, email.strip().casefold()),
        )
        if updated.rowcount == 0:
            raise RuntimeError("No administrator uses that email address.")
        connection.execute("DELETE FROM tenant_login_attempts")


def reset_tenant_admin_mfa(email: str) -> None:
    if not valid_admin_email(email):
        raise ValueError("Provide a valid administrator email.")
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE tenant_admins
            SET mfa_secret = NULL, mfa_enabled = 0, auth_version = auth_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND email = ?
            """,
            (DEFAULT_TENANT_ID, email.strip().casefold()),
        )
        if updated.rowcount == 0:
            raise RuntimeError("No administrator uses that email address.")
        connection.execute("DELETE FROM tenant_login_attempts")


def provision_platform_owner(name: str, email: str, password: str) -> str:
    if (
        not valid_admin_email(email)
        or not name.strip()
        or len(name.strip()) > 120
        or not 14 <= len(password) <= 1024
    ):
        raise ValueError("Provide a valid name, email, and password of at least 14 characters.")
    owner_id = secrets.token_urlsafe(18)
    with closing(database_connect()) as connection, connection:
        created = connection.execute(
            """
            INSERT OR IGNORE INTO platform_owners
                (id, email, display_name, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (owner_id, email.strip().casefold(), name.strip(), generate_password_hash(password)),
        )
        if created.rowcount == 0:
            raise RuntimeError("A platform owner already uses that email address.")
    return owner_id


def reset_platform_owner_password(email: str, password: str) -> None:
    if not valid_admin_email(email) or not 14 <= len(password) <= 1024:
        raise ValueError("Provide a valid email and a password of at least 14 characters.")
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE platform_owners
            SET password_hash = ?, auth_version = auth_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE email = ?
            """,
            (generate_password_hash(password), email.strip().casefold()),
        )
        if updated.rowcount == 0:
            raise RuntimeError("No platform owner uses that email address.")
        connection.execute("DELETE FROM tenant_login_attempts")


def reset_platform_owner_mfa(email: str) -> None:
    if not valid_admin_email(email):
        raise ValueError("Provide a valid platform owner email.")
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE platform_owners
            SET mfa_secret = NULL, mfa_enabled = 0, auth_version = auth_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE email = ?
            """,
            (email.strip().casefold(),),
        )
        if updated.rowcount == 0:
            raise RuntimeError("No platform owner uses that email address.")
        connection.execute("DELETE FROM tenant_login_attempts")


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_value(secret: str, counter: int) -> str:
    padded_secret = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded_secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{number:06d}"


def verify_totp(secret: str, supplied: object) -> bool:
    if not isinstance(supplied, str):
        return False
    # Authenticator apps often display codes as "123 456".
    supplied = re.sub(r"[\s-]", "", supplied)
    if re.fullmatch(r"\d{6}", supplied) is None:
        return False
    counter = int(time_module.time() // 30)
    return any(
        hmac.compare_digest(totp_value(secret, counter + offset), supplied)
        for offset in (-1, 0, 1)
    )


def tenant_authenticated() -> bool:
    admin_id = session.get("tenant_admin_id")
    tenant_id = session.get("tenant_id")
    auth_version = session.get("tenant_auth_version")
    if (
        not isinstance(admin_id, str)
        or not isinstance(tenant_id, str)
        or not isinstance(auth_version, int)
    ):
        return False
    g.tenant_id = tenant_id
    with closing(database_connect()) as connection:
        account = connection.execute(
            """
            SELECT a.auth_version, a.active, a.mfa_enabled, t.status,
                   t.membership_status
            FROM tenant_admins a
            JOIN tenants t ON t.tenant_id = a.tenant_id
            WHERE a.id = ? AND a.tenant_id = ? AND t.status != 'rejected'
            """,
            (admin_id, tenant_id),
        ).fetchone()
    if not account or account[0] != auth_version or not account[1] or not account[2]:
        session.clear()
        g.tenant_id = DEFAULT_TENANT_ID
        return False
    g.tenant_status = account[3]
    g.tenant_membership_status = account[4]
    with closing(database_connect()) as connection:
        if membership_billing.access_suspended(connection, tenant_id):
            g.tenant_membership_status = "billing_suspended"
    return True


def tenant_auth_csrf_valid() -> bool:
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("tenant_auth_csrf", "")
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


def tenant_auth_attempt_key(email: str, bamboohr_subdomain: str) -> str:
    return hmac.new(
        app.config["SECRET_KEY"].encode("utf-8"),
        f"{request.remote_addr or 'unknown'}\0{bamboohr_subdomain}\0{email}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def tenant_auth_attempt_state(
    connection: DatabaseConnection, login_key: str, now: int
) -> tuple[int, int] | None:
    attempt = connection.execute(
        """
        SELECT failures, window_started_at, locked_until
        FROM tenant_login_attempts WHERE login_key = ?
        """,
        (login_key,),
    ).fetchone()
    if attempt and attempt[2] > now:
        return None
    if not attempt or now - attempt[1] >= 900:
        return 0, now
    return attempt[0], attempt[1]


def record_tenant_auth_failure(
    connection: DatabaseConnection,
    login_key: str,
    failures: int,
    window_started_at: int,
    now: int,
) -> None:
    failures += 1
    locked_until = now + 900 if failures >= 5 else 0
    connection.execute(
        """
        INSERT INTO tenant_login_attempts
            (login_key, failures, window_started_at, locked_until)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(login_key) DO UPDATE SET
            failures = excluded.failures,
            window_started_at = excluded.window_started_at,
            locked_until = excluded.locked_until
        """,
        (login_key, failures, window_started_at, locked_until),
    )


def otp_qr_data_uri(otp_uri: str) -> str:
    import segno

    buffer = io.BytesIO()
    segno.make(otp_uri, error="m").save(
        buffer, kind="svg", scale=6, border=4, dark="#000000", light="#ffffff"
    )
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def start_mfa_enrollment(
    connection, admin_id: str, email: str, platform_owner: bool = False
) -> tuple[str, str]:
    secret = new_totp_secret()
    table, column = (
        ("platform_mfa_enrollments", "owner_id")
        if platform_owner
        else ("tenant_mfa_enrollments", "admin_id")
    )
    connection.execute(
        f"""
        INSERT INTO {table} ({column}, encrypted_secret)
        VALUES (?, ?)
        ON CONFLICT({column}) DO UPDATE
        SET encrypted_secret = excluded.encrypted_secret,
            created_at = CURRENT_TIMESTAMP
        """,
        (admin_id, mfa_cipher().encrypt(secret.encode("ascii")).decode("ascii")),
    )
    account_label = f"CBL Schedule:{email}"
    if not platform_owner:
        tenant = connection.execute(
            """
            SELECT t.bamboohr_subdomain
            FROM tenant_admins a
            JOIN tenants t ON t.tenant_id = a.tenant_id
            WHERE a.id = ?
            """,
            (admin_id,),
        ).fetchone()
        if tenant and tenant[0]:
            account_label = f"{account_label} ({tenant[0]})"
    label = quote(account_label)
    return secret, f"otpauth://totp/{label}?secret={secret}&issuer=CBL%20Schedule"


def cross_origin_request() -> bool:
    origin = request.headers.get("Origin")
    if not origin:
        return False
    parsed_origin = urlsplit(origin)
    return (
        parsed_origin.scheme not in {"http", "https"}
        or parsed_origin.netloc.casefold() != request.host.casefold()
    )


session_idle.register(app, sys.modules[__name__])


@app.before_request
def enforce_tenant_authentication():
    g.tenant_id = session.get("tenant_id") or DEFAULT_TENANT_ID
    g.tenant_status = None
    g.tenant_membership_status = None
    if DATABASE_URL and not request.is_secure and not http_allowed_for_client():
        return (
            "HTTPS is required for PostgreSQL-backed deployments. Configure the app's trusted HTTPS reverse proxy.",
            400,
        )
    if request.path == "/api/payments/paypal/webhook":
        return None
    if request.path == "/api/session/state":
        return None
    if request.path.startswith("/api/hub/"):
        if request.method not in {"GET", "HEAD", "OPTIONS"} and cross_origin_request():
            return jsonify(error="Cross-origin requests are not allowed."), 403
        return None
    if (
        request.path.startswith("/api/developer/")
        or request.path.startswith("/api/tenant-auth/")
        or request.path.startswith("/api/access/")
        or request.path.startswith("/api/help/")
    ):
        return None
    if request.path.startswith("/api/"):
        if not tenant_authenticated():
            return jsonify(error="Sign in as a business administrator to continue."), 401
        if request.method not in {"GET", "HEAD", "OPTIONS"} and cross_origin_request():
            return jsonify(error="Cross-origin requests are not allowed."), 403
        if (
            (g.tenant_status != "active" or g.tenant_membership_status != "active")
            and not request.path.startswith("/api/business/")
        ):
            return jsonify(
                error="This business membership is not active. Scheduling is unavailable.",
                businessStatus=g.tenant_status,
                membershipStatus=g.tenant_membership_status,
            ), 403
    return None


@app.after_request
def audit_tenant_mutation(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if DATABASE_URL and request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    if request.path == "/" or request.path.startswith(
        ("/api/tenant-auth/", "/api/hub/", "/api/business/", "/hub", "/api/access",
         "/access", "/api/schedule-portal/", "/trades", "/billing",
         "/api/shift-trades", "/api/shift-overrides", "/api/workspace/")
    ):
        response.headers["Cache-Control"] = "no-store"
    actor_id = session.get("tenant_admin_id") or session.get("pending_tenant_admin_id")
    auth_success = (
        request.path.startswith("/api/tenant-auth/")
        and response.status_code < 400
    )
    if (
        request.path.startswith("/api/")
        and not request.path.startswith("/api/developer/")
        and not request.path.startswith("/api/hub/")
        and request.method not in {"GET", "HEAD", "OPTIONS"}
        and response.status_code < 500
        and (isinstance(actor_id, str) or auth_success)
    ):
        with closing(database_connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO tenant_audit_events
                    (id, tenant_id, actor_id, actor_email, action, route, response_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    secrets.token_urlsafe(18),
                    active_tenant_id(),
                    actor_id,
                    session.get("tenant_admin_email"),
                    request.method,
                    request.endpoint or "unknown",
                    response.status_code,
                ),
            )
    return response


@app.get("/api/tenant-auth/state")
def tenant_auth_state():
    authenticated = tenant_authenticated()
    csrf_token = session.get("tenant_auth_csrf")
    if not isinstance(csrf_token, str):
        csrf_token = secrets.token_urlsafe(32)
        session["tenant_auth_csrf"] = csrf_token
    with closing(database_connect()) as connection:
        configured = connection.execute(
            "SELECT 1 FROM tenant_admins WHERE tenant_id = ? LIMIT 1",
            (DEFAULT_TENANT_ID,),
        ).fetchone() is not None
        profile = (
            connection.execute(
                """
                SELECT display_name, is_primary FROM tenant_admins
                WHERE id = ? AND tenant_id = ?
                """,
                (session.get("tenant_admin_id"), active_tenant_id()),
            ).fetchone()
            if authenticated
            else None
        )
        membership = membership_summary(connection) if authenticated else None
    return jsonify(
        configured=configured,
        authenticated=authenticated,
        tenantId=active_tenant_id() if authenticated else None,
        email=session.get("tenant_admin_email") if authenticated else None,
        displayName=profile[0] if profile else None,
        isPrimaryAdmin=bool(profile and profile[1]),
        businessStatus=g.tenant_status if authenticated else None,
        membership=membership,
        workspaceReadinessEnabled=workspace_readiness_enabled(),
        csrfToken=csrf_token,
        canBootstrap=(
            not DATABASE_URL
            and not configured
            and request.remote_addr in {"127.0.0.1", "::1"}
        ),
    )


def workspace_readiness_enabled() -> bool:
    value = os.environ.get("SCHEDULE_CREATOR_WORKSPACE_READINESS_ENABLED", "1").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    app.logger.warning(
        "Invalid SCHEDULE_CREATOR_WORKSPACE_READINESS_ENABLED value; defaulting to enabled."
    )
    return True


@app.post("/api/workspace/schedule-deletions")
def authorize_workspace_schedule_deletion():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("scope") != "browser-workspace":
        return jsonify(error="Confirm browser-workspace deletion only."), 400
    if payload.get("tenantId") != active_tenant_id():
        return jsonify(error="The signed-in business changed. Reload before deleting."), 409
    run_id = payload.get("runId")
    if not isinstance(run_id, str) or not 1 <= len(run_id.strip()) <= 200:
        return jsonify(error="Choose a valid saved workspace schedule."), 400
    with closing(database_connect()) as connection, connection:
        hub_audit(connection, "workspace-schedule-delete-authorized", active_tenant_id(),
                  json.dumps({"runId": run_id, "scope": "browser-workspace"}),
                  actor_email=session.get("tenant_admin_email"))
    return jsonify(authorized=True, scope="browser-workspace")


def membership_features_for_request() -> dict[str, bool]:
    with closing(database_connect()) as connection:
        tier = tenant_membership_tier(connection)
        return membership_billing.features(connection, tier, MEMBERSHIP_TIERS[tier]["features"])


def membership_feature_denied(feature: str):
    with closing(database_connect()) as connection:
        tier = tenant_membership_tier(connection)
        enabled = membership_billing.features(connection, tier, MEMBERSHIP_TIERS[tier]["features"])
    if enabled.get(feature):
        return None
    labels = {
        "scheduleHistory": "Schedule history is included with Silver and above.",
        "overtimeForecasting": "Overtime forecasting is included with Gold and above.",
        "shiftTrades": "Shift trades are included with Silver and above.",
        "employeeScheduleAccess": "Employee schedule access is included with Silver and above.",
    }
    return jsonify(error=labels.get(feature, "This feature is not included in the business's membership tier.")), 403


@app.post("/api/tenant-auth/bootstrap")
def bootstrap_tenant_admin():
    if DATABASE_URL:
        return jsonify(error="Use the server-side bootstrap-admin command for PostgreSQL."), 403
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return jsonify(error="Initial administrator setup is allowed only from this computer."), 403
    if not tenant_auth_csrf_valid():
        return jsonify(error="The setup session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not valid_admin_email(payload.get("email"))
        or not isinstance(payload.get("name"), str)
        or not payload["name"].strip()
        or len(payload["name"].strip()) > 120
        or not isinstance(payload.get("password"), str)
        or not 14 <= len(payload["password"]) <= 1024
    ):
        return jsonify(error="Enter a valid name, email, and password of at least 14 characters."), 400
    admin_id = secrets.token_urlsafe(18)
    with closing(database_connect()) as connection, connection:
        existing = connection.execute(
            "SELECT 1 FROM tenant_admins WHERE tenant_id = ? LIMIT 1",
            (DEFAULT_TENANT_ID,),
        ).fetchone()
        if existing:
            return jsonify(error="An administrator has already been initialized."), 409
        created = connection.execute(
            """
            INSERT OR IGNORE INTO tenant_admins
                (id, tenant_id, email, display_name, password_hash, is_primary)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                admin_id,
                DEFAULT_TENANT_ID,
                payload["email"].strip().casefold(),
                payload["name"].strip(),
                generate_password_hash(payload["password"]),
            ),
        )
        if created.rowcount == 0:
            return jsonify(error="An administrator already uses that email address."), 409
        secret, otp_uri = start_mfa_enrollment(
            connection, admin_id, payload["email"].strip().casefold()
        )
    session.clear()
    session["pending_tenant_admin_id"] = admin_id
    session["pending_tenant_id"] = DEFAULT_TENANT_ID
    session["tenant_auth_csrf"] = secrets.token_urlsafe(32)
    return jsonify(
        mfaEnrollmentRequired=True,
        secret=secret,
        otpAuthUri=otp_uri,
        qrCode=otp_qr_data_uri(otp_uri),
        csrfToken=session["tenant_auth_csrf"],
    ), 201


@app.post("/api/tenant-auth/login")
def tenant_admin_login():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The sign-in session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not valid_admin_email(payload.get("email"))
        or not isinstance(payload.get("password"), str)
        or not valid_tenant_id(payload.get("bamboohrSubdomain"))
    ):
        return jsonify(error="Enter your BambooHR subdomain, administrator email, and password."), 400
    email = payload["email"].strip().casefold()
    bamboohr_subdomain = payload["bamboohrSubdomain"].strip().lower()
    login_key = tenant_auth_attempt_key(email, bamboohr_subdomain)
    now = int(time_module.time())
    with closing(database_connect()) as connection, connection:
        attempt_state = tenant_auth_attempt_state(connection, login_key, now)
        if attempt_state is None:
            return jsonify(error="Too many failed sign-in attempts. Try again later."), 429
        failures, window_started_at = attempt_state
        account = connection.execute(
            """
            SELECT a.id, a.tenant_id, a.email, a.password_hash, a.mfa_secret,
                   a.mfa_enabled, a.auth_version, a.active
            FROM tenant_admins a
            JOIN tenants t ON t.tenant_id = a.tenant_id AND t.status != 'rejected'
            WHERE a.email = ? AND LOWER(t.bamboohr_subdomain) = ?
            """,
            (email, bamboohr_subdomain),
        ).fetchone()
        password_valid = bool(
            account
            and account[7]
            and check_password_hash(account[3], payload["password"])
        )
        if not password_valid:
            record_tenant_auth_failure(
                connection, login_key, failures, window_started_at, now
            )
            return jsonify(error="The email or password is incorrect."), 401
        if not account[5]:
            g.tenant_id = account[1]
            secret, otp_uri = start_mfa_enrollment(
                connection, account[0], account[2]
            )
            session.clear()
            session["pending_tenant_admin_id"] = account[0]
            session["pending_tenant_id"] = account[1]
            session["tenant_auth_csrf"] = secrets.token_urlsafe(32)
            return jsonify(
                mfaEnrollmentRequired=True,
                secret=secret,
                otpAuthUri=otp_uri,
                qrCode=otp_qr_data_uri(otp_uri),
                csrfToken=session["tenant_auth_csrf"],
            ), 200
        else:
            try:
                secret = mfa_cipher().decrypt(account[4].encode("ascii")).decode("ascii")
            except (AttributeError, InvalidToken, UnicodeDecodeError):
                return jsonify(error="Administrator MFA data is unavailable; contact support."), 503
            if not verify_totp(secret, payload.get("code")):
                record_tenant_auth_failure(
                    connection, login_key, failures, window_started_at, now
                )
                return jsonify(error="The email, password, or verification code is incorrect."), 401
            connection.execute("DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,))
        tenant_admin = account
    session.clear()
    session.permanent = True
    session["tenant_admin_id"] = tenant_admin[0]
    session["tenant_id"] = tenant_admin[1]
    session["tenant_admin_email"] = tenant_admin[2]
    session["tenant_auth_version"] = tenant_admin[6]
    session["tenant_auth_csrf"] = secrets.token_urlsafe(32)
    g.tenant_id = tenant_admin[1]
    return jsonify(authenticated=True, csrfToken=session["tenant_auth_csrf"])


@app.post("/api/tenant-auth/verify-mfa")
def verify_tenant_admin_mfa():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The setup session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    admin_id = session.get("pending_tenant_admin_id")
    tenant_id = session.get("pending_tenant_id")
    if (
        not isinstance(payload, dict)
        or not isinstance(admin_id, str)
        or not isinstance(tenant_id, str)
    ):
        return jsonify(error="Restart administrator sign-in to continue MFA setup."), 401
    g.tenant_id = tenant_id
    with closing(database_connect()) as connection, connection:
        enrollment = connection.execute(
            """
            SELECT e.encrypted_secret, a.email, a.auth_version, a.active,
                   t.bamboohr_subdomain
            FROM tenant_mfa_enrollments e
            JOIN tenant_admins a ON a.id = e.admin_id
            JOIN tenants t ON t.tenant_id = a.tenant_id
            WHERE e.admin_id = ? AND a.tenant_id = ?
            """,
            (admin_id, tenant_id),
        ).fetchone()
        if not enrollment or not enrollment[3]:
            return jsonify(error="The MFA enrollment session is no longer valid."), 401
        now = int(time_module.time())
        login_key = tenant_auth_attempt_key(
            enrollment[1], enrollment[4] or ""
        )
        attempt_state = tenant_auth_attempt_state(connection, login_key, now)
        if attempt_state is None:
            return jsonify(error="Too many failed verification attempts. Try again later."), 429
        try:
            secret = mfa_cipher().decrypt(enrollment[0].encode("ascii")).decode("ascii")
        except (InvalidToken, UnicodeDecodeError):
            return jsonify(error="MFA enrollment data is unavailable; contact support."), 503
        if not verify_totp(secret, payload.get("code")):
            record_tenant_auth_failure(
                connection, login_key, attempt_state[0], attempt_state[1], now
            )
            return jsonify(error="Enter the current six-digit code from your authenticator."), 400
        connection.execute(
            """
            UPDATE tenant_admins
            SET mfa_secret = ?, mfa_enabled = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (mfa_cipher().encrypt(secret.encode("ascii")).decode("ascii"), admin_id, tenant_id),
        )
        connection.execute(
            "DELETE FROM tenant_mfa_enrollments WHERE admin_id = ?", (admin_id,)
        )
        connection.execute(
            "DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,)
        )
    session.clear()
    session.permanent = True
    session["tenant_admin_id"] = admin_id
    session["tenant_id"] = tenant_id
    session["tenant_admin_email"] = enrollment[1]
    session["tenant_auth_version"] = enrollment[2]
    session["tenant_auth_csrf"] = secrets.token_urlsafe(32)
    g.tenant_id = tenant_id
    return jsonify(authenticated=True, csrfToken=session["tenant_auth_csrf"])


@app.post("/api/tenant-auth/logout")
def tenant_admin_logout():
    if not tenant_authenticated():
        return jsonify(error="Sign in first."), 401
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    session.clear()
    return jsonify(loggedOut=True)


BUSINESS_STATUS_TRANSITIONS = {
    "pending": {"active", "rejected"},
    "active": {"suspended"},
    "suspended": {"active"},
    "rejected": {"pending"},
}
# Several businesses can share one database only when PostgreSQL enforces tenant isolation.
MULTI_BUSINESS = bool(DATABASE_URL)


class RegistrationConflict(Exception):
    pass


def hub_csrf_valid() -> bool:
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("hub_csrf", "")
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


def hub_attempt_key(kind: str, identifier: str = "") -> str:
    return hmac.new(
        app.config["SECRET_KEY"].encode("utf-8"),
        f"hub-{kind}\0{request.remote_addr or 'unknown'}\0{identifier}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hub_audit(
    connection: DatabaseConnection,
    action: str,
    tenant_id: str | None = None,
    detail: str = "",
    actor_email: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO hub_audit_events (id, actor_email, action, tenant_id, detail)
        VALUES (?, ?, ?, ?, ?)
        """,
        (secrets.token_urlsafe(18), actor_email, action, tenant_id, detail[:500]),
    )


def clear_hub_session() -> None:
    for key in (
        "platform_owner_id",
        "platform_owner_email",
        "platform_auth_version",
        "pending_platform_owner_id",
    ):
        session.pop(key, None)
    session["hub_csrf"] = secrets.token_urlsafe(32)


def platform_owner_authenticated() -> bool:
    owner_id = session.get("platform_owner_id")
    auth_version = session.get("platform_auth_version")
    if not isinstance(owner_id, str) or not isinstance(auth_version, int):
        return False
    with closing(database_connect()) as connection:
        account = connection.execute(
            "SELECT auth_version, active, mfa_enabled FROM platform_owners WHERE id = ?",
            (owner_id,),
        ).fetchone()
    if not account or account[0] != auth_version or not account[1] or not account[2]:
        clear_hub_session()
        return False
    return True


def platform_owner_guard():
    if not platform_owner_authenticated():
        return jsonify(error="Sign in as the platform owner to continue."), 401
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not hub_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    return None


def business_slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:40].strip("-")
    return f"{base or 'business'}-{secrets.token_hex(3)}"


@app.get("/api/hub/state")
def hub_state():
    if not isinstance(session.get("hub_csrf"), str):
        session["hub_csrf"] = secrets.token_urlsafe(32)
    authenticated = platform_owner_authenticated()
    with closing(database_connect()) as connection:
        configured = connection.execute(
            "SELECT 1 FROM platform_owners LIMIT 1"
        ).fetchone() is not None
    return jsonify(
        csrfToken=session["hub_csrf"],
        registrationOpen=MULTI_BUSINESS,
        ownerConfigured=configured,
        ownerAuthenticated=authenticated,
        ownerEmail=session.get("platform_owner_email") if authenticated else None,
    )


@app.post("/api/hub/register")
def hub_register():
    if not MULTI_BUSINESS:
        return jsonify(
            error="Business registration requires the PostgreSQL multi-business deployment."
        ), 503
    if not hub_csrf_valid():
        return jsonify(error="The registration session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Send the registration details as JSON."), 400
    business_name = payload.get("businessName")
    subdomain = payload.get("bamboohrSubdomain")
    api_key = payload.get("bamboohrApiKey")
    admin_name = payload.get("adminName")
    admin_email = payload.get("adminEmail")
    password = payload.get("password")
    if (
        not isinstance(business_name, str)
        or not 2 <= len(business_name.strip()) <= 120
        or not valid_tenant_id(subdomain)
        or not valid_bamboohr_api_key(api_key)
        or not isinstance(admin_name, str)
        or not 1 <= len(admin_name.strip()) <= 120
        or not valid_admin_email(admin_email)
        or not isinstance(password, str)
        or not 14 <= len(password) <= 1024
    ):
        return jsonify(
            error="Enter the business name, BambooHR subdomain and API key, and an administrator name, email, and password of at least 14 characters."
        ), 400
    business_name, subdomain = business_name.strip(), subdomain.lower()
    email = admin_email.strip().casefold()
    limit_key = hub_attempt_key("register")
    now = int(time_module.time())
    with closing(database_connect()) as connection, connection:
        attempt_state = tenant_auth_attempt_state(connection, limit_key, now)
        if attempt_state is None:
            return jsonify(error="Too many registration attempts. Try again later."), 429
        record_tenant_auth_failure(connection, limit_key, *attempt_state, now)
    with closing(database_connect()) as connection:
        if connection.execute(
            "SELECT 1 FROM tenants WHERE LOWER(bamboohr_subdomain) = ?",
            (subdomain,),
        ).fetchone():
            return jsonify(
                error=(
                    "This BambooHR domain is already registered. Contact the existing "
                    "business owner to be added, or contact the platform owner to "
                    "resolve domain ownership."
                )
            ), 409
    failure = check_bamboohr_credentials(subdomain, api_key)
    if failure:
        return jsonify(error=failure[0]), 400 if failure[1] in {401, 403} else failure[1]

    tenant_id = business_slug(business_name)
    admin_id = secrets.token_urlsafe(18)
    try:
        with closing(database_connect()) as connection, connection:
            if connection.execute(
                "SELECT 1 FROM tenants WHERE LOWER(bamboohr_subdomain) = ?",
                (subdomain,),
            ).fetchone():
                raise BambooDomainConflict
            connection.execute(
                """
                INSERT INTO tenants
                    (tenant_id, business_name, status, contact_email,
                     bamboohr_api_key_encrypted, bamboohr_subdomain)
                VALUES (?, ?, 'pending', ?, ?, ?)
                """,
                (
                    tenant_id,
                    business_name,
                    email,
                    encrypt_bamboohr_api_key(api_key.strip()),
                    subdomain,
                ),
            )
            connection.execute(
                """
                INSERT INTO tenant_admins
                    (id, tenant_id, email, display_name, password_hash, is_primary)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (admin_id, tenant_id, email, admin_name.strip(), generate_password_hash(password)),
            )
            hub_audit(connection, "register", tenant_id, business_name)
    except BambooDomainConflict:
        return jsonify(
            error=(
                "This BambooHR domain is already registered. Contact the existing "
                "business owner to be added, or contact the platform owner to "
                "resolve domain ownership."
            )
        ), 409
    except RegistrationConflict:
        return jsonify(error="An administrator already uses that email address."), 409
    except database_integrity_errors():
        with closing(database_connect()) as connection:
            duplicate_domain = connection.execute(
                "SELECT 1 FROM tenants WHERE LOWER(bamboohr_subdomain) = ?",
                (subdomain,),
            ).fetchone()
        if duplicate_domain:
            return jsonify(
                error=(
                    "This BambooHR domain is already registered. Contact the existing "
                    "business owner to be added, or contact the platform owner to "
                    "resolve domain ownership."
                )
            ), 409
        return jsonify(error="An administrator already uses that email address."), 409
    g.tenant_id = tenant_id
    try:
        save_app_config(
            DEFAULT_APP_CONFIG | {"businessName": business_name, "tenantId": subdomain}
        )
    except database_errors():
        with closing(database_connect()) as connection, connection:
            connection.execute("DELETE FROM tenant_admins WHERE tenant_id = ?", (tenant_id,))
            connection.execute("DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,))
        return jsonify(error="The business could not be registered. Try again."), 500
    return jsonify(registered=True, businessStatus="pending"), 201


@app.post("/api/hub/owner/login")
def hub_owner_login():
    if not hub_csrf_valid():
        return jsonify(error="The sign-in session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not valid_admin_email(payload.get("email"))
        or not isinstance(payload.get("password"), str)
    ):
        return jsonify(error="Enter your platform owner email and password."), 400
    email = payload["email"].strip().casefold()
    login_key = hub_attempt_key("owner", email)
    now = int(time_module.time())
    with closing(database_connect()) as connection, connection:
        attempt_state = tenant_auth_attempt_state(connection, login_key, now)
        if attempt_state is None:
            return jsonify(error="Too many failed sign-in attempts. Try again later."), 429
        account = connection.execute(
            """
            SELECT id, email, password_hash, mfa_secret, mfa_enabled, auth_version
            FROM platform_owners WHERE email = ? AND active = 1
            """,
            (email,),
        ).fetchone()
        if not account or not check_password_hash(account[2], payload["password"]):
            record_tenant_auth_failure(connection, login_key, *attempt_state, now)
            return jsonify(error="The email or password is incorrect."), 401
        if not account[4]:
            secret, otp_uri = start_mfa_enrollment(
                connection, account[0], account[1], platform_owner=True
            )
            clear_hub_session()
            session["pending_platform_owner_id"] = account[0]
            return jsonify(
                mfaEnrollmentRequired=True,
                secret=secret,
                otpAuthUri=otp_uri,
                qrCode=otp_qr_data_uri(otp_uri),
                csrfToken=session["hub_csrf"],
            )
        else:
            try:
                secret = mfa_cipher().decrypt(account[3].encode("ascii")).decode("ascii")
            except (AttributeError, InvalidToken, UnicodeDecodeError):
                return jsonify(error="Owner MFA data is unavailable; reset it from the server."), 503
            if not verify_totp(secret, payload.get("code")):
                record_tenant_auth_failure(connection, login_key, *attempt_state, now)
                return jsonify(error="The email, password, or verification code is incorrect."), 401
            connection.execute("DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,))
        hub_audit(connection, "owner-login", actor_email=account[1])
    clear_hub_session()
    session.permanent = True
    session["platform_owner_id"] = account[0]
    session["platform_owner_email"] = account[1]
    session["platform_auth_version"] = account[5]
    return jsonify(authenticated=True, csrfToken=session["hub_csrf"])


@app.post("/api/hub/owner/verify-mfa")
def hub_owner_verify_mfa():
    if not hub_csrf_valid():
        return jsonify(error="The setup session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    owner_id = session.get("pending_platform_owner_id")
    if not isinstance(payload, dict) or not isinstance(owner_id, str):
        return jsonify(error="Restart platform owner sign-in to continue MFA setup."), 401
    with closing(database_connect()) as connection, connection:
        enrollment = connection.execute(
            """
            SELECT e.encrypted_secret, o.email, o.auth_version, o.active
            FROM platform_mfa_enrollments e
            JOIN platform_owners o ON o.id = e.owner_id
            WHERE e.owner_id = ?
            """,
            (owner_id,),
        ).fetchone()
        if not enrollment or not enrollment[3]:
            return jsonify(error="The MFA enrollment session is no longer valid."), 401
        login_key = hub_attempt_key("owner", enrollment[1])
        now = int(time_module.time())
        attempt_state = tenant_auth_attempt_state(connection, login_key, now)
        if attempt_state is None:
            return jsonify(error="Too many failed verification attempts. Try again later."), 429
        try:
            secret = mfa_cipher().decrypt(enrollment[0].encode("ascii")).decode("ascii")
        except (InvalidToken, UnicodeDecodeError):
            return jsonify(error="MFA enrollment data is unavailable; reset it from the server."), 503
        if not verify_totp(secret, payload.get("code")):
            record_tenant_auth_failure(connection, login_key, *attempt_state, now)
            return jsonify(error="Enter the current six-digit code from your authenticator."), 400
        connection.execute(
            """
            UPDATE platform_owners
            SET mfa_secret = ?, mfa_enabled = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (mfa_cipher().encrypt(secret.encode("ascii")).decode("ascii"), owner_id),
        )
        connection.execute("DELETE FROM platform_mfa_enrollments WHERE owner_id = ?", (owner_id,))
        connection.execute("DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,))
        hub_audit(connection, "owner-mfa-enrolled", actor_email=enrollment[1])
    clear_hub_session()
    session.permanent = True
    session["platform_owner_id"] = owner_id
    session["platform_owner_email"] = enrollment[1]
    session["platform_auth_version"] = enrollment[2]
    return jsonify(authenticated=True, csrfToken=session["hub_csrf"])


@app.post("/api/hub/owner/logout")
def hub_owner_logout():
    denied = platform_owner_guard()
    if denied:
        return denied
    clear_hub_session()
    return jsonify(loggedOut=True)


@app.get("/api/hub/businesses")
def hub_businesses():
    denied = platform_owner_guard()
    if denied:
        return denied
    with closing(database_connect()) as connection:
        rows = connection.execute(
            """
            SELECT t.tenant_id, t.business_name, t.status, t.status_note,
                   t.contact_email, t.created_at, t.reviewed_at,
                   t.membership_tier,
                   (SELECT COUNT(*) FROM tenant_admins a
                    WHERE a.tenant_id = t.tenant_id AND a.active = 1)
            FROM tenants t
            ORDER BY CASE t.status WHEN 'pending' THEN 0 WHEN 'active' THEN 1
                     WHEN 'suspended' THEN 2 ELSE 3 END, t.created_at DESC
            """
        ).fetchall()
        businesses = []
        for row in rows:
            summary = membership_summary(connection, row[0])
            businesses.append({
                "id": row[0],
                "name": row[1],
                "status": row[2],
                "note": row[3],
                "contactEmail": row[4],
                "createdAt": row[5],
                "reviewedAt": row[6],
                "membership": summary,
                "adminCount": row[8],
            })
    return jsonify(businesses=businesses)


@app.post("/api/hub/businesses/<tenant_id>/tier")
def hub_set_business_tier(tenant_id: str):
    denied = platform_owner_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    tier = payload.get("tier") if isinstance(payload, dict) else None
    if tier not in MEMBERSHIP_TIERS:
        return jsonify(error="Choose Bronze, Silver, Gold, or Platinum."), 400
    with closing(database_connect()) as connection, connection:
        tenant = connection.execute(
            "SELECT business_name, membership_tier FROM tenants WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        if not tenant:
            return jsonify(error="Business was not found."), 404
        connection.execute(
            "UPDATE tenants SET membership_tier = ? WHERE tenant_id = ?",
            (tier, tenant_id),
        )
        hub_audit(
            connection,
            "membership-tier-changed",
            tenant_id,
            f"{tenant[1]} -> {tier}",
            session.get("platform_owner_email"),
        )
        summary = membership_summary(connection, tenant_id)
    return jsonify(membership=summary)


@app.post("/api/hub/businesses/<tenant_id>/membership-status")
def hub_restore_cancelled_membership(tenant_id: str):
    denied = platform_owner_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        return jsonify(error="Explicit confirmation is required to restore membership."), 400
    with closing(database_connect()) as connection, connection:
        tenant = connection.execute(
            "SELECT membership_status FROM tenants WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        if not tenant:
            return jsonify(error="Business was not found."), 404
        if tenant[0] != "cancelled":
            return jsonify(error="Only a cancelled membership can be restored by the platform owner."), 409
        connection.execute(
            "UPDATE tenants SET membership_status = 'active' WHERE tenant_id = ?",
            (tenant_id,),
        )
        hub_audit(
            connection,
            "membership-status-cancelled-to-active",
            tenant_id,
            "Platform owner restored cancelled membership.",
            session.get("platform_owner_email"),
        )
        summary = membership_summary(connection, tenant_id)
    return jsonify(membership=summary)


@app.delete("/api/hub/businesses/<tenant_id>")
def hub_delete_business(tenant_id: str):
    denied = platform_owner_guard()
    if denied:
        return denied
    if not MULTI_BUSINESS:
        return jsonify(error="Business deletion requires the PostgreSQL multi-business deployment."), 503
    if tenant_id == DEFAULT_TENANT_ID:
        return jsonify(error="The original business cannot be deleted from the hub."), 409
    with closing(database_connect()) as connection, connection:
        tenant = connection.execute(
            "SELECT business_name, bamboohr_subdomain FROM tenants WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        if not tenant:
            return jsonify(error="Business was not found."), 404
        hub_audit(
            connection,
            "business-permanently-deleted",
            tenant_id,
            f"{tenant[0]} ({tenant[1] or 'no BambooHR domain'})",
            session.get("platform_owner_email"),
        )
        if DATABASE_URL:
            connection.execute(
                "SELECT set_config('app.tenant_id', ?, false)", (tenant_id,)
            )
        for table_name in (
            "employees",
            "accepted_schedules",
            "schedule_locations",
            "application_settings",
            "tenant_audit_events",
            "attendance_time_entries",
            "attendance_shift_records",
            "attendance_shift_audit_events",
            "attendance_reconciliation_audit_events",
            "attendance_score_overrides",
            "attendance_score_audit_events",
            "attendance_notifications",
            "attendance_notification_reads",
            "schedule_portal_codes",
            "shift_trades",
            "shift_trade_events",
            "shift_trade_publish",
            "shift_trade_reads",
            "attendance_reports",
            "attendance_report_settings",
            "billing_events",
            "billing_accounts",
            "billing_subscription_index",
        ):
            connection.execute(
                f"DELETE FROM {table_name} WHERE tenant_id = ?", (tenant_id,)
            )
        connection.execute("DELETE FROM tenant_users WHERE tenant_id = ?", (tenant_id,))
        connection.execute(
            """
            DELETE FROM tenant_mfa_enrollments
            WHERE admin_id IN (
                SELECT id FROM tenant_admins WHERE tenant_id = ?
            )
            """,
            (tenant_id,),
        )
        connection.execute("DELETE FROM tenant_admins WHERE tenant_id = ?", (tenant_id,))
        connection.execute("DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,))
    for token, validation in tuple(_validated_bamboo_keys.items()):
        if validation[3] == tenant_id:
            _validated_bamboo_keys.pop(token, None)
    return jsonify(id=tenant_id, deleted=True)


@app.post("/api/hub/businesses/<tenant_id>/status")
def hub_set_business_status(tenant_id: str):
    denied = platform_owner_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    status = payload.get("status") if isinstance(payload, dict) else None
    note = payload.get("note", "") if isinstance(payload, dict) else ""
    if status not in {"pending", "active", "suspended", "rejected"} or not isinstance(note, str) or len(note) > 500:
        return jsonify(error="Choose a valid status and a note of at most 500 characters."), 400
    with closing(database_connect()) as connection, connection:
        current = connection.execute(
            "SELECT status FROM tenants WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()
        if not current:
            return jsonify(error="Business was not found."), 404
        if status not in BUSINESS_STATUS_TRANSITIONS[current[0]]:
            return jsonify(error=f"A {current[0]} business cannot become {status}."), 409
        changed = connection.execute(
            """
            UPDATE tenants
            SET status = ?, status_note = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND status = ?
            """,
            (status, note.strip(), tenant_id, current[0]),
        )
        if changed.rowcount == 0:
            return jsonify(error="The business changed while you were reviewing it. Reload and retry."), 409
        hub_audit(
            connection,
            f"status-{current[0]}-to-{status}",
            tenant_id,
            note.strip(),
            session.get("platform_owner_email"),
        )
    return jsonify(id=tenant_id, status=status)


@app.get("/api/business/status")
def business_status():
    with closing(database_connect()) as connection:
        row = connection.execute(
            "SELECT business_name, status, status_note FROM tenants WHERE tenant_id = ?",
            (active_tenant_id(),),
        ).fetchone()
        admin = connection.execute(
            "SELECT is_primary FROM tenant_admins WHERE id = ?",
            (session.get("tenant_admin_id"),),
        ).fetchone()
        membership = membership_summary(connection)
    return jsonify(
        businessName=row[0],
        status=row[1],
        note=row[2],
        membership=membership,
        isPrimaryAdmin=bool(admin and admin[0]),
        email=session.get("tenant_admin_email"),
        csrfToken=session.get("tenant_auth_csrf"),
    )


@app.post("/api/business/profile")
def update_business_profile():
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("name"), str)
        or not 1 <= len(payload["name"].strip()) <= 120
        or not valid_admin_email(payload.get("email"))
    ):
        return jsonify(error="Enter a valid name and email address."), 400
    email = payload["email"].strip().casefold()
    try:
        with closing(database_connect()) as connection, connection:
            account = connection.execute(
                """
                SELECT email, password_hash, auth_version FROM tenant_admins
                WHERE id = ? AND tenant_id = ? AND active = 1
                """,
                (session.get("tenant_admin_id"), active_tenant_id()),
            ).fetchone()
            if not account:
                return jsonify(error="Your administrator account could not be found."), 404
            if email != account[0]:
                current_password = payload.get("currentPassword")
                if not isinstance(current_password, str) or not check_password_hash(
                    account[1], current_password
                ):
                    return jsonify(error="Enter your current password to change your email."), 403
                existing = connection.execute(
                    """
                    SELECT 1 FROM tenant_admins
                    WHERE tenant_id = ? AND email = ? AND id != ?
                    """,
                    (active_tenant_id(), email, session.get("tenant_admin_id")),
                ).fetchone()
                if existing:
                    return jsonify(error="That email address is already in use."), 409
            connection.execute(
                """
                UPDATE tenant_admins
                SET display_name = ?,
                    auth_version = auth_version + CASE WHEN email != ? THEN 1 ELSE 0 END,
                    email = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    payload["name"].strip(),
                    email,
                    email,
                    session.get("tenant_admin_id"),
                    active_tenant_id(),
                ),
            )
    except database_integrity_errors():
        return jsonify(error="That email address is already in use."), 409
    session["tenant_admin_email"] = email
    if email != account[0]:
        session["tenant_auth_version"] = account[2] + 1
    return jsonify(name=payload["name"].strip(), email=email)


def primary_admin_guard():
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    with closing(database_connect()) as connection:
        admin = connection.execute(
            "SELECT is_primary FROM tenant_admins WHERE id = ? AND tenant_id = ?",
            (session.get("tenant_admin_id"), active_tenant_id()),
        ).fetchone()
    if not admin or not admin[0]:
        return jsonify(error="Only the main business administrator can perform this operation."), 403
    return None


@app.route("/api/workspace/data-settings", methods=["GET", "POST"])
def workspace_data_settings():
    denied = primary_admin_guard()
    if denied:
        return denied
    if request.method == "GET":
        return jsonify(authorized=True, tenantId=active_tenant_id())
    payload = request.get_json(silent=True)
    operation = payload.get("operation") if isinstance(payload, dict) else None
    if not isinstance(operation, str) or operation not in {
        "source-import", "restore", "backup", "configured-inputs", "portable", "meta-update"
    }:
        return jsonify(error="Choose a valid Data & Settings operation."), 400
    if payload.get("tenantId") != active_tenant_id():
        return jsonify(error="The signed-in business changed. Reload before continuing."), 409
    with closing(database_connect()) as connection, connection:
        hub_audit(
            connection, "workspace-data-settings-authorized", active_tenant_id(),
            json.dumps({"operation": operation, "scope": "browser-workspace"}),
            actor_email=session.get("tenant_admin_email"),
        )
    return jsonify(authorized=True, tenantId=active_tenant_id())


@app.post("/api/business/membership")
def update_business_membership():
    denied = primary_admin_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        return jsonify(error="Explicit confirmation is required for membership changes."), 400
    action = payload.get("action")
    if not isinstance(action, str) or action not in {
        "change_tier", "pause", "resume", "cancel"
    }:
        return jsonify(error="Choose a valid membership action."), 400

    with closing(database_connect()) as connection, connection:
        tenant = connection.execute(
            """
            SELECT status, membership_status, membership_tier
            FROM tenants WHERE tenant_id = ?
            """,
            (active_tenant_id(),),
        ).fetchone()
        if not tenant:
            return jsonify(error="The business membership could not be found."), 404
        business_status, membership_status, current_tier = tenant
        if business_status != "active":
            return jsonify(error="Only an active business can change its membership."), 409

        if action == "change_tier":
            next_tier = payload.get("tier")
            if not isinstance(next_tier, str) or next_tier not in MEMBERSHIP_TIERS:
                return jsonify(error="Choose Bronze, Silver, Gold, or Platinum."), 400
            if membership_status == "cancelled":
                return jsonify(error="A cancelled membership cannot be changed. Contact the platform owner to restore access."), 409
            if current_tier == next_tier:
                return jsonify(
                    membership=membership_summary(connection),
                    accessEnabled=membership_status == "active" and not membership_billing.access_suspended(connection, active_tenant_id()),
                    unchanged=True,
                )
            billing = connection.execute(
                "SELECT provider_status FROM billing_accounts WHERE tenant_id=?",
                (active_tenant_id(),),
            ).fetchone()
            if billing and billing[0] not in {"CANCELLED", "EXPIRED"}:
                return jsonify(error="Cancel or reconcile the current sandbox subscription before changing its tier. Existing subscriptions retain their agreed price."), 409
            connection.execute(
                "UPDATE tenants SET membership_tier = ? WHERE tenant_id = ?",
                (next_tier, active_tenant_id()),
            )
            audit_action = f"membership-tier-{current_tier}-to-{next_tier}"
        else:
            transitions = {
                "pause": {"active": "paused"},
                "resume": {"paused": "active"},
                "cancel": {"active": "cancelled", "paused": "cancelled"},
            }
            next_status = transitions[action].get(membership_status)
            if next_status is None:
                return jsonify(
                    error=f"A {membership_status} membership cannot {action.replace('_', ' ')}."
                ), 409
            try:
                membership_billing.membership_action(connection, active_tenant_id(), billing_provider, action)
            except membership_billing.PaymentError as error:
                return jsonify(error=str(error), outcome="unknown" if error.unknown else "failed"), 502
            connection.execute(
                "UPDATE tenants SET membership_status = ? WHERE tenant_id = ?",
                (next_status, active_tenant_id()),
            )
            audit_action = f"membership-status-{membership_status}-to-{next_status}"

        connection.execute(
            """
            INSERT INTO tenant_audit_events
                (id, tenant_id, actor_id, actor_email, action, route, response_status)
            VALUES (?, ?, ?, ?, ?, ?, 200)
            """,
            (
                secrets.token_urlsafe(18),
                active_tenant_id(),
                session.get("tenant_admin_id"),
                session.get("tenant_admin_email"),
                audit_action,
                request.endpoint or "update_business_membership",
            ),
        )
        membership = membership_summary(connection)
    return jsonify(
        membership=membership,
        accessEnabled=membership["status"] == "active" and not membership["billingSuspended"],
    )


@app.get("/api/business/admins")
def list_business_admins():
    with closing(database_connect()) as connection:
        primary = connection.execute(
            "SELECT is_primary FROM tenant_admins WHERE id = ? AND tenant_id = ?",
            (session.get("tenant_admin_id"), active_tenant_id()),
        ).fetchone()
        rows = connection.execute(
            """
            SELECT id, email, display_name, active, mfa_enabled, is_primary
                 , created_at,
                   EXISTS (
                       SELECT 1 FROM tenant_mfa_enrollments enrollment
                       WHERE enrollment.admin_id = tenant_admins.id
                   )
            FROM tenant_admins
            WHERE tenant_id = ? AND active = 1
            ORDER BY is_primary DESC, created_at, email
            """,
            (active_tenant_id(),),
        ).fetchall()
    is_primary = bool(primary and primary[0])
    return jsonify(
        isPrimaryAdmin=is_primary,
        admins=[
            ({
                "id": row[0],
                "email": row[1],
                "name": row[2],
                "isPrimary": bool(row[5]),
            } | ({
                "active": bool(row[3]),
                "mfaEnabled": bool(row[4]),
                "joinedAt": row[6],
                "mfaEnrollmentPending": bool(row[7]),
            } if is_primary else {}))
            for row in rows
        ]
    )


@app.post("/api/business/admins")
def add_business_admin():
    denied = primary_admin_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not valid_admin_email(payload.get("email"))
        or not isinstance(payload.get("name"), str)
        or not 1 <= len(payload["name"].strip()) <= 120
        or not isinstance(payload.get("password"), str)
        or not 14 <= len(payload["password"]) <= 1024
    ):
        return jsonify(error="Enter a name, a valid email, and a temporary password of at least 14 characters."), 400
    admin_id = secrets.token_urlsafe(18)
    with closing(database_connect()) as connection, connection:
        limit_response = membership_quota_response(connection, "admins")
        if limit_response:
            return limit_response
        created = connection.execute(
            """
            INSERT OR IGNORE INTO tenant_admins
                (id, tenant_id, email, display_name, password_hash, is_primary)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                admin_id,
                active_tenant_id(),
                payload["email"].strip().casefold(),
                payload["name"].strip(),
                generate_password_hash(payload["password"]),
            ),
        )
        if created.rowcount == 0:
            return jsonify(error="An administrator already uses that email address."), 409
    return jsonify(id=admin_id), 201


@app.delete("/api/business/admins/<admin_id>")
def remove_business_admin(admin_id: str):
    denied = primary_admin_guard()
    if denied:
        return denied
    with closing(database_connect()) as connection, connection:
        removed = connection.execute(
            """
            UPDATE tenant_admins
            SET active = 0, auth_version = auth_version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ? AND is_primary = 0 AND active = 1
            """,
            (admin_id, active_tenant_id()),
        )
        if removed.rowcount == 0:
            return jsonify(error="That administrator was not found or cannot be removed."), 404
        connection.execute(
            "DELETE FROM tenant_mfa_enrollments WHERE admin_id = ?", (admin_id,)
        )
    return jsonify(removed=True)


@app.put("/api/business/admins/<admin_id>")
def update_business_admin(admin_id: str):
    denied = primary_admin_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("name"), str)
        or not 1 <= len(payload["name"].strip()) <= 120
        or not valid_admin_email(payload.get("email"))
    ):
        return jsonify(error="Enter a valid name and email address."), 400
    email = payload["email"].strip().casefold()
    try:
        with closing(database_connect()) as connection, connection:
            target = connection.execute(
                """
                SELECT 1 FROM tenant_admins
                WHERE id = ? AND tenant_id = ? AND is_primary = 0 AND active = 1
                """,
                (admin_id, active_tenant_id()),
            ).fetchone()
            if not target:
                return jsonify(error="That administrator was not found or cannot be edited."), 404
            existing = connection.execute(
                """
                SELECT 1 FROM tenant_admins
                WHERE tenant_id = ? AND email = ? AND id != ?
                """,
                (active_tenant_id(), email, admin_id),
            ).fetchone()
            if existing:
                return jsonify(error="That email address is already in use."), 409
            connection.execute(
                """
                UPDATE tenant_admins
                SET display_name = ?,
                    auth_version = auth_version + CASE WHEN email != ? THEN 1 ELSE 0 END,
                    email = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ? AND is_primary = 0 AND active = 1
                """,
                (
                    payload["name"].strip(),
                    email,
                    email,
                    admin_id,
                    active_tenant_id(),
                ),
            )
    except database_integrity_errors():
        return jsonify(error="That email address is already in use."), 409
    return jsonify(updated=True)


@app.post("/api/business/admins/<admin_id>/reset-password")
def reset_business_admin_password(admin_id: str):
    denied = primary_admin_guard()
    if denied:
        return denied
    if admin_id == session.get("tenant_admin_id"):
        return jsonify(error="Use your profile to change your own password."), 400
    temporary_password = secrets.token_urlsafe(24)
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE tenant_admins
            SET password_hash = ?, auth_version = auth_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ? AND is_primary = 0 AND active = 1
            """,
            (
                generate_password_hash(temporary_password),
                admin_id,
                active_tenant_id(),
            ),
        )
        if updated.rowcount == 0:
            return jsonify(error="That administrator was not found or cannot be reset."), 404
    return jsonify(temporaryPassword=temporary_password)


@app.post("/api/business/admins/<admin_id>/reset-mfa")
def reset_business_admin_mfa(admin_id: str):
    denied = primary_admin_guard()
    if denied:
        return denied
    if admin_id == session.get("tenant_admin_id"):
        return jsonify(error="Use account recovery to reset your own authenticator."), 400
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE tenant_admins
            SET mfa_secret = NULL, mfa_enabled = 0, auth_version = auth_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ? AND is_primary = 0 AND active = 1
            """,
            (admin_id, active_tenant_id()),
        )
        if updated.rowcount == 0:
            return jsonify(error="That administrator was not found or cannot be reset."), 404
        connection.execute(
            "DELETE FROM tenant_mfa_enrollments WHERE admin_id = ?", (admin_id,)
        )
    return jsonify(mfaReset=True)


ACCESS_TEMP_PASSWORD_SECONDS = 72 * 3600
ACCESS_SESSION_KEYS = (
    "access_user_id", "access_tenant_id", "access_auth_version", "access_csrf",
    "pending_access_user_id", "pending_access_tenant_id",
)
ATTENDANCE_RECORD_COLUMNS = (
    "schedule_run_id, employee_id, shift_date, shift_start, status, source, reason, "
    "employee_name, location, role, clock_in_at"
)
ATTENDANCE_TIMESHEET_COLUMNS = (
    ATTENDANCE_RECORD_COLUMNS
    + ", clock_out_at, worked_minutes, early_minutes, overtime_minutes"
)


def attendance_record_json(row) -> dict[str, object]:
    return {
        "runId": row[0], "employeeId": row[1], "date": row[2], "shiftStart": row[3],
        "status": row[4], "source": row[5], "reason": row[6], "employeeName": row[7],
        "location": row[8], "role": row[9], "clockInAt": row[10],
        "clockOutAt": row[11], "workedMinutes": row[12],
        "earlyMinutes": row[13] or 0, "overtimeMinutes": row[14] or 0,
    }


def access_csrf_valid() -> bool:
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("access_csrf", "")
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


def access_user() -> dict[str, object] | None:
    """Return the signed-in manager/employee, or None (clearing a stale session)."""
    user_id = session.get("access_user_id")
    tenant_id = session.get("access_tenant_id")
    version = session.get("access_auth_version")
    if (
        not isinstance(user_id, str)
        or not isinstance(tenant_id, str)
        or not isinstance(version, int)
    ):
        return None
    g.tenant_id = tenant_id
    with closing(database_connect()) as connection:
        row = connection.execute(
            """
            SELECT u.role, u.email, u.employee_id, u.display_name, u.auth_version,
                   u.active, u.mfa_enabled, u.must_change_password, t.status,
                   t.membership_status, t.business_name
            FROM tenant_users u
            JOIN tenants t ON t.tenant_id = u.tenant_id
            WHERE u.id = ? AND u.tenant_id = ? AND t.status != 'rejected'
            """,
            (user_id, tenant_id),
        ).fetchone()
    if (
        not row
        or row[4] != version
        or not row[5]
        or row[7]
        or (row[0] == "manager" and not row[6])
    ):
        session.clear()
        g.tenant_id = DEFAULT_TENANT_ID
        return None
    g.tenant_status, g.tenant_membership_status = row[8], row[9]
    with closing(database_connect()) as connection:
        if membership_billing.access_suspended(connection, tenant_id):
            g.tenant_membership_status = "billing_suspended"
    return {
        "id": user_id, "tenantId": tenant_id, "role": row[0], "email": row[1],
        "employeeId": row[2], "name": row[3], "businessName": row[10],
    }


def access_guard(roles: set[str]):
    """Authenticate a manager/employee request; returns (user, error_response)."""
    user = access_user()
    if user is None:
        return None, (jsonify(error="Sign in to continue."), 401)
    if user["role"] not in roles:
        return None, (jsonify(error="Your account cannot use this feature."), 403)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if cross_origin_request():
            return None, (jsonify(error="Cross-origin requests are not allowed."), 403)
        if not access_csrf_valid():
            return None, (jsonify(error="The request token is invalid. Reload the page and retry."), 400)
    if g.tenant_status != "active" or g.tenant_membership_status != "active":
        return None, (jsonify(error="This business membership is not active."), 403)
    if user["role"] == "employee":
        denied = membership_feature_denied("employeeScheduleAccess")
        if denied:
            return None, denied
    return user, None


def access_personal_guard():
    user, failure = access_guard({"employee", "manager"})
    if failure:
        return user, failure
    denied = membership_feature_denied("employeeScheduleAccess")
    if denied:
        return None, denied
    with closing(database_connect()) as connection:
        employee = connection.execute(
            "SELECT 1 FROM employees WHERE tenant_id=? AND employee_id=? AND active=1",
            (user["tenantId"], user["employeeId"]),
        ).fetchone()
    if not employee:
        return None, (jsonify(error="Your account needs an active linked employee record."), 403)
    return user, None


def roster_config_row(connection: DatabaseConnection, tenant_id: str):
    return connection.execute(
        """
        SELECT revision, locked, pools_json
        FROM roster_configurations WHERE tenant_id = ?
        """,
        (tenant_id,),
    ).fetchone()


def roster_pool_starts(pools: list[dict], location: str, role: str) -> list[float] | None:
    for pool in pools:
        if pool["location"].casefold() == location.casefold() and pool["role"].casefold() == role.casefold():
            return pool["starts"]
    return None


def roster_employee_record(connection, tenant_id: str, employee_row, pools: list[dict]) -> dict:
    employee_id, name, location, role, active, schedule_location_id = employee_row[:6]
    profile_row = connection.execute(
        """
        SELECT settings_json, revision FROM roster_employee_settings
        WHERE tenant_id = ? AND employee_id = ?
        """,
        (tenant_id, employee_id),
    ).fetchone()
    starts = roster_pool_starts(pools, location, role)
    if not profile_row or starts is None:
        return {
            "employeeId": employee_id, "name": name, "location": location,
            "role": role, "active": bool(active), "scheduleLocationId": schedule_location_id,
            "settings": None, "revision": None, "starts": starts or [],
        }
    return {
        "employeeId": employee_id, "name": name, "location": location,
        "role": role, "active": bool(active), "scheduleLocationId": schedule_location_id,
        "settings": json.loads(profile_row[0]), "revision": profile_row[1], "starts": starts,
    }


def meta_configuration_row(connection: DatabaseConnection, tenant_id: str):
    return connection.execute(
        """
        SELECT revision, locked, locations_json
        FROM meta_configurations WHERE tenant_id = ?
        """,
        (tenant_id,),
    ).fetchone()


def manager_location_names(
    connection: DatabaseConnection, tenant_id: str, email: str | None
) -> set[str]:
    if not email:
        return set()
    rows = connection.execute(
        """
        SELECT DISTINCT location FROM schedule_locations
        WHERE tenant_id = ? AND LOWER(manager_email) = ? AND location <> ''
        """,
        (tenant_id, email.casefold()),
    ).fetchall()
    return {row[0] for row in rows}


def update_meta_location(
    connection: DatabaseConnection,
    tenant_id: str,
    location_name: str,
    changes: object,
    version: object,
    role: str,
    allowed_locations: set[str] | None = None,
):
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        return jsonify(error="Reload META before saving changes."), 400
    config = meta_configuration_row(connection, tenant_id)
    if not config:
        return jsonify(error="The primary administrator has not initialized shared META settings."), 409
    if config[1]:
        return jsonify(error="META settings are locked. Ask an administrator to unlock them."), 409
    if config[0] != version:
        return jsonify(error="META settings changed elsewhere. Reload before saving."), 409
    locations = json.loads(config[2])
    location = next(
        (item for item in locations if item["name"].casefold() == location_name.casefold()),
        None,
    )
    if not location:
        return jsonify(error="That physical location has no shared META settings. Ask the administrator to synchronize it."), 409
    if allowed_locations is not None and location["name"].casefold() not in {
        name.casefold() for name in allowed_locations
    }:
        return jsonify(error="That physical location is outside your currently authorized teams."), 403
    try:
        updated = meta_settings.apply_changes(location, changes)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    location_index = locations.index(location)
    locations[location_index] = updated
    result = connection.execute(
        """
        UPDATE meta_configurations
        SET locations_json = ?, revision = revision + 1, updated_at = CURRENT_TIMESTAMP
        WHERE tenant_id = ? AND revision = ? AND locked = 0
        """,
        (json.dumps(locations, separators=(",", ":")), tenant_id, version),
    )
    if result.rowcount != 1:
        return jsonify(error="META settings changed or were locked elsewhere. Reload before saving."), 409
    if role == "manager":
        actor = access_user()
        access_audit(
            connection,
            actor,
            "meta-settings-updated:" + location["name"] + ":" + ",".join(
                f"{item['field']}:{item['day']}" for item in changes
            ),
        )
    else:
        connection.execute(
            """
            INSERT INTO tenant_audit_events
                (id, tenant_id, actor_id, actor_email, action, route, response_status)
            VALUES (?, ?, ?, ?, ?, ?, 200)
            """,
            (
                secrets.token_urlsafe(18), tenant_id, session.get("tenant_admin_id"),
                session.get("tenant_admin_email"),
                "meta-settings-updated:" + location["name"] + ":" + ",".join(
                    f"{item['field']}:{item['day']}" for item in changes
                ),
                request.endpoint or "unknown",
            ),
        )
    return jsonify(location=updated, revision=version + 1)


def validate_roster_import(connection, tenant_id: str, payload: object) -> tuple[dict, list[str]]:
    if not isinstance(payload, dict) or payload.get("tenantId") != tenant_id:
        raise ValueError("The business changed. Reload the workspace and retry.")
    pools = roster_settings.normalize_pools(payload.get("pools"))
    raw_employees = payload.get("employees")
    if not isinstance(raw_employees, list) or not raw_employees or len(raw_employees) > 500:
        raise ValueError("Provide the current employee roster.")
    locked = payload.get("locked")
    if not isinstance(locked, bool):
        raise ValueError("The workspace lock state is invalid.")
    employee_ids, employees, warnings = set(), [], []
    for item in raw_employees:
        if not isinstance(item, dict):
            raise ValueError("Each employee roster entry must be an object.")
        employee_id = item.get("employeeId")
        if not isinstance(employee_id, str) or not employee_id.strip() or employee_id in employee_ids:
            raise ValueError("Employee IDs must be unique non-empty strings.")
        employee_ids.add(employee_id)
        row = connection.execute(
            """
            SELECT employee_id, name, location, role, active, schedule_location_id
            FROM employees WHERE tenant_id = ? AND employee_id = ?
            """,
            (tenant_id, employee_id),
        ).fetchone()
        if not row:
            raise ValueError("An employee in the workspace is not registered to this business.")
        starts = roster_pool_starts(pools, row[2], row[3])
        if starts is None:
            raise ValueError(f"No configured shift starts were supplied for {row[2]} · {row[3]}.")
        profile = roster_settings.normalize_profile_for_starts(item.get("settings"), starts)
        if profile["preferred"] is not None and profile["preferred"] not in starts:
            warnings.append(f"{row[1]} has a preferred start outside the configured pool.")
        if profile["flex"] == "No" and not profile["reason"].strip():
            warnings.append(f"{row[1]} is not flexible but has no reason.")
        employees.append({"employeeId": employee_id, "settings": profile})
    active_ids = {
        row[0] for row in connection.execute(
            "SELECT employee_id FROM employees WHERE tenant_id = ? AND active = 1",
            (tenant_id,),
        ).fetchall()
    }
    if not active_ids.issubset(employee_ids):
        raise ValueError("The import must include every active business employee.")
    return {"pools": pools, "employees": employees, "locked": locked}, warnings


def update_roster_employee(connection, tenant_id: str, employee_id: str, changes: object, version: object, role: str):
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        return jsonify(error="Reload the roster before saving changes."), 400
    config = roster_config_row(connection, tenant_id)
    if not config:
        return jsonify(error="The shared roster has not been initialized by the primary administrator."), 409
    if config[1]:
        return jsonify(error="Roster settings are locked. Ask an administrator to unlock them."), 409
    employee = connection.execute(
        """
        SELECT employee_id, name, location, role, active, schedule_location_id
        FROM employees WHERE tenant_id = ? AND employee_id = ?
        """,
        (tenant_id, employee_id),
    ).fetchone()
    if not employee or (role == "employee" and not employee[4]):
        return jsonify(error="The employee record is unavailable."), 404
    pools = json.loads(config[2])
    starts = roster_pool_starts(pools, employee[2], employee[3])
    if starts is None:
        return jsonify(error="No shared shift starts are configured for this employee's current location and role."), 409
    current = connection.execute(
        """
        SELECT settings_json, revision FROM roster_employee_settings
        WHERE tenant_id = ? AND employee_id = ?
        """,
        (tenant_id, employee_id),
    ).fetchone()
    if not current:
        return jsonify(error="The employee is not in the shared roster yet. Ask an administrator to synchronize it."), 409
    if current[1] != version:
        return jsonify(error="These roster settings changed elsewhere. Reload before saving."), 409
    try:
        updated = roster_settings.validate_edit(json.loads(current[0]), changes, starts, role)
    except PermissionError as error:
        return jsonify(error=str(error)), 403
    except ValueError as error:
        return jsonify(error=str(error)), 400
    changed_fields = ",".join(sorted(changes))
    result = connection.execute(
        """
        UPDATE roster_employee_settings
        SET settings_json = ?, revision = revision + 1, updated_at = CURRENT_TIMESTAMP
        WHERE tenant_id = ? AND employee_id = ? AND revision = ?
        """,
        (json.dumps(updated, separators=(",", ":")), tenant_id, employee_id, version),
    )
    if result.rowcount != 1:
        return jsonify(error="These roster settings changed elsewhere. Reload before saving."), 409
    actor = access_user() if role in {"manager", "employee"} else None
    if actor:
        access_audit(connection, actor, f"roster-settings-updated:{employee_id}:{changed_fields}")
    else:
        connection.execute(
            """
            INSERT INTO tenant_audit_events
                (id, tenant_id, actor_id, actor_email, action, route, response_status)
            VALUES (?, ?, ?, ?, ?, ?, 200)
            """,
            (
                secrets.token_urlsafe(18), tenant_id, session.get("tenant_admin_id"),
                session.get("tenant_admin_email"),
                f"roster-settings-updated:{employee_id}:{changed_fields}",
                request.endpoint or "unknown",
            ),
        )
    return jsonify(settings=updated, revision=version + 1)


@app.get("/api/roster-settings")
def get_admin_roster_settings():
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection:
        config = roster_config_row(connection, tenant_id)
        if not config:
            return jsonify(configured=False, revision=None, locked=False, pools=[], employees=[])
        pools = json.loads(config[2])
        rows = connection.execute(
            """
            SELECT employee_id, name, location, role, active, schedule_location_id
            FROM employees WHERE tenant_id = ? ORDER BY name COLLATE NOCASE
            """,
            (tenant_id,),
        ).fetchall()
        employees = [roster_employee_record(connection, tenant_id, row, pools) for row in rows]
    return jsonify(
        configured=True, revision=config[0], locked=bool(config[1]),
        pools=pools, employees=employees,
    )


@app.post("/api/roster-settings/import/preview")
def preview_admin_roster_import():
    denied = primary_admin_guard()
    if denied:
        return denied
    tenant_id = active_tenant_id()
    payload = request.get_json(silent=True)
    with closing(database_connect()) as connection:
        if roster_config_row(connection, tenant_id):
            return jsonify(error="Shared roster data already exists. Import will not overwrite it."), 409
        try:
            normalized, warnings = validate_roster_import(connection, tenant_id, payload)
        except ValueError as error:
            return jsonify(error=str(error)), 400
    return jsonify(
        configured=False, employeeCount=len(normalized["employees"]),
        poolCount=len(normalized["pools"]), locked=normalized["locked"],
        warnings=warnings,
    )


@app.post("/api/roster-settings/import")
def import_admin_roster_settings():
    denied = primary_admin_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        return jsonify(error="Preview the shared roster and explicitly confirm the import."), 400
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection, connection:
        if roster_config_row(connection, tenant_id):
            return jsonify(error="Shared roster data already exists. Import will not overwrite it."), 409
        try:
            normalized, warnings = validate_roster_import(connection, tenant_id, payload)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        connection.execute(
            """
            INSERT INTO roster_configurations (tenant_id, revision, locked, pools_json)
            VALUES (?, 1, ?, ?)
            """,
            (tenant_id, int(normalized["locked"]), json.dumps(normalized["pools"], separators=(",", ":"))),
        )
        connection.execute(
            """
            UPDATE meta_configurations
            SET locked = ?, revision = revision + 1, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND locked != ?
            """,
            (int(normalized["locked"]), tenant_id, int(normalized["locked"])),
        )
        connection.executemany(
            """
            INSERT INTO roster_employee_settings
                (tenant_id, employee_id, settings_json, revision)
            VALUES (?, ?, ?, 1)
            """,
            [
                (tenant_id, item["employeeId"], json.dumps(item["settings"], separators=(",", ":")))
                for item in normalized["employees"]
            ],
        )
        connection.execute(
            """
            INSERT INTO tenant_audit_events
                (id, tenant_id, actor_id, actor_email, action, route, response_status)
            VALUES (?, ?, ?, ?, ?, ?, 200)
            """,
            (
                secrets.token_urlsafe(18), tenant_id, session.get("tenant_admin_id"),
                session.get("tenant_admin_email"), "shared-roster-initialized",
                request.endpoint or "unknown",
            ),
        )
    return jsonify(
        configured=True, revision=1, locked=normalized["locked"],
        employeeCount=len(normalized["employees"]), warnings=warnings,
    ), 201


@app.put("/api/roster-settings/configuration")
def update_admin_roster_configuration():
    tenant_id = active_tenant_id()
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("revision"), int) or isinstance(payload.get("revision"), bool):
        return jsonify(error="Reload the shared roster before changing configuration."), 400
    try:
        pools = roster_settings.normalize_pools(payload.get("pools"))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    if not isinstance(payload.get("locked"), bool):
        return jsonify(error="The workspace lock state is invalid."), 400
    with closing(database_connect()) as connection, connection:
        current = roster_config_row(connection, tenant_id)
        if not current:
            return jsonify(error="Initialize the shared roster before syncing settings."), 409
        if current[0] != payload["revision"]:
            return jsonify(error="Shared roster configuration changed elsewhere. Reload before saving."), 409
        old_pools = json.loads(current[2])
        if current[1] and pools != old_pools:
            return jsonify(error="Unlock configuration before changing possible shift starts."), 409
        if not current[1] and payload["locked"] and pools != old_pools:
            return jsonify(error="Save possible shift starts before locking configuration."), 409
        profile_updates = []
        rows = connection.execute(
            """
            SELECT s.employee_id, s.settings_json, s.revision,
                   e.location, e.role
            FROM roster_employee_settings s
            JOIN employees e
              ON e.tenant_id = s.tenant_id AND e.employee_id = s.employee_id
            WHERE s.tenant_id = ?
            """,
            (tenant_id,),
        ).fetchall()
        for employee_id, settings_json, profile_revision, location, role in rows:
            previous_starts = roster_pool_starts(old_pools, location, role) or []
            next_starts = roster_pool_starts(pools, location, role)
            if next_starts is None:
                return jsonify(error=f"Keep a configured location-role pool for {employee_id}."), 409
            profile = json.loads(settings_json)
            if profile["preferred"] is not None and profile["preferred"] not in next_starts:
                return jsonify(error=f"Change {employee_id}'s preferred start before removing it."), 409
            availability = profile["shiftAvailability"]
            changed = False
            for start in previous_starts:
                if start not in next_starts:
                    key = format(start, ".15g")
                    if key in availability:
                        del availability[key]
                        changed = True
            for start in next_starts:
                key = format(start, ".15g")
                if start not in previous_starts and key not in availability:
                    availability[key] = 0
                    changed = True
            if changed:
                profile_updates.append(
                    (json.dumps(profile, separators=(",", ":")), tenant_id, employee_id, profile_revision)
                )
        result = connection.execute(
            """
            UPDATE roster_configurations
            SET pools_json = ?, locked = ?, revision = revision + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND revision = ?
            """,
            (
                json.dumps(pools, separators=(",", ":")), int(payload["locked"]),
                tenant_id, payload["revision"],
            ),
        )
        if result.rowcount != 1:
            return jsonify(error="Shared roster configuration changed elsewhere. Reload before saving."), 409
        connection.execute(
            """
            UPDATE meta_configurations
            SET locked = ?, revision = revision + 1, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND locked != ?
            """,
            (int(payload["locked"]), tenant_id, int(payload["locked"])),
        )
        for settings_json, profile_tenant, employee_id, profile_revision in profile_updates:
            changed_profile = connection.execute(
                """
                UPDATE roster_employee_settings
                SET settings_json = ?, revision = revision + 1, updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND employee_id = ? AND revision = ?
                """,
                (settings_json, profile_tenant, employee_id, profile_revision),
            )
            if changed_profile.rowcount != 1:
                connection.rollback()
                return jsonify(error="An employee roster profile changed while shift starts were being synchronized. No changes were saved; reload and retry."), 409
        connection.execute(
            """
            INSERT INTO tenant_audit_events
                (id, tenant_id, actor_id, actor_email, action, route, response_status)
            VALUES (?, ?, ?, ?, ?, ?, 200)
            """,
            (
                secrets.token_urlsafe(18), tenant_id, session.get("tenant_admin_id"),
                session.get("tenant_admin_email"), "shared-roster-configuration-updated",
                request.endpoint or "unknown",
            ),
        )
    return jsonify(revision=payload["revision"] + 1, locked=payload["locked"], pools=pools)


def validate_meta_import(tenant_id: str, payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("tenantId") != tenant_id:
        raise ValueError("The business changed. Reload the workspace and retry.")
    if not isinstance(payload.get("locked"), bool):
        raise ValueError("The workspace lock state is invalid.")
    return {
        "locked": payload["locked"],
        "locations": meta_settings.normalize_locations(payload.get("locations")),
    }


@app.get("/api/meta-settings")
def get_admin_meta_settings():
    denied = primary_admin_guard()
    if denied:
        return denied
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection:
        config = meta_configuration_row(connection, tenant_id)
    if not config:
        return jsonify(configured=False, revision=None, locked=False, locations=[])
    return jsonify(
        configured=True, revision=config[0], locked=bool(config[1]),
        locations=json.loads(config[2]),
    )


@app.post("/api/meta-settings/locations/accept")
def accept_meta_locations():
    denied = primary_admin_guard()
    if denied:
        return denied
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    source = payload.get("source") if isinstance(payload, dict) else None
    raw_locations = payload.get("locations") if isinstance(payload, dict) else None
    if source not in {"bamboohr", "manual", "workbook"}:
        return jsonify(error="Choose a supported location source."), 400
    if not isinstance(raw_locations, list) or not raw_locations or len(raw_locations) > 500:
        return jsonify(error="Accept at least one location."), 400
    locations, seen_names = [], set()
    try:
        for item in raw_locations:
            if isinstance(item, str):
                item = {"name": item}
            if not isinstance(item, dict):
                raise ValueError("Each location must be an object or name.")
            name = item.get("name")
            if not isinstance(name, str) or not name.strip() or len(name) > 240:
                raise ValueError("Each location requires a valid name.")
            name = name.strip()
            if name.casefold() in seen_names:
                raise ValueError("Location names must be unique.")
            seen_names.add(name.casefold())
            locations.append({
                "name": name,
                "intensity": item.get("intensity", [None] * 7),
                "open": item.get("open", [None] * 7),
            })
        normalized = meta_settings.normalize_locations(locations)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection, connection:
        if source == "bamboohr":
            available_names = {
                str(row[0]).strip().casefold()
                for row in connection.execute(
                    """SELECT DISTINCT bamboohr_location FROM employees
                       WHERE tenant_id=? AND bamboohr_location IS NOT NULL
                         AND trim(bamboohr_location) != ''""",
                    (tenant_id,),
                ).fetchall()
            }
            unverified = [
                item["name"] for item in normalized
                if item["name"].casefold() not in available_names
            ]
            if unverified:
                return jsonify(
                    error="One or more selected locations are not present in the synced BambooHR employee directory.",
                    locations=unverified,
                ), 409

        config = meta_configuration_row(connection, tenant_id)
        roster_config = roster_config_row(connection, tenant_id)
        if config:
            if roster_config and bool(roster_config[1]) != bool(config[1]):
                return jsonify(error="Shared META and roster lock states differ. Reload the workspace and retry."), 409
            revision = payload.get("revision")
            if not isinstance(revision, int) or isinstance(revision, bool):
                return jsonify(error="Reload META locations before accepting changes."), 400
            if revision != config[0]:
                return jsonify(error="Shared META configuration changed elsewhere. Reload before accepting locations."), 409
            existing_locations = json.loads(config[2])
            existing_names = {item["name"].casefold() for item in existing_locations}
            additions = [item for item in normalized if item["name"].casefold() not in existing_names]
            if additions and config[1]:
                return jsonify(error="Unlock configuration before adding META locations."), 409
            merged_locations = existing_locations + additions
            if additions:
                updated = connection.execute(
                    """UPDATE meta_configurations
                       SET locations_json=?, revision=revision+1, updated_at=CURRENT_TIMESTAMP
                       WHERE tenant_id=? AND revision=?""",
                    (json.dumps(merged_locations, separators=(",", ":")), tenant_id, revision),
                )
                if updated.rowcount != 1:
                    return jsonify(error="Shared META configuration changed elsewhere. Reload before accepting locations."), 409
                revision += 1
            locked = bool(config[1])
        else:
            if roster_config and roster_config[1]:
                return jsonify(error="Unlock roster settings before accepting new locations."), 409
            additions = normalized
            merged_locations = normalized
            locked = bool(roster_config and roster_config[1])
            revision = 1
            connection.execute(
                """INSERT INTO meta_configurations
                   (tenant_id, revision, locked, locations_json)
                   VALUES (?, 1, ?, ?)""",
                (tenant_id, int(locked), json.dumps(merged_locations, separators=(",", ":"))),
            )

        employees_assigned = 0
        if source == "bamboohr":
            for item in normalized:
                result = connection.execute(
                    """UPDATE employees SET location=?
                       WHERE tenant_id=? AND source_type='bamboohr'
                         AND (location IS NULL OR trim(location)='')
                         AND lower(trim(bamboohr_location))=lower(?)""",
                    (item["name"], tenant_id, item["name"]),
                )
                employees_assigned += result.rowcount
        if additions or employees_assigned:
            connection.execute(
                """INSERT INTO tenant_audit_events
                   (id, tenant_id, actor_id, actor_email, action, route, response_status)
                   VALUES (?, ?, ?, ?, ?, ?, 200)""",
                (
                    secrets.token_urlsafe(18), tenant_id, session.get("tenant_admin_id"),
                    session.get("tenant_admin_email"),
                    "meta-locations-accepted:" + source + ":" + ",".join(item["name"] for item in additions),
                    request.endpoint or "unknown",
                ),
            )
    return jsonify(
        configured=True, revision=revision, locked=locked,
        locations=merged_locations,
        selected=[item["name"] for item in normalized],
        accepted=[item["name"] for item in additions],
        employeesAssigned=employees_assigned,
    )


@app.post("/api/meta-settings/import/preview")
def preview_admin_meta_import():
    denied = primary_admin_guard()
    if denied:
        return denied
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection:
        if meta_configuration_row(connection, tenant_id):
            return jsonify(error="Shared META settings already exist. Import will not overwrite them."), 409
    try:
        normalized = validate_meta_import(tenant_id, request.get_json(silent=True))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(
        configured=False, locationCount=len(normalized["locations"]),
        locked=normalized["locked"],
    )


@app.post("/api/meta-settings/import")
def import_admin_meta_settings():
    denied = primary_admin_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        return jsonify(error="Preview the shared META settings and explicitly confirm the import."), 400
    tenant_id = active_tenant_id()
    try:
        normalized = validate_meta_import(tenant_id, payload)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    with closing(database_connect()) as connection, connection:
        if meta_configuration_row(connection, tenant_id):
            return jsonify(error="Shared META settings already exist. Import will not overwrite them."), 409
        roster_config = roster_config_row(connection, tenant_id)
        if roster_config and bool(roster_config[1]) != normalized["locked"]:
            return jsonify(error="The workspace lock state differs from the shared roster configuration. Reload and retry."), 409
        result = connection.execute(
            """
            INSERT OR IGNORE INTO meta_configurations
                (tenant_id, revision, locked, locations_json)
            VALUES (?, 1, ?, ?)
            """,
            (
                tenant_id, int(normalized["locked"]),
                json.dumps(normalized["locations"], separators=(",", ":")),
            ),
        )
        if result.rowcount != 1:
            return jsonify(error="Shared META settings were initialized elsewhere. Reload before continuing."), 409
        connection.execute(
            """
            INSERT INTO tenant_audit_events
                (id, tenant_id, actor_id, actor_email, action, route, response_status)
            VALUES (?, ?, ?, ?, ?, ?, 200)
            """,
            (
                secrets.token_urlsafe(18), tenant_id, session.get("tenant_admin_id"),
                session.get("tenant_admin_email"), "shared-meta-initialized",
                request.endpoint or "unknown",
            ),
        )
    return jsonify(
        configured=True, revision=1, locked=normalized["locked"],
        locationCount=len(normalized["locations"]),
    ), 201


@app.put("/api/meta-settings/configuration")
def update_admin_meta_configuration():
    denied = primary_admin_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("revision"), int)
        or isinstance(payload.get("revision"), bool)
        or not isinstance(payload.get("locked"), bool)
    ):
        return jsonify(error="Reload the shared META settings before changing configuration."), 400
    try:
        locations = meta_settings.normalize_locations(payload.get("locations"))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection, connection:
        config = meta_configuration_row(connection, tenant_id)
        if not config:
            return jsonify(error="Initialize shared META settings before synchronizing locations."), 409
        if config[0] != payload["revision"]:
            return jsonify(error="Shared META configuration changed elsewhere. Reload before saving."), 409
        old_locations = json.loads(config[2])
        roster_config = roster_config_row(connection, tenant_id)
        if roster_config and bool(roster_config[1]) != payload["locked"]:
            return jsonify(error="Use Controls & lock to change the shared workspace lock state."), 409
        if config[1] and locations != old_locations:
            return jsonify(error="Unlock configuration before synchronizing META locations."), 409
        if not config[1] and payload["locked"] and locations != old_locations:
            return jsonify(error="Synchronize META locations before locking configuration."), 409
        result = connection.execute(
            """
            UPDATE meta_configurations
            SET locations_json = ?, locked = ?, revision = revision + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND revision = ?
            """,
            (
                json.dumps(locations, separators=(",", ":")), int(payload["locked"]),
                tenant_id, payload["revision"],
            ),
        )
        if result.rowcount != 1:
            return jsonify(error="Shared META configuration changed elsewhere. Reload before saving."), 409
        connection.execute(
            """
            INSERT INTO tenant_audit_events
                (id, tenant_id, actor_id, actor_email, action, route, response_status)
            VALUES (?, ?, ?, ?, ?, ?, 200)
            """,
            (
                secrets.token_urlsafe(18), tenant_id, session.get("tenant_admin_id"),
                session.get("tenant_admin_email"), "shared-meta-configuration-updated",
                request.endpoint or "unknown",
            ),
        )
    return jsonify(
        revision=payload["revision"] + 1, locked=payload["locked"], locations=locations,
    )


@app.put("/api/meta-settings/<path:location_name>")
def update_admin_meta_location(location_name: str):
    denied = primary_admin_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="META changes must be an object."), 400
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection, connection:
        return update_meta_location(
            connection, tenant_id, location_name, payload.get("changes"),
            payload.get("revision"), "admin",
        )


@app.route("/api/access/meta-settings", methods=["GET", "PUT"])
def manager_meta_settings():
    user, failure = access_guard({"manager"})
    if failure:
        return failure
    if request.args.get("view") == "employee":
        return jsonify(error="META settings are not available in the personal employee view."), 403
    tenant_id = user["tenantId"]
    with closing(database_connect()) as connection:
        config = meta_configuration_row(connection, tenant_id)
        if not config:
            return jsonify(error="The primary administrator has not initialized shared META settings."), 409
        locations = json.loads(config[2])
        authorized_names = manager_location_names(connection, tenant_id, user["email"])
        authorized_keys = {name.casefold() for name in authorized_names}
        records = [item for item in locations if item["name"].casefold() in authorized_keys]
        unconfigured = sorted(
            (name for name in authorized_names if name.casefold() not in {
                item["name"].casefold() for item in locations
            }),
            key=str.casefold,
        )
        if request.method == "GET":
            return jsonify(
                revision=config[0], locked=bool(config[1]),
                locations=records, unconfiguredLocations=unconfigured,
            )
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("location"), str):
            return jsonify(error="Choose one of your currently authorized physical locations."), 400
        with connection:
            return update_meta_location(
                connection, tenant_id, payload["location"], payload.get("changes"),
                payload.get("revision"), "manager", authorized_names,
            )


@app.post("/api/roster-settings/employees")
def add_admin_roster_employees():
    denied = primary_admin_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict) or payload.get("confirmed") is not True
        or not isinstance(payload.get("revision"), int)
        or isinstance(payload.get("revision"), bool)
        or not isinstance(payload.get("employees"), list)
        or not payload["employees"] or len(payload["employees"]) > 500
    ):
        return jsonify(error="Preview the new employee profiles and confirm synchronization."), 400
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection, connection:
        config = roster_config_row(connection, tenant_id)
        if not config:
            return jsonify(error="Initialize the shared roster before adding employees."), 409
        if config[0] != payload["revision"]:
            return jsonify(error="Shared roster configuration changed elsewhere. Reload before synchronizing."), 409
        pools = json.loads(config[2])
        additions = []
        seen = set()
        try:
            for item in payload["employees"]:
                if not isinstance(item, dict):
                    raise ValueError("Each employee profile must be an object.")
                employee_id = item.get("employeeId")
                if not isinstance(employee_id, str) or not employee_id.strip() or employee_id in seen:
                    raise ValueError("Employee IDs must be unique non-empty strings.")
                seen.add(employee_id)
                employee = connection.execute(
                    """
                    SELECT location, role FROM employees
                    WHERE tenant_id = ? AND employee_id = ?
                    """,
                    (tenant_id, employee_id),
                ).fetchone()
                if not employee:
                    raise ValueError("An employee profile does not belong to this business.")
                if connection.execute(
                    """
                    SELECT 1 FROM roster_employee_settings
                    WHERE tenant_id = ? AND employee_id = ?
                    """,
                    (tenant_id, employee_id),
                ).fetchone():
                    raise ValueError("An employee already has shared settings; existing values were not overwritten.")
                if roster_pool_starts(pools, employee[0], employee[1]) is None:
                    raise ValueError(f"No shared shift starts are configured for {employee[0]} · {employee[1]}.")
                profile = roster_settings.normalize_profile_for_starts(
                    item.get("settings"), roster_pool_starts(pools, employee[0], employee[1])
                )
                additions.append((tenant_id, employee_id, json.dumps(profile, separators=(",", ":"))))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        result = connection.execute(
            """
            UPDATE roster_configurations
            SET revision = revision + 1, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND revision = ?
            """,
            (tenant_id, payload["revision"]),
        )
        if result.rowcount != 1:
            return jsonify(error="Shared roster configuration changed elsewhere. Reload before synchronizing."), 409
        connection.executemany(
            """
            INSERT INTO roster_employee_settings
                (tenant_id, employee_id, settings_json, revision)
            VALUES (?, ?, ?, 1)
            """,
            additions,
        )
        connection.execute(
            """
            INSERT INTO tenant_audit_events
                (id, tenant_id, actor_id, actor_email, action, route, response_status)
            VALUES (?, ?, ?, ?, ?, ?, 200)
            """,
            (
                secrets.token_urlsafe(18), tenant_id, session.get("tenant_admin_id"),
                session.get("tenant_admin_email"),
                "shared-roster-employees-added:" + ",".join(item[1] for item in additions),
                request.endpoint or "unknown",
            ),
        )
    return jsonify(revision=payload["revision"] + 1, added=len(additions))


@app.put("/api/roster-settings/<path:employee_id>")
def update_admin_roster_employee(employee_id: str):
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Roster changes must be an object."), 400
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection, connection:
        return update_roster_employee(
            connection, tenant_id, employee_id, payload.get("changes"),
            payload.get("revision"), "admin",
        )


@app.route("/api/access/roster-settings", methods=["GET", "PUT"])
def manager_roster_settings():
    user, failure = access_guard({"manager"})
    if failure:
        return failure
    if request.args.get("view") == "employee":
        return jsonify(error="Use My shifts / employee view to manage your own roster preferences."), 403
    tenant_id = user["tenantId"]
    with closing(database_connect()) as connection:
        config = roster_config_row(connection, tenant_id)
        if not config:
            return jsonify(error="The primary administrator has not initialized the shared roster."), 409
        pools = json.loads(config[2])
        employee_ids = manager_employee_ids(connection, tenant_id, user["email"])
        if request.method == "GET":
            records = []
            if employee_ids:
                placeholders = ",".join("?" for _ in employee_ids)
                rows = connection.execute(
                    f"""
                    SELECT employee_id, name, location, role, active, schedule_location_id
                    FROM employees WHERE tenant_id = ? AND employee_id IN ({placeholders})
                    ORDER BY name COLLATE NOCASE
                    """,
                    (tenant_id, *sorted(employee_ids)),
                ).fetchall()
                records = [roster_employee_record(connection, tenant_id, row, pools) for row in rows]
            if any(record["settings"] is None for record in records):
                return jsonify(error="The shared roster is missing an employee profile. Ask the administrator to synchronize it."), 409
            return jsonify(locked=bool(config[1]), employees=records)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("employeeId"), str):
            return jsonify(error="Choose an employee from your authorized teams."), 400
        employee_id = payload["employeeId"]
        if employee_id not in employee_ids:
            return jsonify(error="That employee is outside your currently authorized teams."), 403
        with connection:
            return update_roster_employee(
                connection, tenant_id, employee_id, payload.get("changes"),
                payload.get("revision"), "manager",
            )


@app.route("/api/access/my/roster-settings", methods=["GET", "PUT"])
def personal_roster_settings():
    user, failure = access_personal_guard()
    if failure:
        return failure
    tenant_id, employee_id = user["tenantId"], user["employeeId"]
    with closing(database_connect()) as connection:
        config = roster_config_row(connection, tenant_id)
        if not config:
            return jsonify(error="The primary administrator has not initialized the shared roster."), 409
        pools = json.loads(config[2])
        employee = connection.execute(
            """
            SELECT employee_id, name, location, role, active, schedule_location_id
            FROM employees WHERE tenant_id = ? AND employee_id = ? AND active = 1
            """,
            (tenant_id, employee_id),
        ).fetchone()
        record = roster_employee_record(connection, tenant_id, employee, pools) if employee else None
        if not record or record["settings"] is None:
            return jsonify(error="Your active employee roster settings are unavailable. Ask the administrator to synchronize the roster."), 409
        if request.method == "GET":
            return jsonify(locked=bool(config[1]), employee=record)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Roster changes must be an object."), 400
        with connection:
            return update_roster_employee(
                connection, tenant_id, employee_id, payload.get("changes"),
                payload.get("revision"), "employee",
            )


def access_audit(
    connection: DatabaseConnection, user: dict[str, object], action: str
) -> None:
    connection.execute(
        """
        INSERT INTO tenant_audit_events
            (id, tenant_id, actor_id, actor_email, action, route, response_status)
        VALUES (?, ?, ?, ?, ?, ?, 200)
        """,
        (
            secrets.token_urlsafe(18), user["tenantId"], user["id"],
            user["email"] or user["employeeId"], action, request.endpoint or "unknown",
        ),
    )


def manager_employee_ids(
    connection: DatabaseConnection, tenant_id: str, email: str | None
) -> set[str]:
    """Employees assigned to schedule locations whose manager email matches."""
    if not email:
        return set()
    rows = connection.execute(
        """
        SELECT e.employee_id
        FROM employees e
        JOIN schedule_locations sl
          ON sl.id = e.schedule_location_id AND sl.tenant_id = e.tenant_id
        WHERE e.tenant_id = ? AND LOWER(sl.manager_email) = ?
        """,
        (tenant_id, email.casefold()),
    ).fetchall()
    return {row[0] for row in rows}


def attendance_window() -> tuple[str, str] | None:
    today = date.today()
    start_text = request.args.get("start") or (today - timedelta(days=30)).isoformat()
    end_text = request.args.get("end") or today.isoformat()
    try:
        start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
    except ValueError:
        return None
    if (
        start.isoformat() != start_text
        or end.isoformat() != end_text
        or end < start
        or (end - start).days > 366
    ):
        return None
    return start_text, end_text


def scoped_attendance_records(
    connection: DatabaseConnection,
    tenant_id: str,
    start: str,
    end: str,
    employee_ids: set[str] | None,
) -> list[dict[str, object]]:
    rows = connection.execute(
        f"""
        SELECT {ATTENDANCE_TIMESHEET_COLUMNS}
        FROM attendance_shift_records
        WHERE tenant_id = ? AND shift_date >= ? AND shift_date <= ?
        ORDER BY shift_date DESC, shift_start DESC, employee_name
        """,
        (tenant_id, start, end),
    ).fetchall()
    return [
        attendance_record_json(row)
        for row in rows
        if employee_ids is None or row[1] in employee_ids
    ]


def notifications_for_reader(
    connection: DatabaseConnection,
    tenant_id: str,
    reader_key: str,
    employee_ids: set[str] | None,
    archived: bool = False,
) -> dict[str, object]:
    rows = connection.execute(
        """
        SELECT n.id, n.kind, n.employee_id, n.employee_name, n.location,
               n.shift_date, n.message, n.created_at,
               (SELECT 1 FROM attendance_notification_reads r
                WHERE r.tenant_id = n.tenant_id AND r.notification_id = n.id
                  AND r.reader_key = ?),
               (SELECT s.shift_start FROM attendance_shift_records s
                WHERE s.tenant_id = n.tenant_id AND s.employee_id = n.employee_id
                  AND s.shift_date = n.shift_date
                ORDER BY s.updated_at DESC LIMIT 1),
               (SELECT r.archived FROM attendance_notification_reads r
                WHERE r.tenant_id = n.tenant_id AND r.notification_id = n.id
                  AND r.reader_key = ?)
        FROM attendance_notifications n
        WHERE n.tenant_id = ?
        ORDER BY n.created_at DESC, n.id
        LIMIT 500
        """,
        (reader_key, reader_key, tenant_id),
    ).fetchall()
    visible = [
        row for row in rows
        if (employee_ids is None or row[2] in employee_ids)
        and bool(row[10]) == archived
    ]
    return {
        "unread": sum(1 for row in visible if not row[8]),
        "notifications": [
            {
                "id": row[0], "kind": row[1], "employeeId": row[2],
                "employeeName": row[3], "location": row[4], "date": row[5],
                "message": row[6], "createdAt": row[7], "read": bool(row[8]),
                "shiftStart": row[9], "archived": archived,
            }
            for row in visible[:50]
        ],
    }


def archive_notifications(
    connection: DatabaseConnection,
    tenant_id: str,
    reader_key: str,
    employee_ids: set[str] | None,
    ids: object,
) -> int:
    visible = notifications_for_reader(connection, tenant_id, reader_key, employee_ids)
    allowed = {item["id"] for item in visible["notifications"]}
    if isinstance(ids, list):
        allowed &= {item for item in ids if isinstance(item, str)}
    else:
        allowed = set()
    for notification_id in allowed:
        connection.execute(
            """
            INSERT INTO attendance_notification_reads
                (tenant_id, notification_id, reader_key, archived)
            VALUES (?, ?, ?, 1)
            ON CONFLICT (tenant_id, notification_id, reader_key)
            DO UPDATE SET archived = 1
            """,
            (tenant_id, notification_id, reader_key),
        )
    return len(allowed)


def mark_notifications_read(
    connection: DatabaseConnection,
    tenant_id: str,
    reader_key: str,
    employee_ids: set[str] | None,
    ids: object,
) -> int:
    visible = notifications_for_reader(connection, tenant_id, reader_key, employee_ids)
    allowed = {item["id"] for item in visible["notifications"] if not item["read"]}
    if isinstance(ids, list):
        allowed &= {item for item in ids if isinstance(item, str)}
    for notification_id in allowed:
        connection.execute(
            """
            INSERT INTO attendance_notification_reads
                (tenant_id, notification_id, reader_key)
            VALUES (?, ?, ?)
            ON CONFLICT (tenant_id, notification_id, reader_key) DO NOTHING
            """,
            (tenant_id, notification_id, reader_key),
        )
    return len(allowed)


def serialize_access_account(row) -> dict[str, object]:
    return {
        "id": row[0], "role": row[1], "email": row[2], "employeeId": row[3],
        "displayName": row[4], "active": bool(row[5]), "mfaEnabled": bool(row[6]),
        "mustChangePassword": bool(row[7]), "createdAt": row[8],
        "authVersion": row[9],
    }


ACCESS_ACCOUNT_COLUMNS = (
    "id, role, email, employee_id, display_name, active, mfa_enabled, "
    "must_change_password, created_at, auth_version"
)


@app.get("/api/access-accounts")
def list_access_accounts():
    with closing(database_connect()) as connection:
        rows = connection.execute(
            f"""
            SELECT {ACCESS_ACCOUNT_COLUMNS} FROM tenant_users
            WHERE tenant_id = ? ORDER BY role, display_name
            """,
            (active_tenant_id(),),
        ).fetchall()
        accounts = []
        for row in rows:
            account = serialize_access_account(row)
            if account["role"] == "manager":
                account["scopeEmployees"] = len(
                    manager_employee_ids(connection, active_tenant_id(), account["email"])
                )
            accounts.append(account)
    return jsonify(accounts=accounts)


@app.post("/api/access-accounts")
def create_access_account():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("role") not in {"manager", "employee"}:
        return jsonify(error="Choose manager or employee."), 400
    role = payload["role"]
    email = payload.get("email")
    email = email.strip().casefold() if isinstance(email, str) and email.strip() else None
    if (role == "manager" or email) and not valid_admin_email(email):
        return jsonify(error="Enter a valid email address."), 400
    employee_id = payload.get("employeeId") or None
    display_name = payload.get("displayName")
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection, connection:
        if role == "employee" or employee_id is not None:
            denied = membership_feature_denied("employeeScheduleAccess")
            if denied:
                return denied
            employee = connection.execute(
                "SELECT name FROM employees WHERE tenant_id = ? AND employee_id = ? AND active = 1",
                (tenant_id, employee_id if isinstance(employee_id, str) else ""),
            ).fetchone()
            if not employee:
                return jsonify(error="Choose an active employee."), 400
            if not isinstance(display_name, str) or not display_name.strip():
                display_name = employee[0]
        if not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 120:
            return jsonify(error="Enter a name of 1 to 120 characters."), 400
        temporary_password = secrets.token_urlsafe(15)
        user_id = secrets.token_urlsafe(18)
        try:
            connection.execute(
                """
                INSERT INTO tenant_users
                    (id, tenant_id, role, email, employee_id, display_name,
                     password_hash, must_change_password, temp_password_expires_at,
                     created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    user_id, tenant_id, role, email, employee_id, display_name.strip(),
                    generate_password_hash(temporary_password),
                    int(time_module.time()) + ACCESS_TEMP_PASSWORD_SECONDS,
                    session.get("tenant_admin_id"),
                ),
            )
        except database_integrity_errors():
            return jsonify(error="An account already exists for that email or employee."), 409
        row = connection.execute(
            f"SELECT {ACCESS_ACCOUNT_COLUMNS} FROM tenant_users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return jsonify(
        account=serialize_access_account(row),
        temporaryPassword=temporary_password,
        temporaryPasswordHours=ACCESS_TEMP_PASSWORD_SECONDS // 3600,
    ), 201


@app.post("/api/access-accounts/<user_id>/reset-password")
def reset_access_account_password(user_id: str):
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    reset_mfa = isinstance(payload, dict) and payload.get("resetMfa") is True
    temporary_password = secrets.token_urlsafe(15)
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE tenant_users
            SET password_hash = ?, must_change_password = 1,
                temp_password_expires_at = ?, auth_version = auth_version + 1,
                mfa_secret = CASE WHEN ? = 1 THEN NULL ELSE mfa_secret END,
                mfa_enabled = CASE WHEN ? = 1 THEN 0 ELSE mfa_enabled END,
                mfa_pending_secret = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (
                generate_password_hash(temporary_password),
                int(time_module.time()) + ACCESS_TEMP_PASSWORD_SECONDS,
                int(reset_mfa), int(reset_mfa), user_id, active_tenant_id(),
            ),
        )
        if updated.rowcount == 0:
            return jsonify(error="Account not found."), 404
    return jsonify(
        temporaryPassword=temporary_password,
        temporaryPasswordHours=ACCESS_TEMP_PASSWORD_SECONDS // 3600,
    )


@app.put("/api/access-accounts/<user_id>/employee")
def link_manager_employee(user_id: str):
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    employee_id = payload.get("employeeId") if isinstance(payload, dict) else False
    if employee_id is not None and (not isinstance(employee_id, str) or not employee_id):
        return jsonify(error="Choose an active employee or explicitly unlink with null."), 400
    with closing(database_connect()) as connection, connection:
        account = connection.execute(
            "SELECT role FROM tenant_users WHERE tenant_id=? AND id=?",
            (active_tenant_id(), user_id),
        ).fetchone()
        if not account or account[0] != "manager":
            return jsonify(error="Choose a manager account."), 404
        if employee_id is not None:
            denied = membership_feature_denied("employeeScheduleAccess")
            if denied:
                return denied
            employee = connection.execute(
                "SELECT 1 FROM employees WHERE tenant_id=? AND employee_id=? AND active=1",
                (active_tenant_id(), employee_id),
            ).fetchone()
            if not employee:
                return jsonify(error="Choose an active employee in this business."), 400
            conflict = connection.execute(
                "SELECT id FROM tenant_users WHERE tenant_id=? AND employee_id=? AND id!=?",
                (active_tenant_id(), employee_id, user_id),
            ).fetchone()
            if conflict:
                return jsonify(error="That employee already has an account. Resolve the "
                               "existing account explicitly; accounts are not merged."), 409
        connection.execute(
            "UPDATE tenant_users SET employee_id=?, auth_version=auth_version+1, "
            "updated_at=CURRENT_TIMESTAMP WHERE tenant_id=? AND id=?",
            (employee_id, active_tenant_id(), user_id),
        )
    return jsonify(updated=True)


@app.put("/api/access-accounts/<user_id>/role")
def change_access_account_role(user_id: str):
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("role") not in {"manager", "employee"}:
        return jsonify(error="Choose manager or employee."), 400
    role = payload["role"]
    tenant_id = active_tenant_id()
    with closing(database_connect()) as connection, connection:
        account = connection.execute(
            "SELECT role,email,employee_id,auth_version FROM tenant_users WHERE tenant_id=? AND id=?",
            (tenant_id, user_id),
        ).fetchone()
        if not account:
            return jsonify(error="Account not found."), 404
        if payload.get("previousRole") != account[0] or payload.get("authVersion") != account[3]:
            return jsonify(error="The account changed. Refresh and retry."), 409
        if role == account[0]:
            return jsonify(error="Choose a different role."), 400
        email = payload.get("email", account[1])
        email = email.strip().casefold() if isinstance(email, str) and email.strip() else None
        if (role == "manager" or email) and not valid_admin_email(email):
            return jsonify(error="Enter a valid email address; managers require an email."), 400
        employee_id = payload.get("employeeId", account[2])
        if employee_id is not None and (not isinstance(employee_id, str) or not employee_id):
            return jsonify(error="Choose an active employee or no personal employee link."), 400
        if role == "employee" or employee_id is not None:
            denied = membership_feature_denied("employeeScheduleAccess")
            if denied:
                return denied
            employee = connection.execute(
                "SELECT 1 FROM employees WHERE tenant_id=? AND employee_id=? AND active=1",
                (tenant_id, employee_id),
            ).fetchone()
            if not employee:
                return jsonify(error="Choose an active employee in this business."), 400
        conflict = connection.execute(
            "SELECT id FROM tenant_users WHERE tenant_id=? AND id!=? AND "
            "(email=? OR employee_id=? OR employee_id=? OR email=?)",
            (tenant_id, user_id, email, email, employee_id, employee_id),
        ).fetchone()
        if conflict:
            return jsonify(error="That email or employee already belongs to another account. "
                           "Accounts are not merged."), 409
        try:
            updated = connection.execute(
                "UPDATE tenant_users SET role=?,email=?,employee_id=?,auth_version=auth_version+1, "
                "mfa_pending_secret=NULL,updated_at=CURRENT_TIMESTAMP "
                "WHERE tenant_id=? AND id=? AND auth_version=?",
                (role, email, employee_id, tenant_id, user_id, account[3]),
            )
        except (sqlite3.IntegrityError, psycopg.IntegrityError):
            return jsonify(error="That email or employee already belongs to another account. "
                           "Accounts are not merged."), 409
        if updated.rowcount != 1:
            return jsonify(error="The account changed. Refresh and retry."), 409
        hub_audit(
            connection, "access-account-role-change", tenant_id,
            json.dumps({"accountId": user_id, "previousRole": account[0], "role": role}),
            actor_email=session.get("tenant_admin_email"),
        )
    return jsonify(updated=True, role=role)


@app.post("/api/access-accounts/<user_id>/active")
def set_access_account_active(user_id: str):
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("active"), bool):
        return jsonify(error="Specify whether the account is active."), 400
    with closing(database_connect()) as connection, connection:
        updated = connection.execute(
            """
            UPDATE tenant_users
            SET active = ?, auth_version = auth_version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (int(payload["active"]), user_id, active_tenant_id()),
        )
        if updated.rowcount == 0:
            return jsonify(error="Account not found."), 404
    return jsonify(updated=True)


@app.get("/api/attendance/notifications")
def admin_attendance_notifications():
    with closing(database_connect()) as connection:
        return jsonify(
            **notifications_for_reader(
                connection, active_tenant_id(),
                f"admin:{session.get('tenant_admin_id')}", None,
                archived=request.args.get("archived") == "1",
            )
        )


@app.post("/api/attendance/notifications/archive")
def admin_archive_attendance_notifications():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    with closing(database_connect()) as connection, connection:
        archived = archive_notifications(
            connection, active_tenant_id(),
            f"admin:{session.get('tenant_admin_id')}", None,
            payload.get("ids") if isinstance(payload, dict) else None,
        )
    return jsonify(archived=archived)


@app.post("/api/attendance/notifications/read")
def admin_read_attendance_notifications():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    with closing(database_connect()) as connection, connection:
        marked = mark_notifications_read(
            connection, active_tenant_id(),
            f"admin:{session.get('tenant_admin_id')}", None,
            payload.get("ids") if isinstance(payload, dict) else None,
        )
    return jsonify(marked=marked)


def start_access_session(user_id: str, tenant_id: str, version: int) -> str:
    session.clear()
    session.permanent = True
    session["access_user_id"] = user_id
    session["access_tenant_id"] = tenant_id
    session["access_auth_version"] = version
    session["access_csrf"] = secrets.token_urlsafe(32)
    g.tenant_id = tenant_id
    return session["access_csrf"]


@app.get("/api/access/state")
def access_state():
    user = access_user()
    if not isinstance(session.get("access_csrf"), str):
        session["access_csrf"] = secrets.token_urlsafe(32)
    return jsonify(
        authenticated=user is not None,
        csrfToken=session["access_csrf"],
        user=user and {
            "role": user["role"], "name": user["name"], "email": user["email"],
            "employeeId": user["employeeId"], "businessName": user["businessName"],
        },
    )


@app.post("/api/access/login")
def access_login():
    if not access_csrf_valid():
        return jsonify(error="The sign-in session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    identifier = payload.get("identifier") if isinstance(payload, dict) else None
    password = payload.get("password") if isinstance(payload, dict) else None
    if (
        not isinstance(identifier, str)
        or not 1 <= len(identifier.strip()) <= 254
        or not isinstance(password, str)
        or not valid_tenant_id(payload.get("bamboohrSubdomain"))
    ):
        return jsonify(error="Enter your BambooHR subdomain, email or employee ID, and password."), 400
    identifier = identifier.strip()
    subdomain = payload["bamboohrSubdomain"].strip().lower()
    new_password = payload.get("newPassword")
    code = payload.get("code")
    login_key = tenant_auth_attempt_key(f"user:{identifier.casefold()}", subdomain)
    now = int(time_module.time())
    with closing(database_connect()) as connection, connection:
        state = tenant_auth_attempt_state(connection, login_key, now)
        if state is None:
            return jsonify(error="Too many failed sign-in attempts. Try again later."), 429
        failures, window_started_at = state
        rows = connection.execute(
            """
            SELECT u.id, u.tenant_id, u.role, u.email, u.password_hash,
                   u.must_change_password, u.temp_password_expires_at,
                   u.mfa_secret, u.mfa_enabled, u.auth_version, u.active
            FROM tenant_users u
            JOIN tenants t ON t.tenant_id = u.tenant_id AND t.status != 'rejected'
            WHERE LOWER(t.bamboohr_subdomain) = ?
              AND (u.email = ? OR u.employee_id = ?)
            """,
            (subdomain, identifier.casefold(), identifier),
        ).fetchall()
        account = rows[0] if len(rows) == 1 else None
        valid = bool(
            account and account[10] and check_password_hash(account[4], password)
        )
        if valid and account[5] and account[6] < now:
            record_tenant_auth_failure(connection, login_key, failures, window_started_at, now)
            return jsonify(error="The temporary password has expired. Ask an administrator to reset it."), 401
        if not valid:
            record_tenant_auth_failure(connection, login_key, failures, window_started_at, now)
            return jsonify(error="The sign-in details are incorrect."), 401
        user_id, tenant_id, role, email = account[0], account[1], account[2], account[3]
        g.tenant_id = tenant_id
        if role == "employee":
            tier = tenant_membership_tier(connection, tenant_id)
            if not membership_billing.features(connection, tier, MEMBERSHIP_TIERS[tier]["features"]).get("employeeScheduleAccess"):
                return jsonify(error="Employee access is not included in this business's membership."), 403
        if account[5]:
            if not isinstance(new_password, str):
                return jsonify(passwordChangeRequired=True)
            if not 14 <= len(new_password) <= 1024 or new_password == password:
                return jsonify(error="Choose a new password of at least 14 characters that differs from the temporary one."), 400
        if role == "manager" and account[8]:
            if not isinstance(code, str) or not code.strip():
                return jsonify(mfaCodeRequired=True)
            try:
                secret = mfa_cipher().decrypt(account[7].encode("ascii")).decode("ascii")
            except (AttributeError, InvalidToken, UnicodeDecodeError):
                return jsonify(error="MFA data is unavailable; contact an administrator."), 503
            if not verify_totp(secret, code):
                record_tenant_auth_failure(connection, login_key, failures, window_started_at, now)
                return jsonify(error="The sign-in details are incorrect."), 401
        version = account[9]
        if account[5]:
            version += 1
            connection.execute(
                """
                UPDATE tenant_users
                SET password_hash = ?, must_change_password = 0,
                    temp_password_expires_at = 0, auth_version = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND tenant_id = ?
                """,
                (generate_password_hash(new_password), version, user_id, tenant_id),
            )
        connection.execute("DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,))
        if role == "manager" and not account[8]:
            secret = new_totp_secret()
            connection.execute(
                "UPDATE tenant_users SET mfa_pending_secret = ? WHERE id = ? AND tenant_id = ?",
                (
                    mfa_cipher().encrypt(secret.encode("ascii")).decode("ascii"),
                    user_id, tenant_id,
                ),
            )
            otp_uri = (
                f"otpauth://totp/{quote(f'CBL Schedule:{email} ({subdomain})')}"
                f"?secret={secret}&issuer=CBL%20Schedule"
            )
            session.clear()
            session["pending_access_user_id"] = user_id
            session["pending_access_tenant_id"] = tenant_id
            session["access_csrf"] = secrets.token_urlsafe(32)
            return jsonify(
                mfaEnrollmentRequired=True, secret=secret, otpAuthUri=otp_uri,
                qrCode=otp_qr_data_uri(otp_uri), csrfToken=session["access_csrf"],
            )
    return jsonify(authenticated=True, csrfToken=start_access_session(user_id, tenant_id, version))


@app.post("/api/access/verify-mfa")
def access_verify_mfa():
    if not access_csrf_valid():
        return jsonify(error="The setup session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    user_id = session.get("pending_access_user_id")
    tenant_id = session.get("pending_access_tenant_id")
    if not isinstance(payload, dict) or not isinstance(user_id, str) or not isinstance(tenant_id, str):
        return jsonify(error="Restart sign-in to continue MFA setup."), 401
    g.tenant_id = tenant_id
    with closing(database_connect()) as connection, connection:
        row = connection.execute(
            """
            SELECT u.mfa_pending_secret, u.email, u.auth_version, u.active,
                   t.bamboohr_subdomain
            FROM tenant_users u JOIN tenants t ON t.tenant_id = u.tenant_id
            WHERE u.id = ? AND u.tenant_id = ? AND u.role = 'manager'
            """,
            (user_id, tenant_id),
        ).fetchone()
        if not row or not row[0] or not row[3]:
            return jsonify(error="The MFA enrollment session is no longer valid."), 401
        now = int(time_module.time())
        login_key = tenant_auth_attempt_key(f"user:{(row[1] or '').casefold()}", row[4] or "")
        state = tenant_auth_attempt_state(connection, login_key, now)
        if state is None:
            return jsonify(error="Too many failed verification attempts. Try again later."), 429
        try:
            secret = mfa_cipher().decrypt(row[0].encode("ascii")).decode("ascii")
        except (InvalidToken, UnicodeDecodeError):
            return jsonify(error="MFA enrollment data is unavailable; contact an administrator."), 503
        if not verify_totp(secret, payload.get("code")):
            record_tenant_auth_failure(connection, login_key, state[0], state[1], now)
            return jsonify(error="Enter the current six-digit code from your authenticator."), 400
        connection.execute(
            """
            UPDATE tenant_users
            SET mfa_secret = mfa_pending_secret, mfa_pending_secret = NULL,
                mfa_enabled = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
            """,
            (user_id, tenant_id),
        )
        connection.execute("DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,))
    return jsonify(authenticated=True, csrfToken=start_access_session(user_id, tenant_id, row[2]))


@app.post("/api/access/logout")
def access_logout():
    if access_user() is None:
        return jsonify(error="Sign in first."), 401
    if not access_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    session.clear()
    return jsonify(loggedOut=True)


@app.get("/api/access/notifications")
def access_notifications():
    user, failure = access_guard({"manager"})
    if failure:
        return failure
    with closing(database_connect()) as connection:
        scope = manager_employee_ids(connection, user["tenantId"], user["email"])
        return jsonify(
            **notifications_for_reader(
                connection, user["tenantId"], f"user:{user['id']}", scope,
                archived=request.args.get("archived") == "1",
            )
        )


@app.post("/api/access/notifications/archive")
def access_archive_notifications():
    user, failure = access_guard({"manager"})
    if failure:
        return failure
    payload = request.get_json(silent=True)
    with closing(database_connect()) as connection, connection:
        scope = manager_employee_ids(connection, user["tenantId"], user["email"])
        archived = archive_notifications(
            connection, user["tenantId"], f"user:{user['id']}", scope,
            payload.get("ids") if isinstance(payload, dict) else None,
        )
    return jsonify(archived=archived)


@app.post("/api/access/notifications/read")
def access_read_notifications():
    user, failure = access_guard({"manager"})
    if failure:
        return failure
    payload = request.get_json(silent=True)
    with closing(database_connect()) as connection, connection:
        scope = manager_employee_ids(connection, user["tenantId"], user["email"])
        marked = mark_notifications_read(
            connection, user["tenantId"], f"user:{user['id']}", scope,
            payload.get("ids") if isinstance(payload, dict) else None,
        )
    return jsonify(marked=marked)


@app.get("/api/access/manager/attendance")
def manager_attendance():
    user, failure = access_guard({"manager"})
    if failure:
        return failure
    window = attendance_window()
    if window is None:
        return jsonify(error="Provide a valid date range of at most 366 days."), 400
    with closing(database_connect()) as connection:
        scope = manager_employee_ids(connection, user["tenantId"], user["email"])
        records = scoped_attendance_records(
            connection, user["tenantId"], window[0], window[1], scope
        )
    return jsonify(
        start=window[0], end=window[1], scopeEmployees=len(scope), records=records
    )


@app.post("/api/access/manager/mark-absent")
def manager_mark_absent():
    user, failure = access_guard({"manager"})
    if failure:
        return failure
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="An attendance correction is required."), 400
    run_id, employee_id = payload.get("runId"), payload.get("employeeId")
    shift_text, reason = payload.get("date"), payload.get("reason")
    if (
        not isinstance(run_id, str) or not run_id
        or not isinstance(employee_id, str) or not employee_id
        or not isinstance(shift_text, str)
        or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500
    ):
        return jsonify(error="Provide the shift and a reason of 1 to 500 characters."), 400
    if employee_id == user["employeeId"]:
        return jsonify(error="An administrator must correct your own attendance."), 403
    try:
        valid_date = date.fromisoformat(shift_text).isoformat() == shift_text
    except ValueError:
        valid_date = False
    if not valid_date:
        return jsonify(error="Provide a valid shift date in YYYY-MM-DD format."), 400
    with closing(database_connect()) as connection, connection:
        scope = manager_employee_ids(connection, user["tenantId"], user["email"])
        if employee_id not in scope:
            return jsonify(error="That employee is outside your locations."), 403
        row = connection.execute(
            f"""
            SELECT {ATTENDANCE_RECORD_COLUMNS}, clock_in_timezone
            FROM attendance_shift_records
            WHERE tenant_id = ? AND schedule_run_id = ? AND employee_id = ?
                AND shift_date = ?
            """,
            (user["tenantId"], run_id, employee_id, shift_text),
        ).fetchone()
        if not row:
            return jsonify(error="The attendance record was not found."), 404
        if row[4] != "late":
            return jsonify(error="Only late shifts can be marked absent."), 409
        record_attendance_status(
            connection, run_id=run_id, employee_id=employee_id,
            shift_date=shift_text, shift_start=row[3], status="absent",
            source="manual", reason=reason.strip(), employee_name=row[7],
            location=row[8], role=row[9], clock_in_at=row[10],
            clock_in_timezone=row[11],
            existing={(run_id, employee_id, shift_text): (row[4], row[5], row[6])},
            preserve_manual=False, actor_id=user["id"], actor_email=user["email"],
        )
        access_audit(connection, user, "manager-mark-absent")
    return jsonify(updated=True, status="absent")


@app.get("/api/access/me/attendance")
def employee_attendance():
    user, failure = access_personal_guard()
    if failure:
        return failure
    window = attendance_window()
    if window is None:
        return jsonify(error="Provide a valid date range of at most 366 days."), 400
    with closing(database_connect()) as connection:
        records = scoped_attendance_records(
            connection, user["tenantId"], window[0], window[1], {user["employeeId"]}
        )
    counts: dict[str, int] = {}
    for record in records:
        counts[record["status"]] = counts.get(record["status"], 0) + 1
    return jsonify(start=window[0], end=window[1], counts=counts, records=records)


@app.get("/access")
def access_page():
    return send_from_directory(APP_DIRECTORY, "access.html")


@app.get("/trades")
def trade_page():
    response = send_from_directory(APP_DIRECTORY, "trades.html")
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    return response


@app.get("/billing")
def billing_page():
    return send_from_directory(APP_DIRECTORY, "billing.html")


def portal_visibility_weeks(connection: DatabaseConnection) -> int:
    row = connection.execute(
        "SELECT setting_value FROM application_settings "
        "WHERE tenant_id = ? AND setting_key = 'schedule_visibility_weeks'",
        (active_tenant_id(),),
    ).fetchone()
    try:
        weeks = int(row[0]) if row else 4
    except (ValueError, TypeError) as error:
        raise RuntimeError("Stored schedule visibility is invalid.") from error
    if not 1 <= weeks <= 52:
        raise RuntimeError("Stored schedule visibility must be 1 to 52 weeks.")
    return weeks


@app.route("/api/schedule-portal/settings", methods=["GET", "PUT"])
def schedule_portal_settings():
    if request.method == "PUT" and not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    with closing(database_connect()) as connection, connection:
        if request.method == "PUT":
            payload = request.get_json(silent=True)
            weeks = payload.get("visibilityWeeks") if isinstance(payload, dict) else None
            if type(weeks) is not int or not 1 <= weeks <= 52:
                return jsonify(error="Choose a schedule visibility of 1 to 52 weeks."), 400
            connection.execute(
                """
                INSERT INTO application_settings (tenant_id, setting_key, setting_value)
                VALUES (?, 'schedule_visibility_weeks', ?)
                ON CONFLICT (tenant_id, setting_key) DO UPDATE SET
                    setting_value = excluded.setting_value
                """,
                (active_tenant_id(), str(weeks)),
            )
        return jsonify(visibilityWeeks=portal_visibility_weeks(connection))


def portal_schedule_groups(connection: DatabaseConnection) -> list[dict]:
    """Project accepted assignments only; never expose source-workbook metadata."""
    tenant = active_tenant_id()
    today = datetime.now(ATTENDANCE_TIMEZONE).date()
    first = today - timedelta(days=today.weekday())
    last = first + timedelta(weeks=portal_visibility_weeks(connection)) - timedelta(days=1)
    employees = {
        str(row[0]): row for row in connection.execute(
            """
            SELECT e.employee_id, e.name, e.role, e.schedule_location_id, sl.name,
                   sl.location, sl.manager_email, sl.role_group
            FROM employees e JOIN schedule_locations sl
                ON sl.tenant_id = e.tenant_id AND sl.id = e.schedule_location_id
            WHERE e.tenant_id = ? AND e.active = 1
            """,
            (tenant,),
        )
    }
    groups = []
    for run_id, encoded in connection.execute(
        "SELECT run_id, payload FROM accepted_schedules "
        "WHERE tenant_id = ? AND week_start >= ? AND week_start <= ? "
        "ORDER BY week_start, location, role, run_id",
        (tenant, (first - timedelta(days=6)).isoformat(), last.isoformat()),
    ):
        try:
            schedule = json.loads(encoded)
            start = date.fromisoformat(schedule["start"])
            end = start + timedelta(days=6)
            if end < today:
                continue
            span = schedule.get("controls", {}).get("span")
            if (
                not isinstance(span, (int, float)) or isinstance(span, bool)
                or not math.isfinite(span) or not 0 < span <= 24
                or not isinstance(schedule["employees"], list)
            ):
                raise ValueError("Invalid duration or assignments.")
            by_location = {}
            for assigned in schedule["employees"]:
                employee = employees.get(str(assigned.get("id", "")))
                if not employee:
                    continue
                if (
                    employee[5] != schedule["location"]
                    or not role_matches_schedule_group(employee[2], schedule["role"])
                    or not role_matches_schedule_group(employee[2], employee[7])
                ):
                    continue
                slots = assigned.get("slots")
                if not isinstance(slots, list) or len(slots) != 7 or any(
                    slot is not None and (
                        not isinstance(slot, (int, float)) or isinstance(slot, bool)
                        or not math.isfinite(slot) or not 0 <= slot < 24
                    ) for slot in slots
                ):
                    raise ValueError("Invalid assignment slots.")
                group = by_location.setdefault(employee[3], {
                    "runId": run_id, "locationId": employee[3],
                    "locationName": employee[4], "location": employee[5],
                    "role": schedule["role"], "start": start.isoformat(),
                    "end": end.isoformat(), "shiftDuration": span,
                    "tradeCount": len(schedule.get("tradeHistory", [])),
                    "managerEmail": employee[6], "employees": [],
                })
                group["employees"].append({
                    "id": employee[0], "name": employee[1], "role": employee[2],
                    "slots": [slot if first <= start + timedelta(days=day) <= last else None
                              for day, slot in enumerate(slots)],
                })
            groups.extend(by_location.values())
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise RuntimeError(f"Accepted schedule {run_id} has invalid portal data.") from error
    return groups


def portal_group_key(group: dict) -> tuple[str, str, str]:
    return group["locationId"], group["role"], group["start"]


def portal_code_hash(code: str) -> str:
    return hmac.new(
        MFA_ENCRYPTION_KEY.encode("utf-8"), b"schedule-portal\0" + code.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def portal_code(connection: DatabaseConnection, group: dict) -> dict:
    tenant = active_tenant_id()
    key = portal_group_key(group)
    expires = int(datetime.combine(
        date.fromisoformat(group["end"]) + timedelta(days=1),
        time.min, tzinfo=ATTENDANCE_TIMEZONE,
    ).timestamp())
    if expires <= int(time_module.time()):
        raise ValueError("This schedule period has ended; its access code has expired.")
    row = connection.execute(
        "SELECT encrypted_code, expires_at FROM schedule_portal_codes "
        "WHERE tenant_id = ? AND location_id = ? AND role = ? AND period_start = ?",
        (tenant, *key),
    ).fetchone()
    if row:
        try:
            code = mfa_cipher().decrypt(row[0].encode("ascii")).decode("ascii")
        except (InvalidToken, UnicodeError) as error:
            raise RuntimeError("The stored schedule code cannot be decrypted.") from error
    else:
        for _ in range(20):
            code = f"{secrets.randbelow(1_000_000):06d}"
            created = connection.execute(
                """
                INSERT INTO schedule_portal_codes
                    (tenant_id, location_id, role, period_start, code_hash,
                     encrypted_code, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (tenant, *key, portal_code_hash(code),
                 mfa_cipher().encrypt(code.encode("ascii")).decode("ascii"), expires),
            )
            if created.rowcount:
                break
            row = connection.execute(
                "SELECT encrypted_code, expires_at FROM schedule_portal_codes "
                "WHERE tenant_id = ? AND location_id = ? AND role = ? AND period_start = ?",
                (tenant, *key),
            ).fetchone()
            if row:
                code = mfa_cipher().decrypt(row[0].encode("ascii")).decode("ascii")
                break
        else:
            raise RuntimeError("A unique schedule access code could not be generated.")
    return {
        "runId": group["runId"], "locationId": group["locationId"],
        "role": group["role"], "start": group["start"], "end": group["end"],
        "code": code, "expiresAt": datetime.fromtimestamp(
            row[1] if row else expires, ATTENDANCE_TIMEZONE
        ).isoformat(),
    }


@app.post("/api/schedule-portal/codes")
def generate_portal_codes():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    ids = payload.get("runIds") if isinstance(payload, dict) else None
    if (
        not isinstance(ids, list) or not 1 <= len(ids) <= 100
        or any(not isinstance(value, str) or not value for value in ids)
        or len(set(ids)) != len(ids)
    ):
        return jsonify(error="Select 1 to 100 distinct accepted schedules."), 400
    with closing(database_connect()) as connection, connection:
        groups = [g for g in portal_schedule_groups(connection) if g["runId"] in ids]
        if {g["runId"] for g in groups} != set(ids):
            return jsonify(error="Accept the selected schedules first and ensure their "
                           "employees have matching active location/role assignments "
                           "within the portal visibility window."), 400
        codes = [portal_code(connection, group) for group in groups]
    return jsonify(codes=codes)


def employee_portal_team(connection: DatabaseConnection, user: dict) -> tuple | None:
    return connection.execute(
        "SELECT schedule_location_id, role FROM employees "
        "WHERE tenant_id = ? AND employee_id = ? AND active = 1",
        (user["tenantId"], user["employeeId"]),
    ).fetchone()


def scoped_portal_groups(connection: DatabaseConnection, user: dict) -> list[dict]:
    groups = portal_schedule_groups(connection)
    if user["role"] == "manager" and request.args.get("view") != "employee":
        return [g for g in groups if
                g["managerEmail"].strip().casefold() == (user["email"] or "").casefold()]
    team = employee_portal_team(connection, user)
    if not team or not team[0]:
        return []
    scoped = []
    for group in groups:
        if group["locationId"] != team[0]:
            continue
        members = [e for e in group["employees"] if e["role"].casefold() == team[1].casefold()]
        if not any(e["id"] == user["employeeId"] and
                   any(slot is not None for slot in e["slots"]) for e in members):
            continue
        scoped.append(group | {"employees": members})
    return scoped


def public_portal_group(group: dict, include_roster: bool) -> dict:
    return {key: value for key, value in group.items()
            if key != "managerEmail" and (include_roster or key != "employees")}


@app.get("/api/access/schedules")
def access_schedules():
    user, failure = access_guard({"manager", "employee"})
    if failure:
        return failure
    personal = user["role"] == "employee" or request.args.get("view") == "employee"
    if personal:
        user, failure = access_personal_guard()
        if failure:
            return failure
    with closing(database_connect()) as connection:
        groups = scoped_portal_groups(connection, user)
        weeks = portal_visibility_weeks(connection)
    return jsonify(
        visibilityWeeks=weeks,
        schedules=[public_portal_group(g, not personal) for g in groups],
    )


@app.get("/api/access/me/shifts")
def access_personal_shifts():
    user, failure = access_personal_guard()
    if failure:
        return failure
    with closing(database_connect()) as connection:
        groups = scoped_portal_groups(connection, user | {"role": "employee"})
    return jsonify(schedules=[
        public_portal_group(group | {"employees": [
            employee for employee in group["employees"] if employee["id"] == user["employeeId"]
        ]}, True) for group in groups
    ])


@app.post("/api/access/schedules/unlock")
def unlock_access_schedule():
    user, failure = access_personal_guard()
    if failure:
        return failure
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("code"), str) or not re.fullmatch(
        r"[0-9]{6}", payload["code"]
    ) or (
        any(key in payload for key in ("runId", "locationId")) and
        not all(isinstance(payload.get(key), str) and payload[key] for key in ("runId", "locationId"))
    ):
        return jsonify(error="Enter a six-digit code, optionally with a selected schedule."), 400
    now = int(time_module.time())
    with closing(database_connect()) as connection, connection:
        login_key = tenant_auth_attempt_key(
            "portal:" + user["id"], user["tenantId"]
        )
        attempt = tenant_auth_attempt_state(connection, login_key, now)
        if attempt is None:
            return jsonify(error="Too many incorrect codes. Try again in 15 minutes."), 429
        matches = []
        for group in scoped_portal_groups(connection, user | {"role": "employee"}):
            if "runId" in payload and (
                group["runId"] != payload["runId"] or group["locationId"] != payload["locationId"]
            ):
                continue
            row = connection.execute(
                "SELECT code_hash, expires_at FROM schedule_portal_codes "
                "WHERE tenant_id = ? AND location_id = ? AND role = ? AND period_start = ?",
                (user["tenantId"], *portal_group_key(group)),
            ).fetchone()
            if row and row[1] > now and hmac.compare_digest(row[0], portal_code_hash(payload["code"])):
                matches.append(public_portal_group(group, True))
        if not matches:
            record_tenant_auth_failure(connection, login_key, *attempt, now)
            return jsonify(error="The code is invalid, expired, or not for your assigned schedule."), 403
        connection.execute("DELETE FROM tenant_login_attempts WHERE login_key = ?", (login_key,))
        return jsonify(schedule=matches[0], schedules=matches)


@app.get("/api/access/me/team-attendance")
def employee_team_attendance():
    user, failure = access_personal_guard()
    if failure:
        return failure
    now = datetime.now(ATTENDANCE_TIMEZONE)
    counts = {}
    with closing(database_connect()) as connection:
        team = employee_portal_team(connection, user)
        scope = set()
        if team and team[0]:
            scope = {row[0] for row in connection.execute(
                "SELECT employee_id FROM employees WHERE tenant_id = ? "
                "AND schedule_location_id = ? AND LOWER(role) = ? AND active = 1",
                (user["tenantId"], team[0], team[1].casefold()),
            )}
        records = scoped_attendance_records(
            connection, user["tenantId"], now.date().isoformat(), now.date().isoformat(), scope
        )
        for item in records:
            if schedule_shift_datetime(now.date(), item["shiftStart"]) > now:
                continue
            counts[item["status"]] = counts.get(item["status"], 0) + 1
    expected = sum(count for status, count in counts.items()
                   if status not in {"approved_leave", "sick", "vacation"})
    present = counts.get("attended", 0) + counts.get("late", 0)
    return jsonify(
        date=now.date().isoformat(), reportedAt=now.isoformat(), timezone="America/Jamaica",
        counts=counts, expected=expected, present=present,
        attendancePercent=round(100 * present / expected, 1) if expected else None,
    )


@app.get("/")
def index():
    if not tenant_authenticated():
        return send_from_directory(APP_DIRECTORY, "tenant-login.html" if request.args.get("legacyLogin") == "1" else "unified-login.html")
    if g.tenant_status != "active" or g.tenant_membership_status != "active":
        return send_from_directory(APP_DIRECTORY, "business-status.html")
    return send_from_directory(APP_DIRECTORY, "CBL-Scheduler2.html")


@app.get("/hub")
def hub_page():
    return send_from_directory(APP_DIRECTORY, "hub.html")


@app.get("/business")
def business_page():
    if not tenant_authenticated():
        return redirect("/")
    return send_from_directory(APP_DIRECTORY, "business-status.html")


@app.get("/<path:asset_name>")
def serve_asset(asset_name):
    if asset_name not in STATIC_ASSETS:
        abort(404)
    return send_from_directory(APP_DIRECTORY, asset_name)


def developer_csrf_valid() -> bool:
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("developer_csrf", "")
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


def migrate_developer_accounts(connection: DatabaseConnection):
    if DATABASE_URL:
        connection.execute("ALTER TABLE developer_users DROP CONSTRAINT IF EXISTS developer_users_id_check")
        connection.execute("ALTER TABLE developer_users ADD COLUMN IF NOT EXISTS username_key TEXT")
    else:
        schema = connection.execute("SELECT sql FROM sqlite_master WHERE name='developer_users'").fetchone()[0]
        if re.search(r"CHECK\s*\(\s*id\s*=\s*1\s*\)", schema, re.IGNORECASE):
            connection.execute("ALTER TABLE developer_users RENAME TO developer_users_single")
            connection.execute(
                "CREATE TABLE developer_users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,"
                "password_hash TEXT NOT NULL, auth_version INTEGER NOT NULL DEFAULT 1,"
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute("INSERT INTO developer_users SELECT * FROM developer_users_single")
            connection.execute("DROP TABLE developer_users_single")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(developer_users)")}
        if "username_key" not in columns:
            connection.execute("ALTER TABLE developer_users ADD COLUMN username_key TEXT")
    for account_id, username in connection.execute("SELECT id,username FROM developer_users").fetchall():
        connection.execute("UPDATE developer_users SET username_key=? WHERE id=?", (username.casefold(), account_id))
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS developer_username_key ON developer_users(username_key)")


def developer_account(connection: DatabaseConnection, username: str):
    # Legacy sessions and imported accounts retain their original display name.
    return next(
        (row for row in connection.execute("SELECT username,password_hash,auth_version,id FROM developer_users")
         if row[0].casefold() == username.casefold()),
        None,
    )


def developer_authenticated() -> bool:
    username = session.get("developer_username")
    auth_version = session.get("developer_auth_version")
    if not isinstance(username, str) or not isinstance(auth_version, int):
        return False
    with closing(database_connect()) as connection:
        account = developer_account(connection, username)
    if (
        not account
        or account[0] != username
        or account[2] != auth_version
    ):
        session.clear()
        return False
    return True


def developer_local_request() -> bool:
    return request.remote_addr in {"127.0.0.1", "::1"}


def valid_developer_username(value: object) -> bool:
    return isinstance(value, str) and 3 <= len(value.strip()) <= 64


def valid_developer_password(value: object) -> bool:
    return isinstance(value, str) and len(value) >= 14 and len(value) <= 1024


def developer_request_order_expression(
    column: str,
) -> tuple[str, tuple[str | int, ...]]:
    request_ids = tuple(item[0] for item in DEVELOPER_REQUESTS)
    cases = " ".join("WHEN ? THEN ?" for _ in request_ids)
    parameters = tuple(
        value
        for index, request_id in enumerate(request_ids)
        for value in (request_id, index)
    ) + (len(request_ids),)
    return f"CASE {column} {cases} ELSE ? END", parameters


@app.get("/developer/change-requests")
def developer_change_requests_page():
    return send_from_directory(APP_DIRECTORY, "developer-change-requests.html")


@app.get("/business/change-requests")
def business_change_requests_page():
    denied = primary_admin_guard()
    if denied:
        return denied
    response = send_from_directory(APP_DIRECTORY, "business-change-requests.html")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/developer/auth-state")
def developer_auth_state():
    csrf_token = session.get("developer_csrf")
    if not isinstance(csrf_token, str):
        csrf_token = secrets.token_urlsafe(32)
        session["developer_csrf"] = csrf_token
    with closing(database_connect()) as connection:
        configured = connection.execute(
            "SELECT 1 FROM developer_users LIMIT 1"
        ).fetchone() is not None
    authenticated = developer_authenticated()
    return jsonify(
        configured=configured,
        authenticated=authenticated,
        username=session.get("developer_username") if authenticated else None,
        csrfToken=csrf_token,
        canBootstrap=not configured and developer_local_request(),
    )


@app.post("/api/developer/setup")
def setup_developer_account():
    if not developer_local_request():
        return jsonify(error="Initial developer setup is allowed only from this computer."), 403
    if not developer_csrf_valid():
        return jsonify(error="The setup session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not valid_developer_username(payload.get("username"))
        or not valid_developer_password(payload.get("password"))
    ):
        return jsonify(
            error="Enter a username of 3–64 characters and a password of at least 14 characters."
        ), 400
    username = payload["username"].strip()
    with closing(database_connect()) as connection, connection:
        if connection.execute("SELECT 1 FROM developer_users LIMIT 1").fetchone():
            return jsonify(error="Developer access has already been initialized."), 409
        try:
            connection.execute(
                """
                INSERT INTO developer_users (id, username, password_hash, username_key)
                VALUES (1, ?, ?, ?)
                """,
                (username, generate_password_hash(payload["password"]), username.casefold()),
            )
        except database_integrity_errors():
            return jsonify(error="Developer access has already been initialized."), 409
    session.clear()
    session["developer_username"] = username
    session["developer_auth_version"] = 1
    session["developer_csrf"] = secrets.token_urlsafe(32)
    return jsonify(username=username, csrfToken=session["developer_csrf"])


@app.post("/api/developer/login")
def developer_login():
    if not developer_csrf_valid():
        return jsonify(error="The login session expired. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Enter your developer username and password."), 400
    now = int(time_module.time())
    client_key = request.remote_addr or "unknown"
    with closing(database_connect()) as connection, connection:
        attempt = connection.execute(
            """
            SELECT failures, window_started_at, locked_until
            FROM developer_login_attempts WHERE client_key = ?
            """,
            (client_key,),
        ).fetchone()
        if attempt and attempt[2] > now:
            return jsonify(error="Too many failed sign-in attempts. Try again later."), 429
        if not attempt or now - attempt[1] >= 900:
            failures, window_started_at = 0, now
        else:
            failures, window_started_at = attempt[0], attempt[1]
        account = developer_account(connection, payload["username"].strip()) if isinstance(payload.get("username"), str) else None
        valid = bool(
            account
            and isinstance(payload.get("username"), str)
            and account[0].casefold() == payload["username"].strip().casefold()
            and isinstance(payload.get("password"), str)
            and check_password_hash(account[1], payload["password"])
        )
        if not valid:
            failures += 1
            locked_until = now + 900 if failures >= 5 else 0
            connection.execute(
                """
                INSERT INTO developer_login_attempts
                    (client_key, failures, window_started_at, locked_until)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_key) DO UPDATE SET
                    failures = excluded.failures,
                    window_started_at = excluded.window_started_at,
                    locked_until = excluded.locked_until
                """,
                (client_key, failures, window_started_at, locked_until),
            )
            return jsonify(error="The developer username or password is incorrect."), 401
        connection.execute(
            "DELETE FROM developer_login_attempts WHERE client_key = ?",
            (client_key,),
        )
    session.clear()
    session["developer_username"] = account[0]
    session["developer_auth_version"] = account[2]
    session["developer_csrf"] = secrets.token_urlsafe(32)
    return jsonify(username=account[0], csrfToken=session["developer_csrf"])


@app.post("/api/developer/logout")
def developer_logout():
    if not developer_authenticated():
        return jsonify(error="Sign in to the developer area first."), 401
    if not developer_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    session.clear()
    return jsonify(loggedOut=True)


@app.post("/api/developer/credentials")
def update_developer_credentials():
    if not developer_authenticated():
        return jsonify(error="Sign in to the developer area first."), 401
    if not developer_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("currentPassword"), str)
        or not valid_developer_username(payload.get("username"))
        or not valid_developer_password(payload.get("newPassword"))
    ):
        return jsonify(
            error="Enter your current password, a username of 3–64 characters, and a new password of at least 14 characters."
        ), 400
    username = payload["username"].strip()
    with closing(database_connect()) as connection, connection:
        account = developer_account(connection, session["developer_username"])
        if not account or not check_password_hash(account[1], payload["currentPassword"]):
            return jsonify(error="The current password is incorrect."), 403
        try:
            connection.execute(
                """
                UPDATE developer_users
                SET username = ?, password_hash = ?, username_key = ?, auth_version = auth_version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (username, generate_password_hash(payload["newPassword"]), username.casefold(), account[3]),
            )
        except database_integrity_errors():
            return jsonify(error="That developer username is already in use."), 409
        auth_version = connection.execute(
            "SELECT auth_version FROM developer_users WHERE id = ?", (account[3],)
        ).fetchone()[0]
    session.clear()
    session["developer_username"] = username
    session["developer_auth_version"] = auth_version
    session["developer_csrf"] = secrets.token_urlsafe(32)
    return jsonify(username=username, csrfToken=session["developer_csrf"])


@app.post("/api/developer/accounts")
def create_developer_account():
    if not developer_authenticated():
        return jsonify(error="Sign in to the developer area first."), 401
    if not developer_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("currentPassword"), str)
        or not valid_developer_username(payload.get("username"))
        or not valid_developer_password(payload.get("newPassword"))
    ):
        return jsonify(error="Enter your current password, a username of 3–64 characters and a new password of at least 14 characters."), 400
    username = payload["username"].strip()
    with closing(database_connect()) as connection, connection:
        account = developer_account(connection, session["developer_username"])
        if not account or not check_password_hash(account[1], payload["currentPassword"]):
            return jsonify(error="The current password is incorrect."), 403
        try:
            provision_developer_account(connection, username, payload["newPassword"])
        except ValueError as error:
            return jsonify(error=str(error)), 409
    return jsonify(username=username), 201


def provision_developer_account(connection: DatabaseConnection, username: str, password: str):
    if not valid_developer_username(username) or not valid_developer_password(password):
        raise ValueError("Use a username of 3–64 characters and a password of at least 14 characters.")
    username = username.strip()
    if developer_account(connection, username):
        raise ValueError("That developer username is already in use.")
    try:
        connection.execute(
            "INSERT INTO developer_users(id,username,password_hash,username_key) VALUES(?,?,?,?)",
            (secrets.randbelow(2147483646) + 2, username, generate_password_hash(password), username.casefold()),
        )
    except database_integrity_errors() as error:
        raise ValueError("The identifier or username is already in use. Retry with a unique username.") from error


@app.get("/api/developer/change-requests")
def list_developer_change_requests():
    if not developer_authenticated():
        return jsonify(error="Sign in to the developer area first."), 401
    status = request.args.get("status", "all")
    statuses = {"pending", "in_progress", "blocked", "done", "rejected"}
    if status != "all" and status not in statuses:
        return jsonify(error="Choose a valid request status filter."), 400
    with closing(database_connect()) as connection:
        query = """
            SELECT request_id, title, description, status, created_at, updated_at
            FROM developer_change_requests
        """
        parameters: tuple[str | int, ...] = ()
        if status != "all":
            query += " WHERE status = ?"
            parameters = (status,)
        request_order, request_order_parameters = developer_request_order_expression(
            "developer_change_requests.request_id"
        )
        query += (
            " ORDER BY CASE status WHEN 'in_progress' THEN 0 "
            "WHEN 'pending' THEN 1 WHEN 'blocked' THEN 2 "
            f"WHEN 'done' THEN 3 ELSE 4 END, {request_order}"
        )
        parameters = (*parameters, *request_order_parameters)
        rows = connection.execute(query, parameters).fetchall()
        dependencies = connection.execute(
            """
            SELECT dependency.request_id, prerequisite.request_id,
                   prerequisite.title, prerequisite.status
            FROM developer_change_request_dependencies AS dependency
            JOIN developer_change_requests AS prerequisite
              ON prerequisite.request_id = dependency.depends_on
            """
        ).fetchall()
        next_request_order, next_order_parameters = developer_request_order_expression(
            "request.request_id"
        )
        next_request = connection.execute(
            f"""
            SELECT request.request_id, request.title
            FROM developer_change_requests AS request
            WHERE request.status = 'pending'
              AND NOT EXISTS (
                  SELECT 1
                  FROM developer_change_request_dependencies AS dependency
                  JOIN developer_change_requests AS prerequisite
                    ON prerequisite.request_id = dependency.depends_on
                  WHERE dependency.request_id = request.request_id
                    AND prerequisite.status != 'done'
              )
            ORDER BY {next_request_order}
            LIMIT 1
            """,
            next_order_parameters,
        ).fetchone()
        dependency_map: dict[str, list[dict[str, str]]] = {}
        for request_id, dependency_id, title, dependency_status in dependencies:
            dependency_map.setdefault(request_id, []).append(
                {"id": dependency_id, "title": title, "status": dependency_status}
            )
    requests = [
        {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "status": row[3],
            "createdAt": row[4],
            "updatedAt": row[5],
            "dependencies": dependency_map.get(row[0], []),
        }
        for row in rows
    ]
    eligible = (
        {"id": next_request[0], "title": next_request[1]}
        if next_request
        else None
    )
    return jsonify(requests=requests, nextEligible=eligible)


@app.get("/api/business/change-requests")
def list_business_change_requests():
    denied = primary_admin_guard()
    if denied:
        return denied
    private_requests = {
        "developer-change-log",
        "tenant-identity",
        "primary-admin-change-request-visibility",
    }
    with closing(database_connect()) as connection:
        rows = connection.execute(
            """
            SELECT request_id, title, status FROM developer_change_requests
            WHERE status != 'rejected'
            ORDER BY CASE status WHEN 'in_progress' THEN 0
                WHEN 'pending' THEN 1 WHEN 'blocked' THEN 2 ELSE 3 END,
                title COLLATE NOCASE
            """
        ).fetchall()
    status_labels = {
        "done": "Completed",
        "in_progress": "In progress",
        "pending": "Planned",
        "blocked": "Planned",
    }
    items = []
    for request_id, title, status in rows:
        if request_id in private_requests or status not in status_labels:
            continue
        display_status = (
            "Awaiting acceptance"
            if status == "pending" and request_id in WORKFORCE_IMPLEMENTATION_NOTES
            else status_labels[status]
        )
        items.append({"title": title, "status": display_status})
    response = jsonify(requests=items)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.put("/api/developer/change-requests/<path:request_id>")
def update_developer_change_request(request_id: str):
    if not developer_authenticated():
        return jsonify(error="Sign in to the developer area first."), 401
    if not developer_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    statuses = {"pending", "in_progress", "blocked", "done", "rejected"}
    if not isinstance(payload, dict) or payload.get("status") not in statuses:
        return jsonify(error="Choose a valid request status."), 400
    status = payload["status"]
    with closing(database_connect()) as connection, connection:
        request_row = connection.execute(
            "SELECT 1 FROM developer_change_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if not request_row:
            return jsonify(error="Change request was not found."), 404
        if status in {"in_progress", "done"}:
            incomplete = connection.execute(
                """
                SELECT prerequisite.title, prerequisite.status
                FROM developer_change_request_dependencies AS dependency
                JOIN developer_change_requests AS prerequisite
                  ON prerequisite.request_id = dependency.depends_on
                WHERE dependency.request_id = ? AND prerequisite.status != 'done'
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()
            if incomplete:
                return jsonify(
                    error=f"Complete blocking request “{incomplete[0]}” first."
                ), 409
        connection.execute(
            """
            UPDATE developer_change_requests
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE request_id = ?
            """,
            (status, request_id),
        )
    return jsonify(id=request_id, status=status)


@app.get("/api/accepted-shifts")
def list_accepted_shifts():
    with closing(database_connect()) as connection:
        rows = connection.execute(
            """
            SELECT run_id, accepted_at, payload
            FROM accepted_schedules
            ORDER BY week_start DESC, accepted_at DESC, location, role
            """
        ).fetchall()
    return jsonify(
        schedules=[
            {
                "id": run_id,
                "acceptedAt": accepted_at,
                "schedule": json.loads(payload),
            }
            for run_id, accepted_at, payload in rows
        ]
    )


@app.post("/api/accepted-shifts")
def accept_shifts():
    payload = request.get_json(silent=True)
    if not valid_schedule(payload):
        return jsonify(error="A valid weekly schedule is required."), 400

    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_ACCEPTED_SCHEDULE_BYTES:
        return jsonify(error="The schedule is too large to save."), 413

    with closing(database_connect()) as connection, connection:
        conflict_key = "tenant_id, run_id" if DATABASE_URL else "run_id"
        connection.execute(
            f"""
            INSERT INTO accepted_schedules (run_id, week_start, location, role, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT({conflict_key}) DO UPDATE SET
                week_start = excluded.week_start,
                location = excluded.location,
                role = excluded.role,
                payload = excluded.payload
            """,
            (
                payload["id"],
                payload["start"],
                payload["location"],
                payload["role"],
                encoded,
            ),
        )
        row = connection.execute(
            "SELECT accepted_at FROM accepted_schedules WHERE run_id = ?",
            (payload["id"],),
        ).fetchone()
    return jsonify(id=payload["id"], acceptedAt=row[0])


@app.put("/api/accepted-shifts/<path:run_id>")
def update_accepted_shifts(run_id: str):
    payload = request.get_json(silent=True)
    if not valid_schedule(payload) or payload["id"] != run_id:
        return jsonify(error="The updated schedule does not match the accepted schedule."), 400

    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_ACCEPTED_SCHEDULE_BYTES:
        return jsonify(error="The schedule is too large to save."), 413

    with closing(database_connect()) as connection, connection:
        cursor = connection.execute(
            """
            UPDATE accepted_schedules
            SET week_start = ?, location = ?, role = ?, payload = ?
            WHERE run_id = ?
            """,
            (payload["start"], payload["location"], payload["role"], encoded, run_id),
        )
        if cursor.rowcount == 0:
            return jsonify(error="Accepted schedule was not found."), 404
    return jsonify(id=run_id)


@app.delete("/api/accepted-shifts/<path:run_id>")
def delete_accepted_shifts(run_id: str):
    with closing(database_connect()) as connection, connection:
        cursor = connection.execute(
            "DELETE FROM accepted_schedules WHERE run_id = ?", (run_id,)
        )
        if cursor.rowcount == 0:
            return jsonify(error="Accepted schedule was not found."), 404
    return jsonify(id=run_id)


def directory_employee(row: tuple) -> dict:
    return {
        "id": row[0],
        "bamboohrId": row[1],
        "name": row[2],
        "location": row[3],
        "role": row[4],
        "active": bool(row[5]),
        "scheduleLocationId": row[6],
        "source": row[7],
        "bamboohrLocation": row[8],
        "bamboohrActive": bool(row[9]) if row[7] == "bamboohr" else None,
    }


def normalized_employee_id(value: object) -> str:
    return str(value or "").strip().casefold()


def employee_id_in_use(
    connection: DatabaseConnection, employee_id: str, exclude_employee_id: str | None = None
) -> bool:
    query = "SELECT 1 FROM employees WHERE lower(trim(employee_id)) = lower(trim(?))"
    parameters: tuple[str, ...] = (employee_id,)
    if exclude_employee_id is not None:
        query += " AND employee_id != ?"
        parameters += (exclude_employee_id,)
    return connection.execute(query, parameters).fetchone() is not None


def fetch_bamboohr_employees(*, require_employee_number: bool = True) -> list[dict[str, str]]:
    api_key = bamboohr_api_key()
    if not api_key:
        raise RuntimeError("The BambooHR API key is not configured for this business.")
    authorization = base64.b64encode(f"{api_key}:x".encode("utf-8")).decode("ascii")
    cursor = None
    seen_cursors: set[str] = set()
    employees: list[dict[str, str]] = []
    expected_total = None

    while True:
        parameters = {
            "fields": "employeeNumber,location",
            "filter[status]": "active",
            "page[limit]": "2500",
        }
        if cursor:
            parameters["page[after]"] = cursor
        outbound = Request(
            f"{bamboohr_endpoint('employees')}?{urlencode(parameters)}",
            headers={"Accept": "application/json", "Authorization": f"Basic {authorization}"},
            method="GET",
        )
        try:
            with urlopen(outbound, timeout=30) as response:
                raw_data = response.read(10_000_001)
        except HTTPError as error:
            if error.code == 401:
                raise RuntimeError("BambooHR rejected the configured API key.") from error
            if error.code == 403:
                raise RuntimeError(
                    "BambooHR denied access to the employee list. Check the API key permissions."
                ) from error
            raise RuntimeError(f"BambooHR employee sync failed with HTTP {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise RuntimeError("The app server could not reach BambooHR for employee data.") from error
        if len(raw_data) > 10_000_000:
            raise RuntimeError("BambooHR employee response exceeds the allowed size.")
        try:
            page = json.loads(raw_data)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RuntimeError("BambooHR returned an invalid employee response.") from error
        if not isinstance(page, dict) or not isinstance(page.get("data"), list):
            raise RuntimeError("BambooHR returned an invalid employee list.")
        meta = page.get("meta")
        page_meta = meta.get("page") if isinstance(meta, dict) else None
        total = meta.get("total") if isinstance(meta, dict) else None
        if not isinstance(total, int) or total < 0 or not isinstance(page_meta, dict):
            raise RuntimeError("BambooHR returned incomplete employee pagination data.")
        if expected_total is None:
            expected_total = total
        elif expected_total != total:
            raise RuntimeError("The BambooHR employee list changed during synchronization; retry.")

        for item in page["data"]:
            if not isinstance(item, dict):
                raise RuntimeError("BambooHR returned an invalid employee record.")
            status = item.get("status")
            if status is not None and str(status).casefold() != "active":
                continue
            bamboohr_id = item.get("employeeId")
            employee_number = item.get("employeeNumber")
            if not isinstance(bamboohr_id, (str, int)) or not str(bamboohr_id).strip():
                raise RuntimeError("A BambooHR employee record is missing its BambooHR ID.")
            if require_employee_number and (
                not isinstance(employee_number, (str, int))
                or not str(employee_number).strip()
            ):
                raise RuntimeError(
                    f"BambooHR employee {bamboohr_id} is missing Employee #. Complete it in BambooHR before syncing."
                )
            first_name = str(item.get("preferredName") or item.get("firstName") or "").strip()
            last_name = str(item.get("lastName") or "").strip()
            name = " ".join(part for part in (first_name, last_name) if part)
            if not name:
                name = str(item.get("displayName") or "").strip()
            if not name:
                raise RuntimeError(
                    f"BambooHR employee {bamboohr_id} is missing a display name."
                )
            employees.append(
                {
                    "bamboohrId": str(bamboohr_id).strip(),
                    "id": str(employee_number).strip()
                    if isinstance(employee_number, (str, int)) else "",
                    "name": name,
                    "bamboohrLocation": str(item.get("location") or "").strip(),
                }
            )
            if len(employees) > 100_000:
                raise RuntimeError("BambooHR employee list exceeds the supported size.")

        next_cursor = page_meta.get("nextCursor")
        if next_cursor is None:
            break
        if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
            raise RuntimeError("BambooHR returned an invalid employee page cursor.")
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    if expected_total != len(employees):
        raise RuntimeError(
            "BambooHR returned an incomplete active employee list; no changes were saved."
        )
    if len({employee["bamboohrId"] for employee in employees}) != len(employees):
        raise RuntimeError("BambooHR returned duplicate internal employee IDs; no changes were saved.")
    employee_numbers = [
        normalized_employee_id(employee["id"])
        for employee in employees
        if employee["id"]
    ]
    if len(set(employee_numbers)) != len(employee_numbers):
        raise RuntimeError("BambooHR returned duplicate Employee # values; no changes were saved.")
    return employees


def bamboo_employee_sync_conflicts(
    connection: DatabaseConnection, remote_employees: list[dict[str, str]]
) -> list[dict]:
    records = connection.execute(
         """
         SELECT employee_id, bamboohr_id, name, location, role, active,
             schedule_location_id, source_type
         FROM employees
         WHERE tenant_id=?
         """,
         (active_tenant_id(),),
        ).fetchall()
    if len({normalized_employee_id(row[0]) for row in records}) != len(records):
        raise RuntimeError(
            "The app contains duplicate Employee IDs ignoring case; resolve them before syncing."
        )
    by_bamboo_id = {
        row[1]: row for row in records if row[1] and row[7] == "bamboohr"
    }
    by_id = {normalized_employee_id(row[0]): row for row in records}
    conflicts = []
    for remote in remote_employees:
        employee = by_bamboo_id.get(remote["bamboohrId"])
        collision = by_id.get(normalized_employee_id(remote["id"]))
        if collision and collision[7] == "manual" and (
            employee is None or collision[0] != employee[0]
        ):
            conflicts.append(
                {
                    "bamboohrId": remote["bamboohrId"],
                    "employeeId": remote["id"],
                    "bamboohrName": remote["name"],
                    "existingBambooEmployeeId": employee[0] if employee else None,
                    "manualEmployee": {
                        "id": collision[0],
                        "name": collision[2],
                        "role": collision[4],
                        "location": collision[3],
                        "scheduleLocationId": collision[6],
                        "active": bool(collision[5]),
                    },
                }
            )
        elif collision and collision[7] == "bamboohr" and (
            employee is None or collision[0] != employee[0]
        ):
            raise RuntimeError(
                f"Employee # {remote['id']} is already assigned to another BambooHR record."
            )
    return conflicts


def mapped_bamboohr_location(connection: DatabaseConnection, location: str) -> str:
    if not location:
        return ""
    rows = connection.execute(
        "SELECT DISTINCT location FROM schedule_locations WHERE tenant_id = ?",
        (active_tenant_id(),),
    ).fetchall()
    meta = connection.execute(
        "SELECT locations_json FROM meta_configurations WHERE tenant_id = ?",
        (active_tenant_id(),),
    ).fetchone()
    if meta:
        rows.extend(
            (item["name"],)
            for item in json.loads(meta[0])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        )
    matches = [
        value for value in dict.fromkeys(row[0] for row in rows)
        if normalized_employee_id(value) == normalized_employee_id(location)
    ]
    return matches[0] if len(matches) == 1 else ""


@app.post("/api/bamboohr/employees/sync")
def sync_bamboohr_employees():
    payload = request.get_json(silent=True) or {}
    resolutions = payload.get("resolutions", []) if isinstance(payload, dict) else None
    if not isinstance(resolutions, list):
        return jsonify(error="Employee reconciliation choices must be a list."), 400
    try:
        remote_employees = fetch_bamboohr_employees()
    except RuntimeError as error:
        return jsonify(error=str(error)), 502 if "not configured" not in str(error) else 503

    with closing(database_connect()) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            conflicts = bamboo_employee_sync_conflicts(connection, remote_employees)
        except RuntimeError as error:
            return jsonify(error=str(error)), 409
        if conflicts and not resolutions:
            return jsonify(requiresReview=True, conflicts=conflicts)
        conflict_by_bamboo_id = {conflict["bamboohrId"]: conflict for conflict in conflicts}
        resolution_by_bamboo_id = {}
        for resolution in resolutions:
            if (
                not isinstance(resolution, dict)
                or not isinstance(resolution.get("bamboohrId"), str)
                or resolution.get("bamboohrId") in resolution_by_bamboo_id
                or not isinstance(resolution.get("samePerson"), bool)
            ):
                return jsonify(error="Each employee conflict needs one valid reconciliation choice."), 400
            resolution_by_bamboo_id[resolution["bamboohrId"]] = resolution
        if set(resolution_by_bamboo_id) != set(conflict_by_bamboo_id):
            if conflicts:
                return jsonify(requiresReview=True, conflicts=conflicts)
            return jsonify(error="The BambooHR list changed; refresh it and review again."), 409
        for bamboohr_id, resolution in resolution_by_bamboo_id.items():
            conflict = conflict_by_bamboo_id[bamboohr_id]
            if resolution.get("employeeId") != conflict["manualEmployee"]["id"]:
                return jsonify(error="A manual employee changed during reconciliation; refresh and review again."), 409
            if not resolution["samePerson"]:
                new_id = resolution.get("newManualEmployeeId")
                if (
                    not isinstance(new_id, str)
                    or not new_id.strip()
                    or normalized_employee_id(new_id) == normalized_employee_id(conflict["employeeId"])
                ):
                    return jsonify(error="Enter a new, unique Employee ID for the different manual employee."), 400
        if conflicts:
            existing_ids = {
                normalized_employee_id(row[0]): row[0]
                for row in connection.execute("SELECT employee_id FROM employees")
            }
            remote_ids = {
                normalized_employee_id(employee["id"]) for employee in remote_employees
            }
            proposed_ids = set()
            for bamboohr_id, resolution in resolution_by_bamboo_id.items():
                if resolution["samePerson"]:
                    continue
                replacement_id = resolution["newManualEmployeeId"].strip()
                normalized_replacement = normalized_employee_id(replacement_id)
                manual_id = conflict_by_bamboo_id[bamboohr_id]["manualEmployee"]["id"]
                if (
                    normalized_replacement in existing_ids
                    and existing_ids[normalized_replacement] != manual_id
                ):
                    return jsonify(error=f"Employee ID {replacement_id} is already in use."), 409
                if normalized_replacement in remote_ids or normalized_replacement in proposed_ids:
                    return jsonify(error=f"Employee ID {replacement_id} is already in use."), 409
                proposed_ids.add(normalized_replacement)

        by_bamboo_id = {
            row[1]: row
            for row in connection.execute(
                """
                SELECT employee_id, bamboohr_id, name, location, role, active,
                       schedule_location_id, source_type
                FROM employees WHERE source_type = 'bamboohr'
                """
            ).fetchall()
        }
        by_employee_id = {
            normalized_employee_id(row[0]): row
            for row in connection.execute(
                """
                SELECT employee_id, bamboohr_id, name, location, role, active,
                       schedule_location_id, source_type
                FROM employees
                """
            ).fetchall()
        }
        added = updated = inactivated = merged = rekeyed = 0
        employee_id_changes = []
        for remote in remote_employees:
            existing = by_bamboo_id.get(remote["bamboohrId"])
            resolution = resolution_by_bamboo_id.get(remote["bamboohrId"])
            collision = by_employee_id.get(normalized_employee_id(remote["id"]))
            if collision and collision[7] == "manual" and (
                existing is None or collision[0] != existing[0]
            ):
                if resolution["samePerson"]:
                    if existing and existing[0] != collision[0]:
                        connection.execute(
                            "DELETE FROM employees WHERE employee_id = ?",
                            (collision[0],),
                        )
                        if not existing[4]:
                            connection.execute(
                                """
                                UPDATE employees
                                SET location = ?, role = ?, active = ?, schedule_location_id = ?
                                WHERE employee_id = ?
                                """,
                                (
                                    collision[3], collision[4], collision[5],
                                    collision[6], existing[0],
                                ),
                            )
                        connection.execute(
                            "UPDATE employees SET employee_id = ? WHERE employee_id = ?",
                            (remote["id"], existing[0]),
                        )
                        employee_id_changes.append(
                            {
                                "oldId": existing[0],
                                "newId": remote["id"],
                                "source": "bamboohr",
                                "bamboohrId": remote["bamboohrId"],
                                "mergedManualId": collision[0],
                            }
                        )
                        rekeyed += 1
                        existing = (
                            remote["id"], existing[1], existing[2],
                            collision[3] if not existing[4] else existing[3],
                            collision[4] if not existing[4] else existing[4],
                            collision[5] if not existing[4] else existing[5],
                            collision[6] if not existing[4] else existing[6],
                            existing[7],
                        )
                    else:
                        connection.execute(
                            """
                            UPDATE employees
                            SET bamboohr_id = ?, name = ?, bamboohr_location = ?,
                                source_type = 'bamboohr', bamboohr_active = 1
                            WHERE employee_id = ? AND source_type = 'manual'
                            """,
                            (
                                remote["bamboohrId"], remote["name"],
                                remote["bamboohrLocation"], collision[0],
                            ),
                        )
                        existing = connection.execute(
                            """
                            SELECT employee_id, bamboohr_id, name, location, role, active,
                                   schedule_location_id, source_type
                            FROM employees WHERE employee_id = ?
                            """,
                            (collision[0],),
                        ).fetchone()
                    merged += 1
                else:
                    replacement_id = resolution["newManualEmployeeId"].strip()
                    connection.execute(
                        "UPDATE employees SET employee_id = ? WHERE employee_id = ?",
                        (replacement_id, collision[0]),
                    )
                    employee_id_changes.append(
                        {"oldId": collision[0], "newId": replacement_id, "source": "manual"}
                    )
                    rekeyed += 1
            if existing is None:
                mapped_location = mapped_bamboohr_location(
                    connection, remote["bamboohrLocation"]
                )
                connection.execute(
                    """
                    INSERT INTO employees
                        (employee_id, bamboohr_id, name, location, role, active,
                         schedule_location_id, source_type, bamboohr_location, bamboohr_active)
                    VALUES (?, ?, ?, ?, '', 0, NULL, 'bamboohr', ?, 1)
                    """,
                    (
                        remote["id"], remote["bamboohrId"], remote["name"],
                        mapped_location, remote["bamboohrLocation"],
                    ),
                )
                added += 1
            else:
                old_id = existing[0]
                if normalized_employee_id(old_id) != normalized_employee_id(remote["id"]):
                    connection.execute(
                        "UPDATE employees SET employee_id = ? WHERE employee_id = ?",
                        (remote["id"], old_id),
                    )
                    employee_id_changes.append(
                        {
                            "oldId": old_id,
                            "newId": remote["id"],
                            "source": "bamboohr",
                            "bamboohrId": remote["bamboohrId"],
                        }
                    )
                    rekeyed += 1
                connection.execute(
                    """
                    UPDATE employees
                    SET name = ?, bamboohr_id = ?, bamboohr_location = ?,
                        location = CASE WHEN trim(COALESCE(location, '')) = '' THEN ? ELSE location END,
                        source_type = 'bamboohr', bamboohr_active = 1
                    WHERE employee_id = ?
                    """,
                    (
                        remote["name"], remote["bamboohrId"],
                        remote["bamboohrLocation"],
                        mapped_bamboohr_location(connection, remote["bamboohrLocation"]),
                        remote["id"],
                    ),
                )
                updated += 1

        active_bamboo_ids = [employee["bamboohrId"] for employee in remote_employees]
        if active_bamboo_ids:
            placeholders = ",".join("?" for _ in active_bamboo_ids)
            inactive_cursor = connection.execute(
                f"""
                UPDATE employees SET active = 0, bamboohr_active = 0
                WHERE source_type = 'bamboohr' AND bamboohr_id NOT IN ({placeholders})
                  AND (active != 0 OR bamboohr_active != 0)
                """,
                active_bamboo_ids,
            )
        else:
            inactive_cursor = connection.execute(
                """
                UPDATE employees SET active = 0, bamboohr_active = 0
                WHERE source_type = 'bamboohr' AND (active != 0 OR bamboohr_active != 0)
                """
            )
        inactivated = inactive_cursor.rowcount
        return jsonify(
            synced=len(remote_employees),
            added=added,
            updated=updated,
            merged=merged,
            rekeyed=rekeyed,
            inactivated=inactivated,
            employeeIdChanges=employee_id_changes,
            syncedAt=datetime.now(timezone.utc).isoformat(),
        )


@app.get("/api/employees")
def list_employees():
    with closing(database_connect()) as connection:
        rows = connection.execute(
            """
            SELECT employee_id, bamboohr_id, name, location, role, active, schedule_location_id,
                   source_type, bamboohr_location, bamboohr_active
            FROM employees
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()
    return jsonify(employees=[directory_employee(row) for row in rows])


@app.put("/api/employees/status")
def update_employee_statuses():
    payload = request.get_json(silent=True)
    employee_ids = payload.get("employeeIds") if isinstance(payload, dict) else None
    active = payload.get("active") if isinstance(payload, dict) else None
    if (
        not isinstance(employee_ids, list)
        or not employee_ids
        or any(not isinstance(employee_id, str) or not employee_id.strip() for employee_id in employee_ids)
        or len(employee_ids) != len(set(employee_ids))
        or not isinstance(active, bool)
    ):
        return jsonify(error="A non-empty list of unique employee IDs and an active status are required."), 400
    with closing(database_connect()) as connection, connection:
        placeholders = ",".join("?" for _ in employee_ids)
        rows = connection.execute(
            f"SELECT employee_id, active FROM employees WHERE employee_id IN ({placeholders})",
            employee_ids,
        ).fetchall()
        if len(rows) != len(employee_ids):
            return jsonify(error="One or more selected employees were not found."), 404
        additions = sum(not bool(row[1]) for row in rows) if active else 0
        limit_response = membership_quota_response(
            connection, "employees", additions=additions
        )
        if limit_response:
            return limit_response
        connection.executemany(
            "UPDATE employees SET active = ? WHERE employee_id = ?",
            [(int(active), employee_id) for employee_id in employee_ids],
        )
    return jsonify(employeeIds=employee_ids, active=active)


@app.put("/api/employees/roles")
def update_employee_roles():
    payload = request.get_json(silent=True)
    employee_ids = payload.get("employeeIds") if isinstance(payload, dict) else None
    role = payload.get("role") if isinstance(payload, dict) else None
    if (
        not isinstance(employee_ids, list)
        or not employee_ids
        or any(not isinstance(employee_id, str) or not employee_id.strip() for employee_id in employee_ids)
        or len(employee_ids) != len(set(employee_ids))
        or not isinstance(role, str)
        or not role.strip()
    ):
        return jsonify(error="Select employees and provide one role to assign."), 400
    role = role.strip()
    with closing(database_connect()) as connection, connection:
        rows = connection.execute(
            """
            SELECT employee_id, location, role, active, schedule_location_id
            FROM employees
            WHERE employee_id IN ({})
            """.format(",".join("?" for _ in employee_ids)),
            employee_ids,
        ).fetchall()
        if len(rows) != len(employee_ids):
            return jsonify(error="One or more selected employees were not found."), 404
        for employee in rows:
            if employee[4] and not role_matches_schedule_group(
                role,
                connection.execute(
                    "SELECT role_group FROM schedule_locations WHERE id = ?",
                    (employee[4],),
                ).fetchone()[0],
            ):
                return jsonify(
                    error=f"The role {role} does not match {employee[0]}'s schedule location. Change the schedule location first."
                ), 400
        changed_ids = [row[0] for row in rows if row[2] != role]
        if changed_ids:
            placeholders = ",".join("?" for _ in changed_ids)
            connection.execute(
                f"""
                UPDATE employees SET role = ?, active = 0
                WHERE employee_id IN ({placeholders})
                """,
                [role, *changed_ids],
            )
    return jsonify(role=role, employeeIds=employee_ids, deactivatedIds=changed_ids)


@app.put("/api/employees/import-review")
def confirm_imported_employee_mappings():
    denied = primary_admin_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    mappings = payload.get("employees") if isinstance(payload, dict) else None
    if not isinstance(mappings, list) or not mappings:
        return jsonify(error="Approve at least one valid employee mapping."), 400
    seen_ids = set()
    normalized_mappings = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            return jsonify(error="The employee mapping review contains an invalid row."), 400
        employee_id = mapping.get("id")
        role = mapping.get("role")
        location = mapping.get("location")
        schedule_location_id = mapping.get("scheduleLocationId")
        if (
            not isinstance(employee_id, str)
            or not employee_id.strip()
            or not isinstance(mapping.get("name"), str)
            or not mapping["name"].strip()
            or not isinstance(location, str)
            or not location.strip()
            or not isinstance(role, str)
            or not role.strip()
            or not isinstance(mapping.get("addManual"), bool)
        ):
            return jsonify(error="Each mapping needs an Employee ID, name, location, role, and manual-add choice."), 400
        normalized_id = normalized_employee_id(employee_id)
        if normalized_id in seen_ids:
            return jsonify(error=f"Employee ID {employee_id} appears more than once in the review."), 400
        seen_ids.add(normalized_id)
        if schedule_location_id is not None and not isinstance(schedule_location_id, str):
            return jsonify(error="A schedule location selection is invalid."), 400
        normalized_mappings.append(
            {
                **mapping,
                "id": employee_id.strip(),
                "name": mapping["name"].strip(),
                "location": location.strip(),
                "role": role.strip(),
                "scheduleLocationId": schedule_location_id.strip() or None
                if isinstance(schedule_location_id, str)
                else None,
            }
        )
    updated = added = deactivated = 0
    with closing(database_connect()) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        existing_rows = connection.execute(
            """
            SELECT employee_id, name, location, role, active,
                   schedule_location_id, source_type
            FROM employees
            """
        ).fetchall()
        if len({normalized_employee_id(row[0]) for row in existing_rows}) != len(existing_rows):
            return jsonify(error="Resolve duplicate Employee IDs before importing mappings."), 409
        current_by_id = {
            normalized_employee_id(row[0]): row for row in existing_rows
        }
        plans = []
        for mapping in normalized_mappings:
            current = current_by_id.get(normalized_employee_id(mapping["id"]))
            if current is None and not mapping["addManual"]:
                plans.append((mapping, None))
                continue
            schedule_location_id = mapping["scheduleLocationId"]
            if schedule_location_id:
                schedule = connection.execute(
                    "SELECT location, role_group FROM schedule_locations WHERE id = ?",
                    (schedule_location_id,),
                ).fetchone()
                if (
                    not schedule
                    or schedule[0] != mapping["location"]
                    or not role_matches_schedule_group(mapping["role"], schedule[1])
                ):
                    return jsonify(error=f"Schedule location does not match {mapping['name']}."), 400
            plans.append((mapping, current))

        for mapping, current in plans:
            employee_id = mapping["id"]
            role = mapping["role"]
            location_name = mapping["location"]
            schedule_location_id = mapping["scheduleLocationId"]
            if current is None:
                if not mapping["addManual"]:
                    continue
                connection.execute(
                    """
                    INSERT INTO employees
                        (employee_id, bamboohr_id, name, location, role, active,
                         schedule_location_id, source_type, bamboohr_location, bamboohr_active)
                    VALUES (?, ?, ?, ?, ?, 0, ?, 'manual', '', 0)
                    """,
                    (
                        employee_id,
                        "MANUAL-" + secrets.token_hex(12).upper(),
                        mapping["name"],
                        location_name,
                        role,
                        schedule_location_id,
                    ),
                )
                added += 1
                continue
            changed = current[2] != location_name or current[3] != role
            active = 0 if changed and current[4] else current[4]
            cursor = connection.execute(
                """
                UPDATE employees
                SET location = ?, role = ?, schedule_location_id = ?, active = ?
                WHERE employee_id = ?
                """,
                (location_name, role, schedule_location_id, active, current[0]),
            )
            updated += cursor.rowcount
            if changed and current[4]:
                deactivated += 1
    return jsonify(updated=updated, addedManual=added, deactivated=deactivated)


def valid_employee(payload: object, *, require_bamboo_id: bool = True) -> bool:
    if not isinstance(payload, dict):
        return False
    fields = ("id", "name", "location")
    if any(not isinstance(payload.get(field), str) or not payload[field].strip() for field in fields):
        return False
    role = payload.get("role")
    if not isinstance(role, str) or not role.strip():
        return False
    bamboohr_id = payload.get("bamboohrId")
    if require_bamboo_id and (
        not isinstance(bamboohr_id, str) or not bamboohr_id.strip()
    ):
        return False
    return isinstance(payload.get("active"), bool) and (
        payload.get("scheduleLocationId") is None
        or isinstance(payload.get("scheduleLocationId"), str)
    )


def role_matches_schedule_group(role: str, role_group: str) -> bool:
    normalized_role = role.strip().casefold()
    normalized_group = role_group.strip().casefold()
    if not normalized_group:
        return True
    if normalized_group == "warehouse/delivery":
        return normalized_role in {"warehouse", "dc associate"}
    if "supervisor" in normalized_group:
        return "supervisor" in normalized_role
    if "settlement" in normalized_group:
        return "settlement" in normalized_role
    return normalized_role == normalized_group


def employee_location_exists(connection: DatabaseConnection, payload: dict) -> bool:
    location_id = payload.get("scheduleLocationId")
    if location_id is None:
        return True
    row = connection.execute(
        "SELECT location, role_group FROM schedule_locations WHERE id = ?", (location_id,)
    ).fetchone()
    return (
        row is not None
        and row[0] == payload["location"]
        and role_matches_schedule_group(payload["role"], row[1])
    )


def directory_conflict():
    return jsonify(error="Employee ID or BambooHR ID is already in use."), 409


@app.post("/api/employees")
def create_employee():
    payload = request.get_json(silent=True)
    if (
        not isinstance(payload, dict)
        or any(
            not isinstance(payload.get(field), str) or not payload[field].strip()
            for field in ("id", "name", "location")
        )
        or not isinstance(payload.get("role", ""), str)
        or not payload.get("role", "").strip()
        or payload.get("active", False) is not False
        or payload.get("scheduleLocationId") not in (None, "")
    ):
        return jsonify(error="A manual employee needs an Employee ID, name, and location and must start inactive."), 400
    employee_id = payload["id"].strip()
    role = payload.get("role", "").strip()
    bamboohr_id = "MANUAL-" + secrets.token_hex(12).upper()
    employee_payload = {
        "id": employee_id,
        "bamboohrId": bamboohr_id,
        "name": payload["name"].strip(),
        "location": payload["location"].strip(),
        "role": role,
        "active": False,
        "scheduleLocationId": None,
        "source": "manual",
    }
    with closing(database_connect()) as connection, connection:
        if employee_id_in_use(connection, employee_id):
            return directory_conflict()
        if not employee_location_exists(connection, employee_payload):
            return jsonify(error="The assigned schedule location does not match the employee's location."), 400
        try:
            connection.execute(
                """
                INSERT INTO employees
                    (employee_id, bamboohr_id, name, location, role, active, schedule_location_id,
                     source_type, bamboohr_location, bamboohr_active)
                VALUES (?, ?, ?, ?, ?, 0, NULL, 'manual', '', 0)
                """,
                (
                    employee_payload["id"],
                    bamboohr_id,
                    employee_payload["name"],
                    employee_payload["location"],
                    role,
                ),
            )
        except database_integrity_errors():
            return directory_conflict()
    return jsonify(employee=employee_payload), 201


@app.put("/api/employees/<path:employee_id>")
def update_employee(employee_id: str):
    payload = request.get_json(silent=True)
    if not valid_employee(payload):
        return jsonify(error="Employee ID, name, location, role, and active status are required."), 400
    with closing(database_connect()) as connection, connection:
        existing = connection.execute(
            """
            SELECT employee_id, bamboohr_id, name, location, role, active,
                   schedule_location_id, source_type
            FROM employees WHERE employee_id = ?
            """,
            (employee_id,),
        ).fetchone()
        if not existing:
            return jsonify(error="Employee was not found."), 404
        source_type = existing[7]
        if source_type == "bamboohr":
            payload = {
                **payload,
                "id": existing[0],
                "bamboohrId": existing[1],
                "name": existing[2],
            }
        else:
            payload = {
                **payload,
                "bamboohrId": existing[1],
                "active": bool(payload["active"]),
            }
        if employee_id_in_use(connection, payload["id"].strip(), employee_id):
            return directory_conflict()
        if not employee_location_exists(connection, payload):
            return jsonify(error="The assigned schedule location does not match the employee's location."), 400
        if payload["active"] and not payload["role"].strip():
            return jsonify(error="Assign a role before making the employee active."), 400
        if payload.get("scheduleLocationId") and not payload["role"].strip():
            return jsonify(error="Assign a role before mapping the employee to a schedule location."), 400
        if payload["active"] and not existing[5]:
            limit_response = membership_quota_response(connection, "employees")
            if limit_response:
                return limit_response
        try:
            cursor = connection.execute(
                """
                UPDATE employees
                SET employee_id = ?, bamboohr_id = ?, name = ?, location = ?, role = ?,
                    active = ?, schedule_location_id = ?
                WHERE employee_id = ?
                """,
                (
                    payload["id"].strip(),
                    payload["bamboohrId"].strip(),
                    payload["name"].strip(),
                    payload["location"].strip(),
                    payload["role"].strip(),
                    int(payload["active"]),
                    payload.get("scheduleLocationId"),
                    employee_id,
                ),
            )
        except database_integrity_errors():
            return directory_conflict()
        if cursor.rowcount == 0:
            return jsonify(error="Employee was not found."), 404
    return jsonify(employee=payload)


@app.delete("/api/employees/<path:employee_id>")
def delete_employee(employee_id: str):
    with closing(database_connect()) as connection, connection:
        employee = connection.execute(
            "SELECT source_type FROM employees WHERE employee_id = ?", (employee_id,)
        ).fetchone()
        if not employee:
            return jsonify(error="Employee was not found."), 404
        if employee[0] != "manual":
            return jsonify(error="BambooHR employees cannot be deleted; make them inactive instead."), 409
        cursor = connection.execute(
            "DELETE FROM employees WHERE employee_id = ?", (employee_id,)
        )
    return jsonify(id=employee_id)


@app.get("/api/schedule-locations")
def list_schedule_locations():
    with closing(database_connect()) as connection:
        rows = connection.execute(
            """
            SELECT s.id, s.name, s.bamboo_schedule_id, s.location, s.role_group,
                   s.manager_name, s.manager_email,
                   COUNT(e.employee_id)
            FROM schedule_locations s
            LEFT JOIN employees e ON e.schedule_location_id = s.id
            GROUP BY s.id, s.name, s.bamboo_schedule_id, s.location, s.role_group,
                     s.manager_name, s.manager_email
            ORDER BY s.name COLLATE NOCASE
            """
        ).fetchall()
    return jsonify(
        scheduleLocations=[
            {
                "id": row[0],
                "name": row[1],
                "bambooScheduleId": row[2],
                "location": row[3],
                "roleGroup": row[4],
                "managerName": row[5],
                "managerEmail": row[6],
                "employeeCount": row[7],
            }
            for row in rows
        ]
    )


def valid_schedule_location(payload: object) -> bool:
    if not isinstance(payload, dict) or not all(
        isinstance(payload.get(field), str) and payload[field].strip()
        for field in ("name", "bambooScheduleId", "location", "managerName", "managerEmail")
    ):
        return False
    manager_name = payload["managerName"].strip()
    manager_email = payload["managerEmail"].strip()
    return (
        not re.search(r"[\r\n<>]", manager_name)
        and re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+", manager_email)
        is not None
    )


def schedule_team_exists(
    connection: DatabaseConnection,
    location: str,
    role_group: str,
    *,
    exclude_id: str | None = None,
) -> bool:
    query = """
        SELECT 1 FROM schedule_locations
        WHERE tenant_id = ? AND LOWER(location) = LOWER(?) AND LOWER(role_group) = LOWER(?)
    """
    parameters: tuple[str, ...] = (active_tenant_id(), location, role_group)
    if exclude_id is not None:
        query += " AND id != ?"
        parameters = (*parameters, exclude_id)
    return connection.execute(query + " LIMIT 1", parameters).fetchone() is not None


def schedule_team_count(
    connection: DatabaseConnection,
    location: str,
    role_group: str,
) -> int:
    return connection.execute(
        """
        SELECT COUNT(*) FROM schedule_locations
        WHERE tenant_id = ? AND LOWER(location) = LOWER(?) AND LOWER(role_group) = LOWER(?)
        """,
        (active_tenant_id(), location, role_group),
    ).fetchone()[0]


def schedule_location_name_exists(
    connection: DatabaseConnection,
    location: str,
    *,
    exclude_id: str | None = None,
) -> bool:
    query = "SELECT 1 FROM schedule_locations WHERE tenant_id = ? AND LOWER(location) = LOWER(?)"
    parameters: tuple[str, ...] = (active_tenant_id(), location)
    if exclude_id is not None:
        query += " AND id != ?"
        parameters = (*parameters, exclude_id)
    return connection.execute(query + " LIMIT 1", parameters).fetchone() is not None


def schedule_location_name_count(
    connection: DatabaseConnection, location: str
) -> int:
    return connection.execute(
        "SELECT COUNT(*) FROM schedule_locations WHERE tenant_id = ? AND LOWER(location) = LOWER(?)",
        (active_tenant_id(), location),
    ).fetchone()[0]


def schedule_location_conflict(error: BaseException):
    return jsonify(error="Schedule name or BambooHR schedule ID is already in use."), 409


@app.post("/api/schedule-locations")
def create_schedule_location():
    payload = request.get_json(silent=True)
    if not valid_schedule_location(payload):
        return jsonify(
            error="Schedule name, BambooHR schedule ID, app location, manager name, and valid manager email are required."
        ), 400
    location_id = os.urandom(16).hex()
    with closing(database_connect()) as connection, connection:
        location = payload["location"].strip()
        if not schedule_location_name_exists(connection, location):
            limit_response = membership_quota_response(connection, "locations")
            if limit_response:
                return limit_response
        role_group = str(payload.get("roleGroup", "")).strip()
        if not schedule_team_exists(
            connection, location, role_group
        ):
            limit_response = membership_quota_response(connection, "teams")
            if limit_response:
                return limit_response
        try:
            connection.execute(
                """
                INSERT INTO schedule_locations
                    (id, name, bamboo_schedule_id, location, role_group,
                     manager_name, manager_email)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    location_id,
                    payload["name"].strip(),
                    payload["bambooScheduleId"].strip(),
                    payload["location"].strip(),
                    role_group,
                    payload["managerName"].strip(),
                    payload["managerEmail"].strip(),
                ),
            )
        except database_integrity_errors() as error:
            return schedule_location_conflict(error)
    return jsonify(id=location_id), 201


@app.put("/api/schedule-locations/<path:location_id>")
def update_schedule_location(location_id: str):
    payload = request.get_json(silent=True)
    if not valid_schedule_location(payload):
        return jsonify(
            error="Schedule name, BambooHR schedule ID, app location, manager name, and valid manager email are required."
        ), 400
    with closing(database_connect()) as connection, connection:
        existing_location = connection.execute(
            "SELECT location, role_group FROM schedule_locations WHERE id = ?",
            (location_id,),
        ).fetchone()
        if not existing_location:
            return jsonify(error="Schedule location was not found."), 404
        new_location = payload["location"].strip()
        new_role_group = str(payload.get("roleGroup", "")).strip()
        if not schedule_location_name_exists(
            connection, new_location, exclude_id=location_id
        ):
            if schedule_location_name_count(connection, existing_location[0]) > 1:
                limit_response = membership_quota_response(connection, "locations")
                if limit_response:
                    return limit_response
        if not schedule_team_exists(
            connection,
            new_location,
            new_role_group,
            exclude_id=location_id,
        ):
            old_team_count = schedule_team_count(
                connection, existing_location[0], existing_location[1]
            )
            if old_team_count > 1:
                limit_response = membership_quota_response(connection, "teams")
                if limit_response:
                    return limit_response
        assigned_roles = connection.execute(
            "SELECT role FROM employees WHERE schedule_location_id = ?",
            (location_id,),
        ).fetchall()
        if any(
            not role_matches_schedule_group(role[0], str(payload.get("roleGroup", "")))
            for role in assigned_roles
        ):
            return jsonify(error="The schedule role group must match every assigned employee role."), 400
        try:
            cursor = connection.execute(
                """
                UPDATE schedule_locations
                SET name = ?, bamboo_schedule_id = ?, location = ?, role_group = ?,
                    manager_name = ?, manager_email = ?
                WHERE id = ?
                """,
                (
                    payload["name"].strip(),
                    payload["bambooScheduleId"].strip(),
                    payload["location"].strip(),
                    str(payload.get("roleGroup", "")).strip(),
                    payload["managerName"].strip(),
                    payload["managerEmail"].strip(),
                    location_id,
                ),
            )
        except database_integrity_errors() as error:
            return schedule_location_conflict(error)
        if cursor.rowcount == 0:
            return jsonify(error="Schedule location was not found."), 404
        connection.execute(
            "UPDATE employees SET location = ? WHERE schedule_location_id = ?",
            (payload["location"].strip(), location_id),
        )
    return jsonify(id=location_id)


@app.delete("/api/schedule-locations/<path:location_id>")
def delete_schedule_location(location_id: str):
    with closing(database_connect()) as connection, connection:
        assigned = connection.execute(
            "SELECT COUNT(*) FROM employees WHERE schedule_location_id = ?",
            (location_id,),
        ).fetchone()[0]
        if assigned:
            return jsonify(error="Reassign employees before deleting this schedule location."), 409
        cursor = connection.execute(
            "DELETE FROM schedule_locations WHERE id = ?", (location_id,)
        )
        if cursor.rowcount == 0:
            return jsonify(error="Schedule location was not found."), 404
    return jsonify(id=location_id)


@app.get("/api/app-config")
def get_application_config():
    return jsonify(current_app_config())


@app.put("/api/app-config")
def update_application_config():
    config = valid_app_config(request.get_json(silent=True))
    if config is None:
        return jsonify(error="Provide valid business, team, logo, color, and BambooHR tenant settings."), 400
    try:
        save_app_config(config)
    except BambooDomainConflict:
        return jsonify(error="That BambooHR domain is already registered to another business."), 409
    except database_integrity_errors():
        with closing(database_connect()) as connection:
            claimed = connection.execute(
                """
                SELECT 1 FROM tenants
                WHERE LOWER(bamboohr_subdomain) = ? AND tenant_id != ?
                """,
                (config["tenantId"].lower(), active_tenant_id()),
            ).fetchone()
        if claimed:
            return jsonify(error="That BambooHR domain is already registered to another business."), 409
        raise
    return jsonify(current_app_config())


@app.put("/api/schedule-locations/<path:location_id>/employees")
def assign_schedule_location_employees(location_id: str):
    payload = request.get_json(silent=True)
    employee_ids = payload.get("employeeIds") if isinstance(payload, dict) else None
    if not isinstance(employee_ids, list) or any(
        not isinstance(employee_id, str) for employee_id in employee_ids
    ):
        return jsonify(error="A list of employee IDs is required."), 400
    if len(employee_ids) != len(set(employee_ids)):
        return jsonify(error="An employee can only be assigned once."), 400
    with closing(database_connect()) as connection, connection:
        location = connection.execute(
            "SELECT location, role_group FROM schedule_locations WHERE id = ?", (location_id,)
        ).fetchone()
        if not location:
            return jsonify(error="Schedule location was not found."), 404
        if employee_ids:
            placeholders = ",".join("?" for _ in employee_ids)
            employees = connection.execute(
                f"""
                SELECT employee_id, active, bamboohr_id, role
                FROM employees WHERE employee_id IN ({placeholders})
                """,
                employee_ids,
            ).fetchall()
            if len(employees) != len(employee_ids):
                return jsonify(error="One or more selected employees were not found."), 404
            if any(not active or not bamboo_id or not role for _, active, bamboo_id, role in employees):
                return jsonify(error="Only active employees with BambooHR IDs and roles can be assigned."), 400
            if any(not role_matches_schedule_group(role, location[1]) for _, _, _, role in employees):
                return jsonify(error="Selected employee roles do not match this schedule location's role group."), 400
        connection.execute(
            """
            UPDATE employees SET schedule_location_id = NULL
            WHERE schedule_location_id = ? AND active = 1
            """,
            (location_id,),
        )
        connection.executemany(
            """
            UPDATE employees
            SET schedule_location_id = ?, location = ?
            WHERE employee_id = ?
            """,
            [(location_id, location[0], employee_id) for employee_id in employee_ids],
        )
    return jsonify(id=location_id, employeeIds=employee_ids)


def accepted_schedule_selections(
    connection: DatabaseConnection, selections: object
) -> list[dict]:
    if not isinstance(selections, list) or not selections:
        raise ValueError("Select at least one accepted shift.")
    if len(selections) > 500:
        raise ValueError("Select no more than 500 shifts per publish request.")
    lookup = {}
    for selection in selections:
        if not isinstance(selection, dict):
            raise ValueError("Each selected shift must specify a schedule, day, and start.")
        run_id = selection.get("runId")
        day = selection.get("day")
        start = selection.get("start")
        if (
            not isinstance(run_id, str)
            or not isinstance(day, int)
            or isinstance(day, bool)
            or not 0 <= day < 7
            or not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not 0 <= start < 24
        ):
            raise ValueError("A selected shift contains an invalid schedule, day, or start.")
        key = (run_id, day, float(start))
        if key in lookup:
            raise ValueError("The same accepted shift was selected more than once.")
        lookup[key] = None

    run_ids = list({run_id for run_id, _, _ in lookup})
    placeholders = ",".join("?" for _ in run_ids)
    rows = connection.execute(
        f"SELECT run_id, payload FROM accepted_schedules WHERE run_id IN ({placeholders})",
        run_ids,
    ).fetchall()
    schedules = {run_id: json.loads(payload) for run_id, payload in rows}
    for run_id, day, start in lookup:
        schedule = schedules.get(run_id)
        if not schedule:
            raise ValueError(f"Accepted schedule {run_id} was not found.")
        if start not in [float(value) for value in schedule.get("shiftStarts", [])]:
            raise ValueError(f"Shift start {start} is not configured in accepted schedule {run_id}.")
        lookup[(run_id, day, start)] = schedule
    return [
        {"runId": run_id, "day": day, "start": start, "schedule": schedule}
        for (run_id, day, start), schedule in lookup.items()
    ]


def bamboo_payloads(
    connection: DatabaseConnection, selections: list[dict]
) -> list[dict]:
    payloads = {}
    employee_rows = connection.execute(
        """
        SELECT employee_id, bamboohr_id, active, schedule_location_id, location, role,
               source_type
        FROM employees
        WHERE tenant_id = ?
        """,
        (active_tenant_id(),),
    ).fetchall()
    employees = {row[0]: row for row in employee_rows}
    schedule_rows = connection.execute(
        "SELECT id, bamboo_schedule_id, location, name, role_group FROM schedule_locations WHERE tenant_id=?",
        (active_tenant_id(),),
    ).fetchall()
    locations = {row[0]: row for row in schedule_rows}

    for selection in selections:
        schedule = selection["schedule"]
        day, start = selection["day"], selection["start"]
        start_time = datetime.fromisoformat(schedule["start"]).date() + timedelta(days=day)
        minute_of_day = round(start * 60)
        local_start = datetime.combine(
            start_time,
            time(minute_of_day // 60, minute_of_day % 60),
            tzinfo=ZoneInfo("America/Jamaica"),
        )
        span = schedule.get("controls", {}).get("span")
        if not isinstance(span, (int, float)) or not 0 < span <= 24:
            raise ValueError(f"Accepted schedule {schedule['id']} has no valid shift duration.")
        local_end = local_start + timedelta(hours=span)

        for assigned in schedule.get("employees", []):
            if not isinstance(assigned, dict) or day >= len(assigned.get("slots", [])):
                continue
            if assigned["slots"][day] != start:
                continue
            employee = employees.get(str(assigned.get("id", "")))
            if employee and employee[6] == "manual":
                continue
            if not employee or not employee[2] or not employee[1]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned.get('id', ''))} is inactive "
                    "or has no BambooHR ID."
                )
            if "active" in assigned and not assigned["active"]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} was inactive when "
                    "the schedule was accepted."
                )
            if "bamboohrId" in assigned and str(assigned["bamboohrId"] or "") != str(employee[1]):
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has a different "
                    "BambooHR ID than when the schedule was accepted. Accept the updated schedule again."
                )
            if "scheduleLocationId" in assigned and assigned["scheduleLocationId"] != employee[3]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has a different "
                    "schedule location than when the schedule was accepted. Accept the updated schedule again."
                )
            if "directoryLocation" in assigned and assigned["directoryLocation"] != employee[4]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has a different "
                    "app location than when the schedule was accepted. Accept the updated schedule again."
                )
            if "directoryRole" in assigned and assigned["directoryRole"] != employee[5]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has a different "
                    "role than when the schedule was accepted. Accept the updated schedule again."
                )
            schedule_location_id = assigned.get("scheduleLocationId") or employee[3]
            location = locations.get(schedule_location_id)
            if not location:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} has no valid BambooHR schedule location."
                )
            if "bambooScheduleId" in assigned and assigned["bambooScheduleId"] != location[1]:
                raise ValueError(
                    f"The BambooHR schedule mapping for {assigned.get('name', assigned['id'])} "
                    "changed after acceptance. Accept the updated schedule again."
                )
            if location[2] != schedule.get("location") or employee[4] != location[2]:
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} is not mapped to "
                    f"the accepted schedule's {schedule.get('location')} location."
                )
            if not role_matches_schedule_group(str(assigned.get("role", employee[5])), location[4]):
                raise ValueError(
                    f"Employee {assigned.get('name', assigned['id'])} does not match "
                    f"the {location[3]} schedule role group."
                )
            group_key = (location[0], local_start.isoformat())
            payload = payloads.setdefault(
                group_key,
                {
                    "scheduleId": location[1],
                    "status": "published",
                    "color": "00FFAA",
                    "employeeIds": [],
                    "timezone": "America/Jamaica",
                    "start": local_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "end": local_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "scheduleName": location[3],
                    "employeeNames": [],
                },
            )
            bamboohr_id = int(employee[1]) if employee[1].isdigit() else employee[1]
            if bamboohr_id not in payload["employeeIds"]:
                payload["employeeIds"].append(bamboohr_id)
                payload["employeeNames"].append(assigned.get("name", assigned["id"]))

    if not payloads:
        raise ValueError(
            "The selected shifts have no BambooHR employees to publish; manually added employees are excluded."
        )
    return sorted(payloads.values(), key=lambda item: (item["start"], item["scheduleName"]))


def bamboo_preview_response(payloads: list[dict]) -> list[dict]:
    return [
        {
            "scheduleName": payload["scheduleName"],
            "scheduleId": payload["scheduleId"],
            "start": payload["start"],
            "end": payload["end"],
            "employeeIds": payload["employeeIds"],
            "employeeNames": payload["employeeNames"],
            "timezone": payload["timezone"],
        }
        for payload in payloads
    ]


@app.get("/api/bamboohr/status")
def bamboohr_status():
    return jsonify(configured=bool(bamboohr_api_key()))


ATTENDANCE_TIMEZONE = ZoneInfo("America/Jamaica")
DEFAULT_ATTENDANCE_SETTINGS = {
    "latenessToleranceMinutes": 15,
    "scorePeriodDays": 30,
}
ATTENDANCE_BAMBOOHR_SOURCE_UNAVAILABLE = (
    "BambooHR shift reconciliation is unavailable because the configured API key "
    "or the mapped BambooHR schedules could not be verified."
)


class AttendanceIntegrationError(Exception):
    pass


def attendance_settings(connection: DatabaseConnection) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT setting_key, setting_value
        FROM application_settings
        WHERE tenant_id = ? AND setting_key IN (
            'attendance_lateness_tolerance_minutes',
            'attendance_score_period_days'
        )
        """,
        (active_tenant_id(),),
    ).fetchall()
    values = {row[0]: row[1] for row in rows}
    try:
        tolerance = int(
            values.get(
                "attendance_lateness_tolerance_minutes",
                DEFAULT_ATTENDANCE_SETTINGS["latenessToleranceMinutes"],
            )
        )
        period = int(
            values.get(
                "attendance_score_period_days",
                DEFAULT_ATTENDANCE_SETTINGS["scorePeriodDays"],
            )
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("Stored attendance settings are invalid.") from error
    if not 0 <= tolerance <= 120 or not 30 <= period <= 45:
        raise RuntimeError("Stored attendance settings are outside allowed limits.")
    return {"latenessToleranceMinutes": tolerance, "scorePeriodDays": period}


def bamboohr_json(
    api_key: str, path: str, params: dict[str, str], label: str
) -> object:
    authorization = base64.b64encode(f"{api_key}:x".encode("utf-8")).decode("ascii")
    outbound = Request(
        f"{bamboohr_endpoint(path)}?{urlencode(params)}",
        headers={"Accept": "application/json", "Authorization": f"Basic {authorization}"},
        method="GET",
    )
    try:
        with urlopen(outbound, timeout=20) as response:
            raw_data = response.read(10_000_001)
        if len(raw_data) > 10_000_000:
            raise AttendanceIntegrationError(
                f"BambooHR {label} response exceeds the allowed size."
            )
        data = json.loads(raw_data)
    except HTTPError as error:
        if error.code == 403:
            detail = "the API key lacks permission"
        elif error.code == 401:
            detail = "the API key was rejected"
        else:
            detail = f"request failed with HTTP {error.code}"
        raise AttendanceIntegrationError(
            f"BambooHR {label} {detail}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise AttendanceIntegrationError(
            f"The app server could not reach BambooHR for {label}."
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise AttendanceIntegrationError(
            f"BambooHR returned invalid {label} data."
        ) from error
    if not isinstance(data, list):
        raise AttendanceIntegrationError(
            f"BambooHR returned an invalid {label} response."
        )
    return data


def bamboo_identifier(value: object, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise AttendanceIntegrationError(f"BambooHR returned an invalid {label}.")
    identifier = str(value).strip()
    if not identifier or len(identifier) > 80:
        raise AttendanceIntegrationError(f"BambooHR returned an invalid {label}.")
    return identifier


def parse_bamboohr_clock_entries(data: object) -> list[dict[str, object]]:
    if not isinstance(data, list):
        raise AttendanceIntegrationError("BambooHR returned an invalid timesheet response.")
    entries = []
    for item in data:
        if not isinstance(item, dict):
            raise AttendanceIntegrationError(
                "BambooHR returned an invalid timesheet entry."
            )
        if item.get("type") != "clock":
            continue
        entry_id = bamboo_identifier(item.get("id"), "timesheet entry ID")
        bamboohr_id = bamboo_identifier(item.get("employeeId"), "timesheet employee ID")
        entry_date = item.get("date")
        start_text = item.get("start")
        end_text = item.get("end")
        timezone_name = item.get("timezone")
        if not isinstance(entry_date, str) or not isinstance(start_text, str):
            raise AttendanceIntegrationError(
                "BambooHR returned a clock entry without a date or start time."
            )
        try:
            parsed_date = date.fromisoformat(entry_date)
            started_at = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
            ended_at = (
                datetime.fromisoformat(end_text.replace("Z", "+00:00"))
                if isinstance(end_text, str) and end_text
                else None
            )
            if (
                parsed_date.isoformat() != entry_date
                or started_at.tzinfo is None
                or (ended_at is not None and ended_at.tzinfo is None)
                or (ended_at is not None and ended_at < started_at)
                or not isinstance(timezone_name, str)
            ):
                raise ValueError
            ZoneInfo(timezone_name)
        except (ValueError, TypeError, ZoneInfoNotFoundError) as error:
            raise AttendanceIntegrationError(
                "BambooHR returned a clock entry with an invalid date, time, or time zone."
            ) from error
        approved = item.get("approved", False)
        if not isinstance(approved, bool):
            raise AttendanceIntegrationError(
                "BambooHR returned an invalid clock approval flag."
            )
        entries.append(
            {
                "id": entry_id,
                "bamboohrId": bamboohr_id,
                "date": entry_date,
                "start": started_at.isoformat(),
                "end": ended_at.isoformat() if ended_at else None,
                "timezone": timezone_name,
                "approved": approved,
            }
        )
    return entries


def parse_bamboohr_time_off(data: object) -> list[dict[str, str]]:
    if not isinstance(data, list):
        raise AttendanceIntegrationError("BambooHR returned an invalid time-off response.")
    entries = []
    for item in data:
        if not isinstance(item, dict) or item.get("type") != "timeOff":
            continue
        if item.get("status") and str(item["status"]).casefold() != "approved":
            continue
        try:
            bamboohr_id = bamboo_identifier(item.get("employeeId"), "time-off employee ID")
            start_text, end_text = item.get("start"), item.get("end")
            if not isinstance(start_text, str) or not isinstance(end_text, str):
                raise ValueError
            start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
            if start.isoformat() != start_text or end.isoformat() != end_text or end < start:
                raise ValueError
        except (AttendanceIntegrationError, ValueError, TypeError) as error:
            raise AttendanceIntegrationError(
                "BambooHR returned an approved time-off record with invalid employee or date data."
            ) from error
        entries.append(
            {"bamboohrId": bamboohr_id, "start": start_text, "end": end_text}
        )
    return entries


def schedule_shift_datetime(shift_date: date, start: object) -> datetime:
    if isinstance(start, bool) or not isinstance(start, (int, float)):
        raise ValueError("Accepted schedule contains an invalid shift start.")
    minutes = round(float(start) * 60)
    if not 0 <= minutes < 24 * 60:
        raise ValueError("Accepted schedule contains an invalid shift start.")
    return datetime.combine(
        shift_date,
        time(minute=minutes % 60, hour=minutes // 60),
        tzinfo=ATTENDANCE_TIMEZONE,
    )


ATTENDANCE_MIN_WORKED_MINUTES = 60
ATTENDANCE_EARLY_OVERTIME_GRACE_MINUTES = 60
ATTENDANCE_ABSENT_AFTER_HOURS = 4


def evaluate_shift_timesheet(
    entries: list[dict[str, object]],
    shift_start: datetime,
    shift_end: datetime,
    now: datetime,
) -> dict[str, object]:
    """Measure how much of a scheduled shift the clock entries actually cover."""
    worked = 0.0
    first_entry = None
    first_start = None
    last_end = None
    open_entry = False
    for entry in entries:
        started = datetime.fromisoformat(str(entry["start"]))
        ended = datetime.fromisoformat(str(entry["end"])) if entry["end"] else None
        overlap = (
            min(ended or max(now, started), shift_end) - max(started, shift_start)
        ).total_seconds() / 60
        if overlap <= 0:
            continue
        worked += overlap
        if first_start is None or started < first_start:
            first_entry, first_start = entry, started
        if ended is None:
            open_entry = True
        elif last_end is None or ended > last_end:
            last_end = ended
    shift_minutes = (shift_end - shift_start).total_seconds() / 60
    required = min(ATTENDANCE_MIN_WORKED_MINUTES, shift_minutes)
    qualifies = first_entry is not None and worked + 1e-6 >= required
    early = overtime = 0
    if qualifies:
        if open_entry:
            if now > shift_end:
                overtime = int((now - shift_end).total_seconds() // 60)
        elif last_end is not None:
            if last_end > shift_end:
                overtime = int((last_end - shift_end).total_seconds() // 60)
            elif now >= shift_end or now >= last_end + timedelta(
                minutes=ATTENDANCE_MIN_WORKED_MINUTES
            ):
                early = int((shift_end - last_end).total_seconds() // 60)
    grace = ATTENDANCE_EARLY_OVERTIME_GRACE_MINUTES
    worked_minutes = int(round(worked))
    return {
        "first": first_entry,
        "workedMinutes": worked_minutes,
        "requiredMinutes": int(required),
        "qualifies": qualifies,
        "inProgress": (
            first_entry is not None and not qualifies and open_entry and now < shift_end
        ),
        "clockOutAt": (
            last_end.isoformat() if last_end is not None and not open_entry else None
        ),
        "earlyMinutes": early if early > grace else 0,
        "overtimeMinutes": overtime if overtime > grace else 0,
        "partial": qualifies and worked_minutes + grace < shift_minutes,
        "shiftMinutes": int(shift_minutes),
    }


def record_attendance_status(
    connection: DatabaseConnection,
    *,
    run_id: str,
    employee_id: str,
    shift_date: str,
    shift_start: float,
    status: str,
    source: str,
    reason: str,
    employee_name: str,
    location: str,
    role: str,
    clock_in_at: str | None,
    clock_in_timezone: str,
    shift_end_at: str | None = None,
    existing: dict[tuple[str, str, str], tuple[str, str, str]],
    preserve_manual: bool = True,
    actor_id: str | None = None,
    actor_email: str | None = None,
    timesheet: dict[str, object] | None = None,
) -> bool:
    tenant_id = active_tenant_id()
    key = (run_id, employee_id, shift_date)
    previous = existing.get(key)
    if preserve_manual and previous and previous[1] == "manual":
        status, source, reason = previous
    prior_status = previous[0] if previous else None
    prior_source = previous[1] if previous else None
    connection.execute(
        """
        INSERT INTO attendance_shift_records
            (tenant_id, schedule_run_id, employee_id, shift_date, shift_start,
             status, source, reason, employee_name, location, role, clock_in_at,
               clock_in_timezone, shift_end_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (tenant_id, schedule_run_id, employee_id, shift_date)
        DO UPDATE SET shift_start = excluded.shift_start, status = excluded.status,
            source = excluded.source, reason = excluded.reason,
            employee_name = excluded.employee_name, location = excluded.location,
            role = excluded.role, clock_in_at = excluded.clock_in_at,
            clock_in_timezone = excluded.clock_in_timezone,
            shift_end_at = COALESCE(excluded.shift_end_at, attendance_shift_records.shift_end_at),
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            tenant_id, run_id, employee_id, shift_date, shift_start, status, source,
            reason, employee_name, location, role, clock_in_at, clock_in_timezone,
            shift_end_at,
        ),
    )
    existing[key] = (status, source, reason)
    if timesheet is not None:
        connection.execute(
            """
            UPDATE attendance_shift_records
            SET clock_out_at = ?, worked_minutes = ?, early_minutes = ?,
                overtime_minutes = ?
            WHERE tenant_id = ? AND schedule_run_id = ? AND employee_id = ?
                AND shift_date = ?
            """,
            (
                timesheet["clockOutAt"], timesheet["workedMinutes"],
                timesheet["earlyMinutes"], timesheet["overtimeMinutes"],
                tenant_id, run_id, employee_id, shift_date,
            ),
        )
        if timesheet["earlyMinutes"]:
            connection.execute(
                """
                INSERT INTO attendance_notifications
                    (id, tenant_id, dedupe_key, kind, employee_id, employee_name,
                     location, shift_date, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, dedupe_key) DO NOTHING
                """,
                (
                    secrets.token_urlsafe(18), tenant_id,
                    f"{run_id}|{employee_id}|{shift_date}|early_leave", "early_leave",
                    employee_id, employee_name, location, shift_date,
                    f"{employee_name or employee_id} left {timesheet['earlyMinutes']} "
                    f"minutes before the end of the {shift_date} shift"
                    f"{' at ' + location if location else ''}.",
                ),
            )
    if status in {"scheduled"} or (prior_status == status and prior_source == source):
        return False
    connection.execute(
        """
        INSERT INTO attendance_shift_audit_events
            (id, tenant_id, schedule_run_id, employee_id, shift_date,
             previous_status, status, source, reason, actor_id, actor_email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            secrets.token_urlsafe(18), tenant_id, run_id, employee_id, shift_date,
            prior_status, status, source, reason,
            actor_id, actor_email,
        ),
    )
    if status in {"late", "absent"} and prior_status != status:
        label = "absent" if status == "absent" else "late"
        connection.execute(
            """
            INSERT INTO attendance_notifications
                (id, tenant_id, dedupe_key, kind, employee_id, employee_name,
                 location, shift_date, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, dedupe_key) DO NOTHING
            """,
            (
                secrets.token_urlsafe(18), tenant_id,
                f"{run_id}|{employee_id}|{shift_date}|{status}", status,
                employee_id, employee_name, location, shift_date,
                f"{employee_name or employee_id} is {label} for the {shift_date} shift"
                f"{' at ' + location if location else ''}.",
            ),
        )
    return prior_status != status


def attendance_payload(
    connection: DatabaseConnection,
    now: datetime | None = None,
    selected_date: date | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict[str, object]:
    now = now or datetime.now(ATTENDANCE_TIMEZONE)
    today = now.date()
    report_start = period_start or selected_date or today
    report_end = period_end or selected_date or today
    as_of = (
        now
        if report_end == today
        else datetime.combine(report_end, time.max, tzinfo=ATTENDANCE_TIMEZONE)
    )
    tenant_id = active_tenant_id()
    source = attendance_shift_source(connection)
    settings = attendance_settings(connection)
    source_clause = (
        "schedule_run_id LIKE 'bamboohr:%'"
        if source == "bamboohr"
        else "schedule_run_id NOT LIKE 'bamboohr:%' AND employee_id IN "
             "(SELECT employee_id FROM employees WHERE tenant_id = ? AND active = 1)"
    )
    row_parameters = (tenant_id, report_start.isoformat(), report_end.isoformat())
    if source == "app":
        row_parameters += (tenant_id,)
    rows = connection.execute(
        f"""
        SELECT schedule_run_id, employee_id, shift_date, shift_start, status,
               source, reason, employee_name, location, role, clock_in_at,
               clock_in_timezone, clock_out_at, worked_minutes, early_minutes,
             overtime_minutes, shift_end_at
        FROM attendance_shift_records
        WHERE tenant_id = ? AND shift_date >= ? AND shift_date <= ? AND {source_clause}
        ORDER BY shift_date, location, role, shift_start, employee_name
        """,
        row_parameters,
    ).fetchall()
    employee_clock_ids = {
        str(row[0]): (str(row[1] or ""), bool(row[2]))
        for row in connection.execute(
            "SELECT employee_id,bamboohr_id,active FROM employees WHERE tenant_id=?",
            (tenant_id,),
        )
    }
    open_clock_entries: dict[str, list[dict[str, object]]] = {}
    for bamboohr_id, entry_id, started_at, timezone_name in connection.execute(
        """SELECT bamboohr_id,entry_id,started_at,timezone FROM attendance_time_entries
           WHERE tenant_id=? AND ended_at IS NULL""",
        (tenant_id,),
    ):
        open_clock_entries.setdefault(str(bamboohr_id), []).append(
            {"id": str(entry_id), "start": str(started_at), "timezone": str(timezone_name)}
        )
    if source == "bamboohr":
        for employee_id in {str(row[1]) for row in rows if str(row[1]).startswith("bamboohr:")}:
            employee_clock_ids[employee_id] = (employee_id.removeprefix("bamboohr:"), True)
    unresolved_clock_actions = {
        str(row[0]): str(row[1])
        for row in connection.execute(
            """SELECT bamboohr_id,action FROM attendance_clock_action_audit_events
               WHERE tenant_id=? AND outcome IN ('pending','unknown')""",
            (tenant_id,),
        )
    }
    clock_actions_enabled = bool(bamboohr_api_key())
    current_shifts = []
    expected = clocked_in = late = absent = approved_leave = 0
    for row in rows:
        shift_day = date.fromisoformat(row[2])
        start = schedule_shift_datetime(shift_day, row[3])
        if start > as_of:
            continue
        shift_end_at = row[16]
        try:
            shift_end = datetime.fromisoformat(shift_end_at) if shift_end_at else None
            if shift_end and (shift_end.tzinfo is None or shift_end <= start):
                shift_end = None
        except (TypeError, ValueError):
            shift_end = None
        app_employee_mapping = employee_clock_ids.get(str(row[1]))
        bamboohr_id, employee_active = app_employee_mapping or ("", False)
        employee_open_entries = open_clock_entries.get(bamboohr_id, [])
        unresolved_action = unresolved_clock_actions.get(bamboohr_id)
        if shift_end is not None:
            matching_open_entries = [
                entry for entry in employee_open_entries
                if datetime.fromisoformat(str(entry["start"])) < shift_end
                and datetime.fromisoformat(str(entry["start"])) <= now
                and start < now
                and (
                    str(entry["start"]) == str(row[10])
                    if row[10]
                    else datetime.fromisoformat(str(entry["start"])) >= start
                )
            ]
        else:
            matching_open_entries = []
        clocked_in_for_shift = len(matching_open_entries) == 1 and len(employee_open_entries) == 1
        eligible_clock_action = (
            clock_actions_enabled
            and app_employee_mapping is not None
            and employee_active
            and re.fullmatch(r"[0-9]+", bamboohr_id) is not None
            and shift_end is not None
            and row[4] not in {"approved_leave", "sick", "vacation"}
            and unresolved_action is None
        )
        item = {
            "runId": row[0],
            "employeeId": row[1],
            "date": row[2],
            "shiftStart": start.isoformat(),
            "status": row[4],
            "source": row[5],
            "reason": row[6],
            "name": row[7],
            "location": row[8],
            "role": row[9],
            "clockIn": row[10] or (matching_open_entries[0]["start"] if matching_open_entries else None),
            "clockInTimezone": row[11] or (matching_open_entries[0]["timezone"] if matching_open_entries else ""),
            "clockOut": row[12],
            "shiftEndAt": shift_end.isoformat() if shift_end else None,
            "workedMinutes": row[13],
            "earlyMinutes": row[14] or 0,
            "overtimeMinutes": row[15] or 0,
            "isClockedInForShift": clocked_in_for_shift,
            "canClockIn": bool(eligible_clock_action and not employee_open_entries
                                and start <= now < shift_end),
            "canClockOut": bool(eligible_clock_action and clocked_in_for_shift),
            "canClockOutAtShiftEnd": bool(eligible_clock_action and clocked_in_for_shift
                                           and now >= shift_end),
            "clockActionUnavailableReason": (
                "A previous BambooHR clock action is unresolved. Reconcile it before continuing."
                if unresolved_action else ""
            ),
        }
        current_shifts.append(item)
        if row[4] in {"approved_leave", "sick", "vacation"}:
            approved_leave += 1
            continue
        expected += 1
        if row[4] in {"attended", "late"}:
            clocked_in += 1
        if row[4] == "late":
            late += 1
        elif row[4] == "absent":
            absent += 1

    score_parameters = (tenant_id, report_start.isoformat(), report_end.isoformat())
    if source == "app":
        score_parameters += (tenant_id,)
    score_rows = connection.execute(
        f"""
        SELECT employee_id, shift_date, shift_start, status
        FROM attendance_shift_records
        WHERE tenant_id = ? AND shift_date >= ? AND shift_date <= ? AND {source_clause}
        """,
        score_parameters,
    ).fetchall()
    totals: dict[str, list[int]] = {}
    for employee_id, shift_text, shift_start, status in score_rows:
        shift_day = date.fromisoformat(shift_text)
        if schedule_shift_datetime(shift_day, shift_start) > as_of:
            continue
        if status in {"approved_leave", "sick", "vacation"}:
            continue
        counts = totals.setdefault(employee_id, [0, 0])
        counts[1] += 1
        if status in {"attended", "late"}:
            counts[0] += 1
    overrides = {
        row[0]: row[1]
        for row in connection.execute(
            """
            SELECT employee_id, score FROM attendance_score_overrides
            WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
    }
    if source == "bamboohr":
        employee_profiles = {}
        for row in rows:
            employee_profiles[str(row[1])] = (row[7], row[8], row[9])
        employees = [
            (employee_id, name, location, role, True)
            for employee_id, (name, location, role) in employee_profiles.items()
        ]
    else:
        employees = connection.execute(
            """
            SELECT employee_id, name, location, role, active
            FROM employees WHERE tenant_id = ? AND active = 1
            ORDER BY name
            """,
            (tenant_id,),
        ).fetchall()
    scores = []
    for employee_id, name, location, role, active in employees:
        attended_count, scheduled_count = totals.get(employee_id, (0, 0))
        computed = (
            round(attended_count * 100 / scheduled_count, 2)
            if scheduled_count
            else None
        )
        scores.append(
            {
                "employeeId": employee_id,
                "name": name,
                "location": location,
                "role": role,
                "active": bool(active),
                "attended": attended_count,
                "scheduled": scheduled_count,
                "computedScore": computed,
                "score": overrides.get(employee_id, computed) if source == "app" else computed,
                "manualOverride": source == "app" and employee_id in overrides,
            }
        )
    percentage = round(clocked_in * 100 / expected, 2) if expected else None
    last_sync = connection.execute(
        """
        SELECT setting_value FROM application_settings
        WHERE tenant_id = ? AND setting_key = 'attendance_last_sync'
        """,
        (tenant_id,),
    ).fetchone()
    return {
        "date": report_start.isoformat() if report_start == report_end else None,
        "periodStart": report_start.isoformat(),
        "periodEnd": report_end.isoformat(),
        "currentDate": today.isoformat(),
        "reportedAt": now.isoformat(),
        "lastSyncedAt": last_sync[0] if last_sync else None,
        "summary": {
            "expected": expected,
            "clockedIn": clocked_in,
            "attendancePercent": percentage,
            "late": late,
            "absent": absent,
            "approvedLeave": approved_leave,
        },
        "shifts": current_shifts,
        "scores": scores,
        "settings": settings,
        "shiftSource": {
            "selected": source,
            "bamboohrAvailable": None,
            "unresolvedDiscrepancies": None,
        },
    }


def attendance_shift_source(connection: DatabaseConnection) -> str:
    row = connection.execute(
        """
        SELECT setting_value FROM application_settings
        WHERE tenant_id = ? AND setting_key = 'attendance_shift_source'
        """,
        (active_tenant_id(),),
    ).fetchone()
    if not row:
        return "app"
    if row[0] != "app":
        if row[0] == "bamboohr":
            return row[0]
        raise RuntimeError("Stored attendance shift source is invalid.")
    return row[0]


def parse_bamboohr_scheduled_shifts(
    payload: object,
    employees_by_bamboo_id: dict[str, dict[str, object]],
    locations_by_schedule_id: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise AttendanceIntegrationError("BambooHR returned an invalid scheduled-shifts response.")
    parsed = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            raise AttendanceIntegrationError("BambooHR returned an invalid scheduled shift.")
        status = item.get("status")
        if status not in {"planned", "published"} or item.get("deletedAt"):
            continue
        try:
            shift_id = bamboo_identifier(item.get("id"), "scheduled shift ID")
            schedule_id = bamboo_identifier(item.get("scheduleId"), "schedule ID")
            start_text, end_text = item.get("start"), item.get("end")
            timezone_name = item.get("timezone")
            employee_values = item.get("employeeIds")
            if (
                not isinstance(start_text, str)
                or not isinstance(end_text, str)
                or not isinstance(timezone_name, str)
                or not isinstance(employee_values, list)
                or not employee_values
            ):
                raise ValueError
            start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
            ZoneInfo(timezone_name)
            employee_ids = [
                bamboo_identifier(value, "scheduled employee ID")
                for value in employee_values
            ]
            if start.tzinfo is None or end.tzinfo is None or end <= start:
                raise ValueError
            location = locations_by_schedule_id.get(schedule_id)
            if not location:
                raise AttendanceIntegrationError(
                    "BambooHR returned a shift for an unmapped schedule location."
                )
        except AttendanceIntegrationError:
            raise
        except (TypeError, ValueError, ZoneInfoNotFoundError) as error:
            raise AttendanceIntegrationError(
                "BambooHR returned a scheduled shift with invalid dates, time zone, or employee IDs."
            ) from error
        mapped_employees = []
        for employee_id in employee_ids:
            employee = employees_by_bamboo_id.get(employee_id)
            if employee:
                mapped_employees.append(
                    {
                        **employee,
                        "location": employee.get("location") or location["location"],
                        "role": employee.get("role") or location.get("roleGroup", ""),
                    }
                )
        parsed.append(
            {
                "id": shift_id,
                "scheduleId": schedule_id,
                "status": status,
                "color": item.get("color") if isinstance(item.get("color"), str) else "00FFAA",
                "start": start.astimezone(timezone.utc).isoformat(),
                "end": end.astimezone(timezone.utc).isoformat(),
                "timezone": timezone_name,
                "employeeIds": employee_ids,
                "employees": mapped_employees,
                "location": location["location"],
                "scheduleName": location["name"],
            }
        )
    return parsed


def fetch_bamboohr_scheduled_shifts(
    connection: DatabaseConnection,
    period_start: date,
    period_end: date,
    *,
    attendance_mode: bool = False,
) -> list[dict[str, object]]:
    api_key = bamboohr_api_key()
    if not api_key:
        raise AttendanceIntegrationError("The BambooHR API key is not configured for this business.")
    if attendance_mode:
        try:
            remote_employees = fetch_bamboohr_employees(require_employee_number=False)
        except RuntimeError as error:
            raise AttendanceIntegrationError(str(error)) from error
        app_employee_rows = connection.execute(
            """
            SELECT employee_id, bamboohr_id, role FROM employees
            WHERE tenant_id = ? AND bamboohr_id IS NOT NULL AND bamboohr_id != ''
            """,
            (active_tenant_id(),),
        ).fetchall()
        app_employees_by_bamboo_id = {
            str(row[1]): {"employeeId": str(row[0]), "role": str(row[2] or "")}
            for row in app_employee_rows
        }
        employees_by_bamboo_id = {}
        for employee in remote_employees:
            bamboohr_id = employee["bamboohrId"]
            app_employee = app_employees_by_bamboo_id.get(bamboohr_id)
            employees_by_bamboo_id[bamboohr_id] = {
                "employeeId": (
                    app_employee["employeeId"]
                    if app_employee else f"bamboohr:{bamboohr_id}"
                ),
                "bamboohrId": bamboohr_id,
                "name": employee["name"],
                "location": "",
                "role": app_employee["role"] if app_employee else "",
            }
    else:
        employee_rows = connection.execute(
            """
            SELECT employee_id, bamboohr_id, name, location, role
            FROM employees
            WHERE tenant_id = ? AND bamboohr_id IS NOT NULL AND bamboohr_id != ''
            """,
            (active_tenant_id(),),
        ).fetchall()
        employees_by_bamboo_id = {
            str(row[1]): {
                "employeeId": str(row[0]),
                "bamboohrId": str(row[1]),
                "name": str(row[2]),
                "location": str(row[3]),
                "role": str(row[4]),
            }
            for row in employee_rows
            if re.fullmatch(r"[0-9]+", str(row[1])) is not None
        }
    if not employees_by_bamboo_id:
        return []
    location_rows = connection.execute(
        """
        SELECT bamboo_schedule_id, name, location, role_group
        FROM schedule_locations WHERE tenant_id = ?
        """,
        (active_tenant_id(),),
    ).fetchall()
    locations_by_schedule_id = {
        str(row[0]): {
            "name": str(row[1]),
            "location": str(row[2]),
            "roleGroup": str(row[3] or ""),
        }
        for row in location_rows
    }
    local_start = datetime.combine(period_start, time.min, tzinfo=ATTENDANCE_TIMEZONE)
    local_end = datetime.combine(period_end, time(23, 59, 59), tzinfo=ATTENDANCE_TIMEZONE)
    start_text = local_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    end_text = local_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    authorization = base64.b64encode(f"{api_key}:x".encode("utf-8")).decode("ascii")
    all_shifts = []
    bamboo_ids = sorted(employees_by_bamboo_id)
    for offset in range(0, len(bamboo_ids), 50):
        employee_batch = bamboo_ids[offset:offset + 50]
        page = 1
        expected_total = None
        while expected_total is None or (page - 1) * 1000 < expected_total:
            params = urlencode(
                {
                    "start": start_text,
                    "end": end_text,
                    "employeeIds": ",".join(employee_batch),
                    "statuses": "planned,published",
                    "page": page,
                    "pageSize": 1000,
                }
            ).replace("%2C", ",")
            outbound = Request(
                f"{bamboohr_endpoint('scheduling/shifts')}?{params}",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Basic {authorization}",
                },
                method="GET",
            )
            try:
                with urlopen(outbound, timeout=30) as response:
                    raw_data = response.read(10_000_001)
                if len(raw_data) > 10_000_000:
                    raise AttendanceIntegrationError(
                        "BambooHR scheduled-shifts response exceeds the allowed size."
                    )
                response_payload = json.loads(raw_data)
            except HTTPError as error:
                raise AttendanceIntegrationError(
                    f"BambooHR scheduled-shifts request failed with HTTP {error.code}."
                ) from error
            except (URLError, TimeoutError, OSError) as error:
                raise AttendanceIntegrationError(
                    "The app server could not reach BambooHR for scheduled shifts."
                ) from error
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise AttendanceIntegrationError(
                    "BambooHR returned invalid scheduled-shifts data."
                ) from error
            meta = response_payload.get("meta") if isinstance(response_payload, dict) else None
            if not isinstance(meta, dict):
                raise AttendanceIntegrationError(
                    "BambooHR scheduled-shifts response omitted pagination metadata."
                )
            total_items = meta.get("totalItems")
            returned_page = meta.get("page")
            page_size = meta.get("pageSize")
            if (
                isinstance(total_items, bool)
                or not isinstance(total_items, int)
                or total_items < 0
                or returned_page != page
                or isinstance(page_size, bool)
                or not isinstance(page_size, int)
                or page_size < 1
            ):
                raise AttendanceIntegrationError(
                    "BambooHR returned invalid scheduled-shifts pagination metadata."
                )
            expected_total = total_items
            all_shifts.extend(
                parse_bamboohr_scheduled_shifts(
                    response_payload,
                    employees_by_bamboo_id,
                    locations_by_schedule_id,
                )
            )
            if page * page_size >= expected_total:
                break
            if page >= 1000:
                raise AttendanceIntegrationError(
                    "BambooHR scheduled-shifts response exceeded the page limit."
                )
            page += 1
    start_utc, end_utc = local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)
    return [
        shift for shift in all_shifts
        if start_utc <= datetime.fromisoformat(str(shift["start"])) <= end_utc
    ]


def accepted_app_shift_inventory(
    connection: DatabaseConnection, period_start: date, period_end: date
) -> list[dict[str, object]]:
    tenant_id = active_tenant_id()
    employees = {
        str(row[0]): {
            "bamboohrId": str(row[1]) if row[1] is not None else "",
            "name": str(row[2]),
            "location": str(row[3]),
            "role": str(row[4]),
            "scheduleLocationId": row[5],
        }
        for row in connection.execute(
            """
            SELECT employee_id, bamboohr_id, name, location, role, schedule_location_id
            FROM employees WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
    }
    locations = {
        str(row[0]): {"bambooScheduleId": str(row[1]), "name": str(row[2]), "location": str(row[3])}
        for row in connection.execute(
            """
            SELECT id, bamboo_schedule_id, name, location
            FROM schedule_locations WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
    }
    rows = connection.execute(
        """
        SELECT run_id, payload FROM accepted_schedules
        WHERE tenant_id = ? AND week_start >= ? AND week_start <= ?
        """,
        (tenant_id, (period_start - timedelta(days=6)).isoformat(), period_end.isoformat()),
    ).fetchall()
    shifts = []
    for run_id, encoded in rows:
        try:
            schedule = json.loads(encoded)
            week_start = date.fromisoformat(schedule["start"])
            span = float(schedule.get("controls", {}).get("span", 8))
            if not 0 < span <= 24 or not isinstance(schedule.get("employees"), list):
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise RuntimeError(f"Accepted schedule {run_id} has invalid reconciliation data.") from error
        for assigned in schedule["employees"]:
            if not isinstance(assigned, dict) or not isinstance(assigned.get("slots"), list):
                raise RuntimeError(f"Accepted schedule {run_id} has invalid employee assignments.")
            employee_id = str(assigned.get("id", ""))
            employee = employees.get(employee_id)
            if not employee:
                continue
            bamboohr_id = employee["bamboohrId"] or str(assigned.get("bamboohrId") or "")
            location_id = assigned.get("scheduleLocationId") or employee["scheduleLocationId"]
            location = locations.get(str(location_id)) if location_id else None
            if not bamboohr_id or not location:
                continue
            for day_index, slot in enumerate(assigned["slots"][:7]):
                if slot is None:
                    continue
                shift_date = week_start + timedelta(days=day_index)
                if not period_start <= shift_date <= period_end:
                    continue
                start = schedule_shift_datetime(shift_date, slot)
                end = start + timedelta(hours=span)
                shifts.append(
                    {
                        "runId": str(run_id),
                        "employeeId": employee_id,
                        "bamboohrId": bamboohr_id,
                        "name": str(assigned.get("name") or employee["name"]),
                        "location": str(assigned.get("location") or location["location"]),
                        "role": str(assigned.get("role") or employee["role"]),
                        "scheduleId": location["bambooScheduleId"],
                        "date": shift_date.isoformat(),
                        "day": day_index,
                        "startHour": float(slot),
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                    }
                )
    return shifts


def attendance_shift_discrepancies(
    connection: DatabaseConnection,
    period_start: date,
    period_end: date,
    bamboo_shifts: list[dict[str, object]],
) -> list[dict[str, object]]:
    app_shifts = accepted_app_shift_inventory(connection, period_start, period_end)
    app_by_employee_day: dict[tuple[str, str], list[dict[str, object]]] = {}
    bamboo_by_employee_day: dict[tuple[str, str], list[dict[str, object]]] = {}
    for shift in app_shifts:
        app_by_employee_day.setdefault((str(shift["employeeId"]), str(shift["date"])), []).append(shift)
    for shift in bamboo_shifts:
        local_start = datetime.fromisoformat(str(shift["start"])).astimezone(ATTENDANCE_TIMEZONE)
        shift_date = local_start.date().isoformat()
        if not period_start <= local_start.date() <= period_end:
            continue
        for employee in shift["employees"]:
            bamboo_by_employee_day.setdefault(
                (str(employee["employeeId"]), shift_date), []
            ).append(shift | {"employee": employee})

    def signature(shift: dict[str, object]) -> tuple[str, str, str]:
        start = datetime.fromisoformat(str(shift["start"])).astimezone(timezone.utc).isoformat()
        end = datetime.fromisoformat(str(shift["end"])).astimezone(timezone.utc).isoformat()
        return start, end, str(shift["location"])

    discrepancies = []
    keys = sorted(set(app_by_employee_day) | set(bamboo_by_employee_day))
    for employee_id, shift_date in keys:
        app_items = app_by_employee_day.get((employee_id, shift_date), [])
        bamboo_items = bamboo_by_employee_day.get((employee_id, shift_date), [])
        app_signatures = sorted(signature(shift) for shift in app_items)
        bamboo_signatures = sorted(signature(shift) for shift in bamboo_items)
        if app_signatures == bamboo_signatures:
            continue
        employee = (
            bamboo_items[0].get("employee")
            if bamboo_items
            else {
                "name": app_items[0]["name"],
                "location": app_items[0]["location"],
                "role": app_items[0]["role"],
            }
        )
        fingerprint = json.dumps(
            {
                "tenant": active_tenant_id(),
                "employee": employee_id,
                "date": shift_date,
                "app": app_signatures,
                "bamboohr": bamboo_signatures,
            },
            sort_keys=True,
        )
        can_apply_app = (
            len(app_items) <= 1
            and len(bamboo_items) <= 1
            and all(len(item["employeeIds"]) == 1 for item in bamboo_items)
        )
        can_apply_bamboo = len(app_items) <= 1 and len(bamboo_items) <= 1
        discrepancies.append(
            {
                "id": hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24],
                "employeeId": employee_id,
                "name": str(employee["name"]),
                "date": shift_date,
                "location": str(employee.get("location", "")),
                "role": str(employee.get("role", "")),
                "appShifts": [
                    {
                        "runId": shift["runId"],
                        "bamboohrId": shift["bamboohrId"],
                        "start": shift["start"],
                        "end": shift["end"],
                        "location": shift["location"],
                        "role": shift["role"],
                        "day": shift["day"],
                        "startHour": shift["startHour"],
                    }
                    for shift in app_items
                ],
                "bamboohrShifts": [
                    {
                        "id": shift["id"],
                        "scheduleId": shift["scheduleId"],
                        "start": shift["start"],
                        "end": shift["end"],
                        "timezone": shift["timezone"],
                        "status": shift["status"],
                        "location": shift["location"],
                        "employeeCount": len(shift["employeeIds"]),
                    }
                    for shift in bamboo_items
                ],
                "canApplyApp": can_apply_app,
                "canApplyBambooHR": can_apply_bamboo,
            }
        )
    return discrepancies


def bamboo_shift_request(
    api_key: str, method: str, path: str, payload: dict[str, object] | None = None
) -> dict[str, object]:
    url = bamboohr_endpoint(path)
    outbound = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Accept": "application/json",
            "Authorization": "Basic "
            + base64.b64encode(f"{api_key}:x".encode("utf-8")).decode("ascii"),
            **({"Content-Type": "application/json"} if payload is not None else {}),
        },
        method=method,
    )
    try:
        with urlopen(outbound, timeout=30) as response:
            response.read(2048)
            return {"success": 200 <= response.status < 300, "status": response.status}
    except HTTPError as error:
        detail = error.read(2048).decode("utf-8", errors="replace").strip()
        return {"success": False, "status": error.code,
                "error": f"BambooHR HTTP {error.code}: {detail or error.reason}"}
    except (URLError, TimeoutError, OSError):
        return {"success": False, "status": None, "outcome": "unknown"}


def bamboo_payload_for_app_shift(
    connection: DatabaseConnection, app_shift: dict[str, object]
) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT payload FROM accepted_schedules
        WHERE tenant_id = ? AND run_id = ?
        """,
        (active_tenant_id(), app_shift["runId"]),
    ).fetchone()
    if not row:
        raise ValueError("The accepted app shift no longer exists.")
    schedule = json.loads(row[0])
    payloads = bamboo_payloads(
        connection,
        [
            {
                "runId": app_shift["runId"],
                "day": app_shift["day"],
                "start": app_shift["startHour"],
                "schedule": schedule,
            }
        ],
    )
    bamboo_id = str(app_shift["bamboohrId"])
    matching = [
        item for item in payloads
        if bamboo_id in {str(value) for value in item["employeeIds"]}
    ]
    if len(matching) != 1:
        raise ValueError("The app shift could not be mapped to one BambooHR shift payload.")
    shift_payload = matching[0]
    return {
        key: shift_payload[key]
        for key in ("scheduleId", "status", "color", "timezone", "start", "end")
    } | {
        "employeeIds": [
            value for value in shift_payload["employeeIds"] if str(value) == bamboo_id
        ]
    }


def write_reconciliation_audit(
    connection: DatabaseConnection,
    *,
    discrepancy: dict[str, object],
    direction: str,
    reason: str,
    before: object,
    after: object,
    outcome: str,
) -> None:
    connection.execute(
        """
        INSERT INTO attendance_reconciliation_audit_events
            (id, tenant_id, discrepancy_id, direction, shift_date, employee_id,
             reason, before_json, after_json, outcome, actor_id, actor_email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            secrets.token_urlsafe(18),
            active_tenant_id(),
            discrepancy["id"],
            direction,
            discrepancy["date"],
            discrepancy["employeeId"],
            reason,
            json.dumps(before, ensure_ascii=False, sort_keys=True),
            json.dumps(after, ensure_ascii=False, sort_keys=True),
            outcome,
            session.get("tenant_admin_id"),
            session.get("tenant_admin_email"),
        ),
    )


def apply_bamboo_shift_to_app(
    connection: DatabaseConnection,
    discrepancy: dict[str, object],
    bamboo_shift: dict[str, object] | None,
) -> tuple[dict[str, object], dict[str, object]]:
    app_shifts = discrepancy["appShifts"]
    if len(app_shifts) > 1:
        raise ValueError("This employee has multiple app shifts on the same day; resolve them manually.")
    app_shift = app_shifts[0] if app_shifts else None
    employee_id = str(discrepancy["employeeId"])
    shift_date = date.fromisoformat(str(discrepancy["date"]))
    bamboo_start = bamboo_end = None
    bamboo_schedule = None
    if bamboo_shift:
        bamboo_start = datetime.fromisoformat(str(bamboo_shift["start"])).astimezone(
            ATTENDANCE_TIMEZONE
        )
        bamboo_end = datetime.fromisoformat(str(bamboo_shift["end"])).astimezone(
            ATTENDANCE_TIMEZONE
        )
        if bamboo_start.date() != shift_date:
            raise ValueError("The BambooHR shift no longer matches the discrepancy date.")
        bamboo_schedule = connection.execute(
            """
            SELECT id, location, role_group
            FROM schedule_locations
            WHERE tenant_id = ? AND bamboo_schedule_id = ?
            """,
            (active_tenant_id(), bamboo_shift["scheduleId"]),
        ).fetchone()
        if not bamboo_schedule:
            raise ValueError("The BambooHR schedule location is no longer mapped.")
    if app_shift:
        row = connection.execute(
            """
            SELECT payload FROM accepted_schedules
            WHERE tenant_id = ? AND run_id = ?
            """,
            (active_tenant_id(), app_shift["runId"]),
        ).fetchone()
        if not row:
            raise ValueError("The accepted app shift no longer exists.")
        schedule = json.loads(row[0])
    else:
        week_start = (shift_date - timedelta(days=shift_date.weekday())).isoformat()
        candidates = connection.execute(
            """
            SELECT run_id, payload FROM accepted_schedules
            WHERE tenant_id = ? AND week_start = ?
            """,
            (active_tenant_id(), week_start),
        ).fetchall()
        schedule = None
        run_id = None
        for candidate_run_id, encoded in candidates:
            candidate = json.loads(encoded)
            if (
                bamboo_schedule
                and candidate.get("location") == bamboo_schedule[1]
                and candidate.get("role") == discrepancy["role"]
            ):
                schedule = candidate
                run_id = candidate_run_id
                break
        if schedule is None:
            raise ValueError(
                "No accepted schedule exists for this BambooHR shift's week, location, and role."
            )
        app_shift = {"runId": run_id, "day": shift_date.weekday()}
    before_schedule = json.loads(json.dumps(schedule))
    day_index = shift_date.weekday()
    assignments = schedule.get("employees")
    if not isinstance(assignments, list):
        raise ValueError("The accepted schedule has invalid employee assignments.")
    assigned = next(
        (
            item for item in assignments
            if isinstance(item, dict) and str(item.get("id", "")) == employee_id
        ),
        None,
    )
    employee_row = connection.execute(
        """
        SELECT bamboohr_id, name, location, role, schedule_location_id
        FROM employees WHERE tenant_id = ? AND employee_id = ?
        """,
        (active_tenant_id(), employee_id),
    ).fetchone()
    if not employee_row:
        raise ValueError("The employee mapping no longer exists.")
    if bamboo_shift:
        if (
            bamboo_schedule[0] != employee_row[4]
            or bamboo_schedule[1] != employee_row[2]
            or not role_matches_schedule_group(str(employee_row[3]), str(bamboo_schedule[2]))
        ):
            raise ValueError(
                "The BambooHR shift's location or role conflicts with the employee's app mapping."
            )
        duration = (bamboo_end - bamboo_start).total_seconds() / 3600
        span = float(schedule.get("controls", {}).get("span", 8))
        if not math.isclose(duration, span, abs_tol=1 / 60):
            raise ValueError(
                "The BambooHR shift duration differs from the accepted schedule's shared shift duration."
            )
    if assigned is None:
        if not bamboo_shift:
            raise ValueError("The app shift assignment could not be found.")
        slots = [None] * 7
        assigned = {
            "id": employee_id,
            "name": str(employee_row[1]),
            "bamboohrId": str(employee_row[0] or ""),
            "location": str(employee_row[2]),
            "role": str(employee_row[3]),
            "slots": slots,
        }
        assignments.append(assigned)
    slots = assigned.get("slots")
    if not isinstance(slots, list) or len(slots) < 7:
        raise ValueError("The accepted app shift has invalid day assignments.")
    while len(slots) < 7:
        slots.append(None)
    if bamboo_shift:
        slots[day_index] = bamboo_start.hour + bamboo_start.minute / 60
    else:
        slots[day_index] = None
    encoded = json.dumps(schedule, ensure_ascii=False, separators=(",", ":"))
    updated = connection.execute(
        """
        UPDATE accepted_schedules
        SET week_start = ?, location = ?, role = ?, payload = ?
        WHERE tenant_id = ? AND run_id = ?
        """,
        (
            schedule["start"], schedule["location"], schedule["role"], encoded,
            active_tenant_id(), app_shift["runId"],
        ),
    )
    if updated.rowcount != 1:
        raise ValueError("The accepted schedule changed before the reconciliation could be saved.")
    before = {
        "runId": app_shift["runId"],
        "employeeId": employee_id,
        "date": shift_date.isoformat(),
        "acceptedSchedule": before_schedule,
    }
    after = {
        "runId": app_shift["runId"],
        "employeeId": employee_id,
        "date": shift_date.isoformat(),
        "startHour": slots[day_index],
        "bambooShiftId": bamboo_shift["id"] if bamboo_shift else None,
        "acceptedSchedule": schedule,
    }
    return before, after


def sync_attendance_data(
    connection: DatabaseConnection,
    clock_entries: list[dict[str, object]],
    time_off: list[dict[str, str]],
    *,
    now: datetime | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    bamboo_shifts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    now = now or datetime.now(ATTENDANCE_TIMEZONE)
    today = now.date()
    tenant_id = active_tenant_id()
    settings = attendance_settings(connection)
    history_start = period_start or today - timedelta(days=settings["scorePeriodDays"] - 1)
    history_end = period_end or today
    api_start = history_start - timedelta(days=1)
    employees = {
        str(row[0]): {
            "bamboohrId": str(row[1]) if row[1] is not None else "",
            "name": row[2],
            "location": row[3],
            "role": row[4],
            "active": bool(row[5]),
        }
        for row in connection.execute(
            """
            SELECT employee_id, bamboohr_id, name, location, role, active
            FROM employees WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
    }
    selected_source = attendance_shift_source(connection)
    if selected_source == "bamboohr":
        bamboo_ids = {
            str(employee.get("bamboohrId") or "")
            for shift in bamboo_shifts or []
            for employee in shift.get("employees", [])
            if employee.get("bamboohrId")
        }
    else:
        bamboo_ids = {
            record["bamboohrId"] for record in employees.values()
            if record["active"] and record["bamboohrId"]
        }
    clock_entries = [
        entry for entry in clock_entries if entry["bamboohrId"] in bamboo_ids
    ]
    connection.execute(
        """
        DELETE FROM attendance_time_entries
        WHERE tenant_id = ? AND entry_date >= ? AND entry_date <= ?
        """,
        (tenant_id, api_start.isoformat(), history_end.isoformat()),
    )
    connection.executemany(
        """
        INSERT INTO attendance_time_entries
            (tenant_id, entry_id, bamboohr_id, entry_date, started_at,
             ended_at, timezone, approved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (tenant_id, entry_id) DO UPDATE SET
            bamboohr_id = excluded.bamboohr_id, entry_date = excluded.entry_date,
            started_at = excluded.started_at, ended_at = excluded.ended_at,
            timezone = excluded.timezone, approved = excluded.approved
        """,
        [
            (
                tenant_id, entry["id"], entry["bamboohrId"], entry["date"],
                entry["start"], entry["end"], entry["timezone"],
                int(entry["approved"]),
            )
            for entry in clock_entries
        ],
    )
    entries_by_bamboo_id: dict[str, list[dict[str, object]]] = {}
    for entry in clock_entries:
        entries_by_bamboo_id.setdefault(str(entry["bamboohrId"]), []).append(entry)
    for entries in entries_by_bamboo_id.values():
        entries.sort(key=lambda entry: str(entry["start"]))
    leave_by_employee: dict[str, list[tuple[date, date]]] = {}
    for leave in time_off:
        leave_by_employee.setdefault(leave["bamboohrId"], []).append(
            (date.fromisoformat(leave["start"]), date.fromisoformat(leave["end"]))
        )

    existing = {
        (row[0], row[1], row[2]): (row[3], row[4], row[5])
        for row in connection.execute(
            """
            SELECT schedule_run_id, employee_id, shift_date, status, source, reason
            FROM attendance_shift_records
            WHERE tenant_id = ? AND shift_date >= ? AND shift_date <= ?
            """,
            (tenant_id, history_start.isoformat(), history_end.isoformat()),
        )
    }
    active_keys: set[tuple[str, str, str]] = set()
    changed = 0
    if selected_source == "bamboohr":
        if bamboo_shifts is None:
            raise RuntimeError("BambooHR shifts must be fetched before attendance can be synced.")
        scheduled = []
        for bamboo_shift in bamboo_shifts:
            shift_start = datetime.fromisoformat(str(bamboo_shift["start"])).astimezone(
                ATTENDANCE_TIMEZONE
            )
            shift_end = datetime.fromisoformat(str(bamboo_shift["end"])).astimezone(
                ATTENDANCE_TIMEZONE
            )
            if not history_start <= shift_start.date() <= history_end:
                continue
            shift_week_start = shift_start.date() - timedelta(days=shift_start.weekday())
            day_index = shift_start.weekday()
            duration = (shift_end - shift_start).total_seconds() / 3600
            if not 0 < duration <= 24:
                raise AttendanceIntegrationError(
                    "BambooHR returned a shift with an unsupported duration."
                )
            shift_hour = shift_start.hour + shift_start.minute / 60
            scheduled_employees = []
            for employee in bamboo_shift["employees"]:
                slots = [None] * 7
                slots[day_index] = shift_hour
                scheduled_employees.append(
                    {
                        "id": employee["employeeId"],
                        "name": employee["name"],
                        "bamboohrId": employee["bamboohrId"],
                        "location": employee["location"],
                        "role": employee["role"],
                        "slots": slots,
                    }
                )
            if not scheduled_employees:
                continue
            schedule = {
                "id": f"bamboohr:{bamboo_shift['id']}",
                "start": shift_week_start.isoformat(),
                "end": (shift_week_start + timedelta(days=6)).isoformat(),
                "location": bamboo_shift["location"],
                "role": scheduled_employees[0]["role"],
                "controls": {"span": duration, "hours": duration},
                "employees": scheduled_employees,
            }
            scheduled.append((schedule["id"], json.dumps(schedule)))
    else:
        scheduled = connection.execute(
            """
            SELECT run_id, payload FROM accepted_schedules
            WHERE tenant_id = ? AND week_start >= ? AND week_start <= ?
            """,
            (
                tenant_id,
                (api_start - timedelta(days=6)).isoformat(),
                history_end.isoformat(),
            ),
        ).fetchall()
    for run_id, encoded in scheduled:
        try:
            schedule = json.loads(encoded)
            week_start = date.fromisoformat(schedule["start"])
            if not isinstance(schedule.get("employees"), list):
                raise ValueError
            span = float(schedule.get("controls", {}).get("span", 8))
            if not 0 < span <= 24:
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise RuntimeError(
                f"Accepted schedule {run_id} has invalid attendance data."
            ) from error
        for scheduled_employee in schedule["employees"]:
            if not isinstance(scheduled_employee, dict):
                raise RuntimeError(
                    f"Accepted schedule {run_id} has an invalid employee row."
                )
            employee_id = str(scheduled_employee.get("id", ""))
            employee = employees.get(employee_id)
            if selected_source == "app" and (not employee or not employee["active"]):
                continue
            if selected_source == "bamboohr" and not employee:
                employee = scheduled_employee
            if not employee:
                continue
            bamboohr_id = (
                employee["bamboohrId"]
                or str(scheduled_employee.get("bamboohrId") or "")
            )
            slots = scheduled_employee.get("slots")
            if not isinstance(slots, list):
                raise RuntimeError(
                    f"Accepted schedule {run_id} has invalid shift assignments."
                )
            for day_index, shift_start_value in enumerate(slots[:7]):
                if shift_start_value is None:
                    continue
                shift_day = week_start + timedelta(days=day_index)
                if not history_start <= shift_day <= history_end:
                    continue
                shift_start = schedule_shift_datetime(shift_day, shift_start_value)
                shift_end = shift_start + timedelta(hours=span)
                matching_entries = []
                for entry in entries_by_bamboo_id.get(bamboohr_id, []):
                    entry_start = datetime.fromisoformat(str(entry["start"]))
                    entry_end = (
                        datetime.fromisoformat(str(entry["end"]))
                        if entry["end"]
                        else None
                    )
                    if (
                        entry_start < shift_end
                        and (entry_end is None or entry_end > shift_start)
                    ):
                        matching_entries.append(entry)
                on_leave = any(
                    leave_start <= shift_day <= leave_end
                    for leave_start, leave_end in leave_by_employee.get(
                        bamboohr_id, []
                    )
                )
                timesheet = evaluate_shift_timesheet(
                    matching_entries, shift_start, shift_end, now
                )
                clock_in = timesheet["first"]
                absent_point = min(
                    shift_end,
                    shift_start + timedelta(hours=ATTENDANCE_ABSENT_AFTER_HOURS),
                )
                recorded_entry = None
                if on_leave:
                    status, source, reason = (
                        "approved_leave",
                        "bamboohr",
                        "Approved BambooHR time off.",
                    )
                elif clock_in and (timesheet["qualifies"] or timesheet["inProgress"]):
                    recorded_entry = clock_in
                    clock_time = datetime.fromisoformat(str(clock_in["start"]))
                    status = (
                        "late"
                        if clock_time.astimezone(timezone.utc)
                        > (shift_start + timedelta(
                            minutes=settings["latenessToleranceMinutes"]
                        )).astimezone(timezone.utc)
                        else "attended"
                    )
                    if timesheet["inProgress"]:
                        if status == "attended":
                            status = "scheduled"
                        source, reason = (
                            "bamboohr",
                            "Clocked in; attendance is confirmed after "
                            f"{timesheet['requiredMinutes']} minutes worked within the shift.",
                        )
                    else:
                        notes = []
                        if timesheet["earlyMinutes"]:
                            notes.append(
                                f"Left {timesheet['earlyMinutes']} minutes before the shift ended."
                            )
                        elif timesheet["partial"]:
                            notes.append(
                                f"Partial shift: worked {timesheet['workedMinutes']} of "
                                f"{timesheet['shiftMinutes']} minutes."
                            )
                        if timesheet["overtimeMinutes"]:
                            notes.append(
                                f"Worked {timesheet['overtimeMinutes']} minutes past the shift end."
                            )
                        source, reason = "bamboohr", " ".join(notes)
                elif clock_in and now >= absent_point:
                    status, source, reason = (
                        "absent",
                        "attendance_rule",
                        f"Timesheet covers only {timesheet['workedMinutes']} minutes of the "
                        f"shift; at least {timesheet['requiredMinutes']} are required.",
                    )
                elif now >= shift_start + timedelta(
                    hours=ATTENDANCE_ABSENT_AFTER_HOURS
                ):
                    status, source, reason = (
                        "absent",
                        "attendance_rule",
                        "No BambooHR clock-in was recorded within four hours of shift start.",
                    )
                elif now > shift_start + timedelta(
                    minutes=settings["latenessToleranceMinutes"]
                ):
                    status, source, reason = (
                        "late",
                        "attendance_rule",
                        "No BambooHR clock-in was recorded within the configured lateness tolerance.",
                    )
                else:
                    status, source, reason = "scheduled", "schedule", ""
                key = (run_id, employee_id, shift_day.isoformat())
                active_keys.add(key)
                changed += record_attendance_status(
                    connection,
                    run_id=run_id,
                    employee_id=employee_id,
                    shift_date=shift_day.isoformat(),
                    shift_start=float(shift_start_value),
                    status=status,
                    source=source,
                    reason=reason,
                    employee_name=str(
                        scheduled_employee.get("name") or employee["name"]
                    ),
                    location=str(
                        scheduled_employee.get("location") or employee["location"]
                    ),
                    role=str(scheduled_employee.get("role") or employee["role"]),
                    clock_in_at=str(recorded_entry["start"]) if recorded_entry else None,
                    clock_in_timezone=(
                        str(recorded_entry["timezone"]) if recorded_entry else ""
                    ),
                    shift_end_at=shift_end.isoformat(),
                    existing=existing,
                    preserve_manual=selected_source == "app",
                    timesheet=timesheet,
                )
    for key in existing.keys() - active_keys:
        record_is_bamboohr = str(key[0]).startswith("bamboohr:")
        if record_is_bamboohr != (selected_source == "bamboohr"):
            continue
        connection.execute(
            """
            DELETE FROM attendance_shift_records
            WHERE tenant_id = ? AND schedule_run_id = ? AND employee_id = ?
                AND shift_date = ?
            """,
            (tenant_id, *key),
        )
    synced_at = now.isoformat()
    connection.execute(
        """
        INSERT INTO application_settings (setting_key, setting_value, tenant_id)
        VALUES ('attendance_last_sync', ?, ?)
        ON CONFLICT (tenant_id, setting_key)
        DO UPDATE SET setting_value = excluded.setting_value
        """,
        (synced_at, tenant_id),
    )
    payload = attendance_payload(
        connection, now, period_start=history_start, period_end=history_end
    )
    payload["classifiedChanges"] = changed
    payload["syncedClockEntries"] = len(clock_entries)
    return payload


def check_bamboohr_credentials(subdomain: str, api_key: str) -> tuple[str, int] | None:
    """Return an error when the key cannot read the app's required BambooHR APIs."""
    authorization = base64.b64encode(f"{api_key.strip()}:x".encode("utf-8")).decode("ascii")
    today = date.today().isoformat()
    endpoints = (
        ("time_off/whos_out", {"start": today, "end": today}, "time-off"),
        (
            "time_tracking/timesheet_entries",
            {"start": today, "end": today},
            "time-tracking",
        ),
    )
    for path, params, label in endpoints:
        outbound = Request(
            f"{bamboohr_endpoint_for_tenant(subdomain, path)}?{urlencode(params)}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Basic {authorization}",
            },
            method="GET",
        )
        try:
            with urlopen(outbound, timeout=20) as response:
                response.read(2048)
        except HTTPError as error:
            if error.code == 401:
                return "BambooHR rejected this API key for the supplied tenant.", 401
            if error.code == 403:
                return (
                    f"BambooHR denied this key access to the {label} endpoint.",
                    403,
                )
            return f"BambooHR {label} validation failed with HTTP {error.code}.", 502
        except (URLError, TimeoutError, OSError):
            return "The app server could not reach BambooHR to validate the key.", 502
    return None


def valid_bamboohr_api_key(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= 4096
        and not any(character in value for character in "\r\n:")
    )


@app.post("/api/bamboohr/validate-key")
def validate_bamboohr_key():
    payload = request.get_json(silent=True)
    tenant_id = payload.get("tenantId") if isinstance(payload, dict) else None
    api_key = payload.get("apiKey") if isinstance(payload, dict) else None
    if not valid_tenant_id(tenant_id) or not valid_bamboohr_api_key(api_key):
        return jsonify(error="Enter a valid BambooHR tenant ID and API key."), 400

    tenant_id = tenant_id.lower()
    failure = check_bamboohr_credentials(tenant_id, api_key)
    if failure:
        return jsonify(error=failure[0]), failure[1]

    now = datetime.now(timezone.utc)
    for token, (_, _, expires_at, _) in list(_validated_bamboo_keys.items()):
        if expires_at <= now:
            del _validated_bamboo_keys[token]
    promotion_token = secrets.token_urlsafe(32)
    _validated_bamboo_keys[promotion_token] = (
        tenant_id,
        api_key.strip(),
        now + timedelta(minutes=10),
        active_tenant_id(),
    )
    return jsonify(valid=True, tenantId=tenant_id, promotionToken=promotion_token)


def bamboohr_endpoint_for_tenant(tenant_id: str, path: str) -> str:
    return f"https://{tenant_id}.bamboohr.com/api/v1/{path.lstrip('/')}"


@app.post("/api/bamboohr/promote-key")
def promote_bamboohr_key():
    payload = request.get_json(silent=True)
    token = payload.get("promotionToken") if isinstance(payload, dict) else None
    tenant_id = payload.get("tenantId") if isinstance(payload, dict) else None
    validation = _validated_bamboo_keys.get(token) if isinstance(token, str) else None
    now = datetime.now(timezone.utc)
    if (
        validation is None
        or validation[2] <= now
        or validation[3] != active_tenant_id()
        or not valid_tenant_id(tenant_id)
        or tenant_id.lower() != validation[0]
        or current_app_config()["tenantId"] != validation[0]
    ):
        if isinstance(token, str):
            _validated_bamboo_keys.pop(token, None)
        return jsonify(error="Test the API key successfully for the currently saved tenant before promoting it."), 400

    with closing(database_connect()) as connection, connection:
        previous = connection.execute(
            "SELECT bamboohr_api_key_encrypted FROM tenants WHERE tenant_id = ?",
            (active_tenant_id(),),
        ).fetchone()
        connection.execute(
            "UPDATE tenants SET bamboohr_api_key_encrypted = ? WHERE tenant_id = ?",
            (encrypt_bamboohr_api_key(validation[1]), active_tenant_id()),
        )
    try:
        save_app_config({"tenantId": validation[0]})
    except BambooDomainConflict:
        with closing(database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET bamboohr_api_key_encrypted = ? WHERE tenant_id = ?",
                (previous[0] if previous else None, active_tenant_id()),
            )
        return jsonify(error="That BambooHR domain is already registered to another business; the key change was rolled back."), 409
    except database_errors():
        with closing(database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET bamboohr_api_key_encrypted = ? WHERE tenant_id = ?",
                (previous[0] if previous else None, active_tenant_id()),
            )
        return jsonify(error="The app settings could not be saved; the API key change was rolled back."), 500

    del _validated_bamboo_keys[token]
    return jsonify(promoted=True, tenantId=validation[0])


@app.get("/api/attendance")
def get_attendance():
    period_start_text = request.args.get("start")
    period_end_text = request.args.get("end")
    selected_date_text = request.args.get("date")
    selected_date = period_start = period_end = None
    if period_start_text is not None or period_end_text is not None:
        if not period_start_text or not period_end_text or selected_date_text is not None:
            return jsonify(error="Provide both attendance period start and end dates."), 400
        try:
            period_start = date.fromisoformat(period_start_text)
            period_end = date.fromisoformat(period_end_text)
        except ValueError:
            return jsonify(error="Provide valid attendance period dates in YYYY-MM-DD format."), 400
        if (
            period_start.isoformat() != period_start_text
            or period_end.isoformat() != period_end_text
            or period_end < period_start
        ):
            return jsonify(error="Provide a valid inclusive attendance period."), 400
    elif selected_date_text:
        try:
            selected_date = date.fromisoformat(selected_date_text)
        except ValueError:
            return jsonify(error="Provide a valid attendance date in YYYY-MM-DD format."), 400
        if selected_date.isoformat() != selected_date_text:
            return jsonify(error="Provide a valid attendance date in YYYY-MM-DD format."), 400
        period_start = period_end = selected_date
    today = datetime.now(ATTENDANCE_TIMEZONE).date()
    if period_end and period_end > today:
        return jsonify(error="Attendance cannot be viewed for a future date."), 400
    with closing(database_connect()) as connection:
        result = attendance_payload(
            connection,
            selected_date=selected_date,
            period_start=period_start,
            period_end=period_end,
        )
        if attendance_shift_source(connection) == "bamboohr":
            report_start = period_start or selected_date or date.fromisoformat(result["periodStart"])
            report_end = period_end or selected_date or date.fromisoformat(result["periodEnd"])
            try:
                bamboo_shifts = fetch_bamboohr_scheduled_shifts(
                    connection, report_start, report_end, attendance_mode=True
                )
                discrepancies = attendance_shift_discrepancies(
                    connection, report_start, report_end, bamboo_shifts
                )
            except AttendanceIntegrationError as error:
                return jsonify(error=str(error)), 502
            result["shiftSource"] = {
                "selected": "bamboohr",
                "bamboohrAvailable": True,
                "unresolvedDiscrepancies": discrepancies,
            }
        return jsonify(result)


def attendance_clock_entries_for_employee(api_key: str, bamboohr_id: str, start: date, end: date):
    raw = bamboohr_json(
        api_key,
        "time_tracking/timesheet_entries",
        {"start": start.isoformat(), "end": end.isoformat()},
        "time-tracking",
    )
    return [
        entry for entry in parse_bamboohr_clock_entries(raw)
        if entry["bamboohrId"] == bamboohr_id
    ]


def clock_action_result_matches(action: str, entries, before_entry, requested_at: datetime) -> dict | None:
    target = requested_at.astimezone(timezone.utc)
    if action == "clock_in":
        matching = [
            entry for entry in entries
            if entry["end"] is None
            and abs((datetime.fromisoformat(entry["start"]).astimezone(timezone.utc) - target).total_seconds()) < 60
        ]
        return matching[0] if len(matching) == 1 else None
    if not before_entry:
        return None
    matching = [
        entry for entry in entries
        if entry["id"] == before_entry["id"]
        and entry["end"] is not None
        and abs((datetime.fromisoformat(entry["end"]).astimezone(timezone.utc) - target).total_seconds()) < 60
    ]
    return matching[0] if len(matching) == 1 else None


def refresh_attendance_after_clock_action(shift_date: date, now: datetime):
    history_start = min(shift_date, now.date())
    history_end = now.date()
    api_start = history_start - timedelta(days=1)
    api_key = bamboohr_api_key()
    clocks = parse_bamboohr_clock_entries(
        bamboohr_json(
            api_key, "time_tracking/timesheet_entries",
            {"start": api_start.isoformat(), "end": history_end.isoformat()}, "time-tracking",
        )
    )
    time_off = parse_bamboohr_time_off(
        bamboohr_json(
            api_key, "time_off/whos_out",
            {"start": api_start.isoformat(), "end": history_end.isoformat()}, "time-off",
        )
    )
    with closing(database_connect()) as connection, connection:
        source = attendance_shift_source(connection)
        bamboo_shifts = (
            fetch_bamboohr_scheduled_shifts(
                connection, history_start, history_end, attendance_mode=True
            )
            if source == "bamboohr" else None
        )
        sync_attendance_data(
            connection, clocks, time_off, now=now,
            period_start=history_start, period_end=history_end,
            bamboo_shifts=bamboo_shifts,
        )
        return attendance_payload(
            connection, now, period_start=history_start, period_end=history_end,
        )


@app.post("/api/attendance/clock-events")
def create_attendance_clock_event():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="A clock action is required."), 400
    action = payload.get("action")
    run_id = payload.get("runId")
    employee_id = payload.get("employeeId")
    shift_text = payload.get("date")
    request_id = payload.get("requestId")
    reason = payload.get("reason")
    if (
        action not in {"clock_in", "clock_out", "clock_out_shift_end"}
        or not isinstance(run_id, str) or not 1 <= len(run_id) <= 200
        or not isinstance(employee_id, str) or not 1 <= len(employee_id) <= 80
        or not isinstance(shift_text, str)
        or not isinstance(request_id, str) or not re.fullmatch(r"[A-Fa-f0-9-]{36}", request_id)
        or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500
    ):
        return jsonify(error="Provide a valid clock action, attendance row, request ID and audit reason."), 400
    try:
        shift_date = date.fromisoformat(shift_text)
        if shift_date.isoformat() != shift_text:
            raise ValueError
    except ValueError:
        return jsonify(error="Provide a valid shift date in YYYY-MM-DD format."), 400

    now = datetime.now(ATTENDANCE_TIMEZONE).replace(second=0, microsecond=0)
    if shift_date > now.date() or (now.date() - shift_date).days > 363:
        return jsonify(error="Clock actions are limited to a current BambooHR-supported attendance period."), 409
    api_key = bamboohr_api_key()
    if not api_key:
        return jsonify(error="The BambooHR API key is not configured for this business."), 503

    with closing(database_connect()) as connection:
        previous_request = connection.execute(
            "SELECT outcome,detail FROM attendance_clock_action_audit_events "
            "WHERE tenant_id=? AND request_id=?",
            (active_tenant_id(), request_id),
        ).fetchone()
        if previous_request:
            if previous_request[0] == "succeeded":
                return jsonify(outcome="succeeded", duplicate=True, message="This clock action was already completed.")
            return jsonify(error="This clock action request is already recorded; refresh attendance before continuing.",
                           outcome=previous_request[0]), 409
        row = connection.execute(
            """SELECT r.shift_start,r.shift_end_at,r.status,r.employee_name,r.location,r.role,
                      e.bamboohr_id,e.active,r.clock_in_at
               FROM attendance_shift_records r
               JOIN employees e ON e.employee_id=r.employee_id AND e.tenant_id=r.tenant_id
               WHERE r.tenant_id=? AND r.schedule_run_id=? AND r.employee_id=? AND r.shift_date=?""",
            (active_tenant_id(), run_id, employee_id, shift_text),
        ).fetchone()
        if not row:
            return jsonify(error="The scheduled attendance record was not found. Sync attendance and retry."), 404
        try:
            shift_start = schedule_shift_datetime(shift_date, row[0])
            shift_end = datetime.fromisoformat(row[1]) if row[1] else None
            if shift_end and (shift_end.tzinfo is None or shift_end <= shift_start):
                raise ValueError
        except (TypeError, ValueError) as error:
            return jsonify(error="A verified scheduled shift end is unavailable. Sync attendance and retry."), 409
        bamboohr_id = str(row[6] or "")
        if not row[7] or re.fullmatch(r"[0-9]+", bamboohr_id) is None:
            return jsonify(error="This active employee has no valid BambooHR employee ID."), 409
        if row[2] in {"approved_leave", "sick", "vacation"}:
            return jsonify(error="Clock actions are unavailable for approved leave."), 409
        if shift_end is None or shift_start > now:
            return jsonify(error="Clock actions are available only for a shift that has started."), 409
        if action == "clock_in" and now >= shift_end:
            return jsonify(error="Clock in is available only before the scheduled shift end."), 409
        if action == "clock_out_shift_end" and now < shift_end:
            return jsonify(error="Clock out at shift end is available only after the scheduled shift end has passed."), 409
        existing_open_claim = connection.execute(
            """SELECT request_id FROM attendance_clock_action_audit_events
               WHERE tenant_id=? AND bamboohr_id=? AND outcome IN ('pending','unknown')""",
            (active_tenant_id(), bamboohr_id),
        ).fetchone()
        if existing_open_claim:
            return jsonify(error="A previous BambooHR clock result is unresolved. Refresh and reconcile it before another action."), 409

    try:
        history_start = min(shift_date - timedelta(days=1), now.date() - timedelta(days=2))
        fresh_entries = attendance_clock_entries_for_employee(
            api_key, bamboohr_id, history_start, now.date(),
        )
    except AttendanceIntegrationError as error:
        return jsonify(error=str(error)), 502

    open_entries = [entry for entry in fresh_entries if entry["end"] is None]
    overlapping_open = [
        entry for entry in open_entries
        if datetime.fromisoformat(str(entry["start"])) < shift_end
        and (
            str(entry["start"]) == str(row[8])
            if row[8]
            else datetime.fromisoformat(str(entry["start"])) >= shift_start
        )
    ]
    if action == "clock_in":
        if open_entries:
            return jsonify(error="The employee already has an open BambooHR clock entry."), 409
        requested_at = now
        request_date = requested_at.date()
        request_time = requested_at.strftime("%H:%M")
        endpoint_action = "clock_in"
        before_entry = None
    else:
        if len(open_entries) != 1 or len(overlapping_open) != 1:
            return jsonify(error="The employee must have exactly one open BambooHR clock entry for this shift."), 409
        before_entry = overlapping_open[0]
        if action == "clock_out_shift_end":
            requested_at = shift_end.astimezone(ATTENDANCE_TIMEZONE).replace(second=0, microsecond=0)
        else:
            requested_at = now
        request_date = requested_at.date()
        request_time = requested_at.strftime("%H:%M")
        endpoint_action = "clock_out"

    try:
        with closing(database_connect()) as connection, connection:
            connection.execute(
                """INSERT INTO attendance_clock_action_audit_events
                   (id,tenant_id,request_id,bamboohr_id,employee_id,schedule_run_id,
                    shift_date,action,outcome,reason,requested_date,requested_time,
                    before_json,actor_id,actor_email)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    secrets.token_urlsafe(18), active_tenant_id(), request_id, bamboohr_id,
                    employee_id, run_id, shift_text, action, "pending", reason.strip(),
                    request_date.isoformat(), request_time,
                    json.dumps(before_entry or {}), session.get("tenant_admin_id"),
                    session.get("tenant_admin_email"),
                ),
            )
    except database_integrity_errors():
        return jsonify(error="Another clock action for this employee is already in progress."), 409

    remote = bamboo_shift_request(
        api_key, "POST",
        f"time_tracking/employees/{bamboohr_id}/{endpoint_action}",
        {"date": request_date.isoformat(), "start" if action == "clock_in" else "end": request_time},
    )
    if not remote.get("success"):
        outcome = "unknown" if remote.get("outcome") == "unknown" else "failed"
        detail = "BambooHR clock action outcome is unknown." if outcome == "unknown" else f"BambooHR rejected the clock action (HTTP {remote.get('status')})."
        with closing(database_connect()) as connection, connection:
            connection.execute(
                "UPDATE attendance_clock_action_audit_events SET outcome=?,detail=?,updated_at=CURRENT_TIMESTAMP "
                "WHERE tenant_id=? AND request_id=?",
                (outcome, detail, active_tenant_id(), request_id),
            )
        return jsonify(error=detail, outcome=outcome, requestId=request_id), 502

    try:
        verified_entries = attendance_clock_entries_for_employee(
            api_key, bamboohr_id, history_start, now.date(),
        )
    except AttendanceIntegrationError:
        verified_entries = []
    verified_entry = clock_action_result_matches(action, verified_entries, before_entry, requested_at)
    if not verified_entry:
        detail = "BambooHR accepted the request but the resulting clock entry could not yet be verified. Do not retry until attendance has been refreshed."
        with closing(database_connect()) as connection, connection:
            connection.execute(
                "UPDATE attendance_clock_action_audit_events SET outcome='unknown',detail=?,updated_at=CURRENT_TIMESTAMP "
                "WHERE tenant_id=? AND request_id=?",
                (detail, active_tenant_id(), request_id),
            )
        return jsonify(error=detail, outcome="unknown", requestId=request_id), 502

    after = {"id": verified_entry["id"], "date": verified_entry["date"],
             "start": verified_entry["start"], "end": verified_entry["end"]}
    with closing(database_connect()) as connection, connection:
        connection.execute(
            "UPDATE attendance_clock_action_audit_events SET outcome='succeeded',after_json=?,detail=?,updated_at=CURRENT_TIMESTAMP "
            "WHERE tenant_id=? AND request_id=? AND outcome='pending'",
            (json.dumps(after), f"Verified BambooHR {endpoint_action} clock event.", active_tenant_id(), request_id),
        )
    try:
        updated_attendance = refresh_attendance_after_clock_action(shift_date, now)
    except AttendanceIntegrationError:
        return jsonify(outcome="succeeded", requestId=request_id,
                       warning="The BambooHR clock action succeeded, but attendance refresh failed. Refresh the Attendance page."), 200
    return jsonify(outcome="succeeded", requestId=request_id, attendance=updated_attendance)


@app.put("/api/attendance/settings")
def update_attendance_settings():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Attendance settings are required."), 400
    tolerance = payload.get("latenessToleranceMinutes")
    period = payload.get("scorePeriodDays")
    if (
        isinstance(tolerance, bool)
        or not isinstance(tolerance, int)
        or not 0 <= tolerance <= 120
        or isinstance(period, bool)
        or not isinstance(period, int)
        or not 30 <= period <= 45
    ):
        return jsonify(
            error="Set lateness tolerance from 0 to 120 minutes and the attendance period from 30 to 45 days."
        ), 400
    with closing(database_connect()) as connection, connection:
        connection.executemany(
            """
            INSERT INTO application_settings (setting_key, setting_value, tenant_id)
            VALUES (?, ?, ?)
            ON CONFLICT (tenant_id, setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
            """,
            [
                (
                    "attendance_lateness_tolerance_minutes",
                    str(tolerance),
                    active_tenant_id(),
                ),
                (
                    "attendance_score_period_days",
                    str(period),
                    active_tenant_id(),
                ),
            ],
        )
    return jsonify(settings={"latenessToleranceMinutes": tolerance, "scorePeriodDays": period})


@app.put("/api/attendance/source")
def update_attendance_shift_source():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    source = payload.get("source") if isinstance(payload, dict) else None
    if not isinstance(source, str) or source not in {"app", "bamboohr"}:
        return jsonify(error="Choose either app or BambooHR shifts as the attendance source."), 400
    if source == "bamboohr" and (not isinstance(payload, dict) or payload.get("confirmed") is not True):
        return jsonify(error="Explicit confirmation is required before switching to BambooHR shifts."), 400
    today = datetime.now(ATTENDANCE_TIMEZONE).date()
    if source == "bamboohr":
        start_text, end_text = payload.get("start"), payload.get("end")
        try:
            if not isinstance(start_text, str) or not isinstance(end_text, str):
                raise ValueError
            period_start = date.fromisoformat(start_text)
            period_end = date.fromisoformat(end_text)
            if (
                period_start.isoformat() != start_text
                or period_end.isoformat() != end_text
                or period_end < period_start
                or period_end > today
                or (period_end - period_start).days > 363
            ):
                raise ValueError
        except ValueError:
            return jsonify(
                error="Provide a valid attendance period of up to 365 inclusive days before switching sources."
            ), 400
        with closing(database_connect()) as connection:
            try:
                bamboo_shifts = fetch_bamboohr_scheduled_shifts(
                    connection, period_start, period_end, attendance_mode=True
                )
                discrepancies = attendance_shift_discrepancies(
                    connection, period_start, period_end, bamboo_shifts
                )
            except AttendanceIntegrationError as error:
                return jsonify(error=str(error), selected=attendance_shift_source(connection)), 502
    with closing(database_connect()) as connection, connection:
        connection.execute(
            """
            INSERT INTO application_settings (setting_key, setting_value, tenant_id)
            VALUES ('attendance_shift_source', ?, ?)
            ON CONFLICT (tenant_id, setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
            """,
            (source, active_tenant_id()),
        )
    if source == "bamboohr":
        return jsonify(
            selected=source,
            bamboohrAvailable=True,
            unresolvedDiscrepancies=discrepancies,
        )
    return jsonify(selected=source, bamboohrAvailable=None, unresolvedDiscrepancies=None)


@app.post("/api/attendance/sync")
def sync_attendance():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if payload is not None and not isinstance(payload, dict):
        return jsonify(error="Attendance sync options must be an object."), 400
    with closing(database_connect()) as connection:
        settings = attendance_settings(connection)
        source = attendance_shift_source(connection)
    now = datetime.now(ATTENDANCE_TIMEZONE)
    today = now.date()
    start_text = payload.get("start") if payload else None
    end_text = payload.get("end") if payload else None
    if start_text is None and end_text is None:
        history_end = today
        history_start = today - timedelta(days=settings["scorePeriodDays"] - 1)
    else:
        if not isinstance(start_text, str) or not isinstance(end_text, str):
            return jsonify(error="Provide both attendance sync period start and end dates."), 400
        try:
            history_start = date.fromisoformat(start_text)
            history_end = date.fromisoformat(end_text)
        except ValueError:
            return jsonify(error="Provide valid attendance sync dates in YYYY-MM-DD format."), 400
        if (
            history_start.isoformat() != start_text
            or history_end.isoformat() != end_text
            or history_end < history_start
        ):
            return jsonify(error="Provide a valid inclusive attendance sync period."), 400
        if history_end > today:
            return jsonify(error="Attendance cannot be synced for a future date."), 400
        if (history_end - history_start).days > 363:
            return jsonify(error="BambooHR attendance sync supports up to 365 inclusive days."), 400
    api_start = history_start - timedelta(days=1)
    start_text, end_text = api_start.isoformat(), history_end.isoformat()
    api_key = bamboohr_api_key()
    if not api_key:
        return jsonify(error="The BambooHR API key is not configured for this business."), 503
    try:
        clock_data = bamboohr_json(
            api_key,
            "time_tracking/timesheet_entries",
            {"start": start_text, "end": end_text},
            "time-tracking",
        )
        time_off_data = bamboohr_json(
            api_key,
            "time_off/whos_out",
            {"start": start_text, "end": end_text},
            "time-off",
        )
        clock_entries = parse_bamboohr_clock_entries(clock_data)
        approved_time_off = parse_bamboohr_time_off(time_off_data)
        bamboo_shifts = None
        if source == "bamboohr":
            with closing(database_connect()) as connection:
                bamboo_shifts = fetch_bamboohr_scheduled_shifts(
                    connection, history_start, history_end, attendance_mode=True
                )
                discrepancies = attendance_shift_discrepancies(
                    connection, history_start, history_end, bamboo_shifts
                )
    except AttendanceIntegrationError as error:
        return jsonify(error=str(error)), 502

    with closing(database_connect()) as connection, connection:
        result = sync_attendance_data(
            connection,
            clock_entries,
            approved_time_off,
            now=now,
            period_start=history_start,
            period_end=history_end,
            bamboo_shifts=bamboo_shifts,
        )
    if source == "bamboohr":
        result["shiftSource"] = {
            "selected": source,
            "bamboohrAvailable": True,
            "unresolvedDiscrepancies": discrepancies,
        }
    return jsonify(result)


@app.post("/api/attendance/reconciliation/resolve")
def resolve_attendance_shift_discrepancy():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        return jsonify(error="Explicit confirmation is required before resolving a shift discrepancy."), 400
    discrepancy_id = payload.get("discrepancyId")
    direction = payload.get("direction")
    reason = payload.get("reason")
    shift_date_text = payload.get("date")
    if (
        not isinstance(discrepancy_id, str)
        or not re.fullmatch(r"[a-f0-9]{24}", discrepancy_id)
        or not isinstance(direction, str)
        or direction not in {"app_to_bamboohr", "bamboohr_to_app"}
        or not isinstance(reason, str)
        or not 1 <= len(reason.strip()) <= 500
        or not isinstance(shift_date_text, str)
    ):
        return jsonify(error="Choose a valid discrepancy, direction, date, and reason."), 400
    try:
        shift_date = date.fromisoformat(shift_date_text)
    except ValueError:
        return jsonify(error="Provide a valid discrepancy date."), 400
    if shift_date.isoformat() != shift_date_text or shift_date > datetime.now(ATTENDANCE_TIMEZONE).date():
        return jsonify(error="Provide a valid, non-future discrepancy date."), 400

    with closing(database_connect()) as connection:
        if attendance_shift_source(connection) != "bamboohr":
            return jsonify(error="Select BambooHR shifts before resolving a discrepancy."), 409
        try:
            bamboo_shifts = fetch_bamboohr_scheduled_shifts(
                connection, shift_date, shift_date, attendance_mode=True
            )
            discrepancies = attendance_shift_discrepancies(
                connection, shift_date, shift_date, bamboo_shifts
            )
        except AttendanceIntegrationError as error:
            return jsonify(error=str(error)), 502
        discrepancy = next(
            (item for item in discrepancies if item["id"] == discrepancy_id),
            None,
        )
        if not discrepancy:
            return jsonify(error="This discrepancy has changed. Refresh attendance and review it again."), 409
        can_resolve = (
            discrepancy["canApplyApp"]
            if direction == "app_to_bamboohr"
            else discrepancy["canApplyBambooHR"]
        )
        if not can_resolve:
            return jsonify(
                error="This discrepancy contains multiple shifts or employees and cannot be safely resolved as one action."
            ), 409
        bamboo_by_id = {str(item["id"]): item for item in bamboo_shifts}
        current_bamboo = [
            bamboo_by_id[str(item["id"])]
            for item in discrepancy["bamboohrShifts"]
            if str(item["id"]) in bamboo_by_id
        ]
        if len(current_bamboo) != len(discrepancy["bamboohrShifts"]):
            return jsonify(error="A BambooHR shift changed while this discrepancy was being prepared."), 409

    if direction == "bamboohr_to_app":
        if len(current_bamboo) > 1:
            return jsonify(error="This employee has multiple BambooHR shifts on the same day; resolve them manually."), 409
        try:
            with closing(database_connect()) as connection, connection:
                before, after = apply_bamboo_shift_to_app(
                    connection,
                    discrepancy,
                    current_bamboo[0] if current_bamboo else None,
                )
                write_reconciliation_audit(
                    connection,
                    discrepancy=discrepancy,
                    direction=direction,
                    reason=reason.strip(),
                    before=before,
                    after=after,
                    outcome="succeeded",
                )
        except ValueError as error:
            return jsonify(error=str(error)), 409
        return jsonify(success=True, outcome="succeeded", updated=after)

    api_key = bamboohr_api_key()
    if not api_key:
        return jsonify(error="The BambooHR API key is not configured for this business."), 503
    if current_bamboo and len(current_bamboo[0]["employeeIds"]) != 1:
        return jsonify(
            error="This BambooHR shift is shared by multiple employees; replacing it individually could alter their schedules."
        ), 409
    operations = []
    try:
        with closing(database_connect()) as connection:
            app_shifts = discrepancy["appShifts"]
            replacement = (
                bamboo_payload_for_app_shift(connection, app_shifts[0])
                if app_shifts
                else None
            )
    except (ValueError, KeyError, TypeError) as error:
        return jsonify(error=str(error)), 409

    if replacement:
        operations.append(
            {
                "operation": "add",
                **bamboo_shift_request(
                    api_key, "POST", "scheduling/shifts", replacement
                ),
            }
        )
    if not replacement or (operations and operations[0]["success"]):
        if current_bamboo:
            shift_id = quote(str(current_bamboo[0]["id"]), safe="")
            delete_path = (
                f"scheduling/shifts/{shift_id}?"
                + urlencode({"recurrenceEditOption": "instance"})
            )
            operations.append(
                {
                    "operation": "delete",
                    **bamboo_shift_request(api_key, "DELETE", delete_path),
                }
            )
    succeeded = bool(operations) and all(item["success"] for item in operations)
    outcome = (
        "succeeded"
        if succeeded
        else "partial"
        if any(item["success"] for item in operations)
        else "failed"
    )
    with closing(database_connect()) as connection, connection:
        write_reconciliation_audit(
            connection,
            discrepancy=discrepancy,
            direction=direction,
            reason=reason.strip(),
            before={
                "appShifts": discrepancy["appShifts"],
                "bamboohrShifts": discrepancy["bamboohrShifts"],
            },
            after={"requestedAppShift": replacement, "operations": operations},
            outcome=outcome,
        )
    status_code = 200 if succeeded else 502
    operation_summary = "; ".join(
        f"{item['operation']}: "
        + (
            str(item["status"])
            if item.get("status") is not None
            else "outcome unknown"
        )
        for item in operations
    )
    return jsonify(
        success=succeeded,
        outcome=outcome,
        operations=operations,
        **(
            {}
            if succeeded
            else {
                "error": (
                    f"BambooHR reconciliation {outcome} ({operation_summary}). "
                    "Refresh and review the current shifts before retrying."
                )
            }
        ),
    ), status_code


@app.post("/api/attendance/scores/<path:employee_id>/override")
@app.delete("/api/attendance/scores/<path:employee_id>/override")
def update_attendance_score_override(employee_id: str):
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    reason = payload.get("reason") if isinstance(payload, dict) else None
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
        return jsonify(error="Provide a reason of 1 to 500 characters for the attendance override."), 400
    score = payload.get("score") if request.method == "POST" and isinstance(payload, dict) else None
    if request.method == "POST" and (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(score)
        or not 0 <= score <= 100
    ):
        return jsonify(error="Attendance score must be a number from 0 to 100."), 400
    with closing(database_connect()) as connection, connection:
        employee = connection.execute(
            """
            SELECT 1 FROM employees
            WHERE tenant_id = ? AND employee_id = ?
            """,
            (active_tenant_id(), employee_id),
        ).fetchone()
        if not employee:
            return jsonify(error="Employee was not found."), 404
        previous = connection.execute(
            """
            SELECT score FROM attendance_score_overrides
            WHERE tenant_id = ? AND employee_id = ?
            """,
            (active_tenant_id(), employee_id),
        ).fetchone()
        if request.method == "POST":
            connection.execute(
                """
                INSERT INTO attendance_score_overrides
                    (tenant_id, employee_id, score, reason, actor_id, actor_email, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (tenant_id, employee_id)
                DO UPDATE SET score = excluded.score, reason = excluded.reason,
                    actor_id = excluded.actor_id, actor_email = excluded.actor_email,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    active_tenant_id(), employee_id, float(score), reason.strip(),
                    session.get("tenant_admin_id"), session.get("tenant_admin_email"),
                ),
            )
            updated_score = float(score)
        else:
            connection.execute(
                "DELETE FROM attendance_score_overrides WHERE tenant_id = ? AND employee_id = ?",
                (active_tenant_id(), employee_id),
            )
            updated_score = None
        connection.execute(
            """
            INSERT INTO attendance_score_audit_events
                (id, tenant_id, employee_id, previous_score, score, reason, actor_id, actor_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                secrets.token_urlsafe(18), active_tenant_id(), employee_id,
                previous[0] if previous else None, updated_score, reason.strip(),
                session.get("tenant_admin_id"), session.get("tenant_admin_email"),
            ),
        )
        result = attendance_payload(connection)
    return jsonify(attendance=result)


@app.post("/api/attendance/shifts/override")
def override_attendance_shift():
    if not tenant_auth_csrf_valid():
        return jsonify(error="The request token is invalid. Reload the page and retry."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="An attendance correction is required."), 400
    run_id = payload.get("runId")
    employee_id = payload.get("employeeId")
    shift_text = payload.get("date")
    status = payload.get("status")
    reason = payload.get("reason")
    if (
        not isinstance(run_id, str)
        or not run_id
        or not isinstance(employee_id, str)
        or not employee_id
        or not isinstance(shift_text, str)
        or not isinstance(reason, str)
        or not 1 <= len(reason.strip()) <= 500
        or status not in {"attended", "late", "absent", "sick", "vacation", "approved_leave"}
    ):
        return jsonify(error="Choose a valid attendance status and provide a reason of 1 to 500 characters."), 400
    try:
        shift_date = date.fromisoformat(shift_text)
    except ValueError:
        return jsonify(error="Provide a valid shift date in YYYY-MM-DD format."), 400
    if shift_date.isoformat() != shift_text:
        return jsonify(error="Provide a valid shift date in YYYY-MM-DD format."), 400
    with closing(database_connect()) as connection, connection:
        row = connection.execute(
            """
            SELECT shift_start, status, source, reason, employee_name, location,
                   role, clock_in_at, clock_in_timezone
            FROM attendance_shift_records
            WHERE tenant_id = ? AND schedule_run_id = ? AND employee_id = ?
                AND shift_date = ?
            """,
            (active_tenant_id(), run_id, employee_id, shift_text),
        ).fetchone()
        if not row:
            return jsonify(error="The scheduled attendance record was not found. Sync attendance and retry."), 404
        existing = {(run_id, employee_id, shift_text): (row[1], row[2], row[3])}
        record_attendance_status(
            connection,
            run_id=run_id,
            employee_id=employee_id,
            shift_date=shift_text,
            shift_start=row[0],
            status=status,
            source="manual",
            reason=reason.strip(),
            employee_name=row[4],
            location=row[5],
            role=row[6],
            clock_in_at=row[7],
            clock_in_timezone=row[8],
            existing=existing,
            preserve_manual=False,
            actor_id=session.get("tenant_admin_id"),
            actor_email=session.get("tenant_admin_email"),
        )
        result = attendance_payload(connection)
    return jsonify(attendance=result)


@app.get("/api/bamboohr/time-offs")
def bamboohr_time_offs():
    start_text, end_text = request.args.get("start", ""), request.args.get("end", "")
    try:
        start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
    except ValueError:
        return jsonify(error="Provide valid start and end dates in YYYY-MM-DD format."), 400
    if start.isoformat() != start_text or end.isoformat() != end_text or end < start:
        return jsonify(error="Provide a valid inclusive time-off date range."), 400

    api_key = bamboohr_api_key()
    if not api_key:
        return jsonify(error="The BambooHR API key is not configured for this business."), 503

    authorization = base64.b64encode(f"{api_key}:x".encode("utf-8")).decode("ascii")
    outbound = Request(
        f"{bamboohr_endpoint('time_off/whos_out')}?{urlencode({'start': start_text, 'end': end_text})}",
        headers={"Accept": "application/json", "Authorization": f"Basic {authorization}"},
        method="GET",
    )
    try:
        with urlopen(outbound, timeout=20) as response:
            raw_data = response.read(10_000_001)
        if len(raw_data) > 10_000_000:
            return jsonify(error="BambooHR time-off response exceeds the allowed size."), 502
        data = json.loads(raw_data)
        if not isinstance(data, list):
            return jsonify(error="BambooHR returned an invalid time-off response."), 502
        entries = []
        for item in data:
            if not isinstance(item, dict) or item.get("type") != "timeOff":
                continue
            if item.get("status") and str(item["status"]).casefold() != "approved":
                continue
            name, item_start, item_end = item.get("name"), item.get("start"), item.get("end")
            if not isinstance(name, str) or not name.strip():
                return jsonify(error="BambooHR returned a time-off record without an employee name."), 502
            try:
                leave_start, leave_end = date.fromisoformat(item_start), date.fromisoformat(item_end)
            except (TypeError, ValueError):
                return jsonify(error="BambooHR returned a time-off record with invalid dates."), 502
            if (
                leave_start.isoformat() != item_start
                or leave_end.isoformat() != item_end
                or leave_end < leave_start
            ):
                return jsonify(error="BambooHR returned a time-off record with invalid dates."), 502
            if leave_end >= start and leave_start <= end:
                entries.append(
                    {
                        "id": item.get("id", ""),
                        "type": "timeOff",
                        "employeeId": item.get("employeeId", ""),
                        "name": name.strip(),
                        "start": item_start,
                        "end": item_end,
                    }
                )
    except HTTPError as error:
        return jsonify(error=f"BambooHR time-off request failed with HTTP {error.code}."), 502
    except (URLError, TimeoutError, OSError):
        return jsonify(error="The app server could not reach BambooHR for time-off data."), 502
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify(error="BambooHR returned an invalid time-off response."), 502
    return jsonify(start=start_text, end=end_text, entries=entries)


@app.post("/api/bamboohr/preview")
def preview_bamboohr_publish():
    payload = request.get_json(silent=True)
    with closing(database_connect()) as connection:
        try:
            selections = accepted_schedule_selections(
                connection, payload.get("selections") if isinstance(payload, dict) else None
            )
            prepared = bamboo_payloads(connection, selections)
        except (ValueError, KeyError, TypeError) as error:
            return jsonify(error=str(error)), 400
    return jsonify(payloads=bamboo_preview_response(prepared))


@app.post("/api/bamboohr/publish")
def publish_bamboohr_schedules():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        return jsonify(error="Explicit confirmation is required before publishing."), 400
    api_key = bamboohr_api_key()
    if not api_key:
        return jsonify(error="Set the BambooHR API key in Settings before publishing."), 503
    with closing(database_connect()) as connection:
        try:
            selections = accepted_schedule_selections(connection, payload.get("selections"))
            prepared = bamboo_payloads(connection, selections)
        except (ValueError, KeyError, TypeError) as error:
            return jsonify(error=str(error)), 400

    authorization = base64.b64encode(f"{api_key}:x".encode("utf-8")).decode("ascii")
    results = []
    for schedule_payload in prepared:
        request_payload = {
            key: value
            for key, value in schedule_payload.items()
            if key not in {"scheduleName", "employeeNames"}
        }
        outbound = Request(
            bamboohr_endpoint("scheduling/shifts"),
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Basic {authorization}",
            },
            method="POST",
        )
        result = {
            "scheduleName": schedule_payload["scheduleName"],
            "start": schedule_payload["start"],
            "employeeIds": schedule_payload["employeeIds"],
        }
        try:
            with urlopen(outbound, timeout=20) as response:
                result.update(status=response.status, success=200 <= response.status < 300)
                if not result["success"]:
                    result["error"] = response.read(2000).decode("utf-8", errors="replace")
        except HTTPError as error:
            result.update(
                status=error.code,
                success=False,
                error=error.read(2000).decode("utf-8", errors="replace"),
            )
        except URLError as error:
            result.update(status=None, success=False, error=str(error.reason))
        results.append(result)
    return jsonify(results=results), (200 if all(result["success"] for result in results) else 502)


trade_workflow = workforce_trades.register(app, sys.modules[__name__])
billing_provider = membership_billing.register(app, sys.modules[__name__])
attendance_reports.register(app, sys.modules[__name__])
historical_attendance_reports.register(app, sys.modules[__name__])
application_shell.register(app, sys.modules[__name__])
knowledge_base.register(app, sys.modules[__name__])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CBL Schedule Creator.")
    commands = parser.add_subparsers(dest="command")
    bootstrap_command = commands.add_parser(
        "bootstrap-admin",
        help="Create the first administrator for the configured tenant.",
    )
    bootstrap_command.add_argument("--email", required=True)
    bootstrap_command.add_argument("--name", required=True)
    reset_command = commands.add_parser(
        "reset-admin-password",
        help="Set a new password for an existing administrator.",
    )
    reset_command.add_argument("--email", required=True)
    mfa_reset_command = commands.add_parser(
        "reset-admin-mfa",
        help="Remove an administrator's authenticator so it can be enrolled again.",
    )
    mfa_reset_command.add_argument("--email", required=True)
    owner_command = commands.add_parser(
        "bootstrap-platform-owner",
        help="Create a platform owner who approves business registrations.",
    )
    owner_command.add_argument("--email", required=True)
    owner_command.add_argument("--name", required=True)
    owner_reset_command = commands.add_parser(
        "reset-platform-owner-password",
        help="Set a new password for a platform owner.",
    )
    owner_reset_command.add_argument("--email", required=True)
    owner_mfa_command = commands.add_parser(
        "reset-platform-owner-mfa",
        help="Remove a platform owner's authenticator so it can be enrolled again.",
    )
    owner_mfa_command.add_argument("--email", required=True)
    migration_command = commands.add_parser(
        "migrate-sqlite",
        help="Import the current SQLite business data into PostgreSQL once.",
    )
    migration_command.add_argument(
        "--source",
        type=Path,
        default=DATABASE_PATH,
        help="SQLite database to import (defaults to the app's local database).",
    )
    developer_command = commands.add_parser(
        "add-developer",
        help="Create an independent developer account using a hidden local password prompt.",
    )
    developer_command.add_argument("--username", required=True)
    arguments = parser.parse_args()
    if arguments.command == "add-developer":
        password = getpass("New developer password (14+ characters): ")
        if password != getpass("Confirm new developer password: "):
            parser.error("The passwords do not match.")
        try:
            with closing(database_connect()) as connection, connection:
                migrate_developer_accounts(connection)
                provision_developer_account(connection, arguments.username, password)
        except ValueError as error:
            parser.error(str(error))
        except database_errors() as error:
            parser.error(str(error))
        print("Developer account created. Sign in at /developer/change-requests.")
        return
    initialize_database()
    if migrate_environment_bamboohr_key():
        print(
            "The BambooHR API key from the server environment is now stored "
            "encrypted for the original business. You can remove it from .env."
        )
    if arguments.command == "bootstrap-platform-owner":
        password = getpass("Platform owner password (14+ characters): ")
        if password != getpass("Confirm platform owner password: "):
            parser.error("The passwords do not match.")
        try:
            provision_platform_owner(arguments.name, arguments.email, password)
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))
        print("Platform owner created. Sign in at /hub to enroll mandatory MFA.")
        return
    if arguments.command == "reset-platform-owner-password":
        password = getpass("New platform owner password (14+ characters): ")
        if password != getpass("Confirm new password: "):
            parser.error("The passwords do not match.")
        try:
            reset_platform_owner_password(arguments.email, password)
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))
        print("Password reset. Existing sessions are signed out.")
        return
    if arguments.command == "reset-platform-owner-mfa":
        try:
            reset_platform_owner_mfa(arguments.email)
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))
        print("MFA reset. Sign in at /hub with the password to scan a new QR code.")
        return
    if arguments.command == "migrate-sqlite":
        confirmation = input(
            "This imports SQLite data and replaces the target tenant's initial "
            "locations, employees, and settings. Type IMPORT to continue: "
        )
        if confirmation != "IMPORT":
            parser.error("SQLite migration cancelled.")
        try:
            migrate_sqlite_business_data(arguments.source)
        except (FileNotFoundError, RuntimeError) as error:
            parser.error(str(error))
        except database_errors() as error:
            parser.error(str(error))
        print("SQLite business data imported into the configured PostgreSQL tenant.")
        return
    if arguments.command == "reset-admin-mfa":
        try:
            reset_tenant_admin_mfa(arguments.email)
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))
        print("MFA reset. Sign in with the password to scan a new QR code.")
        return
    if arguments.command == "reset-admin-password":
        password = getpass("New administrator password (14+ characters): ")
        if password != getpass("Confirm new password: "):
            parser.error("The passwords do not match.")
        try:
            reset_tenant_admin_password(arguments.email, password)
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))
        print("Password reset. Existing sessions are signed out.")
        return
    if arguments.command == "bootstrap-admin":
        password = getpass("Administrator password (14+ characters): ")
        confirmation = getpass("Confirm administrator password: ")
        if password != confirmation:
            parser.error("The passwords do not match.")
        try:
            provision_tenant_admin(
                arguments.name,
                arguments.email,
                password,
            )
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))
        print(
            "Administrator created. Sign in through HTTPS to enroll mandatory MFA."
        )
        return
    port = int(os.environ.get("SCHEDULE_CREATOR_PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
