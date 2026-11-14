"""Loopback-only browser fixture using disposable data and no provider access."""
from flask import abort, redirect, session, Response
from threading import Thread
from werkzeug.serving import make_server
from contextlib import closing

import scheduler
import test_scheduler
import test_workforce_workflows
import attendance_snapshot
from test_attendance_snapshot import SnapshotHtmlTests, example_payload


def seed_historical_report(client):
    today = scheduler.datetime.now(scheduler.ATTENDANCE_TIMEZONE).date()
    current_week = today - scheduler.timedelta(days=today.weekday())
    selected_week = current_week - scheduler.timedelta(days=7)
    previous_week = selected_week - scheduler.timedelta(days=7)
    sample = [
        (selected_week, "attended"),
        (selected_week + scheduler.timedelta(days=1), "late"),
        (selected_week + scheduler.timedelta(days=2), "absent"),
        (selected_week + scheduler.timedelta(days=3), "approved_leave"),
        (selected_week + scheduler.timedelta(days=4), "attended"),
        (previous_week, "attended"),
        (previous_week + scheduler.timedelta(days=1), "absent"),
    ]
    with closing(scheduler.database_connect()) as connection, connection:
        for index, (shift_day, status) in enumerate(sample):
            connection.execute(
                """
                INSERT INTO attendance_shift_records
                    (tenant_id, schedule_run_id, employee_id, shift_date, shift_start,
                     status, source, reason, employee_name, location, role, clock_in_at,
                     clock_in_timezone, worked_minutes, updated_at)
                VALUES (?, ?, 'emp-a', ?, 8, ?, 'schedule', '', 'Ann Kingston',
                        'Kingston', 'Cashier', ?, 'America/Jamaica', ?, CURRENT_TIMESTAMP)
                """,
                (
                    scheduler.DEFAULT_TENANT_ID, f"browser-historical-{index}",
                    shift_day.isoformat(), status,
                    f"{shift_day.isoformat()}T08:03:00-05:00"
                    if status in {"attended", "late"} else None,
                    450 if status in {"attended", "late"} else None,
                ),
            )
    response = client.post(
        "/api/attendance/historical-reports",
        headers={"X-CSRF-Token": "test-csrf-token"},
        json={"period": "week", "start": selected_week.isoformat()},
    )
    if response.status_code != 201:
        raise RuntimeError(f"Could not seed historical browser report: {response.get_json()}")
    result = response.get_json()
    report = result["report"]
    expected = {
        "expected": 4, "present": 3, "score": 75.0,
        "late": 1, "lateDates": 1, "absent": 1, "absentDates": 1, "leave": 1,
    }
    if any(report["summary"].get(key) != value for key, value in expected.items()):
        raise RuntimeError(f"Historical browser fixture metrics changed: {report['summary']}")
    if (
        report["comparison"]["previous"]["score"] != 50.0
        or report["comparison"]["change"] != 25.0
    ):
        raise RuntimeError(f"Historical browser fixture comparison changed: {report['comparison']}")
    stable_id = "browser-historical-report"
    with closing(scheduler.database_connect()) as connection, connection:
        connection.execute(
            "UPDATE attendance_reports SET id=? WHERE tenant_id=? AND id=?",
            (stable_id, scheduler.DEFAULT_TENANT_ID, result["id"]),
        )
    return stable_id, selected_week


def main():
    clients = {}
    server = None

    @scheduler.app.post("/__fixture/stop")
    def stop():
        Thread(target=server.shutdown, daemon=True).start()
        return {"stopping": True}

    @scheduler.app.get("/__fixture/signin/<role>")
    def signin(role):
        if role not in clients:
            abort(404)
        serializer = scheduler.app.session_interface.get_signing_serializer(scheduler.app)
        session.clear()
        session.update(serializer.loads(clients[role].get_cookie("session").value))
        scheduler.session_idle.start(scheduler)
        return redirect("/" if role == "admin" else "/app/access")

    @scheduler.app.get("/__fixture/snapshot/<variant>")
    def snapshot_variant(variant):
        payload = example_payload()
        if variant == "empty":
            payload["attendance"]["shifts"] = []
        elif variant == "stale":
            payload["refreshError"] = "Source unavailable; evidence is stale."
        elif variant == "malicious":
            payload["attendance"]["shifts"][0]["name"] = '</script><img src=x onerror="window.snapshotInjected=true">'
            payload["businessName"] = "__SNAPSHOT_CSP__ </script><script>window.snapshotInjected=true</script>"
        elif variant == "legacy":
            payload.pop("logoDataUrl")
            for row in payload["attendance"]["shifts"]:
                row.pop("shiftEnd")
                row["workedMinutes"] = None
        else:
            abort(404)
        return Response(attendance_snapshot.render(payload), mimetype="text/html")

    fixture = test_workforce_workflows.TradeWorkflowTests()
    scheduler.STATIC_ASSETS.add("test_trade_picker.js")
    scheduler.STATIC_ASSETS.add("test_attendance_snapshot.js")
    fixture.setUp()
    try:
        fixture.seed()
        with closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE tenants SET membership_tier='platinum' WHERE tenant_id=?",
                (scheduler.DEFAULT_TENANT_ID,),
            )
        employee = fixture.portal_employee_client()
        fixture.target_client()
        manager, _, _ = fixture.sign_in_manager()
        scheduler.bamboohr_api_key = lambda: ""
        clients.update(admin=fixture.admin, employee=employee, manager=manager)
        SnapshotHtmlTests.save(fixture, example_payload())
        historical_id, historical_start = seed_historical_report(fixture.admin)
        server = make_server("127.0.0.1", 5097, scheduler.app, threaded=True)
        print("Isolated browser fixture ready on 127.0.0.1:5097", flush=True)
        print(
            "Historical offline report URL: "
            f"http://127.0.0.1:5097/api/attendance/historical-reports/"
            f"{historical_id}/download?format=html",
            flush=True,
        )
        print(
            "Historical Excel download URL: "
            f"http://127.0.0.1:5097/api/attendance/historical-reports/"
            f"{historical_id}/download?format=xlsx",
            flush=True,
        )
        print(
            f"Historical period: {historical_start.isoformat()} through "
            f"{(historical_start + scheduler.timedelta(days=6)).isoformat()}; "
            "expected eligible=4, present=3, score=75.00%, late shifts/dates=1/1, "
            "absent shifts/dates=1/1, approved leave=1; previous score=50.00%, "
            "change=+25.00 pp.",
            flush=True,
        )
        print(
            "Offline report filter selectors: #locationFilter, #roleFilter, "
            "#employeeFilter, #employeeSearch, #sortFilter, #clearFilters. "
            "Charts: #centerChart, #employeeChart, #heatmap.",
            flush=True,
        )
        server.serve_forever()
    finally:
        if server:
            server.server_close()
        fixture.tearDown()


if __name__ == "__main__":
    main()
