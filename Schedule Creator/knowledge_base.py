"""Tenant-scoped help articles with administrator-reviewed publication."""

import json
import secrets
from contextlib import closing

from flask import g, jsonify, request, session


SCHEMA = """
CREATE TABLE IF NOT EXISTS business_knowledge_articles (
    tenant_id TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL,
    body TEXT NOT NULL, category TEXT NOT NULL, audience TEXT NOT NULL,
    schedule_location_id TEXT, revision INTEGER NOT NULL,
    created_by TEXT NOT NULL, created_email TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, published_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id)
);
CREATE TABLE IF NOT EXISTS business_knowledge_submissions (
    tenant_id TEXT NOT NULL, id TEXT NOT NULL, article_id TEXT,
    base_revision INTEGER, title TEXT NOT NULL, body TEXT NOT NULL,
    category TEXT NOT NULL, audience TEXT NOT NULL, schedule_location_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'pending', 'approved', 'rejected')),
    feedback TEXT NOT NULL DEFAULT '', submitted_by TEXT NOT NULL,
    submitted_email TEXT NOT NULL, submitted_role TEXT NOT NULL,
    submitted_at TEXT NOT NULL, reviewed_by TEXT, reviewed_email TEXT,
    reviewed_at TEXT, PRIMARY KEY (tenant_id, id)
);
CREATE TABLE IF NOT EXISTS business_knowledge_revisions (
    tenant_id TEXT NOT NULL, article_id TEXT NOT NULL, revision INTEGER NOT NULL,
    title TEXT NOT NULL, body TEXT NOT NULL, category TEXT NOT NULL,
    audience TEXT NOT NULL, schedule_location_id TEXT,
    author_id TEXT NOT NULL, author_email TEXT NOT NULL,
    reviewer_id TEXT NOT NULL, reviewer_email TEXT NOT NULL,
    published_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, article_id, revision)
);
"""

AUDIENCES = {"all", "manager", "employee"}
CATEGORIES = {"FAQ", "User guide", "Tutorial", "Glossary", "Knowledge bite"}
MAX_TITLE_LENGTH = 160
MAX_BODY_LENGTH = 8000
MAX_FEEDBACK_LENGTH = 2000


def _actor(s):
    if s.tenant_authenticated():
        if g.tenant_status != "active" or g.tenant_membership_status != "active":
            return None, (jsonify(error="This business membership is not active."), 403)
        return {
            "role": "admin",
            "tenantId": s.active_tenant_id(),
            "id": str(session.get("tenant_admin_id") or ""),
            "email": str(session.get("tenant_admin_email") or ""),
        }, None
    user, failure = s.access_guard({"manager", "employee"})
    if failure:
        return None, failure
    return user, None


def _location_rows(connection, tenant_id, email=None):
    if email is None:
        rows = connection.execute(
            "SELECT id, name, location FROM schedule_locations WHERE tenant_id=? ORDER BY name",
            (tenant_id,),
        ).fetchall()
    else:
        rows = connection.execute(
            """SELECT id, name, location FROM schedule_locations
               WHERE tenant_id=? AND LOWER(manager_email)=LOWER(?) ORDER BY name""",
            (tenant_id, email),
        ).fetchall()
    return [{"id": row[0], "name": row[1], "location": row[2]} for row in rows]


def _audit(connection, s, actor, action, detail):
    connection.execute(
        """INSERT INTO tenant_audit_events
           (id, tenant_id, actor_id, actor_email, action, route, response_status)
           VALUES (?, ?, ?, ?, ?, ?, 200)""",
        (
            s.secrets.token_urlsafe(18), actor["tenantId"], actor["id"], actor["email"],
            json.dumps({"action": action, **detail}, ensure_ascii=False),
            "business-knowledge-base",
        ),
    )


