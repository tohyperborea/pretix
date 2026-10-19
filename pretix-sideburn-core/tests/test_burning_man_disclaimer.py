"""
Burning Man Project regional event disclaimer at the bottom of the event front page.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_burning_man_disclaimer.py -v
"""
import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer

EMAIL = "customer@example.org"
PASSWORD = "customerpass"
DISCLAIMER = "Burning Man Project is not a producer or organizer of the Regional Event"


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


def front_page(client, env):
    response = client.get("/{}/{}/".format(env["organizer"].slug, env["event"].slug))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_disclaimer_on_front_page(client, env):
    response = client.post(
        "/{}/account/login".format(env["organizer"].slug), {"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 302
    assert DISCLAIMER in front_page(client, env)


@pytest.mark.django_db
def test_no_disclaimer_without_the_plugin(client, env):
    env["event"].disable_plugin("pretix_sideburn_core")
    env["event"].save()
    assert DISCLAIMER not in front_page(client, env)
