"""Authenticated trade workflow for accepted schedules."""

import hashlib
import json
import secrets
from itertools import combinations
from contextlib import closing
from datetime import date, datetime, timedelta

from flask import jsonify, request, session

SCHEMA = """
CREATE TABLE IF NOT EXISTS shift_trades (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, run_id TEXT NOT NULL,
    day INTEGER NOT NULL, employee_a TEXT NOT NULL, employee_b TEXT NOT NULL,
    slot_a TEXT NOT NULL, slot_b TEXT NOT NULL, location_id TEXT NOT NULL,
    state TEXT NOT NULL, reason TEXT NOT NULL, created_by TEXT NOT NULL,
    override_reason TEXT NOT NULL DEFAULT '',
    days TEXT NOT NULL DEFAULT '[]',
    rest_warnings TEXT NOT NULL DEFAULT '{}',
    rest_acknowledged TEXT NOT NULL DEFAULT '[]',
    initiated_role TEXT NOT NULL DEFAULT 'employee',
    target_confirmed INTEGER NOT NULL DEFAULT 0,
    constraint_policy TEXT NOT NULL DEFAULT 'legacy',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS shift_trade_events (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, trade_id TEXT NOT NULL,
    state TEXT NOT NULL, actor_id TEXT NOT NULL, reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS shift_trade_publish (
    trade_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL, before_payload TEXT NOT NULL, after_payload TEXT NOT NULL,
    operations TEXT NOT NULL, remote_mode TEXT NOT NULL, state TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS shift_trade_reads (
    tenant_id TEXT NOT NULL, reader_id TEXT NOT NULL, trade_id TEXT NOT NULL,
    version INTEGER NOT NULL, PRIMARY KEY(tenant_id,reader_id,trade_id)
);
"""


