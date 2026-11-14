import unittest

import scheduler
import test_scheduler


class BusinessKnowledgeBaseTests(unittest.TestCase):
    setUp = test_scheduler.ManagerEmployeeAccessTests.setUp
    tearDown = test_scheduler.ManagerEmployeeAccessTests.tearDown
    create_account = test_scheduler.ManagerEmployeeAccessTests.create_account
    new_client = test_scheduler.ManagerEmployeeAccessTests.new_client
    sign_in_manager = test_scheduler.ManagerEmployeeAccessTests.sign_in_manager
    portal_employee_client = test_scheduler.ManagerEmployeeAccessTests.portal_employee_client

    def submit(self, client, headers, **values):
        return client.post(
            "/api/help/submissions", headers=headers,
            json={
                "title": values.get("title", "Updated closing procedure"),
                "body": values.get("body", "Record the close after the supervisor check."),
                "category": values.get("category", "Knowledge bite"),
                "audience": values.get("audience", "all"),
                "locationId": values.get("locationId", "loc1"),
                "articleId": values.get("articleId"),
                "baseRevision": values.get("baseRevision"),
                "submissionId": values.get("submissionId"),
                "state": values.get("state", "pending"),
            },
        )

    def test_manager_submission_scope_admin_review_publication_and_history(self):
        manager, _, _ = self.sign_in_manager()
        initial = manager.get("/api/help/knowledge")
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.get_json()["role"], "manager")
        self.assertIn("loc1", {item["id"] for item in initial.get_json()["locations"]})

        denied = self.submit(manager, self.csrf, locationId="loc2")
        self.assertEqual(denied.status_code, 403)
        first = self.submit(manager, self.csrf)
        self.assertEqual(first.status_code, 201, first.get_json())
        submission_id = first.get_json()["id"]
        self.assertEqual(manager.post(
            f"/api/help/submissions/{submission_id}/review",
            headers=self.csrf,
            json={"decision": "approved", "feedback": "Approved."},
        ).status_code, 401)
        self.assertEqual(manager.get("/api/help/knowledge").get_json()["articles"], [])

        admin_page = self.admin.get("/app/help")
        self.assertEqual(admin_page.status_code, 200)
        admin_page.close()
        pending = self.admin.get("/api/help/knowledge").get_json()["submissions"]
        self.assertEqual(len(pending), 1)
        approved = self.admin.post(
            f"/api/help/submissions/{submission_id}/review",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"decision": "approved", "feedback": "Approved for the Kingston team."},
        )
        self.assertEqual(approved.status_code, 200, approved.get_json())
        article_id = approved.get_json()["articleId"]
        published = manager.get("/api/help/knowledge").get_json()["articles"]
        article = next(item for item in published if item["id"] == article_id)
        self.assertEqual(article["revision"], 1)

        edit = self.submit(
            manager, self.csrf, articleId=article_id, baseRevision=1,
            body="Record the close after the supervisor and manager checks.",
        )
        self.assertEqual(edit.status_code, 201, edit.get_json())
        edit_id = edit.get_json()["id"]
        approved_edit = self.admin.post(
            f"/api/help/submissions/{edit_id}/review",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"decision": "approved", "feedback": "Revision published."},
        )
        self.assertEqual(approved_edit.status_code, 200, approved_edit.get_json())
        admin_data = self.admin.get("/api/help/knowledge").get_json()
        revisions = [item for item in admin_data["revisions"] if item["articleId"] == article_id]
        self.assertEqual([item["revision"] for item in revisions], [2, 1])
        self.assertEqual(revisions[1]["body"], "Record the close after the supervisor check.")

    def test_stale_edit_rejected_and_reviewer_feedback_returned(self):
        manager, _, _ = self.sign_in_manager("emp-a")
        first = self.submit(manager, self.csrf, title="Open procedure")
        submission_id = first.get_json()["id"]
        approved = self.admin.post(
            f"/api/help/submissions/{submission_id}/review",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"decision": "approved", "feedback": "Published."},
        ).get_json()
        article_id = approved["articleId"]

        edit = self.submit(manager, self.csrf, articleId=article_id, baseRevision=1)
        self.assertEqual(edit.status_code, 201)
        with scheduler.closing(scheduler.database_connect()) as connection, connection:
            connection.execute(
                "UPDATE business_knowledge_articles SET revision=2 WHERE tenant_id=? AND id=?",
                (scheduler.DEFAULT_TENANT_ID, article_id),
            )
        stale = self.admin.post(
            f"/api/help/submissions/{edit.get_json()['id']}/review",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"decision": "approved", "feedback": "Stale content."},
        )
        self.assertEqual(stale.status_code, 409)

        rejected = self.submit(manager, self.csrf, title="Proposed local checklist")
        rejected_id = rejected.get_json()["id"]
        response = self.admin.post(
            f"/api/help/submissions/{rejected_id}/review",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"decision": "rejected", "feedback": "Please clarify the closing time."},
        )
        self.assertEqual(response.status_code, 200)
        mine = manager.get("/api/help/knowledge").get_json()["submissions"]
        item = next(entry for entry in mine if entry["id"] == rejected_id)
        self.assertEqual(item["status"], "rejected")
        self.assertEqual(item["feedback"], "Please clarify the closing time.")

    def test_manager_drafts_and_rejected_submissions_can_be_resubmitted(self):
        manager, _, _ = self.sign_in_manager()
        draft = self.submit(manager, self.csrf, state="draft", title="Draft shift handover")
        self.assertEqual(draft.status_code, 201)
        submission_id = draft.get_json()["id"]
        self.assertEqual(draft.get_json()["status"], "draft")
        draft_item = next(
            item for item in manager.get("/api/help/knowledge").get_json()["submissions"]
            if item["id"] == submission_id
        )
        self.assertEqual(draft_item["status"], "draft")

        submitted = self.submit(
            manager, self.csrf, submissionId=submission_id, state="pending",
            title="Updated shift handover",
        )
        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(submitted.get_json()["id"], submission_id)
        rejected = self.admin.post(
            f"/api/help/submissions/{submission_id}/review",
            headers={"X-CSRF-Token": "test-csrf-token"},
            json={"decision": "rejected", "feedback": "Add the final register check."},
        )
        self.assertEqual(rejected.status_code, 200)
        resubmitted = self.submit(
            manager, self.csrf, submissionId=submission_id, state="pending",
            title="Shift handover with register check",
        )
        self.assertEqual(resubmitted.status_code, 201)
        self.assertEqual(resubmitted.get_json(), {"id": submission_id, "status": "pending"})

    def test_manual_and_help_pages_require_business_or_workforce_identity(self):
        with self.admin.get("/app/help") as page:
            self.assertEqual(page.status_code, 200)
        with self.admin.get("/user-manual") as manual:
            self.assertEqual(manual.status_code, 200)
        manager, _, _ = self.sign_in_manager("emp-a")
        with manager.get("/app/help") as page:
            self.assertEqual(page.status_code, 200)
        with manager.get("/user-manual") as manual:
            self.assertEqual(manual.status_code, 200)
        anonymous = scheduler.app.test_client()
        self.assertEqual(anonymous.get("/api/help/knowledge").status_code, 401)
        self.assertEqual(anonymous.get("/user-manual").status_code, 401)

    def test_published_articles_obey_audience_and_location_scope(self):
        with scheduler.closing(scheduler.database_connect()) as connection, connection:
            for article_id, audience, location in (
                ("all", "all", None),
                ("manager", "manager", "loc1"),
                ("employee", "employee", "loc1"),
                ("other-location", "manager", "loc2"),
            ):
                connection.execute(
                    """INSERT INTO business_knowledge_articles
                       (tenant_id,id,title,body,category,audience,schedule_location_id,
                        revision,created_by,created_email,created_at,updated_at,published_at)
                       VALUES (?,?,?,?,?,?,?,1,'author','author@example.test',
                               CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""",
                    (scheduler.DEFAULT_TENANT_ID, article_id, article_id, "Help text",
                     "FAQ", audience, location),
                )
        manager, _, _ = self.sign_in_manager()
        manager_ids = {item["id"] for item in manager.get("/api/help/knowledge").get_json()["articles"]}
        self.assertEqual(manager_ids, {"all", "manager"})
        employee = self.portal_employee_client()
        employee_ids = {item["id"] for item in employee.get("/api/help/knowledge").get_json()["articles"]}
        self.assertEqual(employee_ids, {"all", "employee"})


if __name__ == "__main__":
    unittest.main()