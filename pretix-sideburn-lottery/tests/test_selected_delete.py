"""
"Delete selected (including entries with vouchers)" on the control waiting list.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_selected_delete.py -v
"""
from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    Event, Item, LogEntry, Organizer, Team, User, Voucher, WaitingListEntry,
)

URL = "/control/event/dummy/dummy/sideburn-lottery/delete-selected/"
WAITINGLIST_URL = "/control/event/dummy/dummy/waitinglist/"


@pytest.fixture
def env():
    organizer = Organizer.objects.create(name="Dummy", slug="dummy")
    event = Event.objects.create(
        organizer=organizer, name="Dummy", slug="dummy", date_from=now(),
        plugins="pretix_sideburn_lottery",
    )
    item1 = Item.objects.create(event=event, name="Ticket", default_price=23, admission=True)
    item2 = Item.objects.create(event=event, name="Ticket B", default_price=23, admission=True)

    def entry(email, item, **voucher_kwargs):
        voucher = None
        if voucher_kwargs:
            voucher = Voucher.objects.create(item=item, event=event, block_quota=True, **voucher_kwargs)
        return WaitingListEntry.objects.create(event=event, item=item, email=email, voucher=voucher)

    entries = {
        "waiting": entry("waiting@example.org", item1),
        "redeemed": entry("redeemed@example.org", item1, redeemed=1),
        "expired": entry("expired@example.org", item1, redeemed=0, valid_until=now() - timedelta(days=1)),
        "valid": entry("valid@example.org", item1, redeemed=0, valid_until=now() + timedelta(days=5)),
        "other_item_waiting": entry("other-waiting@example.org", item2),
        "other_item_valid": entry("other@example.org", item2, redeemed=0),
    }

    user = User.objects.create_user("dummy@dummy.dummy", "dummy")
    team = Team.objects.create(organizer=organizer, can_view_orders=True, can_change_orders=True)
    team.members.add(user)
    team.limit_events.add(event)

    return {"event": event, "item1": item1, "item2": item2, "entries": entries, "user": user, "team": team}


@pytest.fixture
def admin_client(client, env):
    client.login(email="dummy@dummy.dummy", password="dummy")
    return client


def remaining_emails():
    with scopes_disabled():
        return set(WaitingListEntry.objects.values_list("email", flat=True))


def pks(env, *names):
    return [env["entries"][n].pk for n in names]


def confirm(client, env, names, **extra):
    return client.post(URL, {"action": "confirm", "entry": pks(env, *names), **extra})


@pytest.mark.django_db
def test_requires_change_orders_permission(admin_client, env):
    env["team"].can_change_orders = False
    env["team"].save()

    assert admin_client.post(URL, {"status": "a", "entry": pks(env, "valid")}).status_code == 403
    assert confirm(admin_client, env, ["valid"]).status_code == 403
    assert len(remaining_emails()) == 6


@pytest.mark.django_db
def test_get_not_allowed(admin_client, env):
    assert admin_client.get(URL).status_code == 405


@pytest.mark.django_db
def test_confirmation_page_lists_selected_entries_only(admin_client, env):
    response = admin_client.post(URL, {"status": "a", "entry": pks(env, "waiting", "valid", "redeemed")})
    content = response.content.decode()

    assert response.status_code == 200
    assert "Are you sure you want to delete the following 3 entries?" in content
    assert content.count('name="entry"') == 3
    assert 'name="voucher_action" value="expire" checked' in content
    assert "expired@example.org" not in content
    assert len(remaining_emails()) == 6


@pytest.mark.django_db
def test_confirmation_page_without_valid_vouchers_has_no_voucher_choice(admin_client, env):
    response = admin_client.post(URL, {"status": "a", "entry": pks(env, "redeemed", "expired")})
    content = response.content.decode()

    assert content.count('name="entry"') == 2
    assert "voucher_action" not in content


@pytest.mark.django_db
def test_confirmation_respects_status_filter_like_core(admin_client, env):
    # Ticked rows outside the current filter are ignored, as in core's "Delete selected".
    response = admin_client.post(URL, {"status": "r", "entry": pks(env, "redeemed", "valid")})
    assert response.content.decode().count('name="entry"') == 1


@pytest.mark.django_db
def test_select_all_pages_uses_filter(admin_client, env):
    response = admin_client.post(URL, {"status": "a", "item": env["item1"].pk, "__ALL": "on", "entry": pks(env, "waiting")})
    assert response.content.decode().count('name="entry"') == 4


@pytest.mark.django_db
def test_nothing_selected(admin_client, env):
    response = admin_client.post(URL, {"status": "a"}, follow=True)
    assert "You did not select any entries" in response.content.decode()
    assert len(remaining_emails()) == 6


