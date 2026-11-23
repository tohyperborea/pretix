from urllib.parse import quote

from django.db import transaction
from django.dispatch import receiver
from django.http import Http404
from django.shortcuts import redirect
from django.template.loader import get_template
from django.urls import Resolver404, resolve, reverse
from django.utils.translation import gettext_lazy as _, gettext_noop
from i18nfield.strings import LazyI18nString

from pretix.base.models import Order
from pretix.base.settings import settings_hierarkey
from pretix.base.signals import (
    event_copy_data, item_copy_data, waiting_list_send_voucher,
    waitinglist_entry_validate,
)
from pretix.control.signals import item_forms, nav_organizer, waitinglist_index_html
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.signals import (
    customer_order_actions, front_page_bottom, process_request,
    waitinglist_form_class,
)

from .dgm import (
    dgm_enabled, dgm_leader_deadline, set_dgm_enabled, set_dgm_leader_deadline,
)
from .forms import ItemDirectedGroupsForm, waitinglist_form_with_readonly_email
from .models import DirectedGroup, DirectedGroupCategory
from .waitinglist import validate_no_active_voucher_duplicate

# Hierarkey defaults are global, so this applies to every event on the instance, with or
# without the plugin enabled.
settings_hierarkey.add_default(
    "checkout_email_helptext",
    LazyI18nString.from_gettext(gettext_noop(
        "We will send you an order confirmation including a link that you need to access your order later."
    )),
    LazyI18nString,
)

# Core's header shows this Sideburn string (fragment_login_status.html); listing it here keeps
# makemessages from dropping its French translation from this plugin's catalog.
gettext_noop("My Orders")


@receiver(event_copy_data, dispatch_uid="sideburn_core_copy_membership_discount_rules")
@transaction.atomic
def copy_membership_discount_rules(sender, other, item_map, **kwargs):
    if sender.organizer_id != other.organizer_id:
        return

    for rule in other.membership_discount_rules.prefetch_related("products"):
        copied_rule = sender.membership_discount_rules.create(
            membership_type_id=rule.membership_type_id,
            discount_percent=rule.discount_percent,
            label=rule.label,
        )
        copied_rule.products.set(
            [item_map[product.pk] for product in rule.products.all() if product.pk in item_map]
        )


@receiver(event_copy_data, dispatch_uid="sideburn_core_copy_directed_groups")
@transaction.atomic
def copy_directed_groups(sender, other, item_map, variation_map, **kwargs):
    """
    Clone DGM product settings, categories, and groups. Leaders are cleared and
    slot assignment rows are not copied (capacity via slot_count only).
    """
    for old_item_id, new_item in item_map.items():
        set_dgm_enabled(sender, new_item.pk, dgm_enabled(other, old_item_id))
        set_dgm_leader_deadline(
            sender, new_item.pk, dgm_leader_deadline(other, old_item_id)
        )

    category_map = {}
    for category in other.directed_group_categories.all():
        category_map[category.pk] = DirectedGroupCategory.objects.create(
            event=sender,
            name=category.name,
        )

    for group in other.directed_groups.all():
        if group.item_id not in item_map:
            continue
        variation = None
        if group.variation_id:
            variation = variation_map.get(group.variation_id)
            if variation is None:
                continue
        DirectedGroup.objects.create(
            event=sender,
            item=item_map[group.item_id],
            variation=variation,
            category=category_map.get(group.category_id),
            leader=None,
            name=group.name,
            slot_count=group.slot_count,
            created_by=None,
        )


# Storefront pages that need a logged-in customer. Everything else stays public, notably
# order pages (secret links), resend_link, auth, favicon, iCal, widget CSS and
# waitinglist.remove (the voucher code in the link is the protection).
LOGIN_REQUIRED_URL_NAMES = {"event.index", "event.waitinglist", "event.redeem", "event.checkout"}
LOGIN_REQUIRED_URL_PREFIXES = ("event.cart.", "event.checkout.")


def _requires_login(url_name):
    return url_name in LOGIN_REQUIRED_URL_NAMES or url_name.startswith(LOGIN_REQUIRED_URL_PREFIXES)


