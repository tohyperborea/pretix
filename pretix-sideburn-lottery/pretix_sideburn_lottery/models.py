from django.db import models
from django.utils.translation import gettext_lazy as _


class LotteryGroup(models.Model):
    """
    A set of waiting-list entries for one product that enter the lottery as a single unit.
    """

    event = models.ForeignKey(
        "pretixbase.Event",
        on_delete=models.CASCADE,
        related_name="lottery_groups",
        verbose_name=_("Event"),
    )
    item = models.ForeignKey(
        "pretixbase.Item",
        on_delete=models.CASCADE,
        related_name="lottery_groups",
        verbose_name=_("Product"),
    )
    code = models.CharField(
        max_length=16,
        verbose_name=_("Group code"),
    )
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created"),
    )

    class Meta:
        verbose_name = _("Lottery group")
        verbose_name_plural = _("Lottery groups")
        constraints = [
            models.UniqueConstraint(
                fields=["event", "code"],
                name="sideburn_lottery_group_unique_code_per_event",
            ),
        ]

    def __str__(self):
        return self.code


class LotteryGroupMembership(models.Model):
    entry = models.OneToOneField(
        "pretixbase.WaitingListEntry",
        on_delete=models.CASCADE,
        related_name="lottery_group_membership",
        verbose_name=_("Waiting list entry"),
    )
    group = models.ForeignKey(
        LotteryGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("Lottery group"),
    )
    joined = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Joined"),
    )

    class Meta:
        verbose_name = _("Lottery group membership")
        verbose_name_plural = _("Lottery group memberships")

    def __str__(self):
        return "{} ({})".format(self.entry, self.group)
