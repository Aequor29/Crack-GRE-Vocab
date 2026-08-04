"""Migration completeness tests against the clean PostgreSQL database."""

from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigrationContractTests(TransactionTestCase):
    """Prove migrations are complete, drift-free, and idempotent."""

    def test_all_migration_leaf_nodes_are_applied(self):
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

        self.assertEqual(plan, [])

    def test_models_have_no_unwritten_migration_changes(self):
        output = StringIO()

        call_command(
            "makemigrations",
            check=True,
            dry_run=True,
            no_color=True,
            stdout=output,
            verbosity=1,
        )

        self.assertIn("No changes detected", output.getvalue())

    def test_reapplying_migrations_is_idempotent(self):
        output = StringIO()

        call_command(
            "migrate",
            no_input=True,
            no_color=True,
            stdout=output,
            verbosity=1,
        )

        self.assertIn("No migrations to apply", output.getvalue())
