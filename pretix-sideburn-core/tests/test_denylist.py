"""
Organizer customer denylist: list, add, edit notes, remove, uniqueness.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_denylist.py -v
"""
import pytest
from django.db import IntegrityError
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer, Team, User
from pretix_sideburn_core.models import CustomerDenylistEntry


@pytest.fixture
@scopes_disabled()
def env():
    organizer = Organizer.objects.create(name="Dummy", slug="dummy")
    organizer.settings.customer_accounts = True
    organizer.settings.customer_accounts_native = True
    Event.objects.create(
        organizer=organizer,
        name="Dummy",
        slug="dummy",
        date_from=now(),
        live=True,
        plugins="pretix_sideburn_core",
    )
    customer = organizer.customers.create(
        email="john@example.org", is_verified=True, is_active=True
    )
    other = organizer.customers.create(
        email="jane@example.org", is_verified=True, is_active=True
    )
    user = User.objects.create_user("dummy@dummy.dummy", "dummy")
    team = Team.objects.create(
        organizer=organizer, all_organizer_permissions=True, name="Admin team"
    )
    team.members.add(user)
    return {
        "organizer": organizer,
        "customer": customer,
        "other": other,
        "user": user,
    }


@pytest.mark.django_db
@scopes_disabled()
def test_denylist_entry_unique_per_organizer(env):
    CustomerDenylistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"], notes="first"
    )
    with pytest.raises(IntegrityError):
        CustomerDenylistEntry.objects.create(
            organizer=env["organizer"], customer=env["customer"], notes="dup"
        )


@pytest.mark.django_db
def test_denylist_list_and_search(client, env):
    with scopes_disabled():
        CustomerDenylistEntry.objects.create(
            organizer=env["organizer"],
            customer=env["customer"],
            notes="banned for reason",
            created_by=env["user"],
        )
        CustomerDenylistEntry.objects.create(
            organizer=env["organizer"],
            customer=env["other"],
            notes="other note",
            created_by=env["user"],
        )

    client.login(email="dummy@dummy.dummy", password="dummy")
    resp = client.get("/control/organizer/dummy/sideburn-core/denylist/")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert env["customer"].identifier in content
    assert env["other"].identifier in content
    assert "Denylist" in content

    resp = client.get(
        "/control/organizer/dummy/sideburn-core/denylist/",
        {"query": "john@example.org"},
    )
    content = resp.content.decode()
    assert env["customer"].identifier in content
    assert env["other"].identifier not in content


@pytest.mark.django_db
def test_denylist_add_edit_remove(client, env):
    client.login(email="dummy@dummy.dummy", password="dummy")

    resp = client.get("/control/organizer/dummy/sideburn-core/denylist/add/")
    assert resp.status_code == 200

    resp = client.post(
        "/control/organizer/dummy/sideburn-core/denylist/add/",
        {"customer": env["customer"].pk, "notes": "no tickets"},
    )
    assert resp.status_code == 302
    with scopes_disabled():
        entry = CustomerDenylistEntry.objects.get(
            organizer=env["organizer"], customer=env["customer"]
        )
        assert entry.notes == "no tickets"
        assert entry.created_by_id == env["user"].pk

    resp = client.post(
        "/control/organizer/dummy/sideburn-core/denylist/add/",
        {"customer": env["customer"].pk, "notes": "again"},
    )
    assert resp.status_code == 200
    with scopes_disabled():
        assert (
            CustomerDenylistEntry.objects.filter(
                organizer=env["organizer"], customer=env["customer"]
            ).count()
            == 1
        )

    resp = client.post(
        "/control/organizer/dummy/sideburn-core/denylist/{}/edit/".format(entry.pk),
        {"notes": "updated notes"},
    )
    assert resp.status_code == 302
    with scopes_disabled():
        entry.refresh_from_db()
        assert entry.notes == "updated notes"

    resp = client.post(
        "/control/organizer/dummy/sideburn-core/denylist/{}/delete/".format(entry.pk)
    )
    assert resp.status_code == 302
    with scopes_disabled():
        assert not CustomerDenylistEntry.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_denylist_customer_select2_shows_name_and_email(client, env):
    with scopes_disabled():
        env["customer"].name_parts = {"_scheme": "full", "full_name": "John Doe"}
        env["customer"].name_cached = "John Doe"
        env["customer"].save()

    client.login(email="dummy@dummy.dummy", password="dummy")
    resp = client.get(
        "/control/organizer/dummy/sideburn-core/denylist/customers/select2/",
        {"query": "john"},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(
        r["id"] == env["customer"].pk and r["text"] == "John Doe (john@example.org)"
        for r in results
    )

    resp = client.get(
        "/control/organizer/dummy/sideburn-core/denylist/customers/select2/",
        {"query": "john@example.org"},
    )
    assert any(r["id"] == env["customer"].pk for r in resp.json()["results"])


@pytest.mark.django_db
def test_denylist_requires_customer_permission(client, env):
    with scopes_disabled():
        limited = User.objects.create_user("limited@dummy.dummy", "dummy")
        Team.objects.create(
            organizer=env["organizer"],
            name="No customers",
            all_organizer_permissions=False,
            limit_organizer_permissions={"organizer.settings.general:write": True},
        ).members.add(limited)

    client.login(email="limited@dummy.dummy", password="dummy")
    resp = client.get("/control/organizer/dummy/sideburn-core/denylist/")
    assert resp.status_code == 403
