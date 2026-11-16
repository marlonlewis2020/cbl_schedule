"""Immutable attendance downloads with independently scheduled capture."""

import base64
import io
import json
import logging
import secrets
import zipfile
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta
from html import escape as html_escape
from xml.sax.saxutils import escape

from flask import Response, g, jsonify, request, session
import attendance_snapshot
import attendance_email

SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_reports (
    tenant_id TEXT NOT NULL, id TEXT NOT NULL, run_key TEXT NOT NULL,
    cutoff TEXT NOT NULL, created_at TEXT NOT NULL, state TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,run_key)
);
CREATE TABLE IF NOT EXISTS attendance_report_settings (
    tenant_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
    checked_at TEXT NOT NULL, heartbeat TEXT
);
CREATE TABLE IF NOT EXISTS executive_attendance_report_settings (
    tenant_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
    delay_hours INTEGER NOT NULL DEFAULT 0 CHECK(delay_hours BETWEEN 0 AND 24),
    checked_at TEXT NOT NULL, heartbeat TEXT
);
"""

EXECUTIVE_REPORT_PREFIX = "executive:"
EXECUTIVE_MANUAL_MARKER = ":manual:"
EXECUTIVE_MANUAL_LOOKBACK_DAYS = 14


def executive_cutoff(report_date: date, delay_hours: int, timezone) -> datetime:
    if not isinstance(report_date, date) or isinstance(delay_hours, bool) or not isinstance(delay_hours, int) or not 0 <= delay_hours <= 24:
        raise ValueError("Choose a reporting-day delay from 0 to 24 whole hours.")
    day_end = datetime.combine(report_date + timedelta(days=1), time.min, tzinfo=timezone)
    return day_end + timedelta(hours=delay_hours)


def workbook(payload):
    """Write string-only XLSX cells so employee data can never become formulas."""
    data = payload["attendance"]
    groups = defaultdict(lambda: [0, 0, 0, 0, 0])
    for row in data["shifts"]:
        leave = row["status"] in {"approved_leave", "sick", "vacation"}
        present = row["status"] in {"attended", "late"}
        for key in ((row["location"], "All roles", "All shifts"),
                    (row["location"], row["role"], "All shifts"),
                    (row["location"], row["role"], row["shiftStart"][11:16])):
            values = groups[key]
            values[0] += not leave
            values[1] += present
            values[2] += row["status"] == "absent"
            values[3] += leave
            values[4] += row["status"] == "scheduled"
    sheets = [
        ("Summary", [
            ["Attendance snapshot", payload["cutoff"], "America/Jamaica"],
            ["Shift source", data.get("shiftSource", {}).get("selected", "Unavailable")],
            ["Generated", payload["generatedAt"], "Source refreshed", data.get("lastSyncedAt") or "Never"],
            ["Refresh status", payload["refreshError"] or "Refreshed", "Today plus overnight carry-in; future shifts and approved leave excluded from denominator"],
            ["Location", "Role", "Shift start", "Expected so far", "Present", "Absent", "Approved leave", "Pending", "Attendance %"],
            *[[*key, *values, round(values[1] * 100 / values[0], 2) if values[0] else "N/A"]
              for key, values in sorted(groups.items())],
        ]),
        ("Attendance", [
            ["Employee", "Employee ID", "Location", "Role", "Shift start", "Status", "Clock in", "Clock out",
             "Worked minutes", "Early minutes", "Overtime minutes", "Reason", "Shift end"],
            *[[r["name"], r["employeeId"], r["location"], r["role"], r["shiftStart"], r["status"],
               r["clockIn"] or "", r["clockOut"] or "Open / unavailable", r["workedMinutes"],
               r["earlyMinutes"], r["overtimeMinutes"], r["reason"], r.get("shiftEnd", "Unavailable")] for r in data["shifts"]],
        ]),
    ]
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    styles = f'''<styleSheet xmlns="{ns}"><fonts count="4"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/></font><font><color rgb="FF9C6500"/></font><font><color rgb="FFB91C1C"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF086FA0"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="4"><xf fontId="0"/><xf fontId="1" fillId="2" applyFill="1"/><xf fontId="2"/><xf fontId="3"/></cellXfs></styleSheet>'''
    def safe(value):
        return escape("".join(c for c in str(value if value is not None else "") if c in "\t\n\r" or ord(c) >= 32))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in (1, 2))+"</Types>")
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i, (name, _) in enumerate(sheets, 1))+"</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in (1, 2))+'<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", styles)
        for i, (_, rows) in enumerate(sheets, 1):
            body = []
            for number, row in enumerate(rows, 1):
                header = number == (4 if i == 1 else 1)
                status = row[5] if i == 2 and number > 1 else ""
                cells = []
                for col, value in enumerate(row):
                    style = 1 if header else 2 if col == 0 and status == "late" else 3 if col == 0 and status == "absent" else 0
                    cells.append(f'<c s="{style}" t="inlineStr"><is><t xml:space="preserve">{safe(value)}</t></is></c>')
                body.append(f'<row r="{number}">{"".join(cells)}</row>')
            z.writestr(f"xl/worksheets/sheet{i}.xml", f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="{4 if i == 1 else 1}" topLeftCell="A{5 if i == 1 else 2}" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="13" width="24" customWidth="1"/></cols><sheetData>{"".join(body)}</sheetData></worksheet>')
    return out.getvalue()


def eligible(s, c, tenant):
    return s.tenant_membership_tier(c, tenant) in {"silver", "gold", "platinum"}


def capture(s, tenant, cutoff, run_key, missed=False, now=None):
    now = now or datetime.now(s.ATTENDANCE_TIMEZONE)
    report_id = secrets.token_urlsafe(18)
    with closing(s.database_connect()) as c, c:
        claimed = c.execute(
            "INSERT INTO attendance_reports(tenant_id,id,run_key,cutoff,created_at,state,error) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(tenant_id,run_key) DO NOTHING",
            (tenant, report_id, run_key, cutoff.isoformat(), now.isoformat(),
             "missed" if missed else "running", "Scheduled cutoff missed; no historical capture fabricated." if missed else ""),
        ).rowcount
    if not claimed or missed:
        return report_id if claimed else None
    try:
        refresh_error = ""
        shifts = None
        key = s.bamboohr_api_key()
        try:
            if not key:
                raise s.AttendanceIntegrationError("BambooHR API key is not configured.")
            start = (cutoff.date() - timedelta(days=1)).isoformat()
            end = cutoff.date().isoformat()
            clocks = s.parse_bamboohr_clock_entries(s.bamboohr_json(key, "time_tracking/timesheet_entries", {"start": start, "end": end}, "time-tracking"))
            leave = s.parse_bamboohr_time_off(s.bamboohr_json(key, "time_off/whos_out", {"start": start, "end": end}, "time-off"))
            with closing(s.database_connect()) as c, c:
                shifts = s.fetch_bamboohr_scheduled_shifts(c, cutoff.date() - timedelta(days=1), cutoff.date(), attendance_mode=True) if s.attendance_shift_source(c) == "bamboohr" else None
                s.sync_attendance_data(c, clocks, leave, now=cutoff, period_start=cutoff.date() - timedelta(days=1), period_end=cutoff.date(), bamboo_shifts=shifts)
        except s.AttendanceIntegrationError as error:
            refresh_error = str(error)
            logging.warning("Attendance snapshot source refresh failed for tenant %s: %s", tenant, error)
        with closing(s.database_connect()) as c:
            data = s.attendance_payload(c, now=cutoff, period_start=cutoff.date() - timedelta(days=1), period_end=cutoff.date())
            spans = {}
            for run_id, encoded in c.execute("SELECT run_id,payload FROM accepted_schedules WHERE tenant_id=?", (tenant,)):
                spans[run_id] = float(json.loads(encoded).get("controls", {}).get("span", 8))
            for shift in shifts or []:
                spans["bamboohr:" + str(shift["id"])] = (datetime.fromisoformat(shift["end"]) - datetime.fromisoformat(shift["start"])).total_seconds() / 3600
        midnight = datetime.combine(cutoff.date(), datetime.min.time(), tzinfo=s.ATTENDANCE_TIMEZONE)
        selected = []
        for row in data["shifts"]:
            begin = datetime.fromisoformat(row["shiftStart"])
            span = spans.get(row["runId"])
            end = begin + timedelta(hours=span) if span is not None else None
            row["shiftEnd"] = end.isoformat() if end else "Unavailable"
            if begin >= midnight or (end and end > midnight):
                selected.append(row)
            elif row["runId"].startswith("bamboohr:") and span is None:
                refresh_error = refresh_error or "Previous-day BambooHR boundaries unavailable; overnight coverage incomplete."
        data["shifts"] = selected
        if refresh_error and data["lastSyncedAt"] and datetime.fromisoformat(data["lastSyncedAt"]) > cutoff:
            data["shifts"] = []
            refresh_error += " Cached evidence is newer than the cutoff and has been excluded."
        rows = data["shifts"]
        expected = sum(r["status"] not in {"approved_leave", "sick", "vacation"} for r in rows)
        present = sum(r["status"] in {"attended", "late"} for r in rows)
        data["summary"] = {
            "expected": expected, "clockedIn": present,
            "attendancePercent": round(present * 100 / expected, 2) if expected else None,
            "late": sum(r["status"] == "late" for r in rows),
            "absent": sum(r["status"] == "absent" for r in rows),
            "approvedLeave": sum(r["status"] in {"approved_leave", "sick", "vacation"} for r in rows),
        }
        branding = s.current_app_config()
        logo = s.validate_logo_data_url(branding.get("logoDataUrl", ""))
        if logo is None:
            raise ValueError("The saved business logo is invalid. Update branding before capturing a report.")
        raw_images = branding.get("supportingImages", [])
        if not isinstance(raw_images, list) or len(raw_images) > 2:
            raise ValueError("Business supporting images are invalid. Update branding before capturing a report.")
        supporting_images = [s.validate_logo_data_url(image) for image in raw_images if image]
        if any(image is None for image in supporting_images):
            raise ValueError("A business supporting image is invalid. Update branding before capturing a report.")
        report_theme = branding.get("reportTheme", "light")
        if not isinstance(report_theme, str) or report_theme not in {"light", "dark"}:
            report_theme = "light"
        payload = {"cutoff": cutoff.isoformat(), "generatedAt": now.isoformat(),
                   "businessName": branding["businessName"], "logoDataUrl": logo,
                   "supportingImages": supporting_images, "reportTheme": report_theme,
                   "primaryColor": branding.get("primaryColor", "#176bd5"),
                   "accentColor": branding.get("accentColor", "#079998"),
                   "refreshError": refresh_error, "attendance": data}
        payload["workbook"] = base64.b64encode(workbook(payload)).decode("ascii")
        payload["html"] = attendance_snapshot.render(payload)
        with closing(s.database_connect()) as c, c:
            saved = c.execute("UPDATE attendance_reports SET state=?,payload=?,error=? WHERE tenant_id=? AND id=? AND state='running'",
                              ("stale" if refresh_error else "ready", json.dumps(payload), refresh_error, tenant, report_id)).rowcount
            if not saved:
                raise RuntimeError("The capture claim expired; request a new on-demand snapshot.")
    except Exception as error:
        # Persist an explicit failure, then propagate it to the caller/worker.
        with closing(s.database_connect()) as c, c:
            c.execute("UPDATE attendance_reports SET state='failed',error=? WHERE tenant_id=? AND id=? AND state='running'",
                      (str(error)[:1000], tenant, report_id))
        raise
    return report_id


def executive_report_metrics(shifts, report_date, generated_at):
    leave_statuses = {"approved_leave", "sick", "vacation"}
    locations = defaultdict(lambda: {
        "planned": 0, "actual": 0, "late": 0, "absent": 0,
        "missingClockIns": 0, "earlyDepartures": 0, "overtimeMinutes": 0,
        "leave": 0,
    })
    totals = {
        "planned": 0, "actual": 0, "late": 0, "absent": 0,
        "missingClockIns": 0, "earlyDepartures": 0, "overtimeMinutes": 0,
        "leave": 0, "incompleteOvernight": 0, "unknownShiftEnds": 0,
    }
    for row in shifts:
        location = str(row.get("location") or "Unassigned")
        values = locations[location]
        if row.get("status") in leave_statuses:
            values["leave"] += 1
            totals["leave"] += 1
            continue
        values["planned"] += 1
        totals["planned"] += 1
        if row.get("status") in {"attended", "late"}:
            values["actual"] += 1
            totals["actual"] += 1
        if row.get("status") == "late":
            values["late"] += 1
            totals["late"] += 1
        if row.get("status") == "absent":
            values["absent"] += 1
            totals["absent"] += 1
        if not row.get("clockIn"):
            values["missingClockIns"] += 1
            totals["missingClockIns"] += 1
        if row.get("earlyMinutes"):
            values["earlyDepartures"] += 1
            totals["earlyDepartures"] += 1
        values["overtimeMinutes"] += int(row.get("overtimeMinutes") or 0)
        totals["overtimeMinutes"] += int(row.get("overtimeMinutes") or 0)
        shift_end = row.get("shiftEnd")
        if shift_end and shift_end != "Unavailable":
            try:
                shift_end_at = datetime.fromisoformat(shift_end)
                if shift_end_at.date() > report_date and shift_end_at > generated_at:
                    totals["incompleteOvernight"] += 1
            except (TypeError, ValueError):
                totals["unknownShiftEnds"] += 1
        else:
            totals["unknownShiftEnds"] += 1
    location_rows = []
    for name, values in sorted(locations.items(), key=lambda item: item[0].casefold()):
        location_rows.append({
            "location": name,
            **values,
            "attendancePercent": round(100 * values["actual"] / values["planned"], 2)
            if values["planned"] else None,
        })
    totals["attendancePercent"] = round(100 * totals["actual"] / totals["planned"], 2) if totals["planned"] else None
    totals["locationCount"] = len(location_rows)
    return totals, location_rows


def executive_html(payload):
    summary = payload["summary"]
    number = lambda value: f"{int(value):,}"
    percent = lambda value: f"{value:.1f}%" if value is not None else "N/A"
    locations = "".join(
        "<tr><td>" + html_escape(row["location"]) + "</td><td>" + number(row["planned"])
        + "</td><td>" + number(row["actual"]) + "</td><td>" + percent(row["attendancePercent"])
        + "</td><td>" + number(row["late"]) + "</td><td>" + number(row["absent"])
        + "</td><td>" + number(row["leave"]) + "</td></tr>"
        for row in payload["locations"]
    )
    warning = (
        "<p class=warning>Source warning: " + html_escape(payload["refreshError"]) + "</p>"
        if payload["refreshError"] else ""
    )
    if payload.get("partialDay"):
        warning += (
            "<p class=warning>Partial day: generated before the reporting day ended. "
            "Shifts after the generation time are not yet final.</p>"
        )
    trigger = " · Manually generated" if payload.get("trigger") == "manual" else ""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; object-src 'none'">
<title>Executive attendance report</title><style>
*{box-sizing:border-box}body{margin:0;background:#eef5f7;color:#173340;font:15px/1.5 Segoe UI,Arial,sans-serif}
main{max-width:1180px;margin:auto;padding:28px}header{border-bottom:3px solid #087f8c;padding-bottom:18px;margin-bottom:22px}
h1{font-size:30px;margin:0}h2{font-size:19px;margin:0 0 14px}.meta{color:#526a73}.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:22px 0}
.kpi,section{background:#fff;border:1px solid #d5e1e4;border-radius:8px;padding:18px}.kpi span{display:block;color:#526a73;font-size:13px}.kpi strong{display:block;font-size:28px;margin-top:8px}
section{margin:18px 0}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #d5e1e4}th{background:#f2f7f8;color:#405c65}
.warning{border-left:4px solid #bd3045;background:#fff0f2;padding:12px}.note{color:#526a73;font-size:13px}
@media(max-width:700px){main{padding:14px}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}section{overflow-x:auto}}
@media print{body{background:#fff}main{max-width:none;padding:0}.kpi,section{break-inside:avoid}}
</style></head><body><main><header><p class=meta>""" + html_escape(payload["businessName"]) + "</p><h1>Executive end-of-day attendance</h1><p class=meta>Reporting day " + html_escape(payload["reportDate"]) + " · Generated " + html_escape(payload["generatedAt"]) + " · America/Jamaica" + trigger + "</p><p class=meta>Shift source: " + html_escape(payload["shiftSource"]) + " · Source refreshed: " + html_escape(payload["lastSyncedAt"] or "Unavailable") + "</p></header>" + warning + "<div class=kpis><div class=kpi><span>Scheduled shifts</span><strong>" + number(summary["planned"]) + "</strong></div><div class=kpi><span>Attended / late</span><strong>" + number(summary["actual"]) + "</strong></div><div class=kpi><span>Attendance rate</span><strong>" + percent(summary["attendancePercent"]) + "</strong></div><div class=kpi><span>Late / absent</span><strong>" + number(summary["late"]) + " / " + number(summary["absent"]) + "</strong></div></div><section><h2>Location performance</h2><table><thead><tr><th>Location</th><th>Scheduled</th><th>Attended / late</th><th>Attendance</th><th>Late</th><th>Absent</th><th>Leave</th></tr></thead><tbody>" + locations + "</tbody></table></section><section><h2>Significant exceptions</h2><p>Late arrivals: <strong>" + number(summary["late"]) + "</strong> · Absences: <strong>" + number(summary["absent"]) + "</strong> · Missing clock-ins: <strong>" + number(summary["missingClockIns"]) + "</strong> · Early departures: <strong>" + number(summary["earlyDepartures"]) + "</strong> · Overtime: <strong>" + number(summary["overtimeMinutes"]) + " minutes</strong></p><p>Incomplete overnight shifts: <strong>" + number(summary["incompleteOvernight"]) + "</strong> · Unknown shift ends: <strong>" + number(summary["unknownShiftEnds"]) + "</strong></p><p class=note>Shifts are attributed to their start date; approved leave is excluded from expected staffing. This report aggregates by location and does not include an employee register.</p></section></main></body></html>"


