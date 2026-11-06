"""Shared role-aware application routes without changing existing API permissions."""
from flask import g, jsonify, redirect, request, send_from_directory, session
from urllib.parse import urlencode


def register(app, s):
    @app.after_request
    def shell_cache_headers(response):
        if request.path in {"/api/application/state", "/api/access/application-state", "/api/hub/application-state"}:
            response.headers["Cache-Control"] = "no-store"
        return response

    def branding():
        config = s.current_app_config()
        return {key: config[key] for key in ("businessName", "teamName", "primaryColor", "accentColor", "logoDataUrl") if key in config}

    @app.get("/signin")
    def unified_signin():
        return send_from_directory(s.APP_DIRECTORY, "unified-login.html")

    @app.get("/app/<section>")
    def application_page(section):
        pages = {"access": "access.html", "trades": "trades.html", "business": "business-status.html",
                 "owner": "hub.html", "billing": "billing.html"}
        if section not in pages:
            s.abort(404)
        if section == "owner":
            valid = s.platform_owner_authenticated()
        elif section == "access":
            valid = bool(s.access_user())
        elif section == "trades":
            valid = s.tenant_authenticated() if request.args.get("adminView") == "1" else bool(s.access_user()) or s.tenant_authenticated()
        elif section == "billing" and request.args.get("view") == "owner":
            valid = s.platform_owner_authenticated()
        else:
            valid = s.tenant_authenticated()
        if not valid:
            experience = "owner" if section == "owner" or (section == "billing" and request.args.get("view") == "owner") else "workforce" if section in {"access", "trades"} and request.args.get("adminView") != "1" else "admin"
            return redirect("/signin?" + urlencode({"experience": experience, "next": request.full_path.rstrip("?")}))
        if section == "trades":
            response = app.make_response(send_from_directory(s.APP_DIRECTORY, pages[section]))
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
            return response
        return send_from_directory(s.APP_DIRECTORY, pages[section])

    @app.get("/api/application/state")
    @app.get("/api/access/application-state")
    @app.get("/api/hub/application-state")
    def application_state():
        if request.path.startswith("/api/hub/"):
            if not s.platform_owner_authenticated():
                return jsonify(error="Sign in as the platform owner."), 401
            return jsonify(role="owner", name=session.get("platform_owner_email"),
                           csrfToken=session.get("hub_csrf"), businessName="Platform administration",
                           teamName="Business management", primaryColor="#159bd5", accentColor="#74bf16",
                           logoDataUrl="", isPrimaryAdmin=False)
        if request.path.startswith("/api/access/"):
            user, denied = s.access_guard({"employee", "manager"})
            if denied:
                return denied
            g.tenant_id = user["tenantId"]
            return jsonify(**branding(), role=user["role"], name=user["name"],
                           csrfToken=session.get("access_csrf"), isPrimaryAdmin=False,
                           hasPersonalView=bool(user["employeeId"]))
        if not s.tenant_authenticated():
            return jsonify(error="Sign in as a business administrator."), 401
        with s.closing(s.database_connect()) as c:
            primary = c.execute("SELECT is_primary FROM tenant_admins WHERE tenant_id=? AND id=?",
                                (s.active_tenant_id(), session.get("tenant_admin_id"))).fetchone()
        return jsonify(**branding(), role="admin", name=session.get("tenant_admin_email"),
                       csrfToken=session.get("tenant_auth_csrf"), isPrimaryAdmin=bool(primary and primary[0]))
