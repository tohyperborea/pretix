"""
Creating or joining a lottery group while signing up for the waiting list.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_group_signup.py -v
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Item, Organizer, Quota, WaitingListEntry
from pretix_sideburn_lottery import forms as group_forms
from pretix_sideburn_lottery.services.groups import (
    create_group, get_group, set_groups_allowed,
)


@pytest.fixture
@scopes_disabled()
def signup_env():
    organizer = Organizer.objects.create(name="Dummy", slug="dummy")
    event = Event.objects.create(
        organizer=organizer,
        name="Dummy",
        slug="dummy",
        date_from=datetime.datetime(now().year + 1, 12, 26, 14, 0, tzinfo=datetime.timezone.utc),
        live=True,
        plugins="pretix_sideburn_lottery",
    )
    event.settings.set("waiting_list_enabled", True)
    quota = Quota.objects.create(name="Test", size=0, event=event)
    item = Item.objects.create(event=event, name="Ticket", default_price=23, admission=True)
    quota.items.add(item)
    set_groups_allowed(event, item.pk, True)
    return {"organizer": organizer, "event": event, "item": item, "quota": quota}


@scopes_disabled()
def add_product_without_groups(env):
    item = Item.objects.create(event=env["event"], name="Vehicle pass", default_price=10, admission=True)
    env["quota"].items.add(item)
    return item


def sign_up(client, item, email="foo@bar.com", **group_fields):
    return client.post(
        "/dummy/dummy/waitinglist/?item=%d" % item.pk,
        {"email": email, "itemvar": str(item.pk), **group_fields},
        follow=True,
    )


@scopes_disabled()
def existing_group(env, email="creator@bar.com"):
    entry = WaitingListEntry.objects.create(event=env["event"], item=env["item"], email=email)
    return create_group(entry)


@scopes_disabled()
def entry_for(email):
    return WaitingListEntry.objects.filter(email=email).first()


@pytest.mark.django_db
def test_signup_form_offers_groups(client, signup_env):
    response = client.get("/dummy/dummy/waitinglist/?item=%d" % signup_env["item"].pk)

    assert b'name="lottery_group_action"' in response.content
    assert b'name="lottery_group_code"' in response.content
    assert b"Groups can have up to 10 people." in response.content


@pytest.mark.django_db
def test_signup_form_hides_groups_when_no_product_allows_them(client, signup_env):
    set_groups_allowed(signup_env["event"], signup_env["item"].pk, False)

    response = client.get("/dummy/dummy/waitinglist/?item=%d" % signup_env["item"].pk)

    assert b'name="lottery_group_action"' not in response.content


@pytest.mark.django_db
def test_signup_form_marks_which_products_allow_groups(client, signup_env):
    add_product_without_groups(signup_env)

    response = client.get("/dummy/dummy/waitinglist/?item=%d" % signup_env["item"].pk)

    assert 'data-lottery-group-items="{}"'.format(signup_env["item"].pk) in response.content.decode()
    assert b"pretix_sideburn_lottery/js/waitinglist_groups.js" in response.content


@pytest.mark.django_db
def test_signup_group_for_product_without_groups_shows_error(client, signup_env):
    other_item = add_product_without_groups(signup_env)

    response = sign_up(client, other_item, lottery_group_action="create")

    assert entry_for("foo@bar.com") is None
    assert "Groups aren&#x27;t available for this product." in response.content.decode()


@pytest.mark.django_db
def test_signup_without_group_fields_registers_solo(client, signup_env):
    sign_up(client, signup_env["item"])

    entry = entry_for("foo@bar.com")
    assert entry is not None
    with scopes_disabled():
        assert get_group(entry) is None


@pytest.mark.django_db
def test_signup_can_create_group(client, signup_env):
    response = sign_up(client, signup_env["item"], lottery_group_action="create")

    with scopes_disabled():
        group = get_group(entry_for("foo@bar.com"))
    assert group is not None
    assert "Your group code is {}.".format(group.code) in response.content.decode()


@pytest.mark.django_db
def test_signup_can_join_group(client, signup_env):
    group = existing_group(signup_env)

    response = sign_up(
        client, signup_env["item"], lottery_group_action="join", lottery_group_code=group.code.lower()
    )

    with scopes_disabled():
        assert get_group(entry_for("foo@bar.com")) == group
    assert "You&#x27;ve joined group {}.".format(group.code) in response.content.decode()


@pytest.mark.django_db
def test_signup_join_without_code_shows_error(client, signup_env):
    response = sign_up(client, signup_env["item"], lottery_group_action="join")

    assert entry_for("foo@bar.com") is None
    assert "Enter the code of the group you want to join." in response.content.decode()


@pytest.mark.django_db
def test_signup_join_unknown_code_shows_error(client, signup_env):
    response = sign_up(client, signup_env["item"], lottery_group_action="join", lottery_group_code="ZZZZZZ")

    assert entry_for("foo@bar.com") is None
    assert "We couldn&#x27;t find a group with that code." in response.content.decode()


@pytest.mark.django_db
def test_signup_join_full_group_shows_error(client, signup_env):
    signup_env["event"].settings.set("lottery_group_max_size", 1)
    group = existing_group(signup_env)

    response = sign_up(client, signup_env["item"], lottery_group_action="join", lottery_group_code=group.code)

    assert entry_for("foo@bar.com") is None
    assert "That group is already full." in response.content.decode()


@pytest.mark.django_db
def test_signup_join_for_different_product_shows_error(client, signup_env):
    with scopes_disabled():
        other_item = Item.objects.create(event=signup_env["event"], name="Other", default_price=10)
        set_groups_allowed(signup_env["event"], other_item.pk, True)
        other_entry = WaitingListEntry.objects.create(
            event=signup_env["event"], item=other_item, email="other@bar.com"
        )
        group = create_group(other_entry)

    response = sign_up(client, signup_env["item"], lottery_group_action="join", lottery_group_code=group.code)

    assert entry_for("foo@bar.com") is None
    assert "That group is for a different product." in response.content.decode()


@pytest.mark.django_db
def test_signup_after_lottery_hides_groups_and_registers_solo(client, signup_env):
    signup_env["event"].settings.set(
        f"lottery_date_for_item_{signup_env['item'].pk}", now().isoformat()
    )

    page = client.get("/dummy/dummy/waitinglist/?item=%d" % signup_env["item"].pk)
    sign_up(client, signup_env["item"], lottery_group_action="create")

    assert b'name="lottery_group_action"' not in page.content
    entry = entry_for("foo@bar.com")
    assert entry is not None
    with scopes_disabled():
        assert get_group(entry) is None


@pytest.mark.django_db
def test_signup_still_succeeds_if_group_fills_up_during_signup(client, signup_env, monkeypatch):
    group = existing_group(signup_env)

    def group_filled_up(entry, code):
        raise ValidationError("That group is already full.")

    monkeypatch.setattr(group_forms, "join_group", group_filled_up)
    response = sign_up(client, signup_env["item"], lottery_group_action="join", lottery_group_code=group.code)

    entry = entry_for("foo@bar.com")
    assert entry is not None
    with scopes_disabled():
        assert get_group(entry) is None
    assert (
        "You&#x27;re on the waiting list, but we couldn&#x27;t add you to the group: That group is already full."
        in response.content.decode()
    )
