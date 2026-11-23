from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer


@pytest.mark.django_db
@pytest.mark.parametrize("same_organizer", [True, False])
@scopes_disabled()
def test_copy_membership_discount_rules(same_organizer):
    organizer = Organizer.objects.create(name="Source", slug="source")
    source = Event.objects.create(
        organizer=organizer,
        name="Source event",
        slug="source-event",
        date_from=now(),
        plugins="pretix_sideburn_core",
    )
    membership_type = organizer.membership_types.create(name="Member")
    eligible = source.items.create(name="Eligible ticket", default_price=20)
    source.items.create(name="Other ticket", default_price=20)
    rule = source.membership_discount_rules.create(
        membership_type=membership_type,
        discount_percent=Decimal("12.50"),
        label="Member discount",
    )
    rule.products.add(eligible)

    destination_organizer = organizer if same_organizer else Organizer.objects.create(
        name="Destination", slug="destination"
    )
    destination = Event.objects.create(
        organizer=destination_organizer,
        name="Copied event",
        slug="copied-event",
        date_from=now(),
    )
    destination.copy_data_from(source)

    assert list(rule.products.all()) == [eligible]
    if same_organizer:
        copied_rule = destination.membership_discount_rules.get()
        assert copied_rule.pk != rule.pk
        assert copied_rule.membership_type_id == membership_type.pk
        assert copied_rule.discount_percent == rule.discount_percent
        assert copied_rule.label == rule.label
        copied_product = destination.items.get(name="Eligible ticket")
        assert copied_product.pk != eligible.pk
        assert list(copied_rule.products.all()) == [copied_product]
    else:
        assert not destination.membership_discount_rules.exists()
