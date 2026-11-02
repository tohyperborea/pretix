"""
Managing a lottery group from the "Check my spot in line" box after signing up.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_group_management.py -v
"""
import datetime
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    Event, Item, Organizer, Quota, WaitingListEntry,
)
from pretix_sideburn_lottery.models import LotteryGroup
from pretix_sideburn_lottery.services.groups import (
    create_group, get_group, join_group, set_groups_allowed,
)

EMAIL = "test@example.com"
PASSWORD = "test"
GROUP_URL = "/ccc/30c3/sideburn-lottery/group/"


@pytest.fixture
def env():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="CCC", slug="ccc")
        organizer.settings.customer_accounts = True
        event = Event.objects.create(
            organizer=organizer,
            name="30C3",
            slug="30c3",
            date_from=datetime.datetime(now().year + 1, 12, 26, 14, 0, tzinfo=datetime.timezone.utc),
            live=True,
            plugins="pretix_sideburn_lottery",
        )
        event.settings.set("waiting_list_enabled", True)
        quota = Quota.objects.create(event=event, name="Quota", size=0)
        item = Item.objects.create(event=event, name="Ticket", default_price=Decimal("12.00"), active=True)
        quota.items.add(item)
        set_groups_allowed(event, item.pk, True)
        customer = organizer.customers.create(email=EMAIL, is_verified=True, is_active=True)
        customer.set_password(PASSWORD)
        customer.save()
        entry = WaitingListEntry.objects.create(event=event, item=item, email=EMAIL)
    return {"organizer": organizer, "event": event, "item": item, "entry": entry}


@pytest.fixture
def logged_in(client, env):
    response = client.post("/ccc/account/login", {"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 302
    return client


def event_page(client):
    return client.get("/ccc/30c3/").content.decode()


def post_group(client, env, **data):
    return client.post(GROUP_URL, {"item": env["item"].pk, **data}, follow=True).content.decode()


@scopes_disabled()
def friends_group(env, size=1):
    entries = [
        WaitingListEntry.objects.create(event=env["event"], item=env["item"], email=f"friend{i}@example.com")
        for i in range(size)
    ]
    group = create_group(entries[0])
    for entry in entries[1:]:
        join_group(entry, group.code)
    return group


@scopes_disabled()
def group_of(entry):
    return get_group(entry)


def mark_lottery_run(env):
    env["event"].settings.set(f"lottery_date_for_item_{env['item'].pk}", now().isoformat())


@pytest.mark.django_db
def test_box_offers_to_create_or_join_a_group(logged_in, env):
    content = event_page(logged_in)

    assert "You're registered on your own." in content
    assert 'value="create"' in content
    assert 'value="join"' in content


@pytest.mark.django_db
def test_box_has_no_group_controls_when_product_does_not_allow_groups(logged_in, env):
    set_groups_allowed(env["event"], env["item"].pk, False)

    content = event_page(logged_in)

    assert 'value="create"' not in content
    assert 'value="join"' not in content


@pytest.mark.django_db
def test_create_group(logged_in, env):
    content = post_group(logged_in, env, action="create")

    group = group_of(env["entry"])
    assert group is not None
    assert "Your group code is {}. Share it".format(group.code) in content
    assert "Your group code is <strong>{}</strong> (1 of 10 people).".format(group.code) in content
    assert 'value="leave"' in content


@pytest.mark.django_db
def test_join_group(logged_in, env):
    group = friends_group(env, size=2)

    content = post_group(logged_in, env, action="join", code=group.code.lower())

    assert group_of(env["entry"]) == group
    assert "You&#x27;ve joined group {}.".format(group.code) in content
    assert "(3 of 10 people)" in content


@pytest.mark.django_db
def test_join_unknown_code_shows_error(logged_in, env):
    content = post_group(logged_in, env, action="join", code="ZZZZZZ")

    assert group_of(env["entry"]) is None
    assert "We couldn&#x27;t find a group with that code." in content


@pytest.mark.django_db
def test_join_without_code_shows_error(logged_in, env):
    content = post_group(logged_in, env, action="join", code=" ")

    assert group_of(env["entry"]) is None
    assert "Enter the code of the group you want to join." in content


@pytest.mark.django_db
def test_leave_group(logged_in, env):
    group = friends_group(env)
    with scopes_disabled():
        join_group(env["entry"], group.code)

    content = post_group(logged_in, env, action="leave")

    assert group_of(env["entry"]) is None
    assert "You&#x27;ve left your group." in content
    assert LotteryGroup.objects.filter(pk=group.pk).exists()


@pytest.mark.django_db
def test_can_leave_after_product_stops_allowing_groups(logged_in, env):
    with scopes_disabled():
        create_group(env["entry"])
    set_groups_allowed(env["event"], env["item"].pk, False)

    assert 'value="leave"' in event_page(logged_in)
    post_group(logged_in, env, action="leave")
    assert group_of(env["entry"]) is None


@pytest.mark.django_db
def test_after_lottery_box_shows_group_without_controls(logged_in, env):
    with scopes_disabled():
        group = create_group(env["entry"])
    mark_lottery_run(env)

    content = event_page(logged_in)

    assert "Your group code is <strong>{}</strong>".format(group.code) in content
    assert 'value="leave"' not in content
    assert 'value="create"' not in content


@pytest.mark.django_db
def test_leave_after_lottery_is_refused(logged_in, env):
    with scopes_disabled():
        group = create_group(env["entry"])
    mark_lottery_run(env)

    content = post_group(logged_in, env, action="leave")

    assert group_of(env["entry"]) == group
    assert "The lottery for this product has already taken place" in content


@pytest.mark.django_db
def test_no_group_controls_once_voucher_sent(logged_in, env):
    with scopes_disabled():
        voucher = env["event"].vouchers.create(
            item=env["item"], block_quota=True, valid_until=now() + datetime.timedelta(days=3)
        )
        env["entry"].voucher = voucher
        env["entry"].save()

    content = event_page(logged_in)
    response = post_group(logged_in, env, action="create")

    assert 'value="create"' not in content
    assert group_of(env["entry"]) is None
    assert "You are not on the waiting list for this product." in response


@pytest.mark.django_db
def test_logged_out_request_changes_nothing(client, env):
    client.post(GROUP_URL, {"item": env["item"].pk, "action": "create"})

    assert group_of(env["entry"]) is None


@pytest.mark.django_db
def test_only_changes_the_logged_in_customers_entry(logged_in, env):
    with scopes_disabled():
        other = WaitingListEntry.objects.create(event=env["event"], item=env["item"], email="other@example.com")

    post_group(logged_in, env, action="create")

    assert group_of(env["entry"]) is not None
    assert group_of(other) is None


@pytest.mark.django_db
def test_invalid_product_shows_error(logged_in, env):
    response = logged_in.post(GROUP_URL, {"item": "abc", "action": "create"}, follow=True)

    assert "You are not on the waiting list for this product." in response.content.decode()
