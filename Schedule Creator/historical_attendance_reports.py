"""Immutable, tenant-scoped historical attendance trend reports."""

import calendar
import base64
import hashlib
import io
import json
import secrets
import zipfile
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta
from html import escape
from pathlib import Path

from flask import Response, g, jsonify, request, session

import attendance_email


REPORT_PREFIX = "historical:"
LEAVE = {"approved_leave", "sick", "vacation"}
PRESENT = {"attended", "late"}
OFF = {"day_off", "off"}
MAX_REPORT_ROWS = 20000
MAX_SAVED_REPORT_BYTES = 8 * 1024 * 1024


def period_bounds(period, start_text):
    if period not in {"week", "month"}:
        raise ValueError("Choose a weekly or monthly report.")
    if not isinstance(start_text, str):
        raise ValueError("Choose a valid period start date.")
    try:
        requested = date.fromisoformat(start_text)
    except ValueError as error:
        raise ValueError("Choose a valid period start date.") from error
    if requested.isoformat() != start_text:
        raise ValueError("Choose a valid period start date.")
    if period == "week":
        start = requested - timedelta(days=requested.weekday())
        end = start + timedelta(days=6)
        previous_start, previous_end = start - timedelta(days=7), start - timedelta(days=1)
    else:
        start = requested.replace(day=1)
        end = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
        previous_month = start.replace(day=1) - timedelta(days=1)
        previous_start = previous_month.replace(day=1)
        previous_end = previous_month
    return start, end, previous_start, previous_end


def _location_rows(connection, tenant_id):
    return connection.execute(
        """
        SELECT id, name, location, role_group, manager_email
        FROM schedule_locations WHERE tenant_id = ?
        ORDER BY name, id
        """,
        (tenant_id,),
    ).fetchall()


def _location_matches(value, location):
    normalized = value.strip().casefold() if isinstance(value, str) else ""
    return bool(normalized) and normalized in {
        str(location[1] or "").strip().casefold(),
        str(location[2] or "").strip().casefold(),
    }


def _authorized_locations(s, connection, tenant_id, user):
    locations = _location_rows(connection, tenant_id)
    if user["role"] == "admin":
        return locations
    email = str(user.get("email") or "").casefold()
    return [
        row for row in locations
        if email and str(row[4] or "").casefold() == email
    ]


def _authorized_context(s):
    user, failure = s.access_guard({"manager"})
    if not failure:
        return {
            "role": "manager", "tenantId": user["tenantId"], "actorId": user["id"],
            "email": user.get("email"), "user": user,
        }, None
    if request.method != "GET" and not s.tenant_auth_csrf_valid():
        return None, (jsonify(error="The request token is invalid."), 400)
    if not s.tenant_authenticated():
        return None, (jsonify(error="Sign in to continue."), 401)
    if g.tenant_status != "active" or g.tenant_membership_status != "active":
        return None, (jsonify(error="This business membership is not active."), 403)
    return {
        "role": "admin", "tenantId": s.active_tenant_id(),
        "actorId": session.get("tenant_admin_id") or "",
        "email": session.get("tenant_admin_email"),
        "user": None,
    }, None


def _manager_record_allowed(s, row, locations):
    for location in locations:
        if not _location_matches(row.get("location"), location):
            continue
        group = str(location[3] or "")
        role = str(row.get("role") or "")
        if not role or (group and not s.role_matches_schedule_group(role, group)):
            continue
        return location
    return None


def _selected_location(s, user, locations, selected):
    if not selected or selected == "All":
        return None
    if not isinstance(selected, str):
        raise ValueError("Choose a valid location filter.")
    location = next(
        (entry for entry in locations
         if selected == entry[0] or _location_matches(selected, entry)),
        None,
    )
    if location is None:
        raise PermissionError("That location is outside your authorized teams.")
    if user["role"] == "manager" and location not in locations:
        raise PermissionError("That location is outside your authorized teams.")
    return location