def _validated_submission(payload):
    if not isinstance(payload, dict):
        raise ValueError("Knowledge submission is required.")
    title, body = payload.get("title"), payload.get("body")
    category, audience = payload.get("category"), payload.get("audience")
    location_id = payload.get("locationId")
    if not isinstance(title, str) or not 3 <= len(title.strip()) <= MAX_TITLE_LENGTH:
        raise ValueError(f"Enter a title of 3 to {MAX_TITLE_LENGTH} characters.")
    if not isinstance(body, str) or not 1 <= len(body.strip()) <= MAX_BODY_LENGTH:
        raise ValueError(f"Enter content of 1 to {MAX_BODY_LENGTH} characters.")
    if (
        not isinstance(category, str) or category not in CATEGORIES
        or not isinstance(audience, str) or audience not in AUDIENCES
    ):
        raise ValueError("Choose a valid category and audience.")
    if not isinstance(location_id, str) or not location_id.strip():
        raise ValueError("Choose one of your assigned schedule locations.")
    article_id = payload.get("articleId")
    base_revision = payload.get("baseRevision")
    submission_id = payload.get("submissionId")
    state = payload.get("state", "pending")
    if not isinstance(state, str) or state not in {"draft", "pending"}:
        raise ValueError("Choose save draft or submit for review.")
    if article_id is not None and (
        not isinstance(article_id, str) or not article_id or len(article_id) > 100
        or isinstance(base_revision, bool) or not isinstance(base_revision, int)
        or base_revision < 1
    ):
        raise ValueError("The article revision is invalid; reload and try again.")
    if submission_id is not None and (
        not isinstance(submission_id, str) or not submission_id or len(submission_id) > 100
    ):
        raise ValueError("The submission identifier is invalid; reload and try again.")
    return {
        "title": title.strip(), "body": body.strip(), "category": category,
        "audience": audience, "locationId": location_id.strip(),
        "articleId": article_id, "baseRevision": base_revision,
        "submissionId": submission_id, "state": state,
    }


