"""
Per-product DGM enable + leader deadline settings.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_dgm_product_settings.py -v
"""
from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Item, Organizer, Quota, Team, User
from pretix.base.signals import item_copy_data
from pretix_sideburn_core.dgm import (
    dgm_enabled, dgm_leader_deadline, dgm_leader_editing_closed, set_dgm_enabled,
    set_dgm_leader_deadline,
)
from pretix_sideburn_core.forms import ItemDirectedGroupsForm
from pretix_sideburn_core.signals import item_directed_groups_form


@pytest.fixture
@scopes_disabled()
def env():
    organizer = Organizer.objects.create(name="Dummy", slug="dummy")
    organizer.settings.customer_accounts = True
    event = Event.objects.create(
        organizer=organizer,
        name="Dummy",
        slug="dummy",
        date_from=now(),
        live=True,
        plugins="pretix_sideburn_core",
    )
    item = Item.objects.create(
        event=event, name="GA", default_price=100, admission=True, active=True
    )
    quota = Quota.objects.create(event=event, name="Q", size=10)
    quota.items.add(item)
    return {"organizer": organizer, "event": event, "item": item}


@pytest.fixture
def admin_client(client, env):
    with scopes_disabled():
        user = User.objects.create_user("admin@example.org", "admin")
        team = Team.objects.create(
            organizer=env["organizer"],
            limit_event_permissions={"event.items:read": True, "event.items:write": True},
        )
        team.members.add(user)
        team.limit_events.add(env["event"])
    client.login(email="admin@example.org", password="admin")
    return client


def item_url(env):
    return "/control/event/{}/{}/items/{}/".format(
        env["organizer"].slug, env["event"].slug, env["item"].pk
    )


@pytest.mark.django_db
def test_product_page_shows_dgm_settings_off_by_default(admin_client, env):
    response = admin_client.get(item_url(env))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Enable DGM for this ticket" in content
    assert "DGM leader deadline" in content
    form = next(f for f in response.context["plugin_forms"] if isinstance(f, ItemDirectedGroupsForm))
    assert form["enabled"].value() is False


@pytest.mark.django_db
def test_product_page_shows_settings_when_configured(admin_client, env):
    deadline = now() + timedelta(days=7)
    set_dgm_enabled(env["event"], env["item"].pk, True)
    set_dgm_leader_deadline(env["event"], env["item"].pk, deadline)

    response = admin_client.get(item_url(env))

    form = next(f for f in response.context["plugin_forms"] if isinstance(f, ItemDirectedGroupsForm))
    assert form["enabled"].value() is True
    assert form["leader_deadline"].value() is not None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "posted, expected_enabled",
    [({"sideburn_dgm-enabled": "on"}, True), ({}, False)],
)
def test_saving_product_form_stores_enabled(env, posted, expected_enabled):
    set_dgm_enabled(env["event"], env["item"].pk, not expected_enabled)
    request = RequestFactory().post("/", posted)

    form = item_directed_groups_form(
        sender=env["event"], request=request, item=env["item"]
    )
    assert form.is_valid()
    form.save()

    assert dgm_enabled(env["event"], env["item"].pk) is expected_enabled


@pytest.mark.django_db
def test_saving_product_form_stores_deadline(env):
    deadline = (now() + timedelta(days=3)).replace(microsecond=0)
    request = RequestFactory().post(
        "/",
        {
            "sideburn_dgm-enabled": "on",
            "sideburn_dgm-leader_deadline_0": deadline.strftime("%Y-%m-%d"),
            "sideburn_dgm-leader_deadline_1": deadline.strftime("%H:%M:%S"),
        },
    )

    form = item_directed_groups_form(
        sender=env["event"], request=request, item=env["item"]
    )
    assert form.is_valid(), form.errors
    form.save()

    stored = dgm_leader_deadline(env["event"], env["item"].pk)
    assert stored is not None
    assert abs((stored - deadline).total_seconds()) < 60


@pytest.mark.django_db
def test_copying_product_copies_dgm_settings(env):
    deadline = now() + timedelta(days=5)
    set_dgm_enabled(env["event"], env["item"].pk, True)
    set_dgm_leader_deadline(env["event"], env["item"].pk, deadline)
    with scopes_disabled():
        copy = Item.objects.create(event=env["event"], name="Copy", default_price=100)

    item_copy_data.send(sender=env["event"], source=env["item"], target=copy)

    assert dgm_enabled(env["event"], copy.pk)
    assert dgm_leader_deadline(env["event"], copy.pk) is not None


@pytest.mark.django_db
@scopes_disabled()
def test_leader_editing_closed_when_disabled_or_past_deadline(env):
    assert dgm_leader_editing_closed(env["event"], env["item"].pk) is True

    set_dgm_enabled(env["event"], env["item"].pk, True)
    assert dgm_leader_editing_closed(env["event"], env["item"].pk) is False

    set_dgm_leader_deadline(env["event"], env["item"].pk, now() - timedelta(hours=1))
    assert dgm_leader_editing_closed(env["event"], env["item"].pk) is True

    set_dgm_leader_deadline(env["event"], env["item"].pk, now() + timedelta(hours=1))
    assert dgm_leader_editing_closed(env["event"], env["item"].pk) is False
