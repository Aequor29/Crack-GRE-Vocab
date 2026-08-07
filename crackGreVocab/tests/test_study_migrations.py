"""AEQ-13 clean-schema forward and reverse migration coverage."""

from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase


class StudyMigrationTests(TransactionTestCase):
    def test_initial_study_schema_reverses_and_reapplies(self):
        try:
            call_command("migrate", "study", "zero", verbosity=0)
            self.assertNotIn(
                "study_studysession", connection.introspection.table_names()
            )
        finally:
            call_command("migrate", "study", "0001", verbosity=0)

        self.assertIn("study_studysession", connection.introspection.table_names())
