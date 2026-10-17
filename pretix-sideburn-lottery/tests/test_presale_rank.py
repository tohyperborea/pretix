"""
Presale waiting-list rank display tests for pretix-sideburn-lottery.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_presale_rank.py -v
"""
import datetime
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    Event, Item, Organizer, Quota, Team, User, WaitingListEntry,
)

ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


@pytest.fixture
def presale_rank_env():
    organizer = Organizer.objects.create(name="CCC", slug="ccc")
    organizer.settings.customer_accounts = True
    organizer.save()

    event = Event.objects.create(
        organizer=organizer,
        name="30C3",
        slug="30c3",
        date_from=datetime.datetime(
            now().year + 1, 12, 26, 14, 0, tzinfo=datetime.timezone.utc
        ),
        live=True,
        plugins="pretix_sideburn_lottery",
    )
    event.settings.set("waiting_list_enabled", True)

    quota = Quota.objects.create(event=event, name="Quota", size=0)
    item = Item.objects.create(
        event=event,
        name="Early-bird ticket",
        default_price=Decimal("12.00"),
        active=True,
    )
    quota.items.add(item)

    user = User.objects.create_user("admin@example.com", "admin")
    team = Team.objects.create(
        organizer=organizer, can_view_orders=True, can_change_orders=True
    )
    team.members.add(user)
    team.limit_events.add(event)

    with scopes_disabled():
        create_customer(organizer)

    return {
        "organizer": organizer,
        "event": event,
        "item": item,
        "quota": quota,
        "user": user,
    }


def login_customer(client, organizer, email="test@example.com", password="test"):
    response = client.post(
        f"/{organizer.slug}/account/login",
        {"email": email, "password": password},
    )
    assert response.status_code == 302


def create_customer(organizer, email="test@example.com", password="test"):
    customer = organizer.customers.create(
        email=email, is_verified=True, is_active=True
    )
    customer.set_password(password)
    customer.save()
    return customer


def event_page(client, env):
    login_customer(client, env["organizer"])
    response = client.get(f"/{env['organizer'].slug}/{env['event'].slug}/")
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_rank_box_before_lottery(client, presale_rank_env):
    with scopes_disabled():
        WaitingListEntry.objects.create(
            event=presale_rank_env["event"], item=presale_rank_env["item"], email="test@example.com"
        )

    content = event_page(client, presale_rank_env)
    assert "Check my spot in line" in content
    assert "Early-bird ticket" in content
    assert "yet been run" in content


@pytest.mark.django_db
def test_rank_box_not_on_waiting_list(client, presale_rank_env):
    content = event_page(client, presale_rank_env)
    assert "You are not on the waiting list for this event." in content


@pytest.mark.django_db
def test_rank_box_hidden_when_logged_out(client, presale_rank_env):
    env = presale_rank_env
    response = client.get(f"/{env['organizer'].slug}/{env['event'].slug}/")
    assert "Check my spot in line" not in response.content.decode()


@pytest.mark.django_db
def test_rank_box_lists_each_product(client, presale_rank_env):
    event = presale_rank_env["event"]
    with scopes_disabled():
        item2 = Item.objects.create(
            event=event, name="VIP ticket", default_price=Decimal("50.00"), active=True,
        )
        presale_rank_env["quota"].items.add(item2)
        WaitingListEntry.objects.create(event=event, item=presale_rank_env["item"], email="test@example.com")
        WaitingListEntry.objects.create(event=event, item=item2, email="test@example.com")

    content = event_page(client, presale_rank_env)
    assert "Early-bird ticket" in content
    assert "VIP ticket" in content


@pytest.mark.django_db
def test_rank_after_lottery_matches_admin_list(client, presale_rank_env):
    organizer = presale_rank_env["organizer"]
    event = presale_rank_env["event"]
    item = presale_rank_env["item"]
    user = presale_rank_env["user"]

    with scopes_disabled():
        for i in range(3):
            WaitingListEntry.objects.create(event=event, item=item, email=f"other{i}@example.com")
        WaitingListEntry.objects.create(event=event, item=item, email="test@example.com")

    client.login(email=user.email, password="admin")
    response = client.get(
        f"/control/event/{organizer.slug}/{event.slug}/sideburn-lottery/run/?item={item.pk}"
    )
    assert response.status_code == 200
    response = client.get(f"/control/event/{organizer.slug}/{event.slug}/waitinglist/?item={item.pk}")
    admin_order = [e.email for e in response.context["entries"]]
    expected = ORDINALS[admin_order.index("test@example.com") + 1]
    client.logout()

    content = event_page(client, presale_rank_env)
    assert f"You are {expected} in line" in content
    assert "yet been run" not in content


@pytest.mark.django_db
def test_rank_box_shows_voucher_waiting(client, presale_rank_env):
    event = presale_rank_env["event"]
    item = presale_rank_env["item"]
    with scopes_disabled():
        voucher = event.vouchers.create(
            item=item, block_quota=True, valid_until=now() + datetime.timedelta(days=5),
        )
        WaitingListEntry.objects.create(event=event, item=item, email="test@example.com", voucher=voucher)

    content = event_page(client, presale_rank_env)
    assert "You have a voucher waiting for redemption!" in content


@pytest.mark.django_db
def test_rank_box_shows_expired_voucher(client, presale_rank_env):
    event = presale_rank_env["event"]
    item = presale_rank_env["item"]
    with scopes_disabled():
        voucher = event.vouchers.create(
            item=item, block_quota=True, valid_until=now() - datetime.timedelta(days=1),
        )
        WaitingListEntry.objects.create(event=event, item=item, email="test@example.com", voucher=voucher)

    content = event_page(client, presale_rank_env)
    assert "Your voucher expired on" in content
    assert "re-enter the waiting list" in content


@pytest.mark.django_db
def test_rank_box_hides_product_after_ticket_bought(client, presale_rank_env):
    event = presale_rank_env["event"]
    item = presale_rank_env["item"]
    with scopes_disabled():
        voucher = event.vouchers.create(item=item, block_quota=True, redeemed=1)
        WaitingListEntry.objects.create(event=event, item=item, email="test@example.com", voucher=voucher)

    content = event_page(client, presale_rank_env)
    assert "You are not on the waiting list for this event." in content


@pytest.mark.django_db
def test_rank_box_uses_latest_signup_after_expired_voucher(client, presale_rank_env):
    event = presale_rank_env["event"]
    item = presale_rank_env["item"]
    with scopes_disabled():
        voucher = event.vouchers.create(
            item=item, block_quota=True, valid_until=now() - datetime.timedelta(days=1),
        )
        old = WaitingListEntry.objects.create(event=event, item=item, email="test@example.com", voucher=voucher)
        WaitingListEntry.objects.filter(pk=old.pk).update(created=now() - datetime.timedelta(days=3))
        WaitingListEntry.objects.create(event=event, item=item, email="test@example.com")

    content = event_page(client, presale_rank_env)
    assert "Your voucher expired on" not in content
    assert "yet been run" in content
