"""
Admin lottery run/revert tests for pretix-sideburn-lottery.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_admin_lottery.py -v
"""
import csv
import datetime
import io
from zoneinfo import ZoneInfo

import pytest
from django.utils.formats import date_format
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    Event, Item, Organizer, Quota, Team, User, Voucher, WaitingListEntry,
)

WAITING_EMAILS = ["foo{}@bar.com".format(i) for i in range(5)]


@pytest.fixture
@scopes_disabled()
def admin_lottery_env():
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
    user = User.objects.create_user("dummy@dummy.dummy", "dummy")
    item1 = Item.objects.create(
        event=event, name="Ticket", default_price=23, admission=True
    )
    item2 = Item.objects.create(
        event=event, name="Ticket B", default_price=23, admission=True
    )
    quota = Quota.objects.create(event=event, name="Sold out", size=0)
    quota.items.add(item1, item2)

    signup_time = now() - datetime.timedelta(days=10)
    for i, email in enumerate(WAITING_EMAILS):
        wle = WaitingListEntry.objects.create(event=event, item=item1, email=email)
        WaitingListEntry.objects.filter(pk=wle.pk).update(created=signup_time + datetime.timedelta(hours=i))
    v = Voucher.objects.create(
        item=item1, event=event, block_quota=True, redeemed=1
    )
    WaitingListEntry.objects.create(
        event=event, item=item1, email="success@example.org", voucher=v, priority=0
    )

    team = Team.objects.create(
        organizer=organizer, can_view_orders=True, can_change_orders=True
    )
    team.members.add(user)
    team.limit_events.add(event)

    return {
        "organizer": organizer,
        "event": event,
        "user": user,
        "item1": item1,
        "item2": item2,
    }


def run_lottery(client, item, revert=False):
    action = "revert" if revert else "run"
    return client.get(
        "/control/event/dummy/dummy/sideburn-lottery/%s/?item=%d" % (action, item.pk)
    )


def admin_list_emails(client, item):
    response = client.get("/control/event/dummy/dummy/waitinglist/?item=%d" % item.pk)
    return [e.email for e in response.context["entries"]]


def positions(event, item):
    with scopes_disabled():
        return dict(
            WaitingListEntry.objects.filter(event=event, item=item)
            .values_list("email", "priority")
        )


@pytest.mark.django_db
def test_lottery_requires_product(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")

    response = client.get(
        "/control/event/dummy/dummy/sideburn-lottery/run/"
    )

    assert response.status_code == 302
    assert "/control/event/dummy/dummy/waitinglist/" in response.url

    response = client.get(response.url)
    assert "You must select a product" in response.content.decode()


@pytest.mark.django_db
def test_lottery_gives_each_waiting_entry_a_unique_position(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    event = admin_lottery_env["event"]
    item1 = admin_lottery_env["item1"]

    response = run_lottery(client, item1)
    assert response.status_code == 200

    after = positions(event, item1)
    assert sorted(after[email] for email in WAITING_EMAILS) == [1, 2, 3, 4, 5]
    assert after["success@example.org"] == 0


@pytest.mark.django_db
def test_lottery_order_is_random(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    item1 = admin_lottery_env["item1"]

    orders = set()
    for _ in range(5):
        run_lottery(client, item1)
        orders.add(tuple(admin_list_emails(client, item1)))

    assert len(orders) > 1


@pytest.mark.django_db
def test_lottery_downloads_results_csv(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    event = admin_lottery_env["event"]
    item1 = admin_lottery_env["item1"]

    response = run_lottery(client, item1)
    assert response["Content-Type"] == "text/csv"
    assert "dummy_lottery_results.csv" in response["Content-Disposition"]

    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8"))))
    assert sorted(r["E-mail address"] for r in rows) == sorted(WAITING_EMAILS)
    after = positions(event, item1)
    for row in rows:
        assert int(row["Priority"]) == after[row["E-mail address"]]
        assert row["OldPriority"] == "0"


@pytest.mark.django_db
def test_lottery_isolation(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    event = admin_lottery_env["event"]
    item1 = admin_lottery_env["item1"]
    item2 = admin_lottery_env["item2"]

    with scopes_disabled():
        for i in range(3):
            WaitingListEntry.objects.create(
                event=event, item=item2, email="item2foo{}@bar.com".format(i)
            )

    run_lottery(client, item1)
    item1_after_first_lottery = positions(event, item1)
    assert set(positions(event, item2).values()) == {0}

    run_lottery(client, item2)
    assert positions(event, item1) == item1_after_first_lottery
    assert sorted(positions(event, item2).values()) == [1, 2, 3]


@pytest.mark.django_db
def test_lottery_sets_item_date(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    event = admin_lottery_env["event"]
    item1 = admin_lottery_env["item1"]

    assert not event.settings.get(f"lottery_date_for_item_{item1.pk}")

    run_lottery(client, item1)

    event.settings.flush()
    assert event.settings.get(f"lottery_date_for_item_{item1.pk}")


@pytest.mark.django_db
def test_lottery_revert_clears_item_date(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    event = admin_lottery_env["event"]
    item1 = admin_lottery_env["item1"]

    run_lottery(client, item1)
    event.settings.flush()
    assert event.settings.get(f"lottery_date_for_item_{item1.pk}")

    run_lottery(client, item1, revert=True)

    event.settings.flush()
    assert not event.settings.get(f"lottery_date_for_item_{item1.pk}")


@pytest.mark.django_db
def test_event_page_shows_lottery_date_after_run(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    item1 = admin_lottery_env["item1"]

    content = client.get("/dummy/dummy/").content.decode()
    assert "These tickets will be assigned by lottery" in content
    assert "Ticket lottery held on" not in content

    tz = ZoneInfo(admin_lottery_env["event"].settings.timezone)
    run_lottery(client, item1)
    expected_date = date_format(now().astimezone(tz), "DATE_FORMAT")

    content = client.get("/dummy/dummy/").content.decode()
    assert f"Ticket lottery held on {expected_date}" in content


@pytest.mark.django_db
def test_revert_restores_signup_order(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    item1 = admin_lottery_env["item1"]

    run_lottery(client, item1)
    response = run_lottery(client, item1, revert=True)
    assert response.status_code == 200
    assert "dummy_lottery_results_REVERTED.csv" in response["Content-Disposition"]

    assert admin_list_emails(client, item1) == WAITING_EMAILS


@pytest.mark.django_db
def test_revert_brings_back_pre_lottery_label(client, admin_lottery_env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    item1 = admin_lottery_env["item1"]

    run_lottery(client, item1)
    run_lottery(client, item1, revert=True)

    content = client.get("/dummy/dummy/").content.decode()
    assert "These tickets will be assigned by lottery" in content
    assert "Ticket lottery held on" not in content
