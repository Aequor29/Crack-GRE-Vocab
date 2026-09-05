"""Typed API contract coverage for backend-planned Study Sessions."""

from django.test import Client, SimpleTestCase
from django.urls import reverse


class StudyOpenApiTests(SimpleTestCase):
    def test_schema_publishes_creation_resume_and_failure_contracts(self):
        response = Client().get(
            reverse("api:schema"),
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        create = paths["/api/study/sessions/"]["post"]
        active = paths["/api/study/sessions/active/"]["get"]
        answer = paths["/api/study/sessions/{session_id}/items/{item_id}/answer/"][
            "post"
        ]
        self.assertEqual(create["operationId"], "study_session_create")
        self.assertTrue(
            {"200", "201", "400", "403", "409", "415", "503"}.issubset(
                create["responses"]
            )
        )
        self.assertEqual(active["operationId"], "study_session_active_retrieve")
        self.assertTrue({"200", "403", "404", "503"}.issubset(active["responses"]))
        self.assertEqual(answer["operationId"], "study_session_answer_create")
        self.assertTrue(
            {"200", "201", "400", "403", "404", "409", "415", "503"}.issubset(
                answer["responses"]
            )
        )
        for operation, status, schema_name in (
            (create, "201", "StudySession"),
            (active, "200", "StudySession"),
            (answer, "201", "StudyAnswerResponse"),
            (answer, "400", "StudyValidationError"),
            (answer, "409", "StudyPlanningError"),
        ):
            self.assertEqual(
                operation["responses"][status]["content"]["application/json"][
                    "schema"
                ]["$ref"],
                f"#/components/schemas/{schema_name}",
            )
        for operation in (create, answer):
            self.assertTrue(
                any(
                    parameter["name"] == "X-CSRFToken"
                    and parameter["in"] == "header"
                    and parameter.get("required")
                    for parameter in operation["parameters"]
                )
            )
        components = response.json()["components"]["schemas"]
        create_request = components["CreateStudySessionRequest"]
        session = components["StudySession"]
        self.assertIn("timezone", create_request["required"])
        self.assertTrue(
            {
                "cleared_word_count",
                "current_item",
                "queue_state",
                "remaining_word_count",
                "word_count",
            }.issubset(session["required"])
        )