@receiver(process_request, dispatch_uid="sideburn_core_require_customer_login")
def require_customer_login(sender, request, **kwargs):
    try:
        url_name = resolve(request.path_info).url_name or ""
    except Resolver404:
        return None
    if not _requires_login(url_name) or getattr(request, "customer", None):
        return None
    if not request.organizer.settings.customer_accounts:
        raise Http404("Feature not enabled")
    return redirect(
        eventreverse(request.organizer, "presale:organizer.customer.login", kwargs={})
        + "?next=" + quote(request.path_info + "?" + request.GET.urlencode())
    )


@receiver(waitinglist_form_class, dispatch_uid="sideburn_core_waitinglist_readonly_email")
def waitinglist_readonly_email(sender, cls, **kwargs):
    return waitinglist_form_with_readonly_email(cls)


@receiver(customer_order_actions, dispatch_uid="sideburn_core_customer_order_cancel")
def customer_order_cancel_button(sender, order, request, **kwargs):
    if order.user_cancel_allowed:
        # Mirrors OrderCancelDo: only paid orders with a non-zero total go through approval.
        requires_approval = (
            order.status == Order.STATUS_PAID
            and order.total != 0
            and sender.settings.cancel_allow_user_paid_require_approval
        )
        state = "request" if requires_approval else "cancel"
    elif order.cancellation_requests.exists():
        state = "requested"
    else:
        return None
    template = get_template("pretix_sideburn_core/fragment/customer_order_cancel.html")
    return template.render({"order": order, "state": state})


@receiver(front_page_bottom, dispatch_uid="sideburn_core_burning_man_disclaimer")
def burning_man_disclaimer(sender, request, **kwargs):
    return get_template("pretix_sideburn_core/fragment/burning_man_disclaimer.html").render({})


@receiver(waitinglist_entry_validate, dispatch_uid="sideburn_core_validate_duplicate_voucher")
def validate_waitinglist_duplicate_voucher(sender, entry, **kwargs):
    validate_no_active_voucher_duplicate(entry)


@receiver(waiting_list_send_voucher, dispatch_uid="sideburn_core_ignore_quota")
def allow_waitinglist_ignore_quota(sender, entry, **kwargs):
    return {"ignore_quota": True}


@receiver(waitinglist_index_html, dispatch_uid="sideburn_core_waitinglist_delete_selected")
def render_waitinglist_delete_selected(sender, request, **kwargs):
    if "event.orders:write" not in request.eventpermset:
        return ""
    template = get_template("pretix_sideburn_core/fragment/waitinglist_delete_selected.html")
    return template.render({
        "request": request,
        "delete_selected_url": reverse("plugins:pretix_sideburn_core:delete_selected_entries", kwargs={
            "organizer": request.event.organizer.slug,
            "event": request.event.slug,
        }),
    }, request=request)


@receiver(item_forms, dispatch_uid="sideburn_core_item_dgm_form")
def item_directed_groups_form(sender, request, item, **kwargs):
    return ItemDirectedGroupsForm(
        event=sender,
        item=item,
        data=(request.POST if request.method == "POST" else None),
        prefix="sideburn_dgm",
    )


@receiver(item_copy_data, dispatch_uid="sideburn_core_item_copy_dgm")
def copy_item_dgm_settings(sender, source, target, **kwargs):
    set_dgm_enabled(target.event, target.pk, dgm_enabled(source.event, source.pk))
    set_dgm_leader_deadline(
        target.event, target.pk, dgm_leader_deadline(source.event, source.pk)
    )


@receiver(nav_organizer, dispatch_uid="sideburn_core_nav_organizer_denylist")
def control_nav_organizer_allow_denylist(sender, request=None, **kwargs):
    if not request.organizer.settings.customer_accounts:
        return []
    if (
        "organizer.customers:read" not in request.orgapermset
        and "organizer.customers:write" not in request.orgapermset
    ):
        return []
    url = resolve(request.path_info)
    customers_url = reverse(
        "control:organizer.customers",
        kwargs={"organizer": request.organizer.slug},
    )
    return [
        {
            "label": _("Allow/Denylist"),
            "parent": customers_url,
            "url": reverse(
                "plugins:pretix_sideburn_core:denylist",
                kwargs={"organizer": request.organizer.slug},
            ),
            "active": (
                url.namespace == "plugins:pretix_sideburn_core"
                and (
                    url.url_name.startswith("denylist")
                    or url.url_name.startswith("allowlist")
                )
            ),
        }
    ]
