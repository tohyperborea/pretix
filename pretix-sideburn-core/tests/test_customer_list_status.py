"""
Customer list status helper (#227).

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_customer_list_status.py -v
"""
import pytest
from django_scopes import scopes_disabled

from pretix.base.models import Organizer
from pretix_sideburn_core.customer_list_status import get_customer_list_status
from pretix_sideburn_core.models import (
    CustomerAllowlistEntry, CustomerDenylistEntry,
)


@pytest.fixture
@scopes_disabled()
def env():
    organizer = Organizer.objects.create(name="Dummy", slug="dummy")
    organizer.settings.customer_accounts = True
    customer = organizer.customers.create(
        email="john@example.org", is_verified=True, is_active=True
    )
    return {"organizer": organizer, "customer": customer}


@pytest.mark.django_db
@scopes_disabled()
def test_unfamiliar_by_default(env):
    assert get_customer_list_status(env["customer"]) == "unfamiliar"


@pytest.mark.django_db
@scopes_disabled()
def test_allowlist_only(env):
    CustomerAllowlistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )
    assert get_customer_list_status(env["customer"]) == "allow"


@pytest.mark.django_db
@scopes_disabled()
def test_denylist_only(env):
    CustomerDenylistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )
    assert get_customer_list_status(env["customer"]) == "deny"


@pytest.mark.django_db
@scopes_disabled()
def test_denylist_supersedes_allowlist(env):
    CustomerAllowlistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )
    CustomerDenylistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )
    assert get_customer_list_status(env["customer"]) == "deny"
    # Denylist does not delete allowlist rows
    assert CustomerAllowlistEntry.objects.filter(
        organizer=env["organizer"], customer=env["customer"]
    ).exists()
