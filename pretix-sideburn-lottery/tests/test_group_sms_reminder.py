"""
Group reminder added to the waiting-list voucher SMS for products that allow groups.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_group_sms_reminder.py -v
"""
import datetime
from pathlib import Path

import pytest
from babel.messages.pofile import read_po
from django.utils.timezone import now
from django_scopes import scopes_disabled

import pretix_sideburn_lottery
import pretix_twilio_sms
from pretix.base.models import Event, Item, Organizer, WaitingListEntry
from pretix_sideburn_lottery.services.groups import set_groups_allowed
from pretix_twilio_sms.services import (
    _build_waiting_list_sms_message, sms_segment_count,
)

REMINDER = "If you're in a group, remind your friends to buy their tickets too!"
PRODUCTION_URL = "https://tickets.sideburn.ca/sideburn/sideburn2027/redeem?voucher=" + "A" * 16


def french(package, msgid):
    path = Path(package.__file__).parent / "locale" / "fr" / "LC_MESSAGES" / "django.po"
    with path.open(encoding="utf-8") as f:
        return read_po(f)[msgid].string


@pytest.fixture
@scopes_disabled()
def entry():
    organizer = Organizer.objects.create(name="CCC", slug="ccc")
    event = Event.objects.create(
        organizer=organizer,
        name="30C3",
        slug="30c3",
        date_from=datetime.datetime(now().year + 1, 12, 26, 14, 0, tzinfo=datetime.timezone.utc),
        plugins="pretix_sideburn_lottery,pretix_twilio_sms",
    )
    item = Item.objects.create(event=event, name="Ticket", default_price=12)
    voucher = event.vouchers.create(item=item, block_quota=True)
    return WaitingListEntry.objects.create(event=event, item=item, email="a@example.com", voucher=voucher)


@pytest.mark.django_db
@scopes_disabled()
def test_reminder_added_before_opt_out_when_product_allows_groups(entry):
    set_groups_allowed(entry.event, entry.item_id, True)

    assert _build_waiting_list_sms_message(entry).endswith(" {} Reply STOP to opt out.".format(REMINDER))


@pytest.mark.django_db
@scopes_disabled()
def test_no_reminder_when_product_does_not_allow_groups(entry):
    assert REMINDER not in _build_waiting_list_sms_message(entry)


@pytest.mark.django_db
@scopes_disabled()
def test_no_reminder_when_lottery_plugin_is_disabled(entry):
    set_groups_allowed(entry.event, entry.item_id, True)
    entry.event.plugins = "pretix_twilio_sms"
    entry.event.save()

    assert REMINDER not in _build_waiting_list_sms_message(entry)


@pytest.mark.parametrize("intro, reminder, opt_out", [
    (
        "Your Sideburn waitlist number is up! Voucher: {url}",
        REMINDER,
        "Reply STOP to opt out.",
    ),
    (
        french(pretix_twilio_sms, "Your Sideburn waitlist number is up! Voucher: {url}"),
        french(pretix_sideburn_lottery, REMINDER),
        french(pretix_twilio_sms, "Reply STOP to opt out."),
    ),
], ids=["en", "fr"])
def test_sms_with_reminder_fits_two_segments(intro, reminder, opt_out):
    text = " ".join([intro.format(url=PRODUCTION_URL), reminder, opt_out])

    assert sms_segment_count(text) == 2
