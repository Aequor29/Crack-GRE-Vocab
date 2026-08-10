import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleIdentity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("subject", models.CharField(max_length=255, unique=True)),
                ("email_at_link", models.EmailField(max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="google_identity",
                        to="accounts.learneraccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "Google identity",
                "verbose_name_plural": "Google identities",
            },
        ),
    ]