def _query_period(s, connection, tenant_id, start, end, now, role, locations, selected_location, selected_role):
    rows = connection.execute(
        """
        SELECT schedule_run_id, employee_id, shift_date, shift_start, status,
               source, reason, employee_name, location, role, clock_in_at,
               clock_out_at, worked_minutes, early_minutes, overtime_minutes
        FROM attendance_shift_records
        WHERE tenant_id = ? AND shift_date >= ? AND shift_date <= ?
        ORDER BY shift_date, shift_start, employee_name, employee_id
        """,
        (tenant_id, start.isoformat(), end.isoformat()),
    ).fetchall()
    results = []
    for row in rows:
        run_id, employee_id, day_text, shift_start, status, source, reason, name, location, job_role = row[:10]
        location, job_role = str(location or "").strip(), str(job_role or "").strip()
        try:
            shift_day = date.fromisoformat(day_text)
            started = s.schedule_shift_datetime(shift_day, shift_start)
        except (TypeError, ValueError, OverflowError):
            continue
        if started > now:
            continue
        item = {
            "runId": str(run_id), "employeeId": str(employee_id),
            "date": shift_day.isoformat(), "shiftStart": started.isoformat(),
            "shiftStartTime": started.strftime("%H:%M"),
            "status": str(status or "unknown"), "source": str(source or ""),
            "reason": str(reason or ""), "name": str(name or ""),
            "location": str(location or ""), "role": str(job_role or ""),
            "clockIn": row[10], "clockOut": row[11], "workedMinutes": row[12],
            "earlyMinutes": row[13] or 0, "overtimeMinutes": row[14] or 0,
            "shiftEnd": None,
            "assignmentEvidence": "recorded" if employee_id and location and job_role else "insufficient_evidence",
            "durationEvidence": "insufficient_evidence",
            "leaveEvidence": "recorded_approved_leave" if status in LEAVE else "not_indicated_on_this_shift",
        }
        team = None
        if role == "manager":
            team = _manager_record_allowed(s, item, locations)
            if team is None:
                continue
        else:
            team = next(
                (entry for entry in locations if _location_matches(item["location"], entry)),
                None,
            )
        if selected_location and (team is None or team[0] != selected_location[0]):
            continue
        if selected_role and item["role"].casefold() != selected_role.casefold():
            continue
        item["locationId"] = team[0] if team else None
        results.append(item)
        if len(results) > MAX_REPORT_ROWS:
            raise OverflowError("The selected period contains too many shift records. Narrow the report filters.")
    return results


def _counts(rows):
    eligible = [row for row in rows if row["status"] not in LEAVE | OFF]
    present = sum(row["status"] in PRESENT for row in eligible)
    score = round(100 * present / len(eligible), 2) if eligible else None
    late_date_values = sorted({row["date"] for row in rows if row["status"] == "late"})
    absent_date_values = sorted({row["date"] for row in rows if row["status"] == "absent"})
    details = attendance_email.metrics([row for row in rows if row["status"] not in OFF], max(
        (row["shiftStart"] for row in rows), default=datetime.now().astimezone().isoformat()
    ))
    return {
        "expected": len(eligible), "present": present, "score": score,
        "late": sum(row["status"] == "late" for row in rows),
        "lateDates": len(late_date_values), "lateDateValues": late_date_values,
        "absent": sum(row["status"] == "absent" for row in rows),
        "absentDates": len(absent_date_values), "absentDateValues": absent_date_values,
        "leave": sum(row["status"] in LEAVE for row in rows),
        "confirmed": details["confirmed"],
        "confirmedAttendancePercent": details["attendancePercent"],
    }


def _aggregate(rows, key_fn):
    groups = defaultdict(list)
    for row in rows:
        groups[key_fn(row)].append(row)
    return groups


def _rates_by_location(rows):
    groups = _aggregate(rows, lambda row: row["location"] or "Unassigned")
    return [
        {"distributionCenter": key, **_counts(value)}
        for key, value in sorted(groups.items(), key=lambda entry: entry[0].casefold())
    ]


def _rates_by_employee(rows):
    groups = _aggregate(rows, lambda row: row["employeeId"])
    result = []
    for employee_id, items in sorted(groups.items(), key=lambda entry: (entry[1][0]["name"].casefold(), entry[0])):
        locations = sorted({row["location"] or "Unassigned" for row in items}, key=str.casefold)
        roles = sorted({row["role"] or "Unassigned" for row in items}, key=str.casefold)
        result.append({
            "employeeId": employee_id, "employee": next((row["name"] for row in items if row["name"]), employee_id),
            "distributionCenters": locations, "roles": roles, **_counts(items),
        })
    return result


def _compare(current, previous, key, label):
    newer = {row[key]: row for row in current}
    older = {row[key]: row for row in previous}
    result = []
    for identity in sorted(set(newer) | set(older), key=lambda value: str(value).casefold()):
        row = newer.get(identity)
        prior = older.get(identity)
        sample = row or prior
        before = prior.get("score") if prior else None
        after = row.get("score") if row else None
        previous_effective = prior.get("effectiveScore") if prior else None
        current_effective = row.get("effectiveScore") if row else None
        is_employee = key == "employeeId"
        compared_before = previous_effective if is_employee else before
        compared_after = current_effective if is_employee else after
        delta = (
            round(compared_after - compared_before, 2)
            if compared_after is not None and compared_before is not None else None
        )
        result.append({
            label: identity, "current": after, "previous": before, "change": delta,
            "formulaChange": (
                round(after - before, 2) if after is not None and before is not None else None
            ),
            "evidence": "compared" if delta is not None else "insufficient_evidence",
            "currentExpected": row["expected"] if row else None,
            "previousExpected": prior["expected"] if prior else None,
            "currentEffective": current_effective,
            "previousEffective": previous_effective,
            "overrideEvidence": row.get("overrideEvidence") if row else (
                prior.get("overrideEvidence") if prior else "insufficient_evidence"
            ),
            "present": row["present"] if row else None,
            "late": row["late"] if row else None,
            "lateDates": row["lateDates"] if row else None,
            "lateDateValues": row["lateDateValues"] if row else [],
            "absent": row["absent"] if row else None,
            "absentDates": row["absentDates"] if row else None,
            "absentDateValues": row["absentDateValues"] if row else [],
            "distributionCenters": sample.get("distributionCenters", [sample.get("distributionCenter")])
            if key == "employeeId" else [identity],
            "roles": sample.get("roles", []) if key == "employeeId" else [],
            "employee": sample.get("employee", identity) if key == "employeeId" else "",
        })
    return result


