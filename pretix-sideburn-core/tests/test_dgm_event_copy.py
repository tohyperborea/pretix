"""
Event clone copies DGM settings, categories, and empty groups.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_dgm_event_copy.py -v
"""
from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer
from pretix_sideburn_core.dgm import dgm_enabled, dgm_leader_deadline, set_dgm_enabled, set_dgm_leader_deadline
from pretix_sideburn_core.models import (
    DirectedGroup, DirectedGroupCategory, DirectedGroupSlot,
)


@pytest.mark.django_db
@scopes_disabled()
def test_event_copy_clones_dgm_structure_without_leaders_or_slots():
    organizer = Organizer.objects.create(name="Source", slug="source")
    organizer.settings.customer_accounts = True
    source = Event.objects.create(
        organizer=organizer,
        name="Source event",
        slug="source-event",
        date_from=now(),
        plugins="pretix_sideburn_core",
    )
    item = source.items.create(name="GA", default_price=100, admission=True)
    deadline = now() + timedelta(days=10)
    set_dgm_enabled(source, item.pk, True)
    set_dgm_leader_deadline(source, item.pk, deadline)

    category = DirectedGroupCategory.objects.create(event=source, name="Theme camps")
    leader = organizer.customers.create(
        email="leader@example.org", is_verified=True, is_active=True
    )
    group = DirectedGroup.objects.create(
        event=source,
        item=item,
        category=category,
        leader=leader,
        name="Camp Foo",
        slot_count=4,
    )
    DirectedGroupSlot.objects.create(
        group=group,
        name="A",
        email="a@example.org",
        decision=DirectedGroupSlot.DECISION_PENDING,
        customer=leader,
    )

    destination = Event.objects.create(
        organizer=organizer,
        name="Copied event",
        slug="copied-event",
        date_from=now() + timedelta(days=365),
        plugins="pretix_sideburn_core",
    )
    destination.copy_data_from(source)

    copied_item = destination.items.get(name="GA")
    assert dgm_enabled(destination, copied_item.pk) is True
    assert dgm_leader_deadline(destination, copied_item.pk) is not None

    copied_category = destination.directed_group_categories.get(name="Theme camps")
    assert copied_category.pk != category.pk

    copied_group = destination.directed_groups.get(name="Camp Foo")
    assert copied_group.pk != group.pk
    assert copied_group.item_id == copied_item.pk
    assert copied_group.category_id == copied_category.pk
    assert copied_group.slot_count == group.slot_count
    assert copied_group.leader_id is None
    assert copied_group.slots.count() == 0

    assert group.leader_id == leader.pk
    assert group.slots.count() == 1
