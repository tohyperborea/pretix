from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy

from pretix.base.models import WaitingListEntry

DUPLICATE_VOUCHER_MESSAGE = gettext_lazy(
    "You have already been assigned a ticket! "
    "Contact ticketing@sideburn.ca if this is in error."
)


def validate_no_active_voucher_duplicate(entry):
    """
    Reject signup when the same email/product already has a live voucher assignment.
    """
    if WaitingListEntry.objects.filter(
        item=entry.item,
        variation=entry.variation,
        email__iexact=entry.email,
        voucher__isnull=False,
        subevent=entry.subevent,
    ).exclude(pk=entry.pk).filter(
        Q(voucher__redeemed__gt=0)
        | Q(voucher__valid_until__isnull=True)
        | Q(voucher__valid_until__gte=now())
    ).exists():
        raise ValidationError(DUPLICATE_VOUCHER_MESSAGE)
