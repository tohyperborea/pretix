import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("pretixbase", "0311_fix_unshredded_invoices"),
        ("pretix_sideburn_core", "0003_membership_discount_rule"),
    ]

    operations = [
        migrations.CreateModel(
            name="DirectedGroupCategory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=190, verbose_name="Name")),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="directed_group_categories",
                        to="pretixbase.event",
                        verbose_name="Event",
                    ),
                ),
            ],
            options={
                "verbose_name": "Directed group category",
                "verbose_name_plural": "Directed group categories",
            },
        ),
        migrations.CreateModel(
            name="DirectedGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=190, verbose_name="Name")),
                (
                    "slot_count",
                    models.PositiveIntegerField(
                        default=0,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="Slot count",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True, verbose_name="Created")),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="groups",
                        to="pretix_sideburn_core.directedgroupcategory",
                        verbose_name="Category",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="directed_groups_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created by",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="directed_groups",
                        to="pretixbase.event",
                        verbose_name="Event",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="directed_groups",
                        to="pretixbase.item",
                        verbose_name="Product",
                    ),
                ),
                (
                    "leader",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="directed_groups_led",
                        to="pretixbase.customer",
                        verbose_name="Leader",
                    ),
                ),
                (
                    "variation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="directed_groups",
                        to="pretixbase.itemvariation",
                        verbose_name="Variation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Directed group",
                "verbose_name_plural": "Directed groups",
            },
        ),
        migrations.CreateModel(
            name="DirectedGroupSlot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=255, verbose_name="Name")),
                ("email", models.EmailField(max_length=254, verbose_name="Email")),
                (
                    "decision",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("pending", "Pending approval"),
                            ("rejected", "Rejected"),
                            ("no_account", "No account"),
                            ("already_ticketed", "Already ticketed"),
                        ],
                        default="",
                        max_length=32,
                        verbose_name="Decision",
                    ),
                ),
                (
                    "submitted_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Submitted at"),
                ),
                (
                    "decided_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Decided at"
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="directed_group_slots",
                        to="pretixbase.customer",
                        verbose_name="Customer",
                    ),
                ),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="directed_group_slots_decided",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Decided by",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slots",
                        to="pretix_sideburn_core.directedgroup",
                        verbose_name="Group",
                    ),
                ),
                (
                    "voucher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="directed_group_slots",
                        to="pretixbase.voucher",
                        verbose_name="Voucher",
                    ),
                ),
            ],
            options={
                "verbose_name": "Directed group slot",
                "verbose_name_plural": "Directed group slots",
            },
        ),
        migrations.AddConstraint(
            model_name="directedgroupcategory",
            constraint=models.UniqueConstraint(
                fields=("event", "name"),
                name="sideburn_core_dgm_unique_category_name_per_event",
            ),
        ),
        migrations.AddConstraint(
            model_name="directedgroupslot",
            constraint=models.UniqueConstraint(
                fields=("group", "email"),
                name="sideburn_core_dgm_unique_email_per_group",
            ),
        ),
    ]
