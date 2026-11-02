from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("pretixbase", "0311_fix_unshredded_invoices"),
    ]

    operations = [
        migrations.CreateModel(
            name="LotteryGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("code", models.CharField(max_length=16)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="lottery_groups",
                        to="pretixbase.event",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="lottery_groups",
                        to="pretixbase.item",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lottery group",
                "verbose_name_plural": "Lottery groups",
            },
        ),
        migrations.CreateModel(
            name="LotteryGroupMembership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("joined", models.DateTimeField(auto_now_add=True)),
                (
                    "entry",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="lottery_group_membership",
                        to="pretixbase.waitinglistentry",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="memberships",
                        to="pretix_sideburn_lottery.lotterygroup",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lottery group membership",
                "verbose_name_plural": "Lottery group memberships",
            },
        ),
        migrations.AddConstraint(
            model_name="lotterygroup",
            constraint=models.UniqueConstraint(
                fields=("event", "code"),
                name="sideburn_lottery_group_unique_code_per_event",
            ),
        ),
    ]
