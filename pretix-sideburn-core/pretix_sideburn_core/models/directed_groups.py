from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class DirectedGroupCategory(models.Model):
    """
    Event-scoped label for partitioning directed groups (admin-defined enum).
    """

    event = models.ForeignKey(
        "pretixbase.Event",
        on_delete=models.CASCADE,
        related_name="directed_group_categories",
        verbose_name=_("Event"),
    )
    name = models.CharField(
        max_length=190,
        verbose_name=_("Name"),
    )

    class Meta:
        verbose_name = _("Directed group category")
        verbose_name_plural = _("Directed group categories")
        constraints = [
            models.UniqueConstraint(
                fields=["event", "name"],
                name="sideburn_core_dgm_unique_category_name_per_event",
            ),
        ]

    def __str__(self):
        return self.name


class DirectedGroup(models.Model):
    """
    Admin-defined group with a customer leader and a fixed slot capacity for
    directed ticket assignment. Slots are created on submit, not pre-materialized.
    """

    event = models.ForeignKey(
        "pretixbase.Event",
        on_delete=models.CASCADE,
        related_name="directed_groups",
        verbose_name=_("Event"),
    )
    item = models.ForeignKey(
        "pretixbase.Item",
        on_delete=models.CASCADE,
        related_name="directed_groups",
        verbose_name=_("Product"),
    )
    variation = models.ForeignKey(
        "pretixbase.ItemVariation",
        on_delete=models.CASCADE,
        related_name="directed_groups",
        verbose_name=_("Variation"),
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        DirectedGroupCategory,
        on_delete=models.SET_NULL,
        related_name="groups",
        verbose_name=_("Category"),
        null=True,
        blank=True,
    )
    leader = models.ForeignKey(
        "pretixbase.Customer",
        on_delete=models.CASCADE,
        related_name="directed_groups_led",
        verbose_name=_("Leader"),
    )
    name = models.CharField(
        max_length=190,
        verbose_name=_("Name"),
    )
    slot_count = models.PositiveIntegerField(
        verbose_name=_("Slot count"),
        validators=[MinValueValidator(0)],
        default=0,
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
        related_name="directed_groups_created",
        verbose_name=_("Created by"),
    )

    class Meta:
        verbose_name = _("Directed group")
        verbose_name_plural = _("Directed groups")

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        errors = {}
        if self.event_id and self.item_id and self.item.event_id != self.event_id:
            errors["item"] = _("Select a product from this event.")
        if self.item_id and self.variation_id and self.variation.item_id != self.item_id:
            errors["variation"] = _("Select a variation of the chosen product.")
        if (
            self.category_id
            and self.event_id
            and self.category.event_id != self.event_id
        ):
            errors["category"] = _("Select a category from this event.")
        if (
            self.leader_id
            and self.event_id
            and self.leader.organizer_id != self.event.organizer_id
        ):
            errors["leader"] = _("Select a customer from this event's organizer.")
        if errors:
            raise ValidationError(errors)

    @property
    def slots_used(self):
        return self.slots.count()

    @property
    def slots_remaining(self):
        return max(0, self.slot_count - self.slots_used)


class DirectedGroupSlot(models.Model):
    """
    One submitted assignment in a directed group. Capacity is on DirectedGroup.slot_count;
    this row exists only while a name/email occupies a slot.
    """

    DECISION_PENDING = "pending"
    DECISION_REJECTED = "rejected"
    DECISION_NO_ACCOUNT = "no_account"
    DECISION_ALREADY_TICKETED = "already_ticketed"
    DECISION_CHOICES = (
        (DECISION_PENDING, _("Pending approval")),
        (DECISION_REJECTED, _("Rejected")),
        (DECISION_NO_ACCOUNT, _("No account")),
        (DECISION_ALREADY_TICKETED, _("Already ticketed")),
    )

    group = models.ForeignKey(
        DirectedGroup,
        on_delete=models.CASCADE,
        related_name="slots",
        verbose_name=_("Group"),
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_("Name"),
    )
    email = models.EmailField(
        verbose_name=_("Email"),
    )
    customer = models.ForeignKey(
        "pretixbase.Customer",
        on_delete=models.SET_NULL,
        related_name="directed_group_slots",
        verbose_name=_("Customer"),
        null=True,
        blank=True,
    )
    decision = models.CharField(
        max_length=32,
        choices=DECISION_CHOICES,
        blank=True,
        default="",
        verbose_name=_("Decision"),
    )
    voucher = models.ForeignKey(
        "pretixbase.Voucher",
        on_delete=models.SET_NULL,
        related_name="directed_group_slots",
        verbose_name=_("Voucher"),
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Submitted at"),
    )
    decided_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Decided at"),
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="directed_group_slots_decided",
        verbose_name=_("Decided by"),
    )

    class Meta:
        verbose_name = _("Directed group slot")
        verbose_name_plural = _("Directed group slots")
        constraints = [
            models.UniqueConstraint(
                fields=["group", "email"],
                name="sideburn_core_dgm_unique_email_per_group",
            ),
        ]

    def __str__(self):
        return "{} <{}>".format(self.name, self.email)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()
        super().save(*args, **kwargs)