@pytest.mark.django_db
def test_malformed_selection(admin_client, env):
    response = admin_client.post(URL, {"status": "a", "item": "abc", "entry": pks(env, "waiting")}, follow=True)
    assert "Invalid selection" in response.content.decode()

    response = confirm(admin_client, env, [], entry="abc")
    assert response.status_code == 302
    assert len(remaining_emails()) == 6


@pytest.mark.django_db
def test_confirm_deletes_exactly_the_listed_entries(admin_client, env):
    response = confirm(admin_client, env, ["waiting", "redeemed", "valid"])

    assert response.status_code == 302
    assert remaining_emails() == {"expired@example.org", "other-waiting@example.org", "other@example.org"}


@pytest.mark.django_db
def test_redirects_back_to_next(admin_client, env):
    next_url = WAITINGLIST_URL + "?status=a&item=%d" % env["item1"].pk
    response = admin_client.post(URL + "?next=" + next_url.replace("&", "%26").replace("?", "%3F"), {
        "action": "confirm", "entry": pks(env, "waiting"),
    })
    assert response.url == next_url


@pytest.mark.django_db
def test_cannot_delete_entries_of_other_events(admin_client, env):
    other_event = Event.objects.create(organizer=env["event"].organizer, name="Other", slug="other", date_from=now())
    other_item = Item.objects.create(event=other_event, name="T", default_price=1)
    with scopes_disabled():
        foreign = WaitingListEntry.objects.create(event=other_event, item=other_item, email="foreign@example.org")

    confirm(admin_client, env, [], entry=[foreign.pk])
    assert "foreign@example.org" in remaining_emails()


@pytest.mark.django_db
def test_expire_valid_vouchers_by_default(admin_client, env):
    valid_voucher = env["entries"]["valid"].voucher
    expired_voucher = env["entries"]["expired"].voucher
    expired_until = expired_voucher.valid_until

    confirm(admin_client, env, ["valid", "expired"])

    valid_voucher.refresh_from_db()
    expired_voucher.refresh_from_db()
    assert valid_voucher.valid_until <= now()
    assert expired_voucher.valid_until == expired_until
    with scopes_disabled():
        assert LogEntry.objects.filter(action_type="pretix.voucher.changed", object_id=valid_voucher.pk).exists()


@pytest.mark.django_db
def test_keep_valid_vouchers(admin_client, env):
    valid_voucher = env["entries"]["valid"].voucher
    valid_until = valid_voucher.valid_until

    confirm(admin_client, env, ["valid"], voucher_action="keep")

    valid_voucher.refresh_from_db()
    assert valid_voucher.valid_until == valid_until
    assert "valid@example.org" not in remaining_emails()


@pytest.mark.django_db
def test_delete_valid_vouchers(admin_client, env):
    valid_voucher_pk = env["entries"]["valid"].voucher.pk
    redeemed_voucher_pk = env["entries"]["redeemed"].voucher.pk

    confirm(admin_client, env, ["valid", "redeemed"], voucher_action="delete")

    with scopes_disabled():
        assert not Voucher.objects.filter(pk=valid_voucher_pk).exists()
        assert Voucher.objects.filter(pk=redeemed_voucher_pk).exists()


@pytest.mark.django_db
def test_invalid_voucher_action_deletes_nothing(admin_client, env):
    confirm(admin_client, env, ["valid"], voucher_action="nope")
    assert len(remaining_emails()) == 6


@pytest.mark.django_db
def test_entry_deletion_is_logged(admin_client, env):
    valid_entry = env["entries"]["valid"]
    waiting_entry = env["entries"]["waiting"]

    confirm(admin_client, env, ["valid", "waiting"])

    with scopes_disabled():
        log = LogEntry.objects.get(action_type="pretix.event.orders.waitinglist.deleted", object_id=valid_entry.pk)
        waiting_log = LogEntry.objects.get(action_type="pretix.event.orders.waitinglist.deleted", object_id=waiting_entry.pk)
    assert log.parsed_data["voucher"] == valid_entry.voucher.code
    assert log.parsed_data["voucher_state"] == "valid"
    assert log.parsed_data["voucher_action"] == "expire"
    assert waiting_log.parsed_data["bulk"] is True
    assert "voucher" not in waiting_log.parsed_data


@pytest.mark.django_db
def test_waitinglist_page_has_button_template(admin_client, env):
    content = admin_client.get(WAITINGLIST_URL + "?status=a").content.decode()
    assert 'id="delete-selected-with-vouchers-template"' in content
    assert 'formaction="/control/event/dummy/dummy/sideburn-lottery/delete-selected/?next=' in content


@pytest.mark.django_db
def test_waitinglist_page_hides_button_without_permission(admin_client, env):
    env["team"].can_change_orders = False
    env["team"].save()
    content = admin_client.get(WAITINGLIST_URL).content.decode()
    assert "delete-selected-with-vouchers-template" not in content
