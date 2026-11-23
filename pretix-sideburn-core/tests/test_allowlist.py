"""
Organizer customer allowlist: list, search, manual add, uniqueness; no remove.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_allowlist.py -v
"""
import pytest
from django.db import IntegrityError
from django.urls import NoReverseMatch, reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer, Team, User
from pretix_sideburn_core.models import CustomerAllowlistEntry


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
def test_allowlist_entry_unique_per_organizer(env):
    CustomerAllowlistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )
    with pytest.raises(IntegrityError):
        CustomerAllowlistEntry.objects.create(
            organizer=env["organizer"], customer=env["customer"]
        )


@pytest.mark.django_db
def test_allowlist_list_and_search(client, env):
    with scopes_disabled():
        CustomerAllowlistEntry.objects.create(
            organizer=env["organizer"],
            customer=env["customer"],
            created_by=env["user"],
        )
        CustomerAllowlistEntry.objects.create(
            organizer=env["organizer"],
            customer=env["other"],
        )

    client.login(email="dummy@dummy.dummy", password="dummy")
    resp = client.get("/control/organizer/dummy/sideburn-core/allowlist/")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert env["customer"].identifier in content
    assert env["other"].identifier in content
    assert "Allowlist" in content
    assert "Manual" in content
    assert "Automatic" in content
    assert "fa-trash" not in content
    assert "/sideburn-core/allowlist/" in content
    assert "/sideburn-core/denylist/" in content

    resp = client.get(
        "/control/organizer/dummy/sideburn-core/allowlist/",
        {"query": "john@example.org"},
    )
    content = resp.content.decode()
    assert env["customer"].identifier in content
    assert env["other"].identifier not in content


@pytest.mark.django_db
def test_allowlist_manual_add(client, env):
    client.login(email="dummy@dummy.dummy", password="dummy")

    resp = client.get("/control/organizer/dummy/sideburn-core/allowlist/add/")
    assert resp.status_code == 200

    resp = client.post(
        "/control/organizer/dummy/sideburn-core/allowlist/add/",
        {"customer": env["customer"].pk},
    )
    assert resp.status_code == 302
    with scopes_disabled():
        entry = CustomerAllowlistEntry.objects.get(
            organizer=env["organizer"], customer=env["customer"]
        )
        assert entry.created_by_id == env["user"].pk

    resp = client.post(
        "/control/organizer/dummy/sideburn-core/allowlist/add/",
        {"customer": env["customer"].pk},
    )
    assert resp.status_code == 200
    with scopes_disabled():
        assert (
            CustomerAllowlistEntry.objects.filter(
                organizer=env["organizer"], customer=env["customer"]
            ).count()
            == 1
        )


@pytest.mark.django_db
def test_allowlist_has_no_remove_route(client, env):
    with scopes_disabled():
        entry = CustomerAllowlistEntry.objects.create(
            organizer=env["organizer"],
            customer=env["customer"],
            created_by=env["user"],
        )

    client.login(email="dummy@dummy.dummy", password="dummy")
    # No delete URL is registered for allowlist entries.
    with pytest.raises(NoReverseMatch):
        reverse(
            "plugins:pretix_sideburn_core:allowlist.delete",
            kwargs={"organizer": "dummy", "pk": entry.pk},
        )
    resp = client.post(
        "/control/organizer/dummy/sideburn-core/allowlist/{}/delete/".format(entry.pk)
    )
    assert resp.status_code == 404
    with scopes_disabled():
        assert CustomerAllowlistEntry.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_allowlist_customer_select2_shows_name_and_email(client, env):
    with scopes_disabled():
        env["customer"].name_parts = {"_scheme": "full", "full_name": "John Doe"}
        env["customer"].name_cached = "John Doe"
        env["customer"].save()

    client.login(email="dummy@dummy.dummy", password="dummy")
    resp = client.get(
        "/control/organizer/dummy/sideburn-core/allowlist/customers/select2/",
        {"query": "john"},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(
        r["id"] == env["customer"].pk and r["text"] == "John Doe (john@example.org)"
        for r in results
    )


@pytest.mark.django_db
def test_allowlist_requires_customer_permission(client, env):
    with scopes_disabled():
        limited = User.objects.create_user("limited@dummy.dummy", "dummy")
        Team.objects.create(
            organizer=env["organizer"],
            name="No customers",
            all_organizer_permissions=False,
            limit_organizer_permissions={"organizer.settings.general:write": True},
        ).members.add(limited)

    client.login(email="limited@dummy.dummy", password="dummy")
    resp = client.get("/control/organizer/dummy/sideburn-core/allowlist/")
    assert resp.status_code == 403
