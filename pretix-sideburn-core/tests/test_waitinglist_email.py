"""
Read-only waiting-list email: a logged-in customer always joins the waiting list with their
account's email address, whatever is submitted.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_waitinglist_email.py -v
"""
import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Item, Organizer, Quota, WaitingListEntry
from pretix.presale.forms.waitinglist import WaitingListForm
from pretix.presale.signals import waitinglist_form_class
from pretix_sideburn_core.forms import ReadOnlyEmailMixin

EMAIL = "customer@example.org"
OTHER_EMAIL = "someone-else@example.org"
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
    quota = Quota.objects.create(event=event, name="Tickets", size=0)
    quota.items.add(item)
    customer = organizer.customers.create(email=EMAIL, is_verified=True, is_active=True)
    customer.set_password(PASSWORD)
    customer.save()
    return {"organizer": organizer, "event": event, "item": item}


def waitinglist_url(env):
    return "/{}/{}/waitinglist/?item={}".format(env["organizer"].slug, env["event"].slug, env["item"].pk)


def log_in(client, env):
    response = client.post(
        "/{}/account/login".format(env["organizer"].slug), {"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 302


def join_waiting_list(client, env, email):
    return client.post(waitinglist_url(env), {"email": email, "itemvar": str(env["item"].pk)})


@pytest.mark.django_db
def test_email_field_is_locked_to_the_customer(client, env):
    log_in(client, env)
    response = client.get(waitinglist_url(env))
    assert response.status_code == 200
    field = response.context["form"].fields["email"]
    assert field.disabled
    assert response.context["form"].initial["email"] == EMAIL


@pytest.mark.django_db
def test_submitted_email_is_ignored(client, env):
    log_in(client, env)
    response = join_waiting_list(client, env, OTHER_EMAIL)
    assert response.status_code == 302
    with scopes_disabled():
        assert WaitingListEntry.objects.get(event=env["event"]).email == EMAIL


@pytest.mark.django_db
def test_email_is_editable_without_the_plugin(client, env):
    env["event"].disable_plugin("pretix_sideburn_core")
    env["event"].save()
    log_in(client, env)
    response = join_waiting_list(client, env, OTHER_EMAIL)
    assert response.status_code == 302
    with scopes_disabled():
        assert WaitingListEntry.objects.get(event=env["event"]).email == OTHER_EMAIL


@pytest.mark.django_db
def test_form_hook_keeps_previous_plugins_form(env):
    class EarlierPluginForm(WaitingListForm):
        pass

    form_class = waitinglist_form_class.send_chained(env["event"], "cls", cls=EarlierPluginForm)
    assert issubclass(form_class, EarlierPluginForm)
    assert issubclass(form_class, ReadOnlyEmailMixin)
