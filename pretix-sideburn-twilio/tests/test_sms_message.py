"""
Waiting-list voucher SMS text and its length in billed SMS segments.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-twilio/tests/test_sms_message.py -v
"""
from pathlib import Path

import pytest
from babel.messages.pofile import read_po
from django_scopes import scopes_disabled

import pretix_twilio_sms
from pretix.base.models import WaitingListEntry
from pretix_twilio_sms import services
from pretix_twilio_sms.services import sms_segment_count
from pretix_twilio_sms.signals import waiting_list_sms_extra_text

TEST_EMAIL = "waitlist@example.com"
PRODUCTION_URL = "https://tickets.sideburn.ca/sideburn/sideburn2027/redeem?voucher=" + "A" * 16
INTRO = "Your Sideburn waitlist number is up! Voucher: {url}"
OPT_OUT = "Reply STOP to opt out."
FR_CATALOG = Path(pretix_twilio_sms.__file__).parent / "locale" / "fr" / "LC_MESSAGES" / "django.po"


def french(msgid):
    with FR_CATALOG.open(encoding="utf-8") as f:
        return read_po(f)[msgid].string


@pytest.fixture
@scopes_disabled()
def entry(twilio_env):
    event = twilio_env["event"]
    voucher = event.vouchers.create(item=twilio_env["item"], block_quota=True)
    return WaitingListEntry.objects.create(
        event=event, item=twilio_env["item"], email=TEST_EMAIL, voucher=voucher
    )


@pytest.mark.django_db
@scopes_disabled()
def test_voucher_sms_text(entry):
    url = services._build_waiting_list_redeem_url(entry.event, entry.voucher)

    assert services._build_waiting_list_sms_message(entry) == "{} {}".format(INTRO.format(url=url), OPT_OUT)


@pytest.mark.django_db
@scopes_disabled()
def test_extra_text_goes_before_opt_out(entry, monkeypatch):
    monkeypatch.setattr(
        waiting_list_sms_extra_text,
        "send",
        lambda sender, **kwargs: [(None, "Extra one."), (None, None), (None, "Extra two.")],
    )

    message = services._build_waiting_list_sms_message(entry)

    assert message.endswith(" Extra one. Extra two. Reply STOP to opt out.")


@pytest.mark.parametrize("intro, opt_out", [
    (INTRO, OPT_OUT),
    (french(INTRO), french(OPT_OUT)),
], ids=["en", "fr"])
def test_voucher_sms_fits_one_segment(intro, opt_out):
    assert sms_segment_count("{} {}".format(intro.format(url=PRODUCTION_URL), opt_out)) == 1


@pytest.mark.parametrize("text, segments", [
    ("a" * 160, 1),
    ("a" * 161, 2),
    ("a" * 306, 2),
    ("a" * 307, 3),
    ("€" * 80, 1),
    ("€" * 81, 2),
    ("ê" * 70, 1),
    ("ê" * 71, 2),
    ("a" * 159 + "’", 3),
])
def test_sms_segment_count(text, segments):
    assert sms_segment_count(text) == segments
