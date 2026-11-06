"""Loopback-only browser fixture using disposable data and no provider access."""
from flask import abort, redirect, session, Response
from threading import Thread
from werkzeug.serving import make_server

import scheduler
import test_scheduler
import test_workforce_workflows
import attendance_snapshot
from test_attendance_snapshot import SnapshotHtmlTests, example_payload


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
        employee = fixture.portal_employee_client()
        fixture.target_client()
        manager, _, _ = fixture.sign_in_manager()
        scheduler.bamboohr_api_key = lambda: ""
        clients.update(admin=fixture.admin, employee=employee, manager=manager)
        SnapshotHtmlTests.save(fixture, example_payload())
        server = make_server("127.0.0.1", 5097, scheduler.app, threaded=True)
        print("Isolated browser fixture ready on 127.0.0.1:5097", flush=True)
        server.serve_forever()
    finally:
        if server:
            server.server_close()
        fixture.tearDown()


if __name__ == "__main__":
    main()
