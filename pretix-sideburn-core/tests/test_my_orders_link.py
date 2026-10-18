"""
"My Orders" link in the storefront header: logged-in customers get the link and the script that
moves it in front of their name; it goes to the customer account's order list.

The script itself (static/pretix_sideburn_core/my_orders_link.js) has no automated test.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_my_orders_link.py -v
"""
import re

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer

EMAIL = "customer@example.org"
PASSWORD = "customerpass"
MY_ORDERS_LINK = re.compile(
    r'<template id="sideburn-my-orders-link"><a href="[^"]*/sideburntest/account/">'
    r'\s*<span[^>]*></span>\s*My Orders</a>'
)
SCRIPT = "pretix_sideburn_core/my_orders_link.js"


@pytest.fixture
@scopes_disabled()
def env():
    organizer = Organizer.objects.create(name="Sideburn Test", slug="sideburntest")
    organizer.settings.customer_accounts = True
    organizer.settings.customer_accounts_native = True
    event = Event.objects.create(
        organizer=organizer, name="Test Event", slug="testevent", date_from=now(), live=True,
        plugins="pretix_sideburn_core",
    )
    customer = organizer.customers.create(email=EMAIL, is_verified=True, is_active=True)
    customer.set_password(PASSWORD)
    customer.save()
    return {"organizer": organizer, "event": event}


def log_in(client, env):
    response = client.post(
        "/{}/account/login".format(env["organizer"].slug), {"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/sideburntest/testevent/", "/sideburntest/account/"])
def test_logged_in_customer_gets_my_orders(client, env, path):
    log_in(client, env)
    response = client.get(path)
    assert response.status_code == 200
    html = response.content.decode()
    assert MY_ORDERS_LINK.search(html)
    assert SCRIPT in html


@pytest.mark.django_db
def test_logged_out_visitor_does_not_get_my_orders(client, env):
    response = client.get("/sideburntest/account/login")
    assert response.status_code == 200
    html = response.content.decode()
    assert "My Orders" not in html
    assert SCRIPT not in html
