from django.db import transaction
from django.http import QueryDict
from django.utils.timezone import now

from pretix.base.models import CartPosition, WaitingListEntry
from pretix.control.views.waitinglist import WaitingListQuerySetMixin

SELECTION_PARAMS = ("status", "item", "subevent", "__ALL")

STATE_WAITING = "waiting"
STATE_REDEEMED = "redeemed"
STATE_EXPIRED = "expired"
STATE_VALID = "valid"
STATES = (STATE_WAITING, STATE_REDEEMED, STATE_EXPIRED, STATE_VALID)

VOUCHER_EXPIRE = "expire"
VOUCHER_KEEP = "keep"
VOUCHER_DELETE = "delete"
VOUCHER_ACTIONS = (VOUCHER_EXPIRE, VOUCHER_KEEP, VOUCHER_DELETE)


class _SelectionQuerySet(WaitingListQuerySetMixin):
    def __init__(self, request, params):
        self.request = request
        data = QueryDict(mutable=True)
        for key in SELECTION_PARAMS:
            if params.get(key):
                data[key] = params[key]
        data.setlist("entry", params.getlist("entry"))
        self.request_data = data


def selected_entries(request, params):
    """
    The entries ticked on the waiting-list page, resolved the same way as core's "Delete selected":
    the ticked rows, or every entry matching the filters when "select all results on other pages" is ticked.
    Nothing is selected without either.

    Raises ValueError for malformed filter or entry values.
    """
    qs = _SelectionQuerySet(request, params).get_queryset(force_filtered=True)
    return list(qs.select_related("voucher"))


def entries_by_id(event, ids):
    """Raises ValueError for non-numeric ids."""
    ids = [int(i) for i in ids]
    return list(
        WaitingListEntry.objects.filter(event=event, id__in=ids).select_related("item", "variation", "voucher")
    )


def entry_state(entry):
    voucher = entry.voucher
    if voucher is None:
        return STATE_WAITING
    if voucher.redeemed >= voucher.max_usages:
        return STATE_REDEEMED
    if voucher.valid_until is not None and voucher.valid_until <= now():
        return STATE_EXPIRED
    return STATE_VALID


def group_by_state(entries):
    groups = {state: [] for state in STATES}
    for entry in entries:
        groups[entry_state(entry)].append(entry)
    return groups


@transaction.atomic
def delete_entries(entries, voucher_action, user):
    """
    Delete the given entries. Vouchers that are still valid are expired, kept, or deleted
    (deletion only if unredeemed; otherwise they are expired) according to voucher_action.
    Redeemed and expired vouchers are left untouched.
    """
    if voucher_action not in VOUCHER_ACTIONS:
        raise ValueError(voucher_action)

    for entry in entries:
        voucher = entry.voucher
        state = entry_state(entry)
        data = {"bulk": True}
        if voucher is not None:
            data.update({"voucher": voucher.code, "voucher_state": state, "voucher_action": voucher_action})
        entry.log_action("pretix.event.orders.waitinglist.deleted", user=user, data=data)
        entry.delete()

        if state != STATE_VALID or voucher_action == VOUCHER_KEEP:
            continue
        if voucher_action == VOUCHER_DELETE and voucher.allow_delete():
            voucher.log_action("pretix.voucher.deleted", user=user)
            CartPosition.objects.filter(addon_to__voucher=voucher).delete()
            voucher.cartposition_set.all().delete()
            voucher.delete()
        else:
            voucher.valid_until = now()
            voucher.save(update_fields=["valid_until"])
            voucher.log_action(
                "pretix.voucher.changed", user=user, data={"valid_until": voucher.valid_until.isoformat()}
            )
