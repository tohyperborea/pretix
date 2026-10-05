"""
Presale copy tests for pretix-sideburn-lottery.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_presale_copy.py -v
"""
import datetime
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Item, Organizer, Quota


@pytest.fixture
def presale_copy_env():
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

    return {"organizer": organizer, "event": event, "item": item}


def login_customer(client, organizer, email="test@example.com", password="test"):
    with scopes_disabled():
        customer = organizer.customers.create(
            email=email, is_verified=True, is_active=True
        )
        customer.set_password(password)
        customer.save()
    response = client.post(
        f"/{organizer.slug}/account/login",
        {"email": email, "password": password},
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_waitinglist_page_sideburn_copy(client, presale_copy_env):
    organizer = presale_copy_env["organizer"]
    event = presale_copy_env["event"]
    item = presale_copy_env["item"]

    login_customer(client, organizer)
    response = client.get(
        f"/{organizer.slug}/{event.slug}/waitinglist/?item={item.pk}"
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "How do tickets work for SideBurn?" in content
    assert "Register only once per person" in content


@pytest.mark.django_db
def test_event_page_sold_out_lottery_copy(client, presale_copy_env):
    organizer = presale_copy_env["organizer"]
    event = presale_copy_env["event"]

    login_customer(client, organizer)
    response = client.get(f"/{organizer.slug}/{event.slug}/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "assigned by lottery" in content
    assert "Register here" in content


@pytest.mark.django_db
def test_checkout_questions_step_shows_waiver(client, presale_copy_env):
    organizer = presale_copy_env["organizer"]
    event = presale_copy_env["event"]
    with scopes_disabled():
        on_sale = Item.objects.create(
            event=event, name="Regular ticket", default_price=Decimal("10.00"), active=True,
        )
        Quota.objects.create(event=event, name="On sale", size=10).items.add(on_sale)

    login_customer(client, organizer)
    client.post(f"/{organizer.slug}/{event.slug}/cart/add", {f"item_{on_sale.pk}": "1"}, follow=True)
    client.post(f"/{organizer.slug}/{event.slug}/checkout/customer/", {"customer_mode": "login"}, follow=True)
    response = client.get(f"/{organizer.slug}/{event.slug}/checkout/questions/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Before you proceed, please read the following documents" in content
    assert "Release of Waiver and Liability" in content
    assert "SideBurn Code of Conduct" in content
