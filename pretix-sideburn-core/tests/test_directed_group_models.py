"""
Directed group models and slot display-status helper.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_directed_group_models.py -v
"""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    Event, Item, Order, OrderPosition, Organizer, Quota, Voucher,
)
from pretix_sideburn_core.models import (
    DirectedGroup, DirectedGroupCategory, DirectedGroupSlot,
)
from pretix_sideburn_core.directed_group_status import get_slot_display_status


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
def test_category_unique_per_event(env):
    with pytest.raises(IntegrityError):
        DirectedGroupCategory.objects.create(event=env["event"], name="Theme camps")


@pytest.mark.django_db
@scopes_disabled()
def test_slot_email_unique_per_group_and_lowercased(env):
    DirectedGroupSlot.objects.create(
        group=env["group"],
        name="A",
        email="Person@Example.ORG",
        decision=DirectedGroupSlot.DECISION_PENDING,
        customer=env["assignee"],
    )
    slot = DirectedGroupSlot.objects.get(group=env["group"])
    assert slot.email == "person@example.org"
    with pytest.raises(IntegrityError):
        DirectedGroupSlot.objects.create(
            group=env["group"],
            name="B",
            email="person@example.org",
            decision=DirectedGroupSlot.DECISION_REJECTED,
        )


@pytest.mark.django_db
@scopes_disabled()
def test_group_clean_rejects_cross_event_item(env):
    other = Event.objects.create(
        organizer=env["organizer"],
        name="Other",
        slug="other",
        date_from=now(),
        plugins="pretix_sideburn_core",
    )
    other_item = Item.objects.create(event=other, name="X", default_price=1)
    group = DirectedGroup(
        event=env["event"],
        item=other_item,
        leader=env["leader"],
        name="Bad",
        slot_count=1,
    )
    with pytest.raises(ValidationError) as exc:
        group.clean()
    assert "item" in exc.value.message_dict


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
