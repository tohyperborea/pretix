"""
Directed group models and slot display-status helper.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_directed_group_models.py -v
"""
from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    Event, Item, Order, OrderPosition, Organizer, Quota, Voucher,
)
from pretix_sideburn_core.directed_group_status import get_slot_display_status
from pretix_sideburn_core.models import (
    DirectedGroup, DirectedGroupCategory, DirectedGroupSlot,
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
    item = Item.objects.create(event=event, name="GA", default_price=100, admission=True)
    quota = Quota.objects.create(event=event, name="Q", size=10)
    quota.items.add(item)
    leader = organizer.customers.create(
        email="leader@example.org", is_verified=True, is_active=True
    )
    assignee = organizer.customers.create(
        email="assignee@example.org", is_verified=True, is_active=True
    )
    category = DirectedGroupCategory.objects.create(event=event, name="Theme camps")
    group = DirectedGroup.objects.create(
        event=event,
        item=item,
        category=category,
        leader=leader,
        name="Camp Foo",
        slot_count=3,
    )
    return {
        "organizer": organizer,
        "event": event,
        "item": item,
        "leader": leader,
        "assignee": assignee,
        "category": category,
        "group": group,
    }


@pytest.mark.django_db
@scopes_disabled()
def test_slot_email_is_lowercased_on_save(env):
    DirectedGroupSlot.objects.create(
        group=env["group"],
        name="A",
        email="Person@Example.ORG",
        decision=DirectedGroupSlot.DECISION_PENDING,
        customer=env["assignee"],
    )
    slot = DirectedGroupSlot.objects.get(group=env["group"])
    assert slot.email == "person@example.org"


@pytest.mark.django_db
@scopes_disabled()
def test_group_allows_null_leader_and_survives_customer_delete(env):
    group = DirectedGroup.objects.create(
        event=env["event"],
        item=env["item"],
        leader=None,
        name="Unassigned",
        slot_count=1,
    )
    assert group.leader_id is None

    leader = env["leader"]
    env["group"].leader = leader
    env["group"].save(update_fields=["leader"])
    leader_pk = leader.pk
    leader.delete()
    env["group"].refresh_from_db()
    assert env["group"].leader_id is None
    assert not env["organizer"].customers.filter(pk=leader_pk).exists()


@pytest.mark.django_db
@scopes_disabled()
def test_slots_remaining(env):
    assert env["group"].slots_remaining == 3
    DirectedGroupSlot.objects.create(
        group=env["group"],
        name="A",
        email="a@example.org",
        decision=DirectedGroupSlot.DECISION_NO_ACCOUNT,
    )
    assert env["group"].slots_remaining == 2


@pytest.mark.django_db
@scopes_disabled()
@pytest.mark.parametrize(
    "decision, expected",
    [
        (DirectedGroupSlot.DECISION_NO_ACCOUNT, "no_account"),
        (DirectedGroupSlot.DECISION_ALREADY_TICKETED, "already_ticketed"),
        (DirectedGroupSlot.DECISION_REJECTED, "denied"),
        (DirectedGroupSlot.DECISION_PENDING, "approval_pending"),
    ],
)
def test_slot_display_status_from_decision(env, decision, expected):
    slot = DirectedGroupSlot.objects.create(
        group=env["group"],
        name="A",
        email="a@example.org",
        decision=decision,
        customer=env["assignee"],
    )
    assert get_slot_display_status(slot) == expected


@pytest.mark.django_db
@scopes_disabled()
def test_slot_display_status_voucher_paths(env):
    voucher = Voucher.objects.create(
        event=env["event"],
        item=env["item"],
        max_usages=1,
        block_quota=True,
        valid_until=now() + timedelta(hours=72),
    )
    slot = DirectedGroupSlot.objects.create(
        group=env["group"],
        name="A",
        email="a@example.org",
        customer=env["assignee"],
        voucher=voucher,
        decision="",
    )
    assert get_slot_display_status(slot) == "voucher_sent"

    voucher.valid_until = now() - timedelta(hours=1)
    voucher.save()
    assert get_slot_display_status(slot) == "voucher_expired"

    voucher.valid_until = now() + timedelta(hours=72)
    voucher.redeemed = 1
    voucher.save(update_fields=["valid_until", "redeemed"])
    order = Order.objects.create(
        event=env["event"],
        status=Order.STATUS_PAID,
        expires=now() + timedelta(days=1),
        total=100,
        sales_channel=env["organizer"].sales_channels.get(identifier="web"),
    )
    pos = OrderPosition.objects.create(
        order=order,
        item=env["item"],
        voucher=voucher,
        price=100,
    )
    assert get_slot_display_status(slot) == "ticket_purchased"

    pos.canceled = True
    pos.save(update_fields=["canceled"])
    voucher.redeemed = 0
    voucher.save(update_fields=["redeemed"])
    assert get_slot_display_status(slot) == "ticket_canceled"
