from zoneinfo import ZoneInfo

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.views import View

from pretix.base.models import WaitingListEntry
from pretix.multidomain.urlreverse import eventreverse

from ..services.groups import (
    create_group,
    get_group,
    groups_allowed,
    join_group,
    leave_group,
    lottery_has_run,
)
from ..services.rank import get_waiting_list_rank


def get_waiting_list_ranks(event, customer_email):
    """
    Get waiting list ranks for a customer.

    Returns a list of product data dictionaries with rank information.
    Each dictionary contains: item_id, item_name, variation_id, variation_name, rank,
    lottery_run, the lottery group fields (group, group_size, group_max_size, can_leave_group,
    can_start_group), and optionally voucher_code, voucher_expired, and voucher_expired_date.
    """
    entries = WaitingListEntry.objects.filter(
        event=event,
        email__iexact=customer_email,
    ).select_related("item", "variation", "voucher").order_by(
        "item", "variation", "-created", "-pk"
    )

    products_data = []
    seen_products = set()

    for entry in entries:
        product_key = (entry.item_id, entry.variation_id if entry.variation else None)

        if product_key in seen_products:
            continue

        seen_products.add(product_key)

        rank = get_waiting_list_rank(entry)

        voucher_expired = False
        voucher_expired_date = None
        if rank is None and entry.voucher and not entry.voucher.is_active():
            if entry.voucher.valid_until and entry.voucher.valid_until < now():
                voucher_expired = True
                tz = ZoneInfo(event.settings.timezone)
                voucher_expired_date = entry.voucher.valid_until.astimezone(tz)

        if rank is None and not voucher_expired:
            continue

        lottery_run = lottery_has_run(event, entry.item_id)
        allowed = groups_allowed(event, entry.item_id)
        group = get_group(entry) if allowed else None
        can_change_group = not lottery_run and entry.voucher_id is None

        product_data = {
            "item_id": entry.item_id,
            "item_name": str(entry.item),
            "variation_id": entry.variation_id,
            "variation_name": str(entry.variation) if entry.variation else None,
            "rank": rank,
            "lottery_run": lottery_run,
            "group": group,
            "group_size": group.memberships.count() if group else None,
            "group_max_size": event.settings.lottery_group_max_size,
            "can_leave_group": bool(group) and can_change_group,
            "can_start_group": not group and can_change_group and allowed,
        }

        if rank == 0 and entry.voucher:
            product_data["voucher_code"] = entry.voucher.code

        if voucher_expired:
            product_data["voucher_expired"] = True
            product_data["voucher_expired_date"] = voucher_expired_date

        products_data.append(product_data)

    return products_data


class GroupView(View):
    """Create, join or leave a lottery group from the "Check my spot in line" box."""

    def post(self, request, *args, **kwargs):
        index_url = eventreverse(request.event, "presale:event.index") + "#check-waiting-list-rank"
        entry = self._waiting_entry()
        if not entry:
            messages.error(request, _("You are not on the waiting list for this product."))
            return redirect(index_url)

        action = request.POST.get("action")
        try:
            if action == "create":
                group = create_group(entry)
                messages.success(
                    request,
                    _("Your group code is %(code)s. Share it with your friends so they can join your group.")
                    % {"code": group.code},
                )
            elif action == "join":
                code = request.POST.get("code", "").strip()
                if not code:
                    messages.error(request, _("Enter the code of the group you want to join."))
                else:
                    group = join_group(entry, code)
                    messages.success(request, _("You've joined group %(code)s.") % {"code": group.code})
            elif action == "leave":
                leave_group(entry)
                messages.success(request, _("You've left your group."))
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        return redirect(index_url)

    def _waiting_entry(self):
        customer = getattr(self.request, "customer", None)
        try:
            item_id = int(self.request.POST.get("item", ""))
        except ValueError:
            return None
        if not customer:
            return None
        return (
            WaitingListEntry.objects.filter(
                event=self.request.event,
                email__iexact=customer.email,
                item_id=item_id,
                voucher__isnull=True,
            )
            .order_by("-created", "-pk")
            .first()
        )
