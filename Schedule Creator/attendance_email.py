"""Executive email content derived only from immutable snapshot evidence."""

from collections import defaultdict
from datetime import datetime
from html import escape
from math import isfinite


LEAVE = {"approved_leave", "sick", "vacation"}


def timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result if result.tzinfo else None


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) else None


def confirmed(row):
    if row.get("status") in LEAVE:
        return False
    if row.get("status") == "attended":
        return True
    if row.get("status") != "late" or not row.get("clockIn"):
        return False
    start, end = timestamp(row.get("shiftStart")), timestamp(row.get("shiftEnd"))
    worked = number(row.get("workedMinutes"))
    duration = (end - start).total_seconds() / 60 if start and end else None
    return bool(duration and duration > 0 and worked is not None and worked >= min(60, duration))


def metrics(rows, cutoff):
    values = dict(expected=0, confirmed=0, clocked=0, late=0, missing=0, absent=0,
                  leave=0, early=0, overtime=0, missingOut=0)
    end_of_capture = timestamp(cutoff)
    for row in rows:
        if row.get("status") in LEAVE:
            values["leave"] += 1
            continue
        values["expected"] += 1
        values["confirmed"] += confirmed(row)
        values["clocked"] += bool(row.get("clockIn"))
        values["late"] += row.get("status") == "late" and bool(row.get("clockIn"))
        values["missing"] += not bool(row.get("clockIn"))
        values["absent"] += row.get("status") == "absent"
        values["early"] += (number(row.get("earlyMinutes")) or 0) > 0
        values["overtime"] += max(0, number(row.get("overtimeMinutes")) or 0)
        end = timestamp(row.get("shiftEnd"))
        values["missingOut"] += bool(row.get("clockIn") and not row.get("clockOut") and end and end_of_capture and end <= end_of_capture)
    values["attendancePercent"] = round(values["confirmed"] * 100 / values["expected"], 1) if values["expected"] else None
    return values


def generate(payload):
    cutoff = payload["cutoff"]
    rows = payload["attendance"]["shifts"]
    total = metrics(rows, cutoff)
    rate = lambda m: f'{m["attendancePercent"]:.1f}%' if m["attendancePercent"] is not None else "N/A"
    groups = defaultdict(list)
    for row in rows:
        groups[(row.get("location") or "Unassigned", row.get("role") or "Unassigned")].append(row)
    summaries = [(*key, metrics(items, cutoff)) for key, items in sorted(groups.items())]
    subject = f'{payload.get("businessName", "Workforce")} | Attendance snapshot | {cutoff}'
    paragraphs = [
        f'Please find the accompanying HTML attendance snapshot for {cutoff} (America/Jamaica). Generated: {payload["generatedAt"]}.',
        f'Confirmed attendance is {rate(total)}: {total["confirmed"]} confirmed of {total["expected"]} expected shift records; {total["leave"]} approved-leave records are excluded.',
        f'Highlights: {total["clocked"]} matching clock-ins, {total["late"]} verified late arrivals, {total["absent"]} saved absences and {total["missing"]} missing clock-ins.',
        f'Follow-up: {total["missingOut"]} ended shifts without clock-out, {total["early"]} recorded early departures and {total["overtime"]:g} overtime minutes.',
    ]
    freshness = payload.get("refreshError")
    refreshed = payload["attendance"].get("lastSyncedAt")
    refreshed_at, cutoff_at = timestamp(refreshed), timestamp(cutoff)
    if freshness or not refreshed_at or not cutoff_at or refreshed_at > cutoff_at:
        paragraphs.append("SOURCE WARNING: " + (freshness or "Refresh evidence is missing or newer than the cutoff; treat results as incomplete."))
    else:
        paragraphs.append(f"Source refreshed: {refreshed}. This is saved evidence, not a live feed.")
    gaps = [f"{location} / {role}: {m['absent']} absences, {m['missing']} missing punches, {m['late']} late arrivals"
            for location, role, m in summaries if m["absent"] or m["missing"] or m["late"]]
    if gaps:
        paragraphs.append("Main call-outs: " + "; ".join(gaps) + ".")
    paragraphs += [
        "Missing punches include absences: these overlapping counts must not be added. A missing-punch late status is not a verified late arrival. Confirmed attendance requires the snapshot's saved worked-time validation.",
        "Scope: started reporting-day shifts plus verified overnight carry-in, not full-day staffing demand. Counts are shift records, not unique employees. Share only with authorized recipients.",
        "Attach the downloaded HTML snapshot before sending. This tool does not send email.",
    ]
    headers = ["Location", "Role", "Expected", "Confirmed", "Attendance", "Lates", "Absences", "Missing punches", "Leave"]
    table = [[location, role, m["expected"], m["confirmed"], rate(m), m["late"], m["absent"], m["missing"], m["leave"]] for location, role, m in summaries]
    text = "\n\n".join(paragraphs) + "\n\n" + "\t".join(headers) + "\n" + "\n".join("\t".join(map(str, row)) for row in table)
    formatted = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)
    formatted += '<table border="1" cellpadding="8" cellspacing="0"><thead><tr>' + "".join(f"<th>{escape(h)}</th>" for h in headers) + "</tr></thead><tbody>"
    formatted += "".join("<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>" for row in table) + "</tbody></table>"
    return {"subject": subject, "text": text, "html": formatted, "metrics": total}
