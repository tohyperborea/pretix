from urllib.parse import quote

from django.dispatch import receiver
from django.http import Http404
from django.shortcuts import redirect
from django.template.loader import get_template
from django.urls import Resolver404, resolve
from django.utils.translation import gettext_noop
from i18nfield.strings import LazyI18nString

from pretix.base.models import Order
from pretix.base.settings import settings_hierarkey
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.signals import (
    customer_order_actions, global_html_footer, process_request,
    waitinglist_form_class,
)

from .forms import waitinglist_form_with_readonly_email

# Hierarkey defaults are global, so this applies to every event on the instance, with or
# without the plugin enabled.
settings_hierarkey.add_default(
    "checkout_email_helptext",
    LazyI18nString.from_gettext(gettext_noop(
        "We will send you an order confirmation including a link that you need to access your order later."
    )),
    LazyI18nString,
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


@receiver(global_html_footer, dispatch_uid="sideburn_core_my_orders_link")
def my_orders_link(sender, request, **kwargs):
    organizer = getattr(request, "organizer", None)
    if not getattr(request, "customer", None) or not organizer or not organizer.settings.customer_accounts:
        return None
    template = get_template("pretix_sideburn_core/fragment/my_orders_link.html")
    # Rendering with request= would run the context processors, which send this signal again.
    return template.render({"organizer": organizer})


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
