import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("pretixbase", "0311_fix_unshredded_invoices"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerDenylistEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sideburn_denylist_entries_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sideburn_denylist_entries",
                        to="pretixbase.customer",
                    ),
                ),
                (
                    "organizer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sideburn_denylist_entries",
                        to="pretixbase.organizer",
                    ),
                ),
            ],
            options={
                "verbose_name": "Customer denylist entry",
                "verbose_name_plural": "Customer denylist entries",
            },
        ),
        migrations.AddConstraint(
            model_name="customerdenylistentry",
            constraint=models.UniqueConstraint(
                fields=("organizer", "customer"),
                name="sideburn_core_denylist_unique_customer_per_organizer",
            ),
        ),
        migrations.CreateModel(
            name="CustomerAllowlistEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sideburn_allowlist_entries_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sideburn_allowlist_entries",
                        to="pretixbase.customer",
                    ),
                ),
                (
                    "first_event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sideburn_allowlist_first_entries",
                        to="pretixbase.event",
                    ),
                ),
                (
                    "organizer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sideburn_allowlist_entries",
                        to="pretixbase.organizer",
                    ),
                ),
            ],
            options={
                "verbose_name": "Customer allowlist entry",
                "verbose_name_plural": "Customer allowlist entries",
            },
        ),
        migrations.AddConstraint(
            model_name="customerallowlistentry",
            constraint=models.UniqueConstraint(
                fields=("organizer", "customer"),
                name="sideburn_core_allowlist_unique_customer_per_organizer",
            ),
        ),
    ]