def capture_executive(s, tenant, report_date, cutoff, delay_hours, missed=False, now=None, manual=False):
    now = now or datetime.now(s.ATTENDANCE_TIMEZONE)
    report_id = secrets.token_urlsafe(18)
    run_key = EXECUTIVE_REPORT_PREFIX + report_date.isoformat()
    if manual:
        # Manual runs never claim the scheduled run key, so the worker still generates that day.
        run_key += EXECUTIVE_MANUAL_MARKER + report_id
    with closing(s.database_connect()) as connection, connection:
        claimed = connection.execute(
            "INSERT INTO attendance_reports(tenant_id,id,run_key,cutoff,created_at,state,error) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(tenant_id,run_key) DO NOTHING",
            (tenant, report_id, run_key, cutoff.isoformat(), now.isoformat(),
             "missed" if missed else "running",
             "Scheduled executive report cutoff missed; no late capture fabricated." if missed else ""),
        ).rowcount
    if not claimed or missed:
        return report_id if claimed else None
    try:
        refresh_error = ""
        bamboo_shifts = None
        api_key = s.bamboohr_api_key()
        report_end = report_date + timedelta(days=1)
        try:
            if not api_key:
                raise s.AttendanceIntegrationError("BambooHR API key is not configured.")
            clocks = s.parse_bamboohr_clock_entries(s.bamboohr_json(
                api_key, "time_tracking/timesheet_entries",
                {"start": report_date.isoformat(), "end": report_end.isoformat()}, "time-tracking",
            ))
            leave = s.parse_bamboohr_time_off(s.bamboohr_json(
                api_key, "time_off/whos_out",
                {"start": report_date.isoformat(), "end": report_end.isoformat()}, "time-off",
            ))
            with closing(s.database_connect()) as connection, connection:
                if s.attendance_shift_source(connection) == "bamboohr":
                    bamboo_shifts = s.fetch_bamboohr_scheduled_shifts(
                        connection, report_date, report_end, attendance_mode=True,
                    )
                s.sync_attendance_data(
                    connection, clocks, leave, now=now, period_start=report_date,
                    period_end=report_end, bamboo_shifts=bamboo_shifts,
                )
        except s.AttendanceIntegrationError as error:
            refresh_error = str(error)
            logging.warning("Executive attendance refresh failed for tenant %s: %s", tenant, error)
        with closing(s.database_connect()) as connection:
            attendance = s.attendance_payload(
                connection, now=now, period_start=report_date, period_end=report_date,
            )
            spans = {}
            for run_id, encoded in connection.execute(
                "SELECT run_id,payload FROM accepted_schedules WHERE tenant_id=?", (tenant,),
            ):
                spans[run_id] = float(json.loads(encoded).get("controls", {}).get("span", 8))
            for shift in bamboo_shifts or []:
                spans["bamboohr:" + str(shift["id"])] = (
                    datetime.fromisoformat(shift["end"]) - datetime.fromisoformat(shift["start"])
                ).total_seconds() / 3600
        for row in attendance["shifts"]:
            if row.get("shiftEndAt"):
                row["shiftEnd"] = row["shiftEndAt"]
            else:
                span = spans.get(row["runId"])
                if span is not None:
                    row["shiftEnd"] = (datetime.fromisoformat(row["shiftStart"]) + timedelta(hours=span)).isoformat()
                else:
                    row["shiftEnd"] = "Unavailable"
        summary, locations = executive_report_metrics(attendance["shifts"], report_date, now)
        branding = s.current_app_config()
        payload = {
            "reportType": "executive_end_of_day", "reportDate": report_date.isoformat(),
            "cutoff": cutoff.isoformat(), "generatedAt": now.isoformat(),
            "businessName": branding.get("businessName", "Workforce"),
            "shiftSource": attendance.get("shiftSource", {}).get("selected", "Unavailable"),
            "lastSyncedAt": attendance.get("lastSyncedAt"), "refreshError": refresh_error,
            "delayHours": delay_hours, "summary": summary, "locations": locations,
            "trigger": "manual" if manual else "scheduled",
            "partialDay": now.date() <= report_date,
        }
        payload["html"] = executive_html(payload)
        with closing(s.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE attendance_reports SET state=?,payload=?,error=? WHERE tenant_id=? AND id=? AND state='running'",
                ("stale" if refresh_error else "ready", json.dumps(payload), refresh_error, tenant, report_id),
            )
    except Exception as error:
        with closing(s.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE attendance_reports SET state='failed',error=? WHERE tenant_id=? AND id=? AND state='running'",
                (str(error)[:1000], tenant, report_id),
            )
        raise
    return report_id