def _pattern_rate(rows):
    counts = _counts(rows)
    sample = counts["expected"]
    return {
        "eligibleShifts": sample, "score": counts["score"],
        "lateShifts": counts["late"],
        "lateDates": counts["lateDates"], "lateDateValues": counts["lateDateValues"],
        "absentDates": counts["absentDates"], "absentDateValues": counts["absentDateValues"],
        "absentShifts": counts["absent"],
        "lateShiftRate": round(counts["late"] * 100 / sample, 2) if sample else None,
        "absentShiftRate": round(counts["absent"] * 100 / sample, 2) if sample else None,
        "analysis": "available" if sample >= 3 else "insufficient_sample",
        "minimumEligibleShifts": 3,
    }


def _pattern_analysis(rows):
    eligible = [row for row in rows if row["status"] not in LEAVE | OFF]
    times = _aggregate(
        eligible,
        lambda row: (
            row["employeeId"], row["location"] or "Unassigned",
            row["role"] or "Unassigned", row["shiftStartTime"],
        ),
    )
    weekdays = _aggregate(
        eligible,
        lambda row: (
            row["employeeId"], row["location"] or "Unassigned",
            row["role"] or "Unassigned",
            date.fromisoformat(row["date"]).strftime("%A"),
        ),
    )

    def pattern_row(key, group):
        employee = group[0]
        return {
            "employeeId": key[0], "employee": employee["name"] or key[0],
            "distributionCenter": key[1], "role": key[2], "pattern": key[3],
            **_pattern_rate(group),
        }

    after_leave = defaultdict(list)
    explicit_off = defaultdict(list)
    by_team = _aggregate(
        rows,
        lambda row: (
            row["employeeId"], row["location"] or "Unassigned",
            row["role"] or "Unassigned",
        ),
    )
    for (employee_id, location, role), employee_rows in by_team.items():
        leave_dates = sorted({row["date"] for row in employee_rows if row["status"] in LEAVE})
        work_rows = sorted(
            (row for row in employee_rows if row["status"] not in LEAVE | OFF),
            key=lambda row: (row["date"], row["shiftStart"]),
        )
        used_following = set()
        for leave_day in leave_dates:
            following = next((row for row in work_rows if row["date"] > leave_day), None)
            identity = (following["runId"], following["date"], following["shiftStart"]) if following else None
            if following and identity not in used_following:
                used_following.add(identity)
                after_leave[(employee_id, location, role)].append(following)
        off_rows = [row for row in employee_rows if row["status"] in OFF]
        if off_rows:
            explicit_off[(employee_id, location, role)].extend(off_rows)
    post_leave = []
    for (employee_id, location, role), event_rows in sorted(after_leave.items()):
        employee = event_rows[0]
        item = _pattern_rate(event_rows)
        item.update(
            employeeId=employee_id, employee=employee["name"] or employee_id,
            distributionCenter=location, role=role,
            outcome="attendance score for the next recorded shift after selected-period approved leave",
            evidence="uncertain_first_scheduled_shift",
        )
        post_leave.append(item)

    post_day_off = []
    for (employee_id, location, role), off_rows in sorted(explicit_off.items()):
        employee_rows = by_team[(employee_id, location, role)]
        work_rows = sorted(
            (row for row in employee_rows if row["status"] not in LEAVE | OFF),
            key=lambda row: (row["date"], row["shiftStart"]),
        )
        following = {}
        for off in off_rows:
            shift = next((row for row in work_rows if row["date"] > off["date"]), None)
            if shift:
                following[(shift["runId"], shift["date"], shift["shiftStart"])] = shift
        event_rows = list(following.values())
        if event_rows:
            employee = event_rows[0]
            item = _pattern_rate(event_rows)
            item.update(
                employeeId=employee_id, employee=employee["name"] or employee_id,
                distributionCenter=location, role=role,
                evidence="uncertain_first_scheduled_shift",
            )
            post_day_off.append(item)

    def evidence_state(events):
        if not events:
            return "insufficient_evidence"
        if any(event["eligibleShifts"] >= 3 for event in events):
            return "available"
        return "insufficient_sample"

    return {
        "selectedPeriodOnly": True, "minimumEligibleShifts": 3,
        "shiftTimes": [pattern_row(key, group) for key, group in sorted(times.items())],
        "daysOfWeek": [pattern_row(key, group) for key, group in sorted(weekdays.items())],
        "postDayOff": {
            "analysis": "uncertain_first_scheduled_shift" if post_day_off else "insufficient_evidence",
            "sampleAnalysis": evidence_state(post_day_off),
            "records": post_day_off,
            "message": (
                "Only explicitly recorded day-off statuses are used. Missing attendance or schedule records "
                "are not treated as days off."
            ),
        },
        "postApprovedTimeOff": {
            "analysis": "uncertain_first_scheduled_shift" if post_leave else "insufficient_evidence",
            "sampleAnalysis": evidence_state(post_leave),
            "records": post_leave,
            "message": (
                "Uses approved-leave statuses and the next recorded shift within the selected period only. "
                "The first scheduled shift cannot be verified from attendance rows alone, so outcomes are marked "
                "uncertain. Leave outside the selected period is not used."
            ),
        },
    }


