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
        self.assertEqual(create["operationId"], "study_session_create")
        self.assertEqual(
            set(create["responses"]),
            {"200", "201", "400", "403", "409", "415", "503"},
        )
        self.assertEqual(active["operationId"], "study_session_active_retrieve")
        self.assertEqual(set(active["responses"]), {"200", "403", "404"})