def run_executive_once(s, now=None):
    now = now or datetime.now(s.ATTENDANCE_TIMEZONE)
    with closing(s.database_connect()) as connection:
        tenants = connection.execute(
            "SELECT tenant_id FROM tenants WHERE status='active' AND membership_status='active'"
        ).fetchall()
    for (tenant,) in tenants:
        g.tenant_id = tenant
        with closing(s.database_connect()) as connection, connection:
            setting = connection.execute(
                "SELECT enabled,delay_hours,checked_at FROM executive_attendance_report_settings WHERE tenant_id=?",
                (tenant,),
            ).fetchone()
            if not setting or not setting[0] or s.membership_billing.access_suspended(connection, tenant):
                continue
            tier = s.tenant_membership_tier(connection, tenant)
            features = s.membership_billing.features(
                connection, tier, s.MEMBERSHIP_TIERS[tier]["features"],
            )
            if not features.get("executiveEndOfDayReport"):
                continue
            delay_hours = int(setting[1])
            previous = datetime.fromisoformat(setting[2])
        cursor = previous.date() - timedelta(days=2)
        while cursor <= now.date():
            cutoff = executive_cutoff(cursor, delay_hours, s.ATTENDANCE_TIMEZONE)
            if previous < cutoff <= now:
                missed = now - cutoff > timedelta(minutes=2)
                try:
                    capture_executive(s, tenant, cursor, cutoff, delay_hours, missed=missed, now=now)
                except Exception:
                    logging.exception("Executive attendance report failed for tenant %s, date %s", tenant, cursor)
            cursor += timedelta(days=1)
        with closing(s.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE executive_attendance_report_settings SET checked_at=?,heartbeat=? WHERE tenant_id=? AND checked_at=?",
                (now.isoformat(), now.isoformat(), tenant, setting[2]),
            )


