"""
Cancel button on the customer account's order list: shown when the customer may cancel (or
request to cancel) an order, and links to pretix's own cancellation page.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_order_cancel_button.py -v
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Item, Order, OrderPosition, Organizer

EMAIL = "customer@example.org"
PASSWORD = "customerpass"


@pytest.fixture
@scopes_disabled()
def env():
    organizer = Organizer.objects.create(name="Sideburn Test", slug="sideburntest")
    organizer.settings.customer_accounts = True
    organizer.settings.customer_accounts_native = True
    event = Event.objects.create(
        organizer=organizer, name="Test Event", slug="testevent", date_from=now() + timedelta(days=30),
        live=True, plugins="pretix_sideburn_core",
    )
    item = Item.objects.create(event=event, name="Ticket", default_price=10, admission=True, active=True)
    customer = organizer.customers.create(email=EMAIL, is_verified=True, is_active=True)
    customer.set_password(PASSWORD)
    customer.save()
    order = Order.objects.create(
        event=event, customer=customer, email=EMAIL, status=Order.STATUS_PENDING, total=Decimal("10.00"),
        datetime=now(), expires=now() + timedelta(days=10),
        sales_channel=organizer.sales_channels.get(identifier="web"),
    )
    OrderPosition.objects.create(order=order, item=item, price=Decimal("10.00"))
    return {"organizer": organizer, "event": event, "order": order}


def cancel_url(env):
    order = env["order"]
    return "/{}/{}/order/{}/{}/cancel".format(
        env["organizer"].slug, env["event"].slug, order.code, order.secret,
    )


def account_page(client, env):
    response = client.post(
        "/{}/account/login".format(env["organizer"].slug), {"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 302
    response = client.get("/{}/account/".format(env["organizer"].slug))
    assert response.status_code == 200
    return response.content.decode()


def mark_paid(env):
    env["order"].status = Order.STATUS_PAID
    env["order"].save()
    env["event"].settings.cancel_allow_user_paid = True


@pytest.mark.django_db
def test_cancel_button_on_pending_order(client, env):
    html = account_page(client, env)
    assert cancel_url(env) in html
    assert "Cancel order" in html


@pytest.mark.django_db
def test_paid_order_with_approval_says_request(client, env):
    mark_paid(env)
    env["event"].settings.cancel_allow_user_paid_require_approval = True
    html = account_page(client, env)
    assert cancel_url(env) in html
    assert "Request cancellation" in html
    assert "Cancel order" not in html


@pytest.mark.django_db
def test_paid_order_without_approval_says_cancel(client, env):
    mark_paid(env)
    html = account_page(client, env)
    assert cancel_url(env) in html
    assert "Cancel order" in html


@pytest.mark.django_db
def test_no_button_when_cancelling_is_not_allowed(client, env):
    env["event"].settings.cancel_allow_user = False
    html = account_page(client, env)
    assert cancel_url(env) not in html
    assert "Cancel order" not in html


@pytest.mark.django_db
def test_pending_request_is_shown_instead_of_button(client, env):
    mark_paid(env)
    env["event"].settings.cancel_allow_user_paid_require_approval = True
    env["order"].cancellation_requests.create(cancellation_fee=Decimal("0.00"))
    html = account_page(client, env)
    assert cancel_url(env) not in html
    assert "Cancellation requested" in html


@pytest.mark.django_db
def test_no_button_without_the_plugin(client, env):
    env["event"].disable_plugin("pretix_sideburn_core")
    env["event"].save()
    html = account_page(client, env)
    assert cancel_url(env) not in html
