"""
Phase 2.5 behavioral waiting-list tests for pretix-sideburn-lottery.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_behavior.py -v
"""
import datetime

import pytest
from django.core import mail as djmail
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    Event, Item, Organizer, Quota, Team, WaitingListEntry,
)


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
            organizer=behavior_env["organizer"],
            limit_event_permissions={"event.orders:read": True, "event.orders:write": True},
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
