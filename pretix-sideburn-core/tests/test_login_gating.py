"""
Login-required storefront: logged-out visitors are sent to customer login on the
storefront pages, while order links and the waiting-list removal link stay public.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_login_gating.py -v
"""
from urllib.parse import quote

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Item, Order, Organizer, Quota

EMAIL = "customer@example.org"
PASSWORD = "customerpass"


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
    event.settings.set("waiting_list_enabled", True)
    item = Item.objects.create(event=event, name="Ticket", default_price=10, admission=True, active=True)
    quota = Quota.objects.create(event=event, name="Tickets", size=10)
    quota.items.add(item)
    customer = organizer.customers.create(email=EMAIL, is_verified=True, is_active=True)
    customer.set_password(PASSWORD)
    customer.save()
    order = Order.objects.create(
        event=event, email=EMAIL, status=Order.STATUS_PENDING, total=10, datetime=now(), expires=now(),
    )
    return {"organizer": organizer, "event": event, "item": item, "order": order}


def base(env):
    return "/{}/{}/".format(env["organizer"].slug, env["event"].slug)


def login_url(env, path):
    return "/{}/account/login?next={}".format(env["organizer"].slug, quote(path))


def log_in(client, env):
    response = client.post(
        "/{}/account/login".format(env["organizer"].slug), {"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize("suffix", ["", "waitinglist/", "redeem", "checkout/start", "cart/add"])
def test_logged_out_visitor_is_sent_to_login(client, env, suffix):
    path = base(env) + suffix
    response = client.get(path)
    assert response.status_code == 302
    assert response["Location"] == login_url(env, path + "?")


@pytest.mark.django_db
def test_next_keeps_query_string(client, env):
    path = base(env) + "waitinglist/"
    response = client.get(path, {"item": env["item"].pk})
    assert response["Location"] == login_url(env, path + "?item={}".format(env["item"].pk))


@pytest.mark.django_db
def test_logged_in_customer_sees_storefront(client, env):
    log_in(client, env)
    response = client.get(base(env))
    assert response.status_code == 200


@pytest.mark.django_db
def test_order_link_stays_public(client, env):
    order = env["order"]
    response = client.get(base(env) + "order/{}/{}/".format(order.code, order.secret))
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("suffix", ["waitinglist/remove?voucher=XYZ", "resend/"])
def test_other_public_pages_are_not_redirected_to_login(client, env, suffix):
    response = client.get(base(env) + suffix)
    assert response.status_code in (200, 302)
    assert "/account/login" not in response.get("Location", "")


@pytest.mark.django_db
def test_storefront_is_public_without_the_plugin(client, env):
    env["event"].disable_plugin("pretix_sideburn_core")
    env["event"].save()
    response = client.get(base(env))
    assert response.status_code == 200


@pytest.mark.django_db
def test_404_when_customer_accounts_are_disabled(client, env):
    env["organizer"].settings.customer_accounts = False
    response = client.get(base(env))
    assert response.status_code == 404
