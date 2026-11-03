from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import reverse
from django.utils.translation import gettext
from i18nfield.strings import LazyI18nString

from pretix.base.email import SimpleFunctionalMailTextPlaceholder
from pretix.base.settings import settings_hierarkey
from pretix.base.signals import (
    item_copy_data,
    register_mail_placeholders,
    waitinglist_entry_created,
)
from pretix.control.signals import item_forms, waitinglist_index_html
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.signals import (
    checkout_questions_top,
    front_page_bottom,
    sold_out_availability,
    waitinglist_form_class,
    waitinglist_template_name,
)

from .forms import ItemLotteryGroupsForm, waitinglist_form_with_group
from .services.groups import groups_allowed, set_groups_allowed
from .services.presale import get_sold_out_label
from .services.rank import get_waiting_list_rank
from .services.waitinglist import (
    DEFAULT_MAIL_TEXT_WAITING_LIST_CONFIRM,
    send_signup_confirmation,
)
from .views.presale import get_waiting_list_ranks

settings_hierarkey.add_default(
    "mail_text_waiting_list_confirm",
    LazyI18nString.from_gettext(DEFAULT_MAIL_TEXT_WAITING_LIST_CONFIRM),
    LazyI18nString,
)
settings_hierarkey.add_default("lottery_group_max_size", "10", int)


@receiver(register_mail_placeholders, dispatch_uid="sideburn_lottery_waiting_list_position")
def register_waiting_list_position_placeholder(sender, **kwargs):
    return SimpleFunctionalMailTextPlaceholder(
        "waiting_list_position",
        ["waiting_list_entry"],
        lambda waiting_list_entry: (
            (lambda position: str(position) if position is not None else "")(
                get_waiting_list_rank(waiting_list_entry)
            )
        ),
        "42",
    )


@receiver(front_page_bottom, dispatch_uid="sideburn_lottery_front_page_rank")
def render_waiting_list_rank(sender, request, subevent=None, **kwargs):
    if not getattr(request, "customer", None):
        return ""
    event = sender
    if not event.settings.waiting_list_enabled:
        return ""
    ev = subevent or event
    if not ev.presale_is_running:
        return ""

    ranks = get_waiting_list_ranks(event, request.customer.email)
    template = get_template(
        "pretix_sideburn_lottery/fragment/waitinglist_rank.html"
    )
    return template.render(
        {
            "request": request,
            "waiting_list_ranks": ranks,
            "show_group_column": any(p["group"] or p["can_start_group"] for p in ranks),
            "group_url": eventreverse(event, "plugins:pretix_sideburn_lottery:group"),
        },
        request=request,
    )


@receiver(waitinglist_template_name, dispatch_uid="sideburn_lottery_waitinglist_template")
def provide_waitinglist_template(sender, **kwargs):
    return "pretix_sideburn_lottery/waitinglist.html"


@receiver(waitinglist_form_class, dispatch_uid="sideburn_lottery_waitinglist_group_form")
def inject_waitinglist_group_fields(sender, cls, **kwargs):
    return waitinglist_form_with_group(cls)


@receiver(item_forms, dispatch_uid="sideburn_lottery_item_groups_form")
def item_lottery_groups_form(sender, request, item, **kwargs):
    return ItemLotteryGroupsForm(
        event=sender,
        item=item,
        data=(request.POST if request.method == "POST" else None),
        prefix="sideburn_lottery",
    )


@receiver(item_copy_data, dispatch_uid="sideburn_lottery_item_copy_groups")
def copy_item_lottery_groups_setting(sender, source, target, **kwargs):
    set_groups_allowed(target.event, target.pk, groups_allowed(source.event, source.pk))


@receiver(sold_out_availability, dispatch_uid="sideburn_lottery_sold_out_availability")
def render_sold_out_availability(
    sender,
    item,
    variation=None,
    allow_waitinglist=False,
    cart_namespace=None,
    subevent=None,
    compact=False,
    **kwargs,
):
    template = get_template(
        "pretix_sideburn_lottery/fragment/sold_out_availability.html"
    )
    return template.render(
        {
            "event": sender,
            "item": item,
            "variation": variation,
            "allow_waitinglist": allow_waitinglist,
            "cart_namespace": cart_namespace,
            "subevent": subevent,
            "compact": compact,
            "sold_out_label": get_sold_out_label(sender, item.pk),
        }
    )


@receiver(checkout_questions_top, dispatch_uid="sideburn_lottery_checkout_waiver")
def render_checkout_waiver(sender, request, **kwargs):
    template = get_template(
        "pretix_sideburn_lottery/fragment/checkout_waiver.html"
    )
    return template.render({"request": request}, request=request)


@receiver(waitinglist_index_html, dispatch_uid="sideburn_lottery_waitinglist_index_html")
def render_waitinglist_lottery_actions(sender, request, **kwargs):
    template = get_template(
        "pretix_sideburn_lottery/fragment/waitinglist_lottery_actions.html"
    )
    kwargs = {
        "organizer": request.event.organizer.slug,
        "event": request.event.slug,
    }
    ctx = {
        "request": request,
        "run_url": reverse("plugins:pretix_sideburn_lottery:run", kwargs=kwargs),
        "revert_url": reverse(
            "plugins:pretix_sideburn_lottery:revert", kwargs=kwargs
        ),
    }
    return template.render(ctx, request=request)


@receiver(waitinglist_entry_created, dispatch_uid="sideburn_lottery_signup_confirm")
def send_waitinglist_signup_confirmation(sender, entry, **kwargs):
    send_signup_confirmation(entry, user=kwargs.get("user"), auth=kwargs.get("auth"))


try:
    from pretix_twilio_sms.signals import waiting_list_sms_extra_text
except ImportError:
    waiting_list_sms_extra_text = None

if waiting_list_sms_extra_text is not None:
    @receiver(waiting_list_sms_extra_text, dispatch_uid="sideburn_lottery_sms_group_reminder")
    def group_reminder_sms_text(sender, entry, **kwargs):
        if groups_allowed(sender, entry.item_id):
            # Translators: Sent by SMS. Avoid characters such as "ê" or curly apostrophes, which
            # make the SMS cost more than twice as much.
            return gettext("If you're in a group, remind your friends to buy their tickets too!")