def _dated_score_overrides(connection, tenant_id, period_end):
    cutoff = period_end.isoformat()
    events = defaultdict(list)
    for employee_id, score, reason, created_at in connection.execute(
        """
        SELECT employee_id, score, reason, created_at
        FROM attendance_score_audit_events
        WHERE tenant_id = ? ORDER BY created_at, id
        """,
        (tenant_id,),
    ):
        events[employee_id].append((str(created_at or ""), score, reason or ""))
    active = {
        employee_id: (score, reason or "", str(updated_at or ""))
        for employee_id, score, reason, updated_at in connection.execute(
            """
            SELECT employee_id, score, reason, updated_at
            FROM attendance_score_overrides WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
    }
    results = {}
    for employee_id in set(events) | set(active):
        historical = [event for event in events[employee_id] if event[0][:10] <= cutoff]
        if historical:
            _, score, _ = historical[-1]
            results[employee_id] = (
                score, "recorded_audit_history" if score is not None else "no_override_as_of_period"
            )
            continue
        current = active.get(employee_id)
        if current:
            if current[2][:10] <= cutoff and not events[employee_id]:
                results[employee_id] = (current[0], "recorded_override_timestamp")
            elif current[2][:10] <= cutoff and events[employee_id] and events[employee_id][0][0][:10] <= cutoff:
                # The event ledger has a prior state, but it does not include this active value.
                results[employee_id] = (None, "override_history_unavailable")
            elif events[employee_id] or current[2][:10] > cutoff:
                results[employee_id] = (None, "override_history_unavailable")
            else:
                results[employee_id] = (None, "override_history_unavailable")
        else:
            results[employee_id] = (
                None,
                "no_override_as_of_period" if historical else (
                    "override_history_unavailable" if events[employee_id] else "no_override_recorded"
                ),
            )
    return results


def _apply_score_overrides(connection, tenant_id, employees, period_end):
    overrides = _dated_score_overrides(connection, tenant_id, period_end)
    for employee in employees:
        override, evidence = overrides.get(
            employee["employeeId"], (None, "no_override_recorded")
        )
        employee["formulaScore"] = employee["score"]
        employee["effectiveScore"] = (
            round(float(override), 2) if override is not None else (
                None if evidence == "override_history_unavailable" else employee["score"]
            )
        )
        employee["scoreOverride"] = override
        employee["overrideEvidence"] = evidence
    return employees


def _pattern_heatmap(rows):
    groups = _aggregate(
        [row for row in rows if row["status"] not in LEAVE | OFF],
        lambda row: (
            row["employeeId"], row["location"] or "Unassigned",
            row["role"] or "Unassigned",
            date.fromisoformat(row["date"]).strftime("%A"),
            row["shiftStartTime"],
        ),
    )
    return [
        {
            "employeeId": key[0], "distributionCenter": key[1], "role": key[2],
            "day": key[3], "shiftTime": key[4],
            **_pattern_rate(items),
        }
        for key, items in sorted(groups.items())
    ]


def build_report(s, connection, tenant_id, period, start, end, previous_start, previous_end,
                 now, user, locations, selected_location, selected_role):
    current_now = now
    current = _query_period(
        s, connection, tenant_id, start, end, current_now, user["role"], locations,
        selected_location, selected_role,
    )
    previous = _query_period(
        s, connection, tenant_id, previous_start, previous_end, current_now,
        user["role"], locations, selected_location, selected_role,
    )
    if user["role"] == "manager":
        allowed_ids = [str(row[0]) for row in locations]
        # A manager report is reauthorized at every later history/download request.
        location_ids = allowed_ids
    else:
        location_ids = [str(row[0]) for row in locations]
    current_metrics = _counts(current)
    previous_metrics = _counts(previous)
    rate_change = (
        round(current_metrics["score"] - previous_metrics["score"], 2)
        if current_metrics["score"] is not None and previous_metrics["score"] is not None
        else None
    )
    current_locations, previous_locations = _rates_by_location(current), _rates_by_location(previous)
    current_employees, previous_employees = _rates_by_employee(current), _rates_by_employee(previous)
    current_employees = _apply_score_overrides(
        connection, tenant_id, current_employees, min(end, current_now.date())
    )
    previous_employees = _apply_score_overrides(
        connection, tenant_id, previous_employees, min(previous_end, current_now.date())
    )
    comparison = {
        "period": period, "start": previous_start.isoformat(), "end": previous_end.isoformat(),
        "current": current_metrics, "previous": previous_metrics, "change": rate_change,
        "evidence": "compared" if rate_change is not None else "insufficient_evidence",
        "byDistributionCenter": _compare(
            current_locations, previous_locations, "distributionCenter", "distributionCenter"
        ),
        "byEmployee": _compare(current_employees, previous_employees, "employeeId", "employeeId"),
    }
    return {
        "type": "historical_attendance_trend", "period": period,
        "start": start.isoformat(), "end": end.isoformat(),
        "periodLabel": "Week (Monday–Sunday)" if period == "week" else "Calendar month",
        "timezone": "America/Jamaica", "generatedAt": now.isoformat(),
        "cutoff": min(end, now.date()).isoformat(),
        "filters": {
            "location": selected_location[1] if selected_location else None,
            "role": selected_role or None, "scope": user["role"],
        },
        "summary": current_metrics,
        "comparison": comparison,
        "distributionCenters": current_locations,
        "employees": current_employees,
        "patterns": _pattern_analysis(current),
        "heatmap": _pattern_heatmap(current),
        "records": current,
        "previousRecords": previous,
        "evidence": {
            "selectedRecordCount": len(current),
            "previousRecordCount": len(previous),
            "assignment": (
                "Insufficient evidence for complete historic assignment coverage: location and role are read only "
                "from each dated attendance record; unknown or missing values are not reconstructed."
            ),
            "schedule": (
                "Insufficient evidence for complete historic schedule coverage: only recorded attendance shifts are "
                "counted. A missing row does not establish a scheduled shift or day off."
            ),
            "leave": (
                "Insufficient evidence for unrecorded leave: only approved_leave, sick, or vacation statuses on "
                "recorded shifts count as leave. Missing records are not treated as approved leave."
            ),
            "dayOffPattern": (
                "Insufficient evidence unless a day_off/off status is explicitly recorded in this period."
            ),
            "recordsWithUnknownAssignment": sum(
                row["assignmentEvidence"] == "insufficient_evidence" for row in current
            ),
            "recordsWithUnknownDuration": sum(
                row["durationEvidence"] == "insufficient_evidence" for row in current
            ),
            "employeeOverrides": (
                "Employee effective score uses a score override only when an audit event or override timestamp "
                "proves it existed by the relevant period end. Historical override state that cannot be proven is "
                "reported as unavailable; distribution-center rates remain calculated from recorded shifts."
            ),
        },
        "scope": {
            "role": user["role"], "actorId": user["actorId"],
            "locationIds": location_ids,
        },
    }


def _json_for_html(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "&", "\\u0026"
    ).replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render_html(report):
    template = Path(__file__).with_name("historical_attendance_report.html").read_text(encoding="utf-8")
    return template.replace("__REPORT_JSON__", _json_for_html(report))


def _workbook_sheets(report):
    summary = report["summary"]
    comparison = report["comparison"]
    return [
        ("Summary", [
            ["Historical attendance trends", report["periodLabel"], report["timezone"]],
            ["Selected period", report["start"], report["end"]],
            ["Generated", report["generatedAt"], "Saved cutoff", report["cutoff"]],
            ["Recorded shifts", summary["expected"], "Present", summary["present"], "Attendance score", summary["score"] if summary["score"] is not None else "N/A"],
            ["Late shifts", summary["late"], "Late date count", summary["lateDates"], "Late date values", ", ".join(summary["lateDateValues"]) or "None",
             "Absent shifts", summary["absent"], "Absent date count", summary["absentDates"], "Absent date values", ", ".join(summary["absentDateValues"]) or "None"],
            ["Approved leave shifts", summary["leave"], "Confirmed by snapshot rules", summary["confirmed"],
             "Confirmed rate", summary["confirmedAttendancePercent"] if summary["confirmedAttendancePercent"] is not None else "N/A"],
            ["Preceding period", comparison["start"], comparison["end"]],
            ["Prior attendance score", comparison["previous"]["score"] if comparison["previous"]["score"] is not None else "N/A",
             "Change (percentage points)", comparison["change"] if comparison["change"] is not None else "Insufficient evidence"],
            ["Evidence", report["evidence"]["schedule"]],
            ["Assignment evidence", report["evidence"]["assignment"]],
            ["Leave evidence", report["evidence"]["leave"]],
            ["Patterns", report["evidence"]["dayOffPattern"]],
        ]),
        ("Distribution centers", [
            ["Distribution center", "Eligible shifts", "Present", "Attendance score %", "Late shifts", "Late date count", "Late date values", "Absent shifts", "Absent date count", "Absent date values", "Previous %", "Change pp", "Comparison evidence"],
            *[
                [
                    row["distributionCenter"], row["currentExpected"] if row["currentExpected"] is not None else "N/A",
                    row["present"] if row["present"] is not None else "N/A",
                    row["current"] if row["current"] is not None else "N/A",
                    row["late"] if row["late"] is not None else "N/A",
                    row["lateDates"] if row["lateDates"] is not None else "N/A",
                    ", ".join(row["lateDateValues"]) or "None",
                    row["absent"] if row["absent"] is not None else "N/A",
                    row["absentDates"] if row["absentDates"] is not None else "N/A",
                    ", ".join(row["absentDateValues"]) or "None",
                    row["previous"] if row["previous"] is not None else "N/A",
                    row["change"] if row["change"] is not None else "N/A", row["evidence"],
                ]
                for row in comparison["byDistributionCenter"]
            ],
        ]),
        ("Employee trends", [
            ["Employee", "Employee ID", "Distribution center(s)", "Role(s)", "Eligible shifts", "Present", "Formula score %", "Effective score %", "Override evidence", "Late shifts", "Late date count", "Late date values", "Absent shifts", "Absent date count", "Absent date values", "Previous formula %", "Formula change pp", "Previous effective %", "Effective change pp", "Comparison evidence"],
            *[
                [
                    row["employee"], row["employeeId"], ", ".join(row["distributionCenters"]),
                    ", ".join(row["roles"]), row["currentExpected"] if row["currentExpected"] is not None else "N/A",
                    row["present"] if row["present"] is not None else "N/A",
                    row["current"] if row["current"] is not None else "N/A",
                    row["currentEffective"] if row["currentEffective"] is not None else "N/A",
                    row["overrideEvidence"],
                    row["late"] if row["late"] is not None else "N/A",
                    row["lateDates"] if row["lateDates"] is not None else "N/A",
                    ", ".join(row["lateDateValues"]) or "None",
                    row["absent"] if row["absent"] is not None else "N/A",
                    row["absentDates"] if row["absentDates"] is not None else "N/A",
                    ", ".join(row["absentDateValues"]) or "None",
                    row["previous"] if row["previous"] is not None else "N/A",
                    row["formulaChange"] if row["formulaChange"] is not None else "N/A",
                    row["previousEffective"] if row["previousEffective"] is not None else "N/A",
                    row["change"] if row["change"] is not None else "N/A", row["evidence"],
                ]
                for row in comparison["byEmployee"]
            ],
        ]),
        ("Patterns", [
            ["Pattern", "Employee", "Employee ID", "Distribution center", "Role", "Eligible shifts", "Attendance score %", "Late shifts", "Late date count", "Late date values", "Late shift rate %", "Absent shifts", "Absent date count", "Absent date values", "Absent shift rate %", "Analysis", "Certainty evidence"],
            *[
                [kind, row.get("employee", ""), row.get("employeeId", ""),
                 row.get("distributionCenter", ""), row.get("role", ""),
                 row.get("eligibleShifts", 0), row.get("score") if row.get("score") is not None else "N/A",
                 row.get("lateShifts", 0), row.get("lateDates", 0),
                 ", ".join(row.get("lateDateValues", [])) or "None",
                 row.get("lateShiftRate") if row.get("lateShiftRate") is not None else "N/A",
                 row.get("absentShifts", 0), row.get("absentDates", 0),
                 ", ".join(row.get("absentDateValues", [])) or "None",
                 row.get("absentShiftRate") if row.get("absentShiftRate") is not None else "N/A",
                 row.get("analysis", "insufficient_evidence"),
                 row.get("evidence", "recorded_shift_sample")]
                for kind, values in (
                    ("Shift time", report["patterns"]["shiftTimes"]),
                    ("Day of week", report["patterns"]["daysOfWeek"]),
                    ("Post day off", report["patterns"]["postDayOff"]["records"]),
                    ("Post approved time off", report["patterns"]["postApprovedTimeOff"]["records"]),
                )
                for row in values
            ],
            ["Post day off evidence", report["patterns"]["postDayOff"]["message"]],
            ["Post approved time off evidence", report["patterns"]["postApprovedTimeOff"]["message"]],
        ]),
        ("Shift records", [
            ["Date", "Shift start", "Employee", "Employee ID", "Distribution center", "Role",
             "Status", "Clock in", "Clock out", "Worked minutes", "Late reason",
             "Assignment evidence", "Duration evidence", "Leave evidence"],
            *[
                [row["date"], row["shiftStart"], row["name"], row["employeeId"],
                 row["location"] or "Unassigned", row["role"] or "Unassigned",
                 row["status"], row.get("clockIn") or "", row.get("clockOut") or "",
                 row.get("workedMinutes") if row.get("workedMinutes") is not None else "",
                 row["reason"], row["assignmentEvidence"], row["durationEvidence"],
                 row["leaveEvidence"]]
                for row in report["records"]
            ],
        ]),
    ]


def workbook(report):
    """Create a formula-free XLSX from the same structured evidence as the HTML."""
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheets = _workbook_sheets(report)

    def safe(value):
        text = str(value if value is not None else "")
        return escape("".join(char for char in text if char in "\t\n\r" or ord(char) >= 32))

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{namespace}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            + "".join(
                f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
                for index, (name, _) in enumerate(sheets, 1)
            )
            + "</sheets></workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
                for index in range(1, len(sheets) + 1)
            )
            + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            + "</Relationships>",
        )
        archive.writestr(
            "xl/styles.xml",
            f'<styleSheet xmlns="{namespace}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF086FA0"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0"/><xf fontId="1" fillId="2" applyFill="1"/></cellXfs></styleSheet>',
        )
        for sheet_index, (_, rows) in enumerate(sheets, 1):
            body = []
            for row_number, row in enumerate(rows, 1):
                header = row_number == 1 and sheet_index != 1
                cells = "".join(
                    f'<c r="{chr(65 + column)}{row_number}" s="{1 if header else 0}" t="inlineStr"><is><t xml:space="preserve">{safe(value)}</t></is></c>'
                    for column, value in enumerate(row)
                )
                body.append(f'<row r="{row_number}">{cells}</row>')
            archive.writestr(
                f"xl/worksheets/sheet{sheet_index}.xml",
                f'<worksheet xmlns="{namespace}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><sheetData>{"".join(body)}</sheetData></worksheet>',
            )
    return output.getvalue()


def _history_context(s, report_id, context, locations):
    tenant_id = context["tenantId"]
    with closing(s.database_connect()) as connection:
        row = connection.execute(
            "SELECT payload,state FROM attendance_reports WHERE tenant_id=? AND id=? AND run_key LIKE ?",
            (tenant_id, report_id, REPORT_PREFIX + "%"),
        ).fetchone()
    if not row:
        return None, (jsonify(error="Historical report not found."), 404)
    try:
        report = json.loads(row[0])
    except (TypeError, ValueError):
        return None, (jsonify(error="Historical report evidence is unavailable."), 409)
    if report.get("type") != "historical_attendance_trend" or row[1] != "ready":
        return None, (jsonify(error="Historical report evidence is unavailable."), 404)
    access = report.get("scope") or {}
    if access.get("role") != context["role"]:
        return None, (jsonify(error="Historical report not found."), 404)
    if context["role"] == "manager":
        if access.get("actorId") != context["actorId"]:
            return None, (jsonify(error="Historical report not found."), 404)
        current_ids = {str(location[0]) for location in locations}
        if not set(access.get("locationIds") or []).issubset(current_ids):
            return None, (jsonify(error="Your authorized locations have changed. This report is unavailable."), 404)
        for saved in report["records"]:
            team = next(
                (location for location in locations
                 if str(location[0]) == str(saved.get("locationId"))
                 and _location_matches(saved.get("location"), location)),
                None,
            )
            if team is None or (team[3] and saved.get("role") and not s.role_matches_schedule_group(saved["role"], team[3])):
                return None, (jsonify(error="Your authorized teams have changed. This report is unavailable."), 404)
    return report, None


def _date_range(body):
    if not isinstance(body, dict):
        raise ValueError("Choose a weekly or monthly report period.")
    period = body.get("period")
    start, end, previous_start, previous_end = period_bounds(period, body.get("start"))
    return period, start, end, previous_start, previous_end


def _scope_run_key_prefix(context):
    actor = hashlib.sha256(str(context.get("actorId") or "").encode("utf-8")).hexdigest()[:20]
    return f"{REPORT_PREFIX}{context['role']}:{actor}:"


def register(app, s):
    @app.after_request
    def historical_report_headers(response):
        if request.path.startswith((
            "/api/attendance/historical-reports",
            "/api/access/manager/historical-reports",
        )):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/api/access/manager/historical-reports", methods=["GET", "POST"])
    @app.route("/api/attendance/historical-reports", methods=["GET", "POST"])
    def historical_reports():
        context, denied = _authorized_context(s)
        if denied:
            return denied
        manager_route = request.path.startswith("/api/access/manager/")
        if manager_route != (context["role"] == "manager"):
            return jsonify(error="Your account cannot use this report route."), 403
        tenant_id = context["tenantId"]
        with closing(s.database_connect()) as connection:
            locations = _authorized_locations(s, connection, tenant_id, context)
            if request.method == "POST":
                body = request.get_json(silent=True)
                try:
                    period, start, end, previous_start, previous_end = _date_range(body)
                    now = datetime.now(s.ATTENDANCE_TIMEZONE)
                    if start > now.date():
                        raise ValueError("The selected period cannot start in the future.")
                    selected_location = _selected_location(s, context, locations, body.get("location"))
                    selected_role = body.get("role")
                    if selected_role is not None and (
                        not isinstance(selected_role, str) or len(selected_role) > 120
                    ):
                        raise ValueError("Choose a valid role filter.")
                    if selected_role and context["role"] == "manager":
                        allowed = any(
                            not location[3] or s.role_matches_schedule_group(selected_role, location[3])
                            for location in locations
                        )
                        if not allowed:
                            raise PermissionError("That role is outside your authorized teams.")
                    recent = connection.execute(
                        "SELECT 1 FROM attendance_reports WHERE tenant_id=? AND run_key LIKE ? AND created_at>? LIMIT 1",
                        (
                            tenant_id, _scope_run_key_prefix(context) + "%",
                            (now - timedelta(seconds=60)).isoformat(),
                        ),
                    ).fetchone()
                    if recent:
                        return jsonify(error="Wait one minute between historical report requests."), 429
                    if end > now.date():
                        end = now.date()
                    report = build_report(
                        s, connection, tenant_id, period, start, end, previous_start, previous_end,
                        now, context, locations, selected_location, selected_role,
                    )
                except PermissionError as error:
                    return jsonify(error=str(error)), 403
                except OverflowError as error:
                    return jsonify(error=str(error)), 413
                except ValueError as error:
                    return jsonify(error=str(error)), 400
                report_id = secrets.token_urlsafe(18)
                branding = s.current_app_config()
                logo = s.validate_logo_data_url(branding.get("logoDataUrl", ""))
                if logo is None:
                    return jsonify(error="The saved business logo is invalid. Update branding before generating a report."), 400
                report["businessName"] = branding["businessName"]
                report["logoDataUrl"] = logo
                run_key = _scope_run_key_prefix(context) + secrets.token_urlsafe(24)
                cutoff = datetime.combine(
                    min(end, now.date()), time.max, tzinfo=s.ATTENDANCE_TIMEZONE
                ).isoformat()
                saved_report = report | {
                    "downloadHtml": render_html(report),
                    "downloadWorkbook": base64.b64encode(workbook(report)).decode("ascii"),
                }
                encoded_report = json.dumps(saved_report, ensure_ascii=False, separators=(",", ":"))
                if len(encoded_report.encode("utf-8")) > MAX_SAVED_REPORT_BYTES:
                    return jsonify(error="The report is too large to save. Narrow its location or role filters."), 413
                with closing(s.database_connect()) as save_connection, save_connection:
                    save_connection.execute(
                        """
                        INSERT INTO attendance_reports
                            (tenant_id,id,run_key,cutoff,created_at,state,payload,error)
                        VALUES (?,?,?,?,?,'ready',?,'')
                        """,
                        (
                            tenant_id, report_id, run_key, cutoff, now.isoformat(),
                            encoded_report,
                        ),
                    )
                return jsonify(id=report_id, report=report), 201

            history_scope = (
                _scope_run_key_prefix(context) + "%"
                if context["role"] == "manager"
                else REPORT_PREFIX + "admin:%"
            )
            rows = connection.execute(
                """
                SELECT id, created_at, payload FROM attendance_reports
                WHERE tenant_id = ? AND run_key LIKE ? AND state = 'ready'
                ORDER BY created_at DESC LIMIT 50
                """,
                (tenant_id, history_scope),
            ).fetchall()
            history = []
            for report_id, created_at, payload_text in rows:
                try:
                    saved = json.loads(payload_text)
                except (TypeError, ValueError):
                    continue
                access = saved.get("scope") or {}
                if saved.get("type") != "historical_attendance_trend" or access.get("role") != context["role"]:
                    continue
                if context["role"] == "manager":
                    if access.get("actorId") != context["actorId"]:
                        continue
                    if not set(access.get("locationIds") or []).issubset({str(location[0]) for location in locations}):
                        continue
                history.append({
                    "id": report_id, "createdAt": created_at,
                    "period": saved.get("period"), "start": saved.get("start"),
                    "end": saved.get("end"), "location": (saved.get("filters") or {}).get("location"),
                    "role": (saved.get("filters") or {}).get("role"),
                })
        return jsonify(reports=history)

    @app.get("/api/access/manager/historical-reports/<report_id>/download")
    @app.get("/api/attendance/historical-reports/<report_id>/download")
    def download_historical_report(report_id):
        context, denied = _authorized_context(s)
        if denied:
            return denied
        manager_route = request.path.startswith("/api/access/manager/")
        if manager_route != (context["role"] == "manager"):
            return jsonify(error="Your account cannot use this report route."), 403
        with closing(s.database_connect()) as connection:
            locations = _authorized_locations(s, connection, context["tenantId"], context)
        report, failure = _history_context(s, report_id, context, locations)
        if failure:
            return failure
        output_format = request.args.get("format", "xlsx")
        if output_format == "html":
            content = report.get("downloadHtml") or render_html(report)
            disposition = f'attachment; filename="attendance-trends-{report["period"]}-{report["start"]}.html"'
            return Response(
                content, mimetype="text/html; charset=utf-8",
                headers={
                    "Content-Disposition": disposition, "Cache-Control": "no-store",
                    "Referrer-Policy": "no-referrer",
                    "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
                    "X-Content-Type-Options": "nosniff",
                },
            )
        if output_format != "xlsx":
            return jsonify(error="Choose html or xlsx format."), 400
        encoded = report.get("downloadWorkbook")
        content = base64.b64decode(encoded) if encoded else workbook(report)
        return Response(
            content,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="attendance-trends-{report["period"]}-{report["start"]}.xlsx"',
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            },
        )
