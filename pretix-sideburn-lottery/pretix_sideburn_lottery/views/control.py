from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views import View

from pretix.base.models import Item
from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.control.views.waitinglist import WaitingListQuerySetMixin

from ..services.lottery import run_lottery
from ..services.selected_delete import (
    STATE_EXPIRED, STATE_REDEEMED, STATE_VALID, STATE_WAITING,
    VOUCHER_ACTIONS, VOUCHER_EXPIRE, delete_entries, entries_by_id,
    group_by_state, selected_entries,
)


class BaseLotteryView(EventPermissionRequiredMixin, WaitingListQuerySetMixin, View):
    permission = "can_change_orders"
    revert = False

    def _waitinglist_url(self):
        return reverse(
            "control:event.orders.waitinglist",
            kwargs={
                "event": self.request.event.slug,
                "organizer": self.request.event.organizer.slug,
            },
        )

    def get(self, request, *args, **kwargs):
        item_id = request.GET.get("item", "")
        if not item_id:
            messages.error(
                request,
                _("You must select a product to run or revert its lottery."),
            )
            return redirect(self._waitinglist_url())

        try:
            Item.objects.get(pk=item_id, event=request.event)
        except (ValueError, Item.DoesNotExist):
            messages.error(request, _("Invalid product selected."))
            return redirect(self._waitinglist_url())

        response = run_lottery(
            request.event,
            self.get_queryset(),
            item_id,
            revert=self.revert,
        )
        if response is None:
            messages.error(
                request,
                _("No waiting list entries found for the selected product."),
            )
            return redirect(self._waitinglist_url())

        return response


class RunLotteryView(BaseLotteryView):
    revert = False


class RevertLotteryView(BaseLotteryView):
    revert = True


class DeleteSelectedEntriesView(EventPermissionRequiredMixin, View):
    """
    Like core's "Delete selected", but also deletes entries that have a voucher. The first POST
    comes from the waiting-list form and shows a confirmation page; the second deletes.
    """
    permission = "can_change_orders"
    http_method_names = ["post"]

    def _back_url(self):
        next_url = self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            return next_url
        return reverse(
            "control:event.orders.waitinglist",
            kwargs={
                "event": self.request.event.slug,
                "organizer": self.request.event.organizer.slug,
            },
        )

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "confirm":
            return self._delete()
        return self._confirm()

    def _confirm(self):
        try:
            entries = selected_entries(self.request, self.request.POST)
        except ValueError:
            messages.error(self.request, _("Invalid selection."))
            return redirect(self._back_url())
        if not entries:
            messages.error(self.request, _("You did not select any entries."))
            return redirect(self._back_url())

        groups = group_by_state(entries)
        return render(self.request, "pretix_sideburn_lottery/delete_selected.html", {
            "total": len(entries),
            "groups": [
                (_("Still waiting (no voucher yet)"), groups[STATE_WAITING]),
                (_("Voucher redeemed (ticket bought)"), groups[STATE_REDEEMED]),
                (_("Voucher expired"), groups[STATE_EXPIRED]),
                (_("Voucher still valid"), groups[STATE_VALID]),
            ],
            "has_valid": bool(groups[STATE_VALID]),
            "back_url": self._back_url(),
        })

    def _delete(self):
        voucher_action = self.request.POST.get("voucher_action", VOUCHER_EXPIRE)
        if voucher_action not in VOUCHER_ACTIONS:
            messages.error(self.request, _("Please choose what should happen to vouchers that are still valid."))
            return redirect(self._back_url())
        try:
            entries = entries_by_id(self.request.event, self.request.POST.getlist("entry"))
        except ValueError:
            messages.error(self.request, _("Invalid selection."))
            return redirect(self._back_url())
        if not entries:
            messages.error(self.request, _("You did not select any entries."))
            return redirect(self._back_url())

        delete_entries(entries, voucher_action, self.request.user)
        messages.success(self.request, _("{num} waiting list entries have been deleted.").format(num=len(entries)))
        return redirect(self._back_url())
