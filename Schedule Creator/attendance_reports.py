"""Immutable attendance downloads with independently scheduled capture."""

import base64
import io
import json
import logging
import secrets
import zipfile
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta
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
"""


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
        payload = {"cutoff": cutoff.isoformat(), "generatedAt": now.isoformat(),
                   "businessName": branding["businessName"], "logoDataUrl": logo,
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


def register(app, s):
    @app.after_request
    def report_cache_headers(response):
        if request.path.startswith("/api/attendance/reports"):
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
                recent = c.execute("SELECT 1 FROM attendance_reports WHERE tenant_id=? AND run_key NOT LIKE 'historical:%' AND created_at>? LIMIT 1",
                                   (tenant, (now - timedelta(seconds=60)).isoformat())).fetchone()
            if recent:
                return jsonify(error="Wait one minute between report requests."), 429
            report_id = capture(s, tenant, now, "manual:" + secrets.token_urlsafe(18))
            return jsonify(id=report_id), 201
        with closing(s.database_connect()) as c:
            rows = c.execute("SELECT id,cutoff,created_at,state,error FROM attendance_reports WHERE tenant_id=? AND run_key NOT LIKE 'historical:%' AND state<>'deleted' ORDER BY created_at DESC LIMIT 100", (tenant,)).fetchall()
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
            rows = c.execute(f"SELECT id,state FROM attendance_reports WHERE tenant_id=? AND run_key NOT LIKE 'historical:%' AND id IN ({placeholders})", (tenant, *ids)).fetchall()
            if len(rows) != len(ids):
                return jsonify(error="One or more snapshots are unavailable. Refresh history before deleting."), 404
            if any(state in {"running", "deleted"} for _, state in rows):
                return jsonify(error="Running or already deleted snapshots cannot be deleted. Refresh history."), 409
            changed = c.execute(
                f"UPDATE attendance_reports SET state='deleted',payload='{{}}',error='' WHERE tenant_id=? AND run_key NOT LIKE 'historical:%' AND id IN ({placeholders}) AND state NOT IN ('running','deleted')",
                (tenant, *ids),
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
            row = c.execute("SELECT payload,state FROM attendance_reports WHERE tenant_id=? AND id=? AND run_key NOT LIKE 'historical:%'",
                            (s.active_tenant_id(), report_id)).fetchone()
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
