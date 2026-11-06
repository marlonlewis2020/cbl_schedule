"""Shared server-side idle and absolute deadlines for browser authentication."""

import secrets
from contextlib import closing

from flask import g, jsonify, request, session

IDLE_SECONDS = 900
ABSOLUTE_SECONDS = 8 * 60 * 60
SCHEMA = """
CREATE TABLE IF NOT EXISTS browser_sessions (
    id TEXT PRIMARY KEY,
    started_at BIGINT NOT NULL,
    last_activity BIGINT NOT NULL
);
"""
IDENTITIES = ("tenant_admin_id", "platform_owner_id", "access_user_id", "developer_username")
SIGN_INS = {
    "tenant_admin_login", "verify_tenant_admin_mfa", "hub_owner_login",
    "hub_owner_verify_mfa", "access_login", "access_verify_mfa",
    "setup_developer_account", "developer_login",
}


def has_identity():
    return any(session.get(key) for key in IDENTITIES)


def start(s):
    now = int(s.time_module.time())
    token = secrets.token_urlsafe(32)
    with closing(s.database_connect()) as connection, connection:
        connection.execute(
            "DELETE FROM browser_sessions WHERE started_at <= ? OR last_activity <= ?",
            (now - ABSOLUTE_SECONDS, now - IDLE_SECONDS),
        )
        connection.execute(
            "INSERT INTO browser_sessions(id,started_at,last_activity) VALUES(?,?,?)",
            (token, now, now),
        )
    session.permanent = True
    session["idle_session_id"] = token
    session["idle_csrf"] = secrets.token_urlsafe(32)


def register(app, s):
    def expired_response():
        return jsonify(error="Your session expired. Sign in again.", sessionExpired=True), 401

    @app.before_request
    def enforce_browser_deadline():
        g.previous_idle_session = session.get("idle_session_id")
        g.idle_clock = None
        if request.path == "/api/payments/paypal/webhook" or not has_identity():
            return None
        now = int(s.time_module.time())
        with closing(s.database_connect()) as connection:
            row = connection.execute(
                "SELECT started_at,last_activity FROM browser_sessions WHERE id=?",
                (session.get("idle_session_id"),),
            ).fetchone()
        if row and now < row[0] + ABSOLUTE_SECONDS and now < row[1] + IDLE_SECONDS:
            g.idle_clock = row
            return None
        session.clear()
        if request.path.startswith("/api/"):
            return expired_response()
        return None

    @app.after_request
    def maintain_browser_deadline(response):
        previous = g.get("previous_idle_session")
        if response.status_code < 400 and has_identity():
            result = response.get_json(silent=True) or {}
            completed_login = result.get("authenticated") is True or (
                request.endpoint in {"setup_developer_account", "developer_login"}
                and isinstance(result.get("username"), str)
            )
            if request.endpoint in SIGN_INS and completed_login:
                start(s)
            elif request.endpoint == "update_developer_credentials" and previous and not session.get("idle_session_id"):
                # Password changes rotate credentials, not the absolute session deadline.
                session["idle_session_id"] = previous
                session["idle_csrf"] = secrets.token_urlsafe(32)
        if previous and (not has_identity() or previous != session.get("idle_session_id")):
            with closing(s.database_connect()) as connection, connection:
                connection.execute("DELETE FROM browser_sessions WHERE id=?", (previous,))
        if request.path.startswith("/api/session/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def authenticated():
        if session.get("tenant_admin_id") and s.tenant_authenticated():
            return True
        if session.get("platform_owner_id") and s.platform_owner_authenticated():
            return True
        if session.get("access_user_id") and s.access_user():
            return True
        return bool(session.get("developer_username") and s.developer_authenticated())

    @app.route("/api/session/state", methods=["GET", "POST"])
    def browser_session_state():
        if s.cross_origin_request():
            return jsonify(error="Cross-origin requests are not allowed."), 403
        if not g.get("idle_clock") or not authenticated():
            return jsonify(authenticated=False), 401
        now = int(s.time_module.time())
        started, last = g.idle_clock
        if request.method == "POST":
            supplied = request.headers.get("X-CSRF-Token", "")
            expected = session.get("idle_csrf", "")
            if not supplied or not expected or not secrets.compare_digest(supplied, expected):
                return jsonify(error="The activity token is invalid. Reload the page."), 400
            if request.content_length and request.content_length > 256:
                return jsonify(error="Activity report exceeds the size limit."), 413
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict) or set(payload) != {"activity"} or payload["activity"] not in (
                "interaction", "continue",
            ):
                return jsonify(error="Choose a valid user activity report."), 400
            with closing(s.database_connect()) as connection, connection:
                connection.execute(
                    """UPDATE browser_sessions SET last_activity=?
                       WHERE id=? AND last_activity>? AND started_at>? AND last_activity<=?""",
                    (now, session["idle_session_id"], now - IDLE_SECONDS,
                     now - ABSOLUTE_SECONDS, now - 15),
                )
                row = connection.execute(
                    "SELECT started_at,last_activity FROM browser_sessions WHERE id=?",
                    (session["idle_session_id"],),
                ).fetchone()
            if not row or now >= row[0] + ABSOLUTE_SECONDS or now >= row[1] + IDLE_SECONDS:
                session.clear()
                return expired_response()
            last = row[1]
        return jsonify(
            authenticated=True, serverTime=now, idleExpiresAt=last + IDLE_SECONDS,
            absoluteExpiresAt=started + ABSOLUTE_SECONDS, csrfToken=session["idle_csrf"],
        )
