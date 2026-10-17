"""
Phase 2.5 behavioral waiting-list tests for pretix-sideburn-lottery.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_behavior.py -v
"""
import datetime
from datetime import timedelta

import pytest
from django.core import mail as djmail
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    CartPosition, Event, Item, Organizer, Quota, Team, Voucher,
    WaitingListEntry,
)
from pretix.base.models.waitinglist import WaitingListException


@pytest.fixture
@scopes_disabled()
def behavior_env():
    organizer = Organizer.objects.create(name="Dummy", slug="dummy")
    event = Event.objects.create(
        organizer=organizer,
        name="Dummy",
        slug="dummy",
        date_from=datetime.datetime(now().year + 1, 12, 26, 14, 0, tzinfo=datetime.timezone.utc),
        live=True,
        plugins="pretix_sideburn_lottery",
    )
    event.settings.set("waiting_list_enabled", True)
    quota = Quota.objects.create(name="Test", size=0, event=event)
    item = Item.objects.create(
        event=event, name="Ticket", default_price=23, admission=True
    )
    quota.items.add(item)
    return {"organizer": organizer, "event": event, "item": item, "quota": quota}


def sign_up(client, item, email="foo@bar.com"):
    return client.post(
        "/dummy/dummy/waitinglist/?item=%d" % item.pk,
        {"email": email, "itemvar": str(item.pk)},
        follow=True,
    )


@pytest.mark.django_db
def test_waiting_list_voucher_can_be_used_while_sold_out(client, behavior_env):
    item = behavior_env["item"]
    with scopes_disabled():
        wle = WaitingListEntry.objects.create(
            event=behavior_env["event"], item=item, email="foo@bar.com"
        )
        djmail.outbox = []
        wle.send_voucher()
        wle.refresh_from_db()
        code = wle.voucher.code
    assert len(djmail.outbox) == 1
    assert code in djmail.outbox[0].body

    client.post(
        "/dummy/dummy/cart/add",
        {"item_%d" % item.pk: "1", "_voucher_code": code},
        follow=True,
    )
    with scopes_disabled():
        assert CartPosition.objects.filter(item=item, voucher__code=code).count() == 1


@pytest.mark.django_db
@scopes_disabled()
def test_send_voucher_respects_quota_without_plugin():
    organizer = Organizer.objects.create(name="Plain", slug="plain")
    event = Event.objects.create(
        organizer=organizer,
        name="Plain",
        slug="plain",
        date_from=now(),
        live=True,
    )
    quota = Quota.objects.create(name="Test", size=0, event=event)
    item = Item.objects.create(
        event=event, name="Ticket", default_price=23, admission=True
    )
    quota.items.add(item)
    wle = WaitingListEntry.objects.create(
        event=event, item=item, email="foo@bar.com"
    )
    with pytest.raises(WaitingListException):
        wle.send_voucher()


@pytest.mark.django_db
def test_signing_up_sends_lottery_confirmation_email(client, behavior_env):
    djmail.outbox = []
    sign_up(client, behavior_env["item"])

    with scopes_disabled():
        assert WaitingListEntry.objects.filter(email="foo@bar.com").exists()
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ["foo@bar.com"]
    assert djmail.outbox[0].subject == "You have been added to the lottery waiting list for Dummy"
    assert "you have been added to the lottery for Dummy" in djmail.outbox[0].body


@pytest.mark.django_db
def test_confirmation_email_can_show_waiting_list_position(client, behavior_env):
    behavior_env["event"].settings.mail_text_waiting_list_confirm = "You are number {waiting_list_position}."
    sign_up(client, behavior_env["item"], email="first@bar.com")
    djmail.outbox = []

    sign_up(client, behavior_env["item"], email="second@bar.com")

    assert len(djmail.outbox) == 1
    assert "You are number 2." in djmail.outbox[0].body


@pytest.mark.django_db
def test_signing_up_through_the_api_sends_lottery_confirmation_email(client, behavior_env):
    with scopes_disabled():
        team = Team.objects.create(
            organizer=behavior_env["organizer"], can_view_orders=True, can_change_orders=True,
            all_events=True,
        )
        token = team.tokens.create(name="Test")

    djmail.outbox = []
    response = client.post(
        "/api/v1/organizers/dummy/events/dummy/waitinglistentries/",
        {"item": behavior_env["item"].pk, "email": "api@bar.com", "locale": "en"},
        format="json",
        content_type="application/json",
        HTTP_AUTHORIZATION="Token " + token.token,
    )
    assert response.status_code == 201, response.content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ["api@bar.com"]
    assert "lottery waiting list" in djmail.outbox[0].subject


@pytest.mark.django_db
def test_signup_rejected_when_customer_already_has_a_valid_voucher(client, behavior_env):
    with scopes_disabled():
        v = Voucher.objects.create(
            event=behavior_env["event"], valid_until=now() + timedelta(days=1), redeemed=0
        )
        WaitingListEntry.objects.create(
            event=behavior_env["event"], item=behavior_env["item"], email="foo@bar.com", voucher=v
        )

    response = sign_up(client, behavior_env["item"])

    assert "You have already been assigned a ticket!" in response.content.decode()
    with scopes_disabled():
        assert WaitingListEntry.objects.filter(email="foo@bar.com").count() == 1


@pytest.mark.django_db
@scopes_disabled()
def test_duplicate_allows_expired_unredeemed_voucher(behavior_env):
    event = behavior_env["event"]
    item = behavior_env["item"]
    v = Voucher.objects.create(
        event=event, valid_until=now() - timedelta(days=1), redeemed=0
    )
    WaitingListEntry.objects.create(
        event=event, item=item, email="foo@bar.com", voucher=v
    )
    wle = WaitingListEntry(event=event, item=item, email="foo@bar.com")
    wle.full_clean()


@pytest.mark.django_db
@scopes_disabled()
def test_duplicate_blocks_redeemed_voucher(behavior_env):
    event = behavior_env["event"]
    item = behavior_env["item"]
    v = Voucher.objects.create(
        event=event, valid_until=now() - timedelta(days=1), redeemed=1
    )
    WaitingListEntry.objects.create(
        event=event, item=item, email="foo@bar.com", voucher=v
    )
    wle = WaitingListEntry(event=event, item=item, email="foo@bar.com")
    with pytest.raises(ValidationError):
        wle.full_clean()


@pytest.mark.django_db
@scopes_disabled()
def test_duplicate_blocks_valid_unredeemed_voucher(behavior_env):
    event = behavior_env["event"]
    item = behavior_env["item"]
    v = Voucher.objects.create(
        event=event, valid_until=now() + timedelta(days=1), redeemed=0
    )
    WaitingListEntry.objects.create(
        event=event, item=item, email="foo@bar.com", voucher=v
    )
    wle = WaitingListEntry(event=event, item=item, email="foo@bar.com")
    with pytest.raises(ValidationError):
        wle.full_clean()
