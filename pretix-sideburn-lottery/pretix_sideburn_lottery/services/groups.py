from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _

from pretix.base.banlist import banned

from ..models import LotteryGroup, LotteryGroupMembership

GROUP_CODE_CHARSET = "ABCDEFGHKLMNPQRSTUVWXYZ23456789"
GROUP_CODE_LENGTH = 6


def normalize_group_code(raw):
    return "".join(ch for ch in (raw or "").upper() if ch not in " -")


def generate_group_code(event):
    while True:
        code = get_random_string(GROUP_CODE_LENGTH, allowed_chars=GROUP_CODE_CHARSET)
        if banned(code):
            continue
        if not LotteryGroup.objects.filter(event=event, code=code).exists():
            return code


def lottery_has_run(event, item_id):
    return bool(event.settings.get(f"lottery_date_for_item_{item_id}"))


def get_group(entry):
    membership = LotteryGroupMembership.objects.filter(entry=entry).select_related("group").first()
    return membership.group if membership else None


def _ensure_unlocked(entry):
    if lottery_has_run(entry.event, entry.item_id):
        raise ValidationError(
            _("The lottery for this product has already taken place, so groups can no longer be changed.")
        )


def _remove_membership(entry):
    membership = LotteryGroupMembership.objects.filter(entry=entry).select_related("group").first()
    if not membership:
        return
    group = membership.group
    membership.delete()
    if not group.memberships.exists():
        group.delete()


@transaction.atomic
def create_group(entry):
    """Create a new group for the entry's product, moving the entry out of any group it's in."""
    _ensure_unlocked(entry)
    _remove_membership(entry)
    group = LotteryGroup.objects.create(
        event=entry.event,
        item_id=entry.item_id,
        code=generate_group_code(entry.event),
    )
    LotteryGroupMembership.objects.create(entry=entry, group=group)
    return group


@transaction.atomic
def join_group(entry, code):
    """Add the entry to the group with this code, moving it out of any group it's in."""
    _ensure_unlocked(entry)
    group = (
        LotteryGroup.objects.select_for_update()
        .filter(event=entry.event, code=normalize_group_code(code))
        .first()
    )
    if not group:
        raise ValidationError(_("We couldn't find a group with that code."))
    if group.item_id != entry.item_id:
        raise ValidationError(_("That group is for a different product."))
    if group.memberships.filter(entry=entry).exists():
        return group
    if group.memberships.count() >= entry.event.settings.lottery_group_max_size:
        raise ValidationError(_("That group is already full."))
    _remove_membership(entry)
    LotteryGroupMembership.objects.create(entry=entry, group=group)
    return group


@transaction.atomic
def leave_group(entry):
    """Remove the entry from its group. Deletes the group if nobody is left in it."""
    _ensure_unlocked(entry)
    _remove_membership(entry)
