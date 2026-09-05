"""Current schema availability on a freshly initialized PostgreSQL database."""

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigrationContractTests(TransactionTestCase):
    """Verify the schema prepared by the test database setup."""

    def test_clean_database_contains_the_current_product_schema(self):
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

        self.assertEqual(plan, [])
        expected_tables = {
            model._meta.db_table
            for model in apps.get_models()
            if model._meta.managed and not model._meta.proxy
        }
        self.assertTrue(
            expected_tables.issubset(connection.introspection.table_names())
        )