def run_once(s, now=None):
    now = now or datetime.now(s.ATTENDANCE_TIMEZONE)
    with closing(s.database_connect()) as c:
        tenants = c.execute("SELECT tenant_id FROM tenants WHERE status='active' AND membership_status='active'").fetchall()
    for (tenant,) in tenants:
        g.tenant_id = tenant
        with closing(s.database_connect()) as c, c:
            setting = c.execute("SELECT enabled,checked_at FROM attendance_report_settings WHERE tenant_id=?", (tenant,)).fetchone()
            if not setting or not setting[0] or not eligible(s, c, tenant) or s.membership_billing.access_suspended(c, tenant):
                continue
            previous = datetime.fromisoformat(setting[1])
            # Record abandoned claims explicitly; never repeat an unknown capture.
            c.execute("UPDATE attendance_reports SET state='failed',error='Capture interrupted; request a new on-demand snapshot.' WHERE tenant_id=? AND state='running' AND created_at<?",
                      (tenant, (now - timedelta(minutes=15)).isoformat()))
        cursor = previous.date()
        while cursor <= now.date():
            for hour in (7, 15, 23):
                cutoff = datetime.combine(cursor, datetime.min.time(), tzinfo=s.ATTENDANCE_TIMEZONE).replace(hour=hour)
                if previous < cutoff <= now:
                    try:
                        capture(s, tenant, cutoff, "scheduled:" + cutoff.isoformat(),
                                missed=(now - cutoff).total_seconds() > 120, now=now)
                    except Exception:
                        logging.exception("Attendance report capture failed for tenant %s", tenant)
            cursor += timedelta(days=1)
        with closing(s.database_connect()) as c, c:
            c.execute("UPDATE attendance_report_settings SET checked_at=?,heartbeat=? WHERE tenant_id=? AND checked_at=?",
                      (now.isoformat(), now.isoformat(), tenant, previous.isoformat()))
    run_executive_once(s, now)