def register(app, s):
    @app.after_request
    def knowledge_cache_headers(response):
        if request.path.startswith(("/api/help/", "/app/help", "/user-manual")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/user-manual")
    def user_manual_page():
        _, failure = _actor(s)
        if failure:
            return failure
        return s.send_from_directory(s.APP_DIRECTORY / "docs", "User-Manual.html")

    @app.get("/api/help/knowledge")
    def help_knowledge():
        actor, failure = _actor(s)
        if failure:
            return failure
        tenant_id = actor["tenantId"]
        with closing(s.database_connect()) as connection:
            if actor["role"] == "admin":
                locations = _location_rows(connection, tenant_id)
                location_ids = {row["id"] for row in locations}
            elif actor["role"] == "manager":
                locations = _location_rows(connection, tenant_id, actor.get("email", ""))
                location_ids = {row["id"] for row in locations}
            else:
                locations = []
                employee = connection.execute(
                    """SELECT schedule_location_id FROM employees
                       WHERE tenant_id=? AND employee_id=? AND active=1""",
                    (tenant_id, actor.get("employeeId")),
                ).fetchone()
                location_ids = {employee[0]} if employee and employee[0] else set()
            rows = connection.execute(
                """SELECT article.id, article.title, article.body, article.category,
                          article.audience, article.schedule_location_id, article.revision,
                          article.updated_at, location.name
                   FROM business_knowledge_articles AS article
                   LEFT JOIN schedule_locations AS location
                     ON location.tenant_id=article.tenant_id
                    AND location.id=article.schedule_location_id
                   WHERE article.tenant_id=? ORDER BY article.category, article.title""",
                (tenant_id,),
            ).fetchall()
            articles = []
            if actor["role"] == "admin":
                allowed_audiences = AUDIENCES
            elif actor["role"] == "manager":
                allowed_audiences = {"all", "manager"}
            else:
                allowed_audiences = {"all", "employee"}
            for row in rows:
                if row[4] not in allowed_audiences:
                    continue
                if row[5] is not None and row[5] not in location_ids:
                    continue
                articles.append({
                    "id": row[0], "title": row[1], "body": row[2], "category": row[3],
                    "audience": row[4], "locationId": row[5], "revision": row[6],
                    "updatedAt": row[7], "locationName": row[8] or "All locations",
                })
            if actor["role"] == "admin":
                submissions = connection.execute(
                    """SELECT id, article_id, base_revision, title, body, category,
                              audience, schedule_location_id, submitted_email, submitted_role,
                              submitted_at
                       FROM business_knowledge_submissions
                       WHERE tenant_id=? AND status='pending' ORDER BY submitted_at""",
                    (tenant_id,),
                ).fetchall()
                revisions = connection.execute(
                    """SELECT article_id, revision, title, body, category, audience,
                              schedule_location_id, author_email, reviewer_email, published_at
                       FROM business_knowledge_revisions WHERE tenant_id=?
                       ORDER BY article_id, revision DESC""",
                    (tenant_id,),
                ).fetchall()
            elif actor["role"] == "manager":
                submissions = connection.execute(
                    """SELECT id, article_id, base_revision, title, body, category,
                              audience, schedule_location_id, submitted_email, submitted_role,
                              submitted_at, status, feedback
                       FROM business_knowledge_submissions
                       WHERE tenant_id=? AND submitted_by=? ORDER BY submitted_at DESC""",
                    (tenant_id, actor["id"]),
                ).fetchall()
                revisions = []
            else:
                submissions, revisions = [], []
        return jsonify(
            role=actor["role"], articles=articles, locations=locations,
            submissions=[dict(zip(
                ("id", "articleId", "baseRevision", "title", "body", "category",
                 "audience", "locationId", "submittedEmail", "submittedRole", "submittedAt"), row
            )) | ({"status": row[11], "feedback": row[12]} if actor["role"] == "manager" else {})
                for row in submissions],
            revisions=[dict(zip(
                 ("articleId", "revision", "title", "body", "category", "audience", "locationId",
                  "authorEmail", "reviewerEmail", "publishedAt"), row
            )) for row in revisions],
        )

    @app.post("/api/help/submissions")
    def submit_knowledge():
        user, failure = s.access_guard({"manager"})
        if failure:
            return failure
        payload = request.get_json(silent=True)
        try:
            submission = _validated_submission(payload)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        tenant_id = user["tenantId"]
        with closing(s.database_connect()) as connection, connection:
            locations = _location_rows(connection, tenant_id, user.get("email", ""))
            if submission["locationId"] not in {row["id"] for row in locations}:
                return jsonify(error="Choose a schedule location assigned to your manager account."), 403
            article_id = submission["articleId"]
            if article_id:
                article = connection.execute(
                    """SELECT revision, schedule_location_id FROM business_knowledge_articles
                       WHERE tenant_id=? AND id=?""",
                    (tenant_id, article_id),
                ).fetchone()
                if not article or article[1] != submission["locationId"]:
                    return jsonify(error="That article is outside your assigned location."), 403
                if article[0] != submission["baseRevision"]:
                    return jsonify(error="This article changed. Reload it before suggesting an edit."), 409
            submission_id = submission["submissionId"]
            if submission_id:
                previous = connection.execute(
                    """SELECT article_id,base_revision,status FROM business_knowledge_submissions
                       WHERE tenant_id=? AND id=? AND submitted_by=?""",
                    (tenant_id, submission_id, user["id"]),
                ).fetchone()
                if not previous or previous[2] not in {"draft", "rejected"}:
                    return jsonify(error="Only your draft or rejected submission can be edited."), 404
                if previous[0] != article_id or previous[1] != submission["baseRevision"]:
                    return jsonify(error="The submission base revision changed. Reload it before resubmitting."), 409
                connection.execute(
                    """UPDATE business_knowledge_submissions SET title=?,body=?,category=?,audience=?,
                       schedule_location_id=?,status=?,feedback='',submitted_at=CURRENT_TIMESTAMP,
                       reviewed_by=NULL,reviewed_email=NULL,reviewed_at=NULL
                       WHERE tenant_id=? AND id=? AND submitted_by=?""",
                    (submission["title"], submission["body"], submission["category"],
                     submission["audience"], submission["locationId"], submission["state"],
                     tenant_id, submission_id, user["id"]),
                )
            else:
                submission_id = s.secrets.token_urlsafe(18)
                connection.execute(
                    """INSERT INTO business_knowledge_submissions
                       (tenant_id,id,article_id,base_revision,title,body,category,audience,
                        schedule_location_id,status,submitted_by,submitted_email,submitted_role,submitted_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                    (tenant_id, submission_id, article_id, submission["baseRevision"],
                     submission["title"], submission["body"], submission["category"],
                     submission["audience"], submission["locationId"], submission["state"],
                     user["id"], user.get("email", ""), user["role"]),
                )
            _audit(connection, s, user, "knowledge-submitted", {
                "submissionId": submission_id, "status": submission["state"],
            })
        return jsonify(id=submission_id, status=submission["state"]), 201

    @app.post("/api/help/submissions/<submission_id>/review")
    def review_knowledge(submission_id):
        if not s.tenant_authenticated():
            return jsonify(error="Sign in as a business administrator."), 401
        if g.tenant_status != "active" or g.tenant_membership_status != "active":
            return jsonify(error="This business membership is not active."), 403
        if s.cross_origin_request():
            return jsonify(error="Cross-origin requests are not allowed."), 403
        if not s.tenant_auth_csrf_valid():
            return jsonify(error="The request token is invalid. Reload the page and retry."), 400
        payload = request.get_json(silent=True)
        decision = payload.get("decision") if isinstance(payload, dict) else None
        feedback = payload.get("feedback") if isinstance(payload, dict) else None
        if not isinstance(decision, str) or decision not in {"approved", "rejected"}:
            return jsonify(error="Choose approve or reject."), 400
        if not isinstance(feedback, str) or not 1 <= len(feedback.strip()) <= MAX_FEEDBACK_LENGTH:
            return jsonify(error=f"Enter review feedback of 1 to {MAX_FEEDBACK_LENGTH} characters."), 400
        tenant_id = s.active_tenant_id()
        admin = {"tenantId": tenant_id, "id": str(session.get("tenant_admin_id") or ""),
                 "email": str(session.get("tenant_admin_email") or ""), "role": "admin"}
        with closing(s.database_connect()) as connection, connection:
            submission = connection.execute(
                """SELECT article_id,base_revision,title,body,category,audience,
                          schedule_location_id,submitted_by,submitted_email
                   FROM business_knowledge_submissions
                   WHERE tenant_id=? AND id=? AND status='pending'""",
                (tenant_id, submission_id),
            ).fetchone()
            if not submission:
                return jsonify(error="Pending submission not found."), 404
            article_id, base_revision, title, body, category, audience, location_id, author_id, author_email = submission
            if decision == "approved":
                current = None
                if article_id:
                    lock = " FOR UPDATE" if s.DATABASE_URL else ""
                    current = connection.execute(
                        "SELECT revision,created_by,created_email,created_at FROM business_knowledge_articles "
                        "WHERE tenant_id=? AND id=?" + lock,
                        (tenant_id, article_id),
                    ).fetchone()
                    if not current or current[0] != base_revision:
                        return jsonify(error="The published article changed; reject this stale edit and ask the manager to resubmit."), 409
                    revision = current[0] + 1
                    created_by, created_email, created_at = current[1:]
                else:
                    article_id = s.secrets.token_urlsafe(18)
                    revision = 1
                    created_by, created_email, created_at = author_id, author_email, s.datetime.now(s.timezone.utc).isoformat()
                now = s.datetime.now(s.timezone.utc).isoformat()
                connection.execute(
                    """INSERT INTO business_knowledge_articles
                       (tenant_id,id,title,body,category,audience,schedule_location_id,revision,
                        created_by,created_email,created_at,updated_at,published_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT (tenant_id,id) DO UPDATE SET
                         title=excluded.title,body=excluded.body,category=excluded.category,
                         audience=excluded.audience,schedule_location_id=excluded.schedule_location_id,
                         revision=excluded.revision,updated_at=excluded.updated_at,published_at=excluded.published_at""",
                    (tenant_id, article_id, title, body, category, audience, location_id,
                     revision, created_by, created_email, created_at, now, now),
                )
                connection.execute(
                    """INSERT INTO business_knowledge_revisions
                       (tenant_id,article_id,revision,title,body,category,audience,
                        schedule_location_id,author_id,author_email,reviewer_id,reviewer_email,published_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (tenant_id, article_id, revision, title, body, category, audience,
                     location_id, author_id, author_email, admin["id"], admin["email"], now),
                )
            connection.execute(
                """UPDATE business_knowledge_submissions SET status=?,feedback=?,reviewed_by=?,
                   reviewed_email=?,reviewed_at=CURRENT_TIMESTAMP
                   WHERE tenant_id=? AND id=? AND status='pending'""",
                (decision, feedback.strip(), admin["id"], admin["email"], tenant_id, submission_id),
            )
            _audit(connection, s, admin, "knowledge-" + decision, {"submissionId": submission_id})
        return jsonify(id=submission_id, status=decision, articleId=article_id if decision == "approved" else None)