"""
Customer allowlist / denylist model constraints.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_access_list_models.py -v
"""
import pytest
from django.db import IntegrityError
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer
from pretix_sideburn_core.models import (
    CustomerAllowlistEntry, CustomerDenylistEntry,
)


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
    customer = organizer.customers.create(
        email="john@example.org", is_verified=True, is_active=True
    )
    other = organizer.customers.create(
        email="jane@example.org", is_verified=True, is_active=True
    )
    return {
        "organizer": organizer,
        "event": event,
        "customer": customer,
        "other": other,
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
@scopes_disabled()
def test_allowlist_entry_unique_per_organizer(env):
    CustomerAllowlistEntry.objects.create(
        organizer=env["organizer"],
        customer=env["customer"],
        first_event=env["event"],
    )
    with pytest.raises(IntegrityError):
        CustomerAllowlistEntry.objects.create(
            organizer=env["organizer"], customer=env["customer"]
        )


@pytest.mark.django_db
@scopes_disabled()
def test_customer_can_be_on_both_lists(env):
    CustomerDenylistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )
    CustomerAllowlistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )
    assert CustomerDenylistEntry.objects.filter(customer=env["customer"]).count() == 1
    assert CustomerAllowlistEntry.objects.filter(customer=env["customer"]).count() == 1


@pytest.mark.django_db
@scopes_disabled()
def test_allowlist_first_event_optional(env):
    entry = CustomerAllowlistEntry.objects.create(
        organizer=env["organizer"], customer=env["other"]
    )
    assert entry.first_event_id is None