def register(app, s):
    def actor():
        if request.path.startswith("/api/access/"):
            user, failure = s.access_guard({"manager", "employee"})
            if failure:
                return None, failure
            if user["role"] == "employee" or request.args.get("view") == "employee":
                user, failure = s.access_personal_guard()
                if failure:
                    return None, failure
                user = dict(user, role="employee")
            denied = s.membership_feature_denied("shiftTrades")
            return user, denied
        if not s.tenant_auth_csrf_valid() and request.method != "GET":
            return None, (jsonify(error="The request token is invalid."), 400)
        denied = s.membership_feature_denied("shiftTrades")
        return {
            "id": session.get("tenant_admin_id"), "tenantId": s.active_tenant_id(),
            "role": "admin", "employeeId": None, "email": session.get("tenant_admin_email"),
        }, denied

    def fail(message, status=400):
        return jsonify(error=message), status

    def personal_location(c, user):
        if user["role"] != "employee":
            return None
        row = c.execute(
            "SELECT e.schedule_location_id,l.location,e.role,l.name FROM employees e "
            "JOIN schedule_locations l ON l.id=e.schedule_location_id AND l.tenant_id=e.tenant_id "
            "WHERE e.tenant_id=? AND e.employee_id=? AND e.active=1 AND e.location=l.location",
            (user["tenantId"], user["employeeId"]),
        ).fetchone()
        if not row:
            raise ValueError("Your active employee assignment has no verified schedule location. Contact an administrator.")
        return {"id": row[0], "location": row[1], "role": row[2], "name": row[3]}

    def require_personal_location(c, user, doc, location_id, payload=None):
        fixed = personal_location(c, user)
        if fixed and (location_id != fixed["id"] or doc.get("location") != fixed["location"]
                      or doc.get("role") != fixed["role"]):
            raise ValueError("Your location or team changed. Reload and select a schedule for your current assignment.")
        if fixed and payload and payload.get("locationId", fixed["id"]) != fixed["id"]:
            raise ValueError("Trade location is fixed to your current verified assignment.")

    def event(c, trade, user, state, reason):
        c.execute(
            "INSERT INTO shift_trade_events(id,tenant_id,trade_id,state,actor_id,reason,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (secrets.token_urlsafe(18), user["tenantId"], trade["id"], state, user["id"], reason,
             datetime.now(s.timezone.utc).isoformat(timespec="microseconds")),
        )

    def read(c, trade_id, tenant):
        row = c.execute(
            "SELECT id,run_id,day,employee_a,employee_b,slot_a,slot_b,location_id,"
            "state,reason,created_by,version,created_at,override_reason,days,rest_warnings,"
            "rest_acknowledged,initiated_role,target_confirmed,constraint_policy FROM shift_trades "
            "WHERE tenant_id=? AND id=?", (tenant, trade_id),
        ).fetchone()
        if not row:
            return None
        keys = ("id", "runId", "day", "employeeA", "employeeB", "slotA", "slotB",
                "locationId", "state", "reason", "createdBy", "version", "createdAt", "overrideReason",
                "days", "restWarnings", "restAcknowledged", "initiatedRole", "targetConfirmed", "constraintPolicy")
        trade = dict(zip(keys, row))
        creator_table = "tenant_admins" if trade["initiatedRole"] == "admin" else "tenant_users"
        creator = c.execute(
            f"SELECT display_name FROM {creator_table} WHERE tenant_id=? AND id=?",
            (tenant, trade["createdBy"]),
        ).fetchone()
        trade["initiatorName"] = creator[0] if creator else "Former account"
        trade["slotA"] = json.loads(trade["slotA"])
        trade["slotB"] = json.loads(trade["slotB"])
        trade["days"] = json.loads(trade["days"]) or [trade["day"]]
        trade["restWarnings"] = json.loads(trade["restWarnings"])
        trade["restAcknowledged"] = json.loads(trade["restAcknowledged"])
        trade["warnings"] = trade["restWarnings"]
        trade["acknowledged"] = trade["restAcknowledged"]
        trade["swaps"] = [
            {"day": day, "slotA": trade["slotA"][str(day)] if isinstance(trade["slotA"], dict) else trade["slotA"],
             "slotB": trade["slotB"][str(day)] if isinstance(trade["slotB"], dict) else trade["slotB"]}
            for day in trade["days"]
        ]
        row = c.execute("SELECT payload FROM accepted_schedules WHERE tenant_id=? AND run_id=?",
                        (tenant, trade["runId"])).fetchone()
        if row:
            doc = json.loads(row[0])
            names = {str(e["id"]): e["name"] for e in doc["employees"]}
            trade.update(employeeNameA=names.get(trade["employeeA"], trade["employeeA"]),
                         employeeNameB=names.get(trade["employeeB"], trade["employeeB"]),
                         start=doc["start"], shiftDuration=doc.get("controls", {}).get("span", 9))
            trade["shiftCounts"] = {}
            targets = [(trade["employeeA"], "slotB")]
            if trade["employeeA"] != trade["employeeB"]:
                targets.append((trade["employeeB"], "slotA"))
            for person, target in targets:
                slots = next((e["slots"][:] for e in doc["employees"] if str(e["id"]) == person), None)
                if slots is not None:
                    if trade["state"] in {"requested", "confirmed", "manager_accepted", "approved"}:
                        for swap in trade["swaps"]:
                            slots[swap["day"]] = swap[target]
                    trade["shiftCounts"][person] = sum(slot is not None for slot in slots)
        else:
            trade.update(employeeNameA=trade["employeeA"], employeeNameB=trade["employeeB"],
                         start=None, shiftDuration=None)
            trade["shiftCounts"] = {}
        return trade

    def visible(c, trade, user):
        if user["role"] == "admin":
            return True
        if user["role"] == "employee":
            return user["employeeId"] in {trade["employeeA"], trade["employeeB"]}
        row = c.execute(
            "SELECT manager_email FROM schedule_locations WHERE tenant_id=? AND id=?",
            (user["tenantId"], trade["locationId"]),
        ).fetchone()
        return bool(row and (row[0] or "").strip().casefold() == user["email"].casefold())

    def schedule(c, run_id, tenant, lock=False):
        row = c.execute(
            "SELECT payload FROM accepted_schedules WHERE tenant_id=? AND run_id=?" +
            (" FOR UPDATE" if lock and s.DATABASE_URL else ""),
            (tenant, run_id),
        ).fetchone()
        if not row:
            raise ValueError("The accepted schedule no longer exists.")
        return json.loads(row[0])

    def assignments(c, doc, a, b, tenant):
        people = {}
        for employee_id in (a, b):
            row = c.execute(
                "SELECT schedule_location_id,role,active FROM employees "
                "WHERE tenant_id=? AND employee_id=?", (tenant, employee_id),
            ).fetchone()
            assigned = [e for e in doc["employees"] if str(e.get("id")) == employee_id]
            if not row or not row[2] or len(assigned) != 1 or not row[0]:
                raise ValueError("Both employees need active, unambiguous accepted assignments.")
            people[employee_id] = (row, assigned[0])
        if people[a][0][:2] != people[b][0][:2]:
            raise ValueError("Trade participants must belong to the same schedule location and role.")
        location = c.execute(
            "SELECT location FROM schedule_locations WHERE tenant_id=? AND id=?",
            (tenant, people[a][0][0]),
        ).fetchone()
        if not location or doc.get("location") != location[0] or not s.role_matches_schedule_group(
            people[a][0][1], doc.get("role", "")
        ):
            raise ValueError("The accepted schedule does not match the current team assignment.")
        return people

    def past(doc, day, slots):
        shift_date = date.fromisoformat(doc["start"]) + timedelta(days=day)
        now = datetime.now(s.ATTENDANCE_TIMEZONE)
        return any(s.schedule_shift_datetime(shift_date, slot) <= now
                   for slot in slots if slot is not None)

    def allowed(c, trade, user):
        result = []
        state = trade["state"]
        if state == "requested" and user["role"] == "employee" and user["employeeId"] == trade["employeeB"] and not trade["targetConfirmed"]:
            result += ["confirm", "reject"]
        if state == "requested" and user["role"] == "employee" and user["employeeId"] == trade["employeeA"] and (
            (trade["restWarnings"] if trade["constraintPolicy"] == "warnings-five" else user["employeeId"] in trade["restWarnings"])
            and user["employeeId"] not in trade["restAcknowledged"]
        ):
            result += ["acknowledge", "reject"]
        if state == "confirmed" and user["role"] == "manager":
            result += ["accept", "reject"]
        if state in {"requested", "confirmed", "manager_accepted"} and user["id"] == trade["createdBy"]:
            result += ["withdraw"]
        if state == "manager_accepted" and user["role"] == "admin":
            result += ["approve", "reject"]
        if state in {"requested", "confirmed"} and user["role"] == "admin":
            result += ["reject"]
        if state == "approved" and user["role"] == "admin":
            result += ["apply", "reject"]
        return result

    def selected_days(p):
        days = p.get("days", [p.get("day")])
        if not isinstance(days, list) or not 1 <= len(days) <= 7 or any(
            type(day) is not int or not 0 <= day < 7 for day in days
        ) or len(set(days)) != len(days):
            raise ValueError("Select one to seven distinct swap days.")
        return sorted(days)

    def pending_days(c, run_id, people, tenant):
        blocked = set()
        for a, b, day, days in c.execute(
            "SELECT employee_a,employee_b,day,days FROM shift_trades WHERE tenant_id=? AND run_id=? "
            "AND state IN ('requested','confirmed','manager_accepted','approved')", (tenant, run_id),
        ):
            if set(people) & {a, b}:
                blocked.update(json.loads(days) or [day])
        return blocked

    def candidate(c, doc, a, b, days, user, other=None):
        if a == b:
            raise ValueError("Choose two different employees.")
        people = assignments(c, doc, a, b, user["tenantId"])
        require_personal_location(c, user, doc, people[a][0][0])
        if user["role"] == "employee" and user["employeeId"] != a:
            raise ValueError("Employee 1 must be your own linked employee record.")
        if user["role"] == "manager" and not visible(c, {"locationId": people[a][0][0]}, user):
            raise ValueError("That schedule is outside your assigned locations.")
        if user["role"] == "employee":
            permitted = s.scoped_portal_groups(c, dict(user, role="employee"))
            if not any(group["runId"] == doc["id"] and group["locationId"] == people[a][0][0] for group in permitted):
                raise ValueError("Choose a visible schedule assigned to your own team.")
        sa, sb = people[a][1]["slots"], people[b][1]["slots"]
        if any(sa[day] == sb[day] for day in days) or not any(sa[day] is not None for day in days):
            raise ValueError("Select changed shifts, including an assigned shift offered by employee 1.")
        if user["role"] != "admin" and any(past(doc, day, (sa[day], sb[day])) for day in days):
            raise ValueError("Started or past shifts require an administrator override.")
        if set(days) & pending_days(c, doc["id"], (a, b), user["tenantId"]):
            raise ValueError("A selected day already has a pending trade for one of these employees.")
        next_doc = json.loads(json.dumps(doc))
        next_a, next_b = (next(e for e in next_doc["employees"] if str(e["id"]) == person) for person in (a, b))
        for day in days:
            next_a["slots"][day], next_b["slots"][day] = sb[day], sa[day]
        minimum_shifts(next_doc, (a, b))
        warnings = {}
        issues = violations(c, next_doc, (a, b), user["tenantId"], warnings, other, warn_only=True)
        for person in (a, b):
            if (user["role"] == "employee" or warnings) and not c.execute(
                "SELECT 1 FROM tenant_users WHERE tenant_id=? AND employee_id=? AND active=1",
                (user["tenantId"], person),
            ).fetchone():
                raise ValueError("Affected employees need active accounts to confirm trades or reduced-rest warnings.")
        return people, next_doc, issues, warnings

    def minimum_shifts(doc, people):
        counts = {
            person: sum(slot is not None for slot in next(e for e in doc["employees"] if str(e["id"]) == person)["slots"])
            for person in people
        }
        if any(count < 5 for count in counts.values()):
            names = {str(e["id"]): e["name"] for e in doc["employees"]}
            raise ValueError("Trade cannot proceed: " + "; ".join(
                f"{names[person]} would have {count} shifts" for person, count in counts.items()
            ) + ". Both employees require at least 5 shifts in the selected schedule week.")
        return counts

    def current_warnings(c, trade, doc, tenant):
        people = tuple(dict.fromkeys((trade["employeeA"], trade["employeeB"])))
        if trade["employeeA"] != trade["employeeB"]:
            minimum_shifts(doc, people)
        warnings = {}
        issues = violations(c, doc, people, tenant, warnings,
                            warn_only=trade["constraintPolicy"] == "warnings-five")
        if trade["overrideReason"] and trade["employeeA"] == trade["employeeB"]:
            return issues, warnings
        if issues:
            raise ValueError("Trade violates scheduling constraints: " + " ".join(issues))
        if warnings != trade["restWarnings"]:
            raise ValueError("Scheduling warnings changed. Withdraw and request a new trade so everyone reviews the current warnings.")
        return issues, warnings

    def require_rest_ack(c, trade, doc, tenant):
        issues, warnings = current_warnings(c, trade, doc, tenant)
        if trade["overrideReason"] and trade["employeeA"] == trade["employeeB"]:
            return issues, warnings
        required = (trade["employeeA"], trade["employeeB"]) if warnings and trade["constraintPolicy"] == "warnings-five" else warnings
        if any(person not in trade["restAcknowledged"] for person in required):
            raise ValueError("Both employees must acknowledge the scheduling warnings first.")
        if warnings and trade["constraintPolicy"] == "warnings-five":
            for stage in ("manager", "admin") if trade["state"] == "approved" else ("manager",) if trade["state"] == "manager_accepted" else ():
                if not any(value.startswith(stage + ":") for value in trade["restAcknowledged"]):
                    raise ValueError(f"The {stage} must acknowledge the scheduling warnings before proceeding.")
        return issues, warnings

    @app.get("/api/access/trades/choices")
    @app.get("/api/shift-trades/choices")
    def trade_choices():
        user, failure = actor()
        if failure:
            return failure
        with closing(s.database_connect()) as c:
            try:
                fixed = personal_location(c, user)
            except ValueError as error:
                return fail(str(error), 403)
            groups = s.scoped_portal_groups(c, user) if user["role"] != "admin" else s.portal_schedule_groups(c)
            items = []
            for group in groups:
                if fixed and group["locationId"] != fixed["id"]:
                    continue
                teams = {}
                for employee in group["employees"]:
                    teams.setdefault(employee["role"], []).append({"id": employee["id"], "name": employee["name"]})
                for team, employees in teams.items():
                    if fixed and team != fixed["role"]:
                        continue
                    items.append({
                        "runId": group["runId"], "locationId": group["locationId"],
                        "locationName": group["locationName"], "team": team,
                        "start": group["start"], "end": group["end"], "employees": employees,
                    })
        return jsonify(schedules=items, employee1=user["employeeId"] if user["role"] == "employee" else None,
                       lockedLocation=fixed)

    @app.post("/api/access/trades/options")
    @app.post("/api/shift-trades/options")
    def trade_options():
        user, failure = actor()
        if failure:
            return failure
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or any(not isinstance(p.get(key), str) for key in ("runId", "employeeA", "employeeB")):
            return fail("Choose a schedule and both employees.")
        with closing(s.database_connect()) as c:
            try:
                doc = schedule(c, p["runId"], user["tenantId"])
                a, b = p["employeeA"], p["employeeB"]
                people = assignments(c, doc, a, b, user["tenantId"])
                require_personal_location(c, user, doc, people[a][0][0], p)
                if user["role"] == "employee" and a != user["employeeId"]:
                    return fail("Employee 1 is fixed to your own employee record.", 403)
                if user["role"] == "manager" and not visible(c, {"locationId": people[a][0][0]}, user):
                    return fail("That schedule is outside your assigned locations.", 403)
                other = [json.loads(row[0]) for row in c.execute(
                    "SELECT payload FROM accepted_schedules WHERE tenant_id=? AND run_id!=?", (user["tenantId"], doc["id"]),
                )]
                days = [day for day in range(7) if people[a][1]["slots"][day] != people[b][1]["slots"][day]]
                eligible, rejected = [], []
                for count in range(1, len(days) + 1):
                    for selected in combinations(days, count):
                        try:
                            _, proposed, issues, warnings = candidate(c, doc, a, b, list(selected), user, other)
                        except ValueError as error:
                            rejected.append(str(error))
                            continue
                        if not issues:
                            eligible.append({"days": list(selected), "restWarnings": warnings, "warnings": warnings,
                                             "shiftCounts": minimum_shifts(proposed, (a, b))})
                        else:
                            rejected.extend(issues)
                shown = sorted({day for option in eligible for day in option["days"]})
                return jsonify(
                    days=[{"day": day, "date": (date.fromisoformat(doc["start"]) + timedelta(days=day)).isoformat(),
                           "slotA": people[a][1]["slots"][day], "slotB": people[b][1]["slots"][day]} for day in shown],
                    combinations=eligible, explanations=sorted(set(rejected)), shiftDuration=doc["controls"]["span"],
                )
            except ValueError as error:
                return fail(str(error), 409)

    @app.route("/api/access/trades", methods=["GET", "POST"])
    @app.route("/api/shift-trades", methods=["GET", "POST"])
    def trades():
        user, failure = actor()
        if failure:
            return failure
        with closing(s.database_connect()) as c, c:
            if not s.DATABASE_URL and request.method == "POST":
                c.execute("BEGIN IMMEDIATE")
            if request.method == "GET":
                ids = c.execute(
                    "SELECT id FROM shift_trades WHERE tenant_id=? ORDER BY created_at DESC",
                    (user["tenantId"],),
                ).fetchall()
                items = []
                for (trade_id,) in ids:
                    trade = read(c, trade_id, user["tenantId"])
                    if visible(c, trade, user):
                        trade["actions"] = allowed(c, trade, user)
                        seen = c.execute(
                            "SELECT version FROM shift_trade_reads WHERE tenant_id=? AND reader_id=? AND trade_id=?",
                            (user["tenantId"], user["id"], trade_id),
                        ).fetchone()
                        trade["unread"] = not seen or seen[0] < trade["version"]
                        if user["role"] == "admin":
                            publish = c.execute(
                                "SELECT state,operations FROM shift_trade_publish "
                                "WHERE tenant_id=? AND trade_id=?", (user["tenantId"], trade_id),
                            ).fetchone()
                            if publish:
                                trade["remoteState"] = publish[0]
                                trade["operations"] = json.loads(publish[1])
                        trade["history"] = [
                            {"state": r[0], "actorId": r[1], "reason": r[2], "createdAt": r[3]}
                            for r in c.execute(
                                "SELECT state,actor_id,reason,created_at FROM shift_trade_events "
                                "WHERE tenant_id=? AND trade_id=? ORDER BY created_at,id",
                                (user["tenantId"], trade_id),
                            )
                        ]
                        items.append(trade)
                return jsonify(trades=items, unread=sum(trade["unread"] for trade in items))
            p = request.get_json(silent=True)
            if not isinstance(p, dict) or not isinstance(p.get("reason"), str) or not 1 <= len(p["reason"].strip()) <= 500:
                return fail("A trade reason of 1 to 500 characters is required.")
            run_id = p.get("runId")
            a, b = p.get("employeeA"), p.get("employeeB")
            if not isinstance(run_id, str) or not isinstance(a, str) or not isinstance(b, str) or a == b:
                return fail("Choose an accepted schedule, day (0 to 6), and two different employees.")
            try:
                days = selected_days(p)
                doc = schedule(c, run_id, user["tenantId"], True)
                require_personal_location(c, user, doc, personal_location(c, user)["id"] if user["role"] == "employee" else None, p)
                if user["role"] == "employee" and user["employeeId"] != a:
                    return fail("You can request trades only for your own shifts.", 403)
                people, _, issues, warnings = candidate(c, doc, a, b, days, user)
                if issues:
                    return jsonify(error="The combined swap violates scheduling constraints.", violations=issues), 409
                if warnings and p.get("warnings", p.get("restWarnings")) != warnings:
                    return jsonify(error="Review the current scheduling warnings before submitting.", warnings=warnings, restWarnings=warnings), 409
                acknowledged = []
                if warnings:
                    if p.get("acknowledgeWarnings", p.get("acknowledgeRest")) is not True:
                        return jsonify(error="Acknowledge the scheduling warnings before submitting.", warnings=warnings), 400
                if user["role"] == "employee" and warnings:
                    acknowledged.append(a)
                location_id = people[a][0][0]
                trade = {"id": secrets.token_urlsafe(18), "employeeA": a,
                         "employeeB": b, "locationId": location_id}
                if user["role"] == "manager" and not visible(c, trade, user):
                    return fail("That schedule is outside your assigned locations.", 403)
                state = {"employee": "requested", "manager": "manager_accepted", "admin": "approved"}[user["role"]]
                if warnings:
                    state = "requested"
                sa = {str(day): people[a][1]["slots"][day] for day in days}
                sb = {str(day): people[b][1]["slots"][day] for day in days}
                c.execute(
                    "INSERT INTO shift_trades(id,tenant_id,run_id,day,employee_a,employee_b,"
                    "slot_a,slot_b,location_id,state,reason,created_by,days,rest_warnings,rest_acknowledged,"
                    "initiated_role,constraint_policy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (trade["id"], user["tenantId"], run_id, days[0], a, b, json.dumps(sa),
                     json.dumps(sb), location_id, state, p["reason"].strip(), user["id"],
                     json.dumps(days), json.dumps(warnings), json.dumps(acknowledged), user["role"], "warnings-five"),
                )
                event(c, trade, user, state, p["reason"].strip() + (
                    " [Scheduling warnings reviewed at submission: " + json.dumps(warnings, sort_keys=True) + "]" if warnings else ""
                ))
                return jsonify(id=trade["id"], state=state), 201
            except ValueError as error:
                return fail(str(error), 409)

    @app.post("/api/access/trades/<trade_id>/action")
    @app.post("/api/shift-trades/<trade_id>/action")
    def action(trade_id):
        user, failure = actor()
        if failure:
            return failure
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or type(p.get("version")) is not int:
            return fail("Reload the trade and provide its current version.")
        if not isinstance(p.get("reason"), str) or not 1 <= len(p["reason"].strip()) <= 500:
            return fail("An action reason of 1 to 500 characters is required.")
        with closing(s.database_connect()) as c, c:
            if not s.DATABASE_URL:
                c.execute("BEGIN IMMEDIATE")
            trade = read(c, trade_id, user["tenantId"])
            if not trade or not visible(c, trade, user):
                return fail("Trade not found.", 404)
            operation = p.get("action")
            if operation not in allowed(c, trade, user):
                return fail("You cannot perform this action on the trade.", 403)
            if p["version"] != trade["version"]:
                return fail("The trade changed. Reload before continuing.", 409)
            if operation == "apply":
                return fail("Preview and apply this approved trade through the publishing workflow.", 409)
            if operation not in {"reject", "withdraw"}:
                try:
                    _, _, doc = proposal(c, trade, user["tenantId"])
                    if user["role"] != "admin" and any(
                        past(doc, swap["day"], (swap["slotA"], swap["slotB"])) for swap in trade["swaps"]
                    ):
                        return fail("Started or past shifts require an administrator.", 409)
                    if operation in {"confirm", "acknowledge"}:
                        _, warnings = current_warnings(c, trade, doc, user["tenantId"])
                        person = user["employeeId"]
                        needs_ack = bool(warnings) if trade["constraintPolicy"] == "warnings-five" else person in warnings
                        expected = warnings if trade["constraintPolicy"] == "warnings-five" else warnings.get(person, [])
                        if needs_ack:
                            if p.get("acknowledgeWarnings", p.get("acknowledgeRest")) is not True or p.get("warnings", p.get("restWarnings")) != expected:
                                return jsonify(error="Review and acknowledge the scheduling warnings before accepting.",
                                               warnings=expected), 400
                            trade["restAcknowledged"] = sorted(set(trade["restAcknowledged"]) | {person})
                        if operation == "confirm":
                            trade["targetConfirmed"] = 1
                    else:
                        _, warnings = require_rest_ack(c, trade, doc, user["tenantId"])
                        if warnings and trade["constraintPolicy"] == "warnings-five":
                            if p.get("acknowledgeWarnings") is not True or p.get("warnings") != warnings:
                                return jsonify(error="Explicitly acknowledge all scheduling warnings before approval.", warnings=warnings), 400
                            trade["restAcknowledged"].append(user["role"] + ":" + user["id"])
                except ValueError as error:
                    return fail(str(error), 409)
            state = {"confirm": "confirmed", "accept": "manager_accepted",
                     "acknowledge": "requested", "approve": "approved", "reject": "rejected", "withdraw": "withdrawn"}[operation]
            if operation in {"confirm", "acknowledge"}:
                required = (trade["employeeA"], trade["employeeB"]) if trade["restWarnings"] and trade["constraintPolicy"] == "warnings-five" else trade["restWarnings"]
                ready = trade["targetConfirmed"] and all(person in trade["restAcknowledged"] for person in required)
                state = ("confirmed" if trade["restWarnings"] and trade["constraintPolicy"] == "warnings-five" else
                         {"employee": "confirmed", "manager": "manager_accepted", "admin": "approved"}[trade["initiatedRole"]]) if ready else "requested"
            changed = c.execute(
                "UPDATE shift_trades SET state=?,rest_acknowledged=?,target_confirmed=?,version=version+1,updated_at=CURRENT_TIMESTAMP "
                "WHERE tenant_id=? AND id=? AND version=?",
                (state, json.dumps(trade["restAcknowledged"]), int(trade["targetConfirmed"]),
                 user["tenantId"], trade_id, trade["version"]),
            )
            if changed.rowcount != 1:
                return fail("The trade changed. Reload before continuing.", 409)
            event(c, trade, user, state, p["reason"].strip() + (
                " [Scheduling warnings acknowledged: " + json.dumps(trade["restWarnings"], sort_keys=True) + "]"
                if operation in {"confirm", "acknowledge", "accept", "approve"} and trade["restWarnings"] else ""
            ))
        return jsonify(state=state)

    def proposal(c, trade, tenant):
        doc = schedule(c, trade["runId"], tenant, True)
        people = assignments(c, doc, trade["employeeA"], trade["employeeB"], tenant)
        a, b = trade["employeeA"], trade["employeeB"]
        if people[a][0][0] != trade["locationId"]:
            raise ValueError("Assignments changed since the trade request. Request a new trade.")
        before = json.dumps(doc, sort_keys=True, separators=(",", ":"))
        for swap in trade.get("swaps", [{"day": trade["day"], "slotA": trade["slotA"], "slotB": trade["slotB"]}]):
            day, sa, sb = swap["day"], swap["slotA"], swap["slotB"]
            if people[a][1]["slots"][day] != sa or a != b and people[b][1]["slots"][day] != sb:
                raise ValueError("Assignments changed since the trade request. Request a new trade.")
            if a == b:
                people[a][1]["slots"][day] = sb
            else:
                people[a][1]["slots"][day], people[b][1]["slots"][day] = sb, sa
            for person in dict.fromkeys((a, b)):
                types = people[person][1].get("types")
                if not isinstance(types, list) or len(types) != 7:
                    types = ["Demand" if slot is not None else "" for slot in people[person][1]["slots"]]
                    people[person][1]["types"] = types
                types[day] = "Trade" if people[person][1]["slots"][day] is not None else ""
        doc.setdefault("tradeHistory", []).append({
            "tradeId": trade["id"], "day": trade["day"], "employeeA": a, "employeeB": b,
            "at": trade["createdAt"], "week": doc["start"], "firstId": a, "secondId": b,
            "firstName": people[a][1]["name"], "secondName": people[b][1]["name"],
            "days": trade.get("days", [trade["day"]]), "reason": trade["reason"], "manual": a == b,
            "restWarnings": trade.get("restWarnings", {}), "restAcknowledged": trade.get("restAcknowledged", []),
            "warnings": trade.get("restWarnings", {}), "acknowledged": trade.get("restAcknowledged", []),
        })
        after = json.dumps(doc, sort_keys=True, separators=(",", ":"))
        return before, after, doc

    def violations(c, doc, people, tenant, rest_warnings=None, other=None, warn_only=False):
        issues = []
        controls = doc.get("controls", {})
        span, rest = controls.get("span", 9), controls.get("rest", 0)
        if type(span) not in {int, float} or not 0 < span <= 24 or type(rest) not in {int, float} or not 0 <= rest <= 168:
            raise ValueError("The accepted schedule has invalid shift-duration or rest controls.")
        if type(controls.get("shifts", 7)) is not int or not 0 <= controls.get("shifts", 7) <= 7:
            raise ValueError("The accepted schedule has an invalid weekly shift cap.")
        other = other if other is not None else [json.loads(row[0]) for row in c.execute(
            "SELECT payload FROM accepted_schedules WHERE tenant_id=? AND run_id!=?",
            (tenant, doc["id"]),
        )]
        for person in people:
            first_issue = len(issues)
            employee = next(e for e in doc["employees"] if str(e["id"]) == person)
            for key, length in (("days", 7), ("timeOff", 8), ("allow", 4)):
                if key in employee and (not isinstance(employee[key], list) or len(employee[key]) < length):
                    raise ValueError(f"Accepted profile {key} for {person} needs review.")
            if "shiftAvailability" in employee and not isinstance(employee["shiftAvailability"], dict):
                raise ValueError(f"Accepted shift permissions for {person} need review.")
            slots = employee["slots"]
            if sum(slot is not None for slot in slots) > controls.get("shifts", 7):
                issues.append(f"Weekly shift cap: {sum(slot is not None for slot in slots)} shifts assigned; configured maximum {controls.get('shifts', 7)}.")
            for day, slot in enumerate(slots):
                if slot is None:
                    continue
                if (employee.get("timeOff", [False] * 8)[day] or
                    slot + span > 24 and employee.get("timeOff", [False] * 8)[day + 1]):
                    issues.append(f"Approved leave: work assigned on {(date.fromisoformat(doc['start']) + timedelta(days=day)).isoformat()} or into the next leave day. The trade does not cancel approved leave.")
                if not employee.get("days", [True] * 7)[day]:
                    issues.append(f"Availability: work assigned on unavailable day {(date.fromisoformat(doc['start']) + timedelta(days=day)).isoformat()}.")
                if not doc.get("locationPattern", {}).get("open", [True] * 7)[day]:
                    issues.append(f"Operating days: work assigned while the location is closed on {(date.fromisoformat(doc['start']) + timedelta(days=day)).isoformat()}.")
                modern = employee.get("shiftAvailability", {})
                key = format(slot, "g")
                permission = modern.get(key)
                if key not in modern and "allow" in employee:
                    starts = [6, 8.5, 14, 22]
                    permission = employee["allow"][starts.index(slot)] if slot in starts else None
                if ("shiftAvailability" in employee or "allow" in employee) and permission != 1:
                    issues.append(f"Shift-start permission: {int(slot):02d}:{round(slot % 1 * 60):02d} on {(date.fromisoformat(doc['start']) + timedelta(days=day)).isoformat()} is not granted.")
                if employee.get("flex") == "No" and employee.get("preferred") != slot:
                    issues.append(f"Fixed shift preference: assigned start {slot:g} differs from preferred start {employee.get('preferred')} on day {day + 1}.")
            intervals = []
            for schedule_doc in [doc] + other:
                person_row = next((e for e in schedule_doc["employees"] if str(e["id"]) == person), None)
                if not person_row:
                    continue
                week = date.fromisoformat(schedule_doc["start"])
                duration = schedule_doc.get("controls", {}).get("span", 9)
                required_rest = schedule_doc.get("controls", {}).get("rest", 0)
                if type(duration) not in {int, float} or not 0 < duration <= 24 or type(required_rest) not in {int, float} or not 0 <= required_rest <= 168:
                    raise ValueError("Another accepted schedule has invalid shift-duration or rest controls.")
                for day, slot in enumerate(person_row["slots"]):
                    if slot is not None:
                        beginning = s.schedule_shift_datetime(week + timedelta(days=day), slot)
                        intervals.append((beginning, beginning + timedelta(hours=duration), schedule_doc["id"], required_rest))
            intervals.sort()
            for before, after in combinations(intervals, 2):
                available = (after[0] - before[1]).total_seconds() / 3600
                required_rest = max(rest, before[3], after[3])
                if doc["id"] not in {before[2], after[2]} or available >= required_rest:
                    continue
                if available < 0 or rest_warnings is None:
                    issues.append(
                        f"Shift overlap: {-available:g} hours of simultaneous assignments at {after[0].isoformat()}."
                        if available < 0 else
                        f"Minimum rest: {available:g} hours before {after[0].isoformat()}; required {required_rest:g} hours."
                    )
                else:
                    rest_warnings.setdefault(person, []).append({
                        "hours": round(available, 2), "requiredHours": required_rest,
                        "shiftStart": after[0].isoformat(),
                        "message": f"Reduced rest: {available:g} hours before {after[0].strftime('%a %d %b %H:%M')}; required {required_rest:g} hours.",
                    })
            previous = employee.get("previous")
            if type(previous) in {int, float} and 0 <= previous < 24 and not any(
                item[2] != doc["id"] and item[0].date() == date.fromisoformat(doc["start"]) - timedelta(days=1) for item in intervals
            ):
                first = next((item for item in intervals if item[2] == doc["id"]), None)
                if first:
                    prior_end = s.schedule_shift_datetime(date.fromisoformat(doc["start"]) - timedelta(days=1), previous) + timedelta(hours=span)
                    available = (first[0] - prior_end).total_seconds() / 3600
                    if available < rest:
                        if available < 0 or rest_warnings is None:
                            issues.append(f"Prior-Sunday shift overlap or minimum-rest conflict for {person}.")
                        else:
                            rest_warnings.setdefault(person, []).append({
                                "hours": round(available, 2), "requiredHours": rest, "shiftStart": first[0].isoformat(),
                                "message": f"Reduced prior-Sunday rest: {available:g} hours; required {rest:g} hours.",
                            })
            if warn_only:
                for issue in sorted(set(issues[first_issue:])):
                    rest_warnings.setdefault(person, []).append({"message": issue})
                del issues[first_issue:]
        return sorted(set(issues))

    def order_remote_operations(ops):
        return sorted(ops, key=lambda op: op["method"] != "DELETE")

    def remote_operations(c, trade, doc):
        days = trade.get("days", [trade["day"]])
        start = date.fromisoformat(doc["start"])
        remote = s.fetch_bamboohr_scheduled_shifts(c, start + timedelta(days=min(days)), start + timedelta(days=max(days)))
        return order_remote_operations(
            [op for day in days for op in remote_operations_day(c, trade, doc, day, remote)]
        )

    def remote_operations_day(c, trade, doc, day, remote):
        shift_date = date.fromisoformat(doc["start"]) + timedelta(days=day)
        ops = []
        for person in dict.fromkeys((trade["employeeA"], trade["employeeB"])):
            old = [shift for shift in remote if
                   any(str(employee["employeeId"]) == person for employee in shift["employees"]) and
                   datetime.fromisoformat(shift["start"]).astimezone(s.ATTENDANCE_TIMEZONE).date() == shift_date]
            if len(old) > 1 or any(len(shift["employeeIds"]) != 1 for shift in old):
                raise ValueError("Shared or multiple BambooHR shifts require manual reconciliation.")
            assigned = next(e for e in doc["employees"] if str(e["id"]) == person)
            slot = assigned["slots"][day]
            if slot is not None:
                payloads = s.bamboo_payloads(c, [
                    {"runId": trade["runId"], "day": day, "start": slot, "schedule": doc}
                ])
                employee = c.execute(
                    "SELECT bamboohr_id FROM employees WHERE tenant_id=? AND employee_id=?",
                    (s.active_tenant_id(), person),
                ).fetchone()
                if not employee or not employee[0]:
                    raise ValueError("Both employees need valid BambooHR IDs for remote publishing.")
                bamboo_id = str(employee[0])
                payload = next((p for p in payloads if bamboo_id in {
                    str(value) for value in p["employeeIds"]
                }), None)
                if payload is None:
                    raise ValueError("A trade shift could not be mapped to BambooHR.")
                payload = {key: payload[key] for key in
                           ("scheduleId", "status", "color", "timezone", "start", "end")}
                schedule_id = s.bamboo_identifier(payload["scheduleId"], "schedule ID")
                payload["scheduleId"] = int(schedule_id) if schedule_id.isdigit() else schedule_id
                bamboo_id = s.bamboo_identifier(bamboo_id, "employee ID")
                payload["employeeIds"] = [int(bamboo_id) if bamboo_id.isdigit() else bamboo_id]
                ops.append({"method": "POST", "path": "scheduling/shifts",
                            "payload": payload, "employeeId": person, "state": "pending"})
            for shift in old:
                ops.append({"method": "DELETE", "path":
                            "scheduling/shifts/" + s.quote(str(shift["id"]), safe="") +
                            "?recurrenceEditOption=instance", "payload": None,
                            "employeeId": person, "state": "pending"})
        return ops

    @app.post("/api/shift-trades/<trade_id>/preview")
    def preview(trade_id):
        user, failure = actor()
        if failure:
            return failure
        p = request.get_json(silent=True)
        mode = p.get("remoteMode") if isinstance(p, dict) else None
        if mode not in {"app_only", "bamboohr"}:
            return fail("Choose app_only or bamboohr publishing explicitly.")
        with closing(s.database_connect()) as c, c:
            if not s.DATABASE_URL:
                c.execute("BEGIN IMMEDIATE")
            trade = read(c, trade_id, user["tenantId"])
            if not trade or trade["state"] != "approved":
                return fail("An approved trade is required.", 409)
            existing = c.execute(
                "SELECT state FROM shift_trade_publish WHERE tenant_id=? AND trade_id=?" +
                (" FOR UPDATE" if s.DATABASE_URL else ""),
                (user["tenantId"], trade_id),
            ).fetchone()
            if existing and existing[0] != "preview":
                return fail("Publishing has started. Use its retry/reconciliation action.", 409)
            try:
                before, after, doc = proposal(c, trade, user["tenantId"])
                issues, warnings = require_rest_ack(c, trade, doc, user["tenantId"])
                ops = remote_operations(c, trade, doc) if mode == "bamboohr" else []
            except (ValueError, s.AttendanceIntegrationError) as error:
                return fail(str(error), 409)
            fingerprint = hashlib.sha256(
                (before + after + mode + json.dumps(ops, sort_keys=True)).encode()
            ).hexdigest()
            c.execute(
                "INSERT INTO shift_trade_publish(trade_id,tenant_id,fingerprint,before_payload,"
                "after_payload,operations,remote_mode,state) VALUES(?,?,?,?,?,?,?,'preview') "
                "ON CONFLICT(trade_id) DO UPDATE SET fingerprint=excluded.fingerprint,"
                "before_payload=excluded.before_payload,after_payload=excluded.after_payload,"
                "operations=excluded.operations,remote_mode=excluded.remote_mode,state='preview'",
                (trade_id, user["tenantId"], fingerprint, before, after, json.dumps(ops), mode),
            )
        return jsonify(fingerprint=fingerprint, operations=ops, remoteMode=mode,
                       violations=issues, overrideReason=trade["overrideReason"],
                       restWarnings=warnings, restAcknowledged=trade["restAcknowledged"],
                       warning="App-only does not modify BambooHR. Remote operations are not transactional: "
                               "original shifts scheduled for replacement are removed before replacement creation. "
                               "A failure after removal needs reconciliation/retry; do not reapply the app trade.")

    @app.post("/api/shift-trades/<trade_id>/apply")
    def apply(trade_id):
        user, failure = actor()
        if failure:
            return failure
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or p.get("confirmed") is not True or not isinstance(p.get("reason"), str) or not p["reason"].strip():
            return fail("Confirm the preview and provide an audit reason.")
        with closing(s.database_connect()) as c, c:
            if not s.DATABASE_URL:
                c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT fingerprint,before_payload,after_payload,operations,remote_mode,state "
                "FROM shift_trade_publish WHERE tenant_id=? AND trade_id=?" +
                (" FOR UPDATE" if s.DATABASE_URL else ""), (user["tenantId"], trade_id),
            ).fetchone()
            trade = read(c, trade_id, user["tenantId"])
            if not row or p.get("fingerprint") != row[0] or row[5] != "preview" or not trade or trade["state"] != "approved":
                return fail("A current preview is required.", 409)
            try:
                before, after, doc = proposal(c, trade, user["tenantId"])
                if before != row[1] or after != row[2]:
                    return fail("The accepted schedule changed. Preview again.", 409)
                require_rest_ack(c, trade, doc, user["tenantId"])
                if row[4] == "bamboohr" and json.dumps(remote_operations(c, trade, doc), sort_keys=True) != json.dumps(json.loads(row[3]), sort_keys=True):
                    return fail("BambooHR shifts changed. Preview again.", 409)
            except (ValueError, s.AttendanceIntegrationError) as error:
                return fail(str(error), 409)
            changed = c.execute(
                "UPDATE shift_trades SET state='applied',version=version+1,"
                "updated_at=CURRENT_TIMESTAMP WHERE tenant_id=? AND id=? AND state='approved' AND version=?",
                (user["tenantId"], trade_id, trade["version"]),
            )
            if changed.rowcount != 1:
                return fail("The trade changed. Reload.", 409)
            c.execute(
                "UPDATE accepted_schedules SET payload=? WHERE tenant_id=? AND run_id=?",
                (after, user["tenantId"], trade["runId"]),
            )
            c.execute(
                "UPDATE shift_trade_publish SET state=?,updated_at=CURRENT_TIMESTAMP "
                "WHERE tenant_id=? AND trade_id=?",
                ("pending" if row[4] == "bamboohr" else "app_only", user["tenantId"], trade_id),
            )
            event(c, trade, user, "applied", p["reason"].strip())
        if row[4] == "bamboohr":
            return execute_remote(trade_id, user)
        return jsonify(state="applied", remoteState="app_only",
                       warning="BambooHR was not changed. Reconcile published shifts separately.")

    def execute_remote(trade_id, user):
        with closing(s.database_connect()) as c, c:
            row = c.execute(
                "SELECT operations,state,after_payload FROM shift_trade_publish WHERE tenant_id=? AND trade_id=?" +
                (" FOR UPDATE" if s.DATABASE_URL else ""), (user["tenantId"], trade_id),
            ).fetchone()
            if not row or row[1] not in {"pending", "failed"}:
                return fail("This publish is complete, busy or has an unknown outcome. Reconcile before retrying.", 409)
            trade = read(c, trade_id, user["tenantId"])
            try:
                current = schedule(c, trade["runId"], user["tenantId"])
            except ValueError as error:
                return fail(str(error), 409)
            if current != json.loads(row[2]):
                return fail("The accepted schedule changed after application. Use attendance discrepancy reconciliation, not this stale publish plan.", 409)
            ops = order_remote_operations(json.loads(row[0]))
            changed = c.execute(
                "UPDATE shift_trade_publish SET state='running',updated_at=CURRENT_TIMESTAMP WHERE tenant_id=? AND trade_id=? AND state=?",
                (user["tenantId"], trade_id, row[1]),
            )
            if changed.rowcount != 1:
                return fail("Another publish is running.", 409)
        for op in ops:
            if op["state"] == "success":
                continue
            op["state"] = "attempting"
            with closing(s.database_connect()) as c, c:
                try:
                    current = schedule(c, trade["runId"], user["tenantId"])
                except ValueError as error:
                    c.execute("UPDATE shift_trade_publish SET state='failed' WHERE tenant_id=? AND trade_id=?",
                              (user["tenantId"], trade_id))
                    return fail(str(error), 409)
                if current != json.loads(row[2]):
                    c.execute("UPDATE shift_trade_publish SET state='failed' WHERE tenant_id=? AND trade_id=?",
                              (user["tenantId"], trade_id))
                    return fail("The accepted schedule changed during publishing. Some operations may have completed; reconcile current shifts.", 409)
                c.execute("UPDATE shift_trade_publish SET operations=?,updated_at=CURRENT_TIMESTAMP WHERE tenant_id=? AND trade_id=?",
                          (json.dumps(ops), user["tenantId"], trade_id))
            result = s.bamboo_shift_request(s.bamboohr_api_key(), op["method"], op["path"], op["payload"])
            op["result"] = result
            unknown = result.get("outcome") == "unknown" or (result.get("status") or 0) >= 500
            op["state"] = "success" if result["success"] else "unknown" if unknown else "failed"
            state = "running" if result["success"] else op["state"]
            with closing(s.database_connect()) as c, c:
                c.execute(
                    "UPDATE shift_trade_publish SET operations=?,state=?,updated_at=CURRENT_TIMESTAMP "
                    "WHERE tenant_id=? AND trade_id=?",
                    (json.dumps(ops), state, user["tenantId"], trade_id),
                )
            if not result["success"]:
                detail = result.get("error") or f"BambooHR operation status: {result.get('status') or 'unknown'}."
                return jsonify(error=f"App trade applied; BambooHR publishing is incomplete. {detail}",
                               remoteState=state, operations=ops), 502
        with closing(s.database_connect()) as c, c:
            c.execute("UPDATE shift_trade_publish SET state='published' WHERE tenant_id=? AND trade_id=?",
                      (user["tenantId"], trade_id))
            c.execute("UPDATE shift_trades SET state='published',version=version+1 WHERE tenant_id=? AND id=?",
                      (user["tenantId"], trade_id))
            event(c, read(c, trade_id, user["tenantId"]), user, "published", "BambooHR operations completed.")
        return jsonify(state="published", operations=ops)

    @app.post("/api/shift-trades/<trade_id>/retry")
    def retry(trade_id):
        user, failure = actor()
        if failure:
            return failure
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or p.get("confirmed") is not True:
            return fail("Confirm retry of failed remote operations.")
        return execute_remote(trade_id, user)

    @app.post("/api/shift-trades/<trade_id>/reconcile")
    def reconcile_remote(trade_id):
        user, failure = actor()
        if failure:
            return failure
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or p.get("confirmed") is not True or not isinstance(p.get("reason"), str) or not 1 <= len(p["reason"].strip()) <= 500:
            return fail("Confirm read-only remote reconciliation and provide an audit reason.")
        with closing(s.database_connect()) as c, c:
            if not s.DATABASE_URL:
                c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT operations,state,updated_at,after_payload FROM shift_trade_publish WHERE tenant_id=? AND trade_id=?" +
                (" FOR UPDATE" if s.DATABASE_URL else ""), (user["tenantId"], trade_id),
            ).fetchone()
            if not row or row[1] not in {"running", "unknown", "failed"}:
                return fail("This publish does not need remote reconciliation.", 409)
            updated = datetime.fromisoformat(row[2])
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=s.timezone.utc)
            if row[1] == "running" and (datetime.now(s.timezone.utc) - updated).total_seconds() < 600:
                return fail("Publishing is active. Wait at least ten minutes before reconciling an interrupted job.", 409)
            doc = json.loads(row[3])
            trade = read(c, trade_id, user["tenantId"])
            shift_day = date.fromisoformat(doc["start"]) + timedelta(days=min(trade["days"]))
            last_day = date.fromisoformat(doc["start"]) + timedelta(days=max(trade["days"]))
            try:
                remote = s.fetch_bamboohr_scheduled_shifts(c, shift_day, last_day)
            except s.AttendanceIntegrationError as error:
                return fail(str(error), 502)
            ops = json.loads(row[0])
            for op in ops:
                if op["method"] == "DELETE":
                    remote_id = op["path"].split("/")[-1].split("?")[0]
                    exists = any(str(shift["id"]) == remote_id for shift in remote)
                    op["state"] = "pending" if exists else "success"
                else:
                    payload = op["payload"]
                    matches = [shift for shift in remote if
                               str(shift["scheduleId"]) == str(payload["scheduleId"]) and
                               {str(value) for value in shift["employeeIds"]} == {str(value) for value in payload["employeeIds"]} and
                               datetime.fromisoformat(shift["start"]) == datetime.fromisoformat(payload["start"]) and
                               datetime.fromisoformat(shift["end"]) == datetime.fromisoformat(payload["end"])]
                    if len(matches) > 1:
                        return fail("Duplicate matching BambooHR shifts require manual correction before retrying.", 409)
                    op["state"] = "success" if matches else "pending"
                op.pop("result", None)
            # Retrying an absent write requires a separate explicit confirmation.
            c.execute(
                "UPDATE shift_trade_publish SET operations=?,state='pending',updated_at=CURRENT_TIMESTAMP WHERE tenant_id=? AND trade_id=?",
                (json.dumps(ops), user["tenantId"], trade_id),
            )
            event(c, trade, user, "remote-reconciled", p["reason"].strip())
        return jsonify(remoteState="pending", operations=ops,
                       warning="Read-only reconciliation completed. Confirm retry to send only missing operations.")

    @app.post("/api/access/trades/<trade_id>/read")
    @app.post("/api/shift-trades/<trade_id>/read")
    def mark_read(trade_id):
        user, failure = actor()
        if failure:
            return failure
        p = request.get_json(silent=True)
        with closing(s.database_connect()) as c, c:
            trade = read(c, trade_id, user["tenantId"])
            if not trade or not visible(c, trade, user):
                return fail("Trade not found.", 404)
            if not isinstance(p, dict) or type(p.get("version")) is not int or p["version"] != trade["version"]:
                return fail("Reload the current trade before marking it read.", 409)
            c.execute(
                "INSERT INTO shift_trade_reads(tenant_id,reader_id,trade_id,version) VALUES(?,?,?,?) "
                "ON CONFLICT(tenant_id,reader_id,trade_id) DO UPDATE SET version=excluded.version",
                (user["tenantId"], user["id"], trade_id, trade["version"]),
            )
        return jsonify(read=True)

    @app.post("/api/shift-overrides")
    def manual_override():
        user, failure = actor()
        if failure:
            return failure
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or p.get("confirmed") is not True or not isinstance(p.get("reason"), str) or not 1 <= len(p["reason"].strip()) <= 500:
            return fail("Confirm the manual shift/day-off override and provide an audit reason.")
        run_id, day, person, start = p.get("runId"), p.get("day"), p.get("employeeId"), p.get("start")
        if not isinstance(run_id, str) or type(day) is not int or not 0 <= day < 7 or not isinstance(person, str) or (
            start is not None and (type(start) not in {float, int} or not 0 <= start < 24 or start * 4 != int(start * 4))
        ) or type(p.get("overrideConstraints", False)) is not bool:
            return fail("Choose an accepted schedule, employee, day and quarter-hour start or null day off.")
        with closing(s.database_connect()) as c, c:
            if not s.DATABASE_URL:
                c.execute("BEGIN IMMEDIATE")
            try:
                doc = schedule(c, run_id, user["tenantId"], True)
                people = assignments(c, doc, person, person, user["tenantId"])
            except ValueError as error:
                return fail(str(error), 409)
            slot = people[person][1]["slots"][day]
            if slot == start:
                return fail("The manual assignment does not change the accepted shift.")
            if day in pending_days(c, run_id, (person,), user["tenantId"]):
                return fail("Resolve the employee's pending trade first.", 409)
            trade = {"id": secrets.token_urlsafe(18)}
            c.execute(
                "INSERT INTO shift_trades(id,tenant_id,run_id,day,employee_a,employee_b,slot_a,slot_b,"
                "location_id,state,reason,created_by,override_reason) VALUES(?,?,?,?,?,?,?,?,?,'approved',?,?,?)",
                (trade["id"], user["tenantId"], run_id, day, person, person, json.dumps(slot), json.dumps(start),
                 people[person][0][0], p["reason"].strip(), user["id"],
                 p["reason"].strip() if p.get("overrideConstraints") else ""),
            )
            event(c, trade, user, "approved", "Manual assignment: " + p["reason"].strip())
        return jsonify(id=trade["id"], state="approved"), 201

    return {"actor": actor, "read": read, "event": event,
            "schedule": schedule, "assignments": assignments, "fail": fail}
