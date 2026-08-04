"""PostgreSQL integration tests for the clean foundation."""

from django.db import connection
from django.test import TransactionTestCase


class PostgreSQLIntegrationTests(TransactionTestCase):
    """Prove that the test suite is using a live PostgreSQL database."""

    def test_default_database_round_trip_uses_postgresql(self):
        self.assertEqual(connection.vendor, "postgresql")

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()

        self.assertEqual(row, (1,))