def register(app, s):
    @app.after_request
    def report_cache_headers(response):
        if request.path.startswith(("/api/attendance/reports", "/api/attendance/executive-reports")):
            response.headers["Cache-Control"] = "no-store"
        return response

    def guard():
        denied = s.primary_admin_guard() if request.method == "PUT" else None
        if denied:
            return denied
        with closing(s.database_connect()) as c:
            if not eligible(s, c, s.active_tenant_id()):
                return jsonify(error="Attendance snapshots require Silver or above."), 403
        if request.method in {"POST", "DELETE"} and not s.tenant_auth_csrf_valid():
            return jsonify(error="The request token is invalid."), 400
        return None

    @app.route("/api/attendance/reports", methods=["GET", "POST", "PUT"])
    def reports():
        denied = guard()
        if denied:
            return denied
        tenant = s.active_tenant_id()
        now = datetime.now(s.ATTENDANCE_TIMEZONE)
        if request.method == "PUT":
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict) or type(payload.get("enabled")) is not bool:
                return jsonify(error="Choose whether scheduled downloads are enabled."), 400
            with closing(s.database_connect()) as c, c:
                c.execute("INSERT INTO attendance_report_settings(tenant_id,enabled,checked_at) VALUES(?,?,?) ON CONFLICT(tenant_id) DO UPDATE SET enabled=excluded.enabled,checked_at=excluded.checked_at",
                          (tenant, int(payload["enabled"]), now.isoformat()))
            return jsonify(saved=True)
        if request.method == "POST":
            with closing(s.database_connect()) as c:
                recent = c.execute("SELECT 1 FROM attendance_reports WHERE tenant_id=? AND run_key NOT LIKE ? AND run_key NOT LIKE ? AND created_at>? LIMIT 1",
                                   (tenant, "historical:%", EXECUTIVE_REPORT_PREFIX + "%", (now - timedelta(seconds=60)).isoformat())).fetchone()
            if recent:
                return jsonify(error="Wait one minute between report requests."), 429
            report_id = capture(s, tenant, now, "manual:" + secrets.token_urlsafe(18))
            return jsonify(id=report_id), 201
        with closing(s.database_connect()) as c:
            rows = c.execute("SELECT id,cutoff,created_at,state,error FROM attendance_reports WHERE tenant_id=? AND run_key NOT LIKE ? AND run_key NOT LIKE ? AND state<>'deleted' ORDER BY created_at DESC LIMIT 100", (tenant, "historical:%", EXECUTIVE_REPORT_PREFIX + "%")).fetchall()
            setting = c.execute("SELECT enabled,heartbeat FROM attendance_report_settings WHERE tenant_id=?", (tenant,)).fetchone()
        return jsonify(reports=[dict(zip(("id", "cutoff", "createdAt", "state", "error"), row)) for row in rows],
                       enabled=bool(setting and setting[0]), heartbeat=setting[1] if setting else None,
                       emailStatus="Automatic email deferred; downloads only.")

    @app.delete("/api/attendance/reports")
    def delete_reports():
        denied = guard()
        if denied:
            return denied
        body = request.get_json(silent=True)
        ids = body.get("ids") if isinstance(body, dict) else None
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(not isinstance(value, str) or not value or len(value) > 128 for value in ids) or len(set(ids)) != len(ids):
            return jsonify(error="Select between 1 and 100 distinct snapshots."), 400
        if body.get("confirm") is not True:
            return jsonify(error="Confirm deletion of the selected snapshots."), 400
        tenant = s.active_tenant_id()
        placeholders = ",".join("?" for _ in ids)
        with closing(s.database_connect()) as c, c:
            rows = c.execute(f"SELECT id,state FROM attendance_reports WHERE tenant_id=? AND run_key NOT LIKE ? AND run_key NOT LIKE ? AND id IN ({placeholders})", (tenant, "historical:%", EXECUTIVE_REPORT_PREFIX + "%", *ids)).fetchall()
            if len(rows) != len(ids):
                return jsonify(error="One or more snapshots are unavailable. Refresh history before deleting."), 404
            if any(state in {"running", "deleted"} for _, state in rows):
                return jsonify(error="Running or already deleted snapshots cannot be deleted. Refresh history."), 409
            changed = c.execute(
                f"UPDATE attendance_reports SET state='deleted',payload='{{}}',error='' WHERE tenant_id=? AND run_key NOT LIKE ? AND run_key NOT LIKE ? AND id IN ({placeholders}) AND state NOT IN ('running','deleted')",
                (tenant, "historical:%", EXECUTIVE_REPORT_PREFIX + "%", *ids),
            ).rowcount
            if changed != len(ids):
                c.rollback()
                return jsonify(error="Snapshot history changed during deletion. Refresh and retry."), 409
            # Keep run keys as tombstones so scheduled cutoffs are never regenerated.
            c.execute("INSERT INTO tenant_audit_events(id,tenant_id,actor_id,actor_email,action,route,response_status) VALUES(?,?,?,?,?,?,?)",
                      (secrets.token_urlsafe(18), tenant, session.get("tenant_admin_id"), session.get("tenant_admin_email"),
                       json.dumps({"action": "attendance-snapshots-deleted", "ids": ids}), "delete_reports", 200))
        return jsonify(deleted=ids)

    def saved_report(report_id):
        denied = guard()
        if denied:
            return None, denied
        with closing(s.database_connect()) as c:
            row = c.execute("SELECT payload,state FROM attendance_reports WHERE tenant_id=? AND id=? AND run_key NOT LIKE ? AND run_key NOT LIKE ?",
                            (s.active_tenant_id(), report_id, "historical:%", EXECUTIVE_REPORT_PREFIX + "%")).fetchone()
        if not row:
            return None, (jsonify(error="Snapshot not found."), 404)
        if row[1] not in {"ready", "stale"}:
            return None, (jsonify(error="This capture has no downloadable report."), 409)
        return json.loads(row[0]), None

    @app.get("/api/attendance/reports/<report_id>/download")
    def download_report(report_id):
        payload, denied = saved_report(report_id)
        if denied:
            return denied
        return Response(base64.b64decode(payload["workbook"]),
                        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="attendance-{report_id}.xlsx"',
                                 "Cache-Control": "no-store"})

    @app.get("/api/attendance/reports/<report_id>/html")
    @app.get("/api/attendance/reports/<report_id>/html/download")
    def html_report(report_id):
        payload, denied = saved_report(report_id)
        if denied:
            return denied
        # Older captures use saved evidence only, never current branding or provider data.
        html = payload["html"] if "html" in payload else attendance_snapshot.render(payload)
        disposition = "attachment" if request.path.endswith("/download") else "inline"
        return Response(html, mimetype="text/html",
                        headers={"Content-Disposition": f'{disposition}; filename="attendance-{report_id}.html"',
                                 "Cache-Control": "no-store",
                                 "Referrer-Policy": "no-referrer",
                                 "Content-Security-Policy": "frame-ancestors 'none'"})

    @app.get("/api/attendance/reports/<report_id>/email")
    def email_body(report_id):
        payload, denied = saved_report(report_id)
        if denied:
            return denied
        return jsonify(attendance_email.generate(payload))

    def executive_guard(write=False):
        denied = s.membership_feature_denied("executiveEndOfDayReport")
        if denied:
            return denied
        if write:
            denied = s.primary_admin_guard()
            if denied:
                return denied
            if not s.tenant_auth_csrf_valid():
                return jsonify(error="The request token is invalid. Reload the page and retry."), 400
        return None

    @app.route("/api/attendance/executive-reports", methods=["GET", "PUT"])
    def executive_reports():
        denied = executive_guard(write=request.method == "PUT")
        if denied:
            return denied
        tenant = s.active_tenant_id()
        with closing(s.database_connect()) as connection:
            if request.method == "PUT":
                payload = request.get_json(silent=True)
                enabled = payload.get("enabled") if isinstance(payload, dict) else None
                delay_hours = payload.get("delayHours") if isinstance(payload, dict) else None
                if (
                    type(enabled) is not bool
                    or isinstance(delay_hours, bool)
                    or not isinstance(delay_hours, int)
                    or not 0 <= delay_hours <= 24
                ):
                    return jsonify(error="Enable or disable the report and choose a whole-hour delay from 0 to 24."), 400
                now = datetime.now(s.ATTENDANCE_TIMEZONE).isoformat()
                with connection:
                    connection.execute(
                        "INSERT INTO executive_attendance_report_settings(tenant_id,enabled,delay_hours,checked_at) VALUES(?,?,?,?) "
                        "ON CONFLICT(tenant_id) DO UPDATE SET enabled=excluded.enabled,delay_hours=excluded.delay_hours,checked_at=excluded.checked_at",
                        (tenant, int(enabled), delay_hours, now),
                    )
                return jsonify(saved=True, enabled=enabled, delayHours=delay_hours)
            setting = connection.execute(
                "SELECT enabled,delay_hours,checked_at,heartbeat FROM executive_attendance_report_settings WHERE tenant_id=?",
                (tenant,),
            ).fetchone()
            rows = connection.execute(
                "SELECT id,run_key,cutoff,created_at,state,error FROM attendance_reports "
                "WHERE tenant_id=? AND run_key LIKE ? AND state<>'deleted' "
                "ORDER BY cutoff DESC LIMIT 100",
                (tenant, EXECUTIVE_REPORT_PREFIX + "%"),
            ).fetchall()
        return jsonify(
            enabled=bool(setting and setting[0]), delayHours=int(setting[1]) if setting else 0,
            checkedAt=setting[2] if setting else None, heartbeat=setting[3] if setting else None,
            reports=[{
                "id": row[0], "reportDate": row[1].removeprefix(EXECUTIVE_REPORT_PREFIX).split(":", 1)[0],
                "trigger": "manual" if EXECUTIVE_MANUAL_MARKER in row[1] else "scheduled",
                "cutoff": row[2], "createdAt": row[3], "state": row[4], "error": row[5],
            } for row in rows],
        )

    @app.post("/api/attendance/executive-reports/generate")
    def generate_executive_report():
        denied = executive_guard()
        if denied:
            return denied
        if not s.tenant_auth_csrf_valid():
            return jsonify(error="The request token is invalid. Reload the page and retry."), 400
        body = request.get_json(silent=True)
        raw_date = body.get("reportDate") if isinstance(body, dict) else None
        now = datetime.now(s.ATTENDANCE_TIMEZONE)
        try:
            report_date = date.fromisoformat(raw_date) if isinstance(raw_date, str) and len(raw_date) == 10 else None
        except ValueError:
            report_date = None
        earliest = now.date() - timedelta(days=EXECUTIVE_MANUAL_LOOKBACK_DAYS)
        if report_date is None or not earliest <= report_date <= now.date():
            return jsonify(
                error=f"Choose a reporting day from {earliest.isoformat()} to {now.date().isoformat()}.",
            ), 400
        tenant = s.active_tenant_id()
        with closing(s.database_connect()) as connection:
            recent = connection.execute(
                "SELECT 1 FROM attendance_reports WHERE tenant_id=? AND run_key LIKE ? AND created_at>? LIMIT 1",
                (tenant, EXECUTIVE_REPORT_PREFIX + "%" + EXECUTIVE_MANUAL_MARKER + "%",
                 (now - timedelta(seconds=60)).isoformat()),
            ).fetchone()
            setting = connection.execute(
                "SELECT delay_hours FROM executive_attendance_report_settings WHERE tenant_id=?", (tenant,),
            ).fetchone()
        if recent:
            return jsonify(error="Wait one minute between manual executive reports."), 429
        cutoff = min(now, executive_cutoff(report_date, 0, s.ATTENDANCE_TIMEZONE))
        try:
            report_id = capture_executive(
                s, tenant, report_date, cutoff, int(setting[0]) if setting else 0, now=now, manual=True,
            )
        except Exception:
            logging.getLogger(__name__).exception("Manual executive report failed for tenant %s", tenant)
            return jsonify(error="The executive report could not be generated. The failure is recorded in the report history."), 500
        with closing(s.database_connect()) as connection:
            state = connection.execute(
                "SELECT state FROM attendance_reports WHERE tenant_id=? AND id=?", (tenant, report_id),
            ).fetchone()
        return jsonify(id=report_id, state=state[0] if state else "failed", reportDate=report_date.isoformat()), 201

    @app.get("/api/attendance/executive-reports/<report_id>/download")
    def download_executive_report(report_id):
        denied = executive_guard()
        if denied:
            return denied
        with closing(s.database_connect()) as connection:
            row = connection.execute(
                "SELECT payload,state FROM attendance_reports WHERE tenant_id=? AND id=? AND run_key LIKE ?",
                (s.active_tenant_id(), report_id, EXECUTIVE_REPORT_PREFIX + "%"),
            ).fetchone()
        if not row:
            return jsonify(error="Executive report not found."), 404
        if row[1] not in {"ready", "stale"}:
            return jsonify(error="This executive report has no downloadable file."), 409
        payload = json.loads(row[0])
        suffix = "-manual" if payload.get("trigger") == "manual" else ""
        return Response(
            payload["html"], mimetype="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="executive-attendance-{payload["reportDate"]}{suffix}.html"',
                "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; object-src 'none'",
                "X-Content-Type-Options": "nosniff",
            },
        )
