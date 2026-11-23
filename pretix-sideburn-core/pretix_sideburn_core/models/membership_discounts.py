from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager

from pretix.base.models.base import LoggedModel


class DiscountGrantingMembershipRule(LoggedModel):
    event = models.ForeignKey(
        "pretixbase.Event",
        on_delete=models.CASCADE,
        related_name="membership_discount_rules",
    )
    membership_type = models.ForeignKey(
        "pretixbase.MembershipType",
        on_delete=models.PROTECT,
        related_name="discount_rules",
    )
    discount_percent = models.DecimalField(
        _("Discount percentage"),
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )
    label = models.CharField(_("Label"), max_length=255)
    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created"),
    )
    products = models.ManyToManyField(
        "pretixbase.Item",
        verbose_name=_("Products"),
        related_name="membership_discount_rules",
    )

    objects = ScopedManager(organizer="event__organizer")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    discount_percent__gte=Decimal("0.01"),
                    discount_percent__lte=Decimal("100.00"),
                ),
                name="sideburn_membership_discount_percent_range",
            ),
        ]

    def __str__(self):
        return self.label

    def clean(self):
        super().clean()
        if (
            self.event_id
            and self.membership_type_id
            and self.event.organizer_id != self.membership_type.organizer_id
        ):
            raise ValidationError({
                "membership_type": _("Select a membership type from the event's organizer."),
            })
