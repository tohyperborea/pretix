"""
Allowlist sync plumbing (#226): item setting helpers, attendance sync, backfill command.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_allowlist_sync.py -v
"""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Item, Order, OrderPosition, Organizer
from pretix.base.signals import item_copy_data
from pretix_sideburn_core.allowlist_items import (
    get_allowlist_item_ids, item_counts_for_allowlist, set_item_counts_for_allowlist,
)
from pretix_sideburn_core.allowlist_sync import sync_allowlists, sync_event_allowlist
from pretix_sideburn_core.models import CustomerAllowlistEntry


@pytest.fixture
@scopes_disabled()
def env():
    organizer = Organizer.objects.create(name="Dummy", slug="dummy")
    organizer.settings.customer_accounts = True
    past = now() - timedelta(days=7)
    event = Event.objects.create(
        organizer=organizer,
        name="Past Event",
        slug="past",
        date_from=past - timedelta(days=3),
        date_to=past,
        live=True,
        plugins="pretix_sideburn_core",
    )
    admission = Item.objects.create(
        event=event, name="Admission", default_price=100, admission=True, active=True
    )
    merch = Item.objects.create(
        event=event, name="Merch", default_price=20, admission=False, active=True
    )
    customer = organizer.customers.create(
        email="john@example.org", is_verified=True, is_active=True
    )
    other = organizer.customers.create(
        email="jane@example.org", is_verified=True, is_active=True
    )
    channel = organizer.sales_channels.get(identifier="web")
    return {
        "organizer": organizer,
        "event": event,
        "admission": admission,
        "merch": merch,
        "customer": customer,
        "other": other,
        "channel": channel,
    }


def _paid_order(env, customer, item):
    order = Order.objects.create(
        event=env["event"],
        customer=customer,
        email=customer.email,
        status=Order.STATUS_PAID,
        total=item.default_price,
        datetime=now(),
        expires=now() + timedelta(days=10),
        sales_channel=env["channel"],
    )
    OrderPosition.objects.create(order=order, item=item, price=item.default_price)
    return order


@pytest.mark.django_db
@scopes_disabled()
def test_item_setting_default_off(env):
    assert item_counts_for_allowlist(env["event"], env["admission"].pk) is False
    assert get_allowlist_item_ids(env["event"]) == set()


@pytest.mark.django_db
@scopes_disabled()
def test_item_setting_toggle(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)
    assert item_counts_for_allowlist(env["event"], env["admission"].pk) is True
    assert get_allowlist_item_ids(env["event"]) == {env["admission"].pk}

    set_item_counts_for_allowlist(env["event"], env["admission"].pk, False)
    assert item_counts_for_allowlist(env["event"], env["admission"].pk) is False


@pytest.mark.django_db
@scopes_disabled()
def test_sync_only_after_event_end(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)
    _paid_order(env, env["customer"], env["admission"])

    env["event"].date_from = now() + timedelta(days=1)
    env["event"].date_to = now() + timedelta(days=3)
    env["event"].save()

    assert sync_event_allowlist(env["event"]) == 0
    assert not CustomerAllowlistEntry.objects.filter(customer=env["customer"]).exists()


@pytest.mark.django_db
@scopes_disabled()
def test_sync_only_configured_items(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)
    _paid_order(env, env["customer"], env["merch"])

    assert sync_event_allowlist(env["event"]) == 0
    assert not CustomerAllowlistEntry.objects.filter(customer=env["customer"]).exists()


@pytest.mark.django_db
@scopes_disabled()
def test_sync_only_paid_with_customer(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)

    pending = Order.objects.create(
        event=env["event"],
        customer=env["customer"],
        email=env["customer"].email,
        status=Order.STATUS_PENDING,
        total=Decimal("100.00"),
        datetime=now(),
        expires=now() + timedelta(days=10),
        sales_channel=env["channel"],
    )
    OrderPosition.objects.create(
        order=pending, item=env["admission"], price=Decimal("100.00")
    )

    no_customer = Order.objects.create(
        event=env["event"],
        customer=None,
        email="anon@example.org",
        status=Order.STATUS_PAID,
        total=Decimal("100.00"),
        datetime=now(),
        expires=now() + timedelta(days=10),
        sales_channel=env["channel"],
    )
    OrderPosition.objects.create(
        order=no_customer, item=env["admission"], price=Decimal("100.00")
    )

    assert sync_event_allowlist(env["event"]) == 0
    assert CustomerAllowlistEntry.objects.count() == 0


@pytest.mark.django_db
@scopes_disabled()
def test_sync_creates_idempotent_and_keeps_existing(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)
    _paid_order(env, env["customer"], env["admission"])
    _paid_order(env, env["other"], env["admission"])

    existing = CustomerAllowlistEntry.objects.create(
        organizer=env["organizer"], customer=env["customer"]
    )

    assert sync_event_allowlist(env["event"]) == 1
    assert CustomerAllowlistEntry.objects.filter(customer=env["other"]).count() == 1
    assert CustomerAllowlistEntry.objects.get(pk=existing.pk).pk == existing.pk

    assert sync_event_allowlist(env["event"]) == 0
    assert CustomerAllowlistEntry.objects.count() == 2


@pytest.mark.django_db
@scopes_disabled()
def test_sync_skips_canceled_positions(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)
    order = Order.objects.create(
        event=env["event"],
        customer=env["customer"],
        email=env["customer"].email,
        status=Order.STATUS_PAID,
        total=Decimal("100.00"),
        datetime=now(),
        expires=now() + timedelta(days=10),
        sales_channel=env["channel"],
    )
    pos = OrderPosition.objects.create(
        order=order, item=env["admission"], price=Decimal("100.00")
    )
    pos.canceled = True
    pos.save()

    assert sync_event_allowlist(env["event"]) == 0


@pytest.mark.django_db
@scopes_disabled()
def test_backfill_command_happy_path(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)
    _paid_order(env, env["customer"], env["admission"])

    out = StringIO()
    call_command(
        "sync_sideburn_allowlist",
        "--organizer",
        "dummy",
        "--event",
        "past",
        stdout=out,
    )
    assert "Created 1 allowlist entry." in out.getvalue()
    assert CustomerAllowlistEntry.objects.filter(customer=env["customer"]).exists()


@pytest.mark.django_db
@scopes_disabled()
def test_sync_allowlists_finds_plugin_events(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)
    _paid_order(env, env["customer"], env["admission"])

    assert sync_allowlists() == 1


@pytest.mark.django_db
@scopes_disabled()
def test_item_copy_copies_setting(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)
    copy = Item.objects.create(
        event=env["event"], name="Copy", default_price=100, active=True
    )
    item_copy_data.send(sender=env["event"], source=env["admission"], target=copy)
    assert item_counts_for_allowlist(env["event"], copy.pk) is True


@pytest.mark.django_db
@scopes_disabled()
def test_event_copy_remaps_allowlist_item_settings(env):
    set_item_counts_for_allowlist(env["event"], env["admission"].pk, True)
    destination = Event.objects.create(
        organizer=env["organizer"],
        name="Copy",
        slug="copy",
        date_from=now(),
        plugins="pretix_sideburn_core",
    )
    destination.copy_data_from(env["event"])
    copied = destination.items.get(name="Admission")
    assert item_counts_for_allowlist(destination, copied.pk) is True
    assert item_counts_for_allowlist(destination, env["admission"].pk) is False
