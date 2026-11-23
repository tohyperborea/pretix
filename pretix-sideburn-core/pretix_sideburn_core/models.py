from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomerDenylistEntry(models.Model):
    """
    Organizer-wide denylist of a customer account. Effective status and purchase
    enforcement are handled separately; this model is storage and admin only.
    """

    organizer = models.ForeignKey(
        "pretixbase.Organizer",
        on_delete=models.CASCADE,
        related_name="sideburn_denylist_entries",
        verbose_name=_("Organizer"),
    )
    customer = models.ForeignKey(
        "pretixbase.Customer",
        on_delete=models.CASCADE,
        related_name="sideburn_denylist_entries",
        verbose_name=_("Customer"),
    )
    notes = models.TextField(
        verbose_name=_("Notes"),
        blank=True,
    )
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sideburn_denylist_entries_created",
        verbose_name=_("Created by"),
    )

    class Meta:
        verbose_name = _("Customer denylist entry")
        verbose_name_plural = _("Customer denylist entries")
        constraints = [
            models.UniqueConstraint(
                fields=["organizer", "customer"],
                name="sideburn_core_denylist_unique_customer_per_organizer",
            ),
        ]

    def __str__(self):
        return str(self.customer)


class CustomerAllowlistEntry(models.Model):
    """
    Organizer-wide allowlist of a customer account (past attendance and/or manual
    add). Denylist supersedes allowlist for effective status; rows are not removed
    when someone is denylisted.
    """

    organizer = models.ForeignKey(
        "pretixbase.Organizer",
        on_delete=models.CASCADE,
        related_name="sideburn_allowlist_entries",
        verbose_name=_("Organizer"),
    )
    customer = models.ForeignKey(
        "pretixbase.Customer",
        on_delete=models.CASCADE,
        related_name="sideburn_allowlist_entries",
        verbose_name=_("Customer"),
    )
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sideburn_allowlist_entries_created",
        verbose_name=_("Created by"),
    )

    class Meta:
        verbose_name = _("Customer allowlist entry")
        verbose_name_plural = _("Customer allowlist entries")
        constraints = [
            models.UniqueConstraint(
                fields=["organizer", "customer"],
                name="sideburn_core_allowlist_unique_customer_per_organizer",
            ),
        ]

    def __str__(self):
        return str(self.customer)
