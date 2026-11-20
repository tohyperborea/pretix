"""
Customer allowlist / denylist model smoke checks.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_access_list_models.py -v
"""
import pytest
from django_scopes import scopes_disabled

from pretix.base.models import Organizer
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
def test_customer_can_be_on_both_lists(env):
    CustomerDenylistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )
    CustomerAllowlistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )
    assert CustomerDenylistEntry.objects.filter(customer=env["customer"]).count() == 1
    assert CustomerAllowlistEntry.objects.filter(customer=env["customer"]).count() == 1
