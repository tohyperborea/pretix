"""
Lottery group models and service.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_groups.py -v
"""
import pytest
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Item, WaitingListEntry
from pretix_sideburn_lottery.models import LotteryGroup, LotteryGroupMembership
from pretix_sideburn_lottery.services import groups
from pretix_sideburn_lottery.services.groups import (
    GROUP_CODE_CHARSET, GROUP_CODE_LENGTH, create_group, generate_group_code,
    get_group, join_group, leave_group, normalize_group_code,
)


@pytest.fixture
def entries(lottery_env):
    with scopes_disabled():
        return [
            WaitingListEntry.objects.create(
                event=lottery_env["event"], item=lottery_env["item"], email=f"user{i}@example.org"
            )
            for i in range(4)
        ]


def _mark_lottery_run(lottery_env):
    lottery_env["event"].settings.set(
        f"lottery_date_for_item_{lottery_env['item'].pk}", now().isoformat()
    )


@pytest.mark.django_db
@scopes_disabled()
def test_create_group(lottery_env, entries):
    group = create_group(entries[0])

    assert group.event == lottery_env["event"]
    assert group.item == lottery_env["item"]
    assert len(group.code) == GROUP_CODE_LENGTH
    assert set(group.code) <= set(GROUP_CODE_CHARSET)
    assert get_group(entries[0]) == group


@pytest.mark.django_db
@scopes_disabled()
def test_create_group_moves_entry_out_of_previous_group(entries):
    first = create_group(entries[0])
    second = create_group(entries[0])

    assert get_group(entries[0]) == second
    assert not LotteryGroup.objects.filter(pk=first.pk).exists()


@pytest.mark.django_db
@scopes_disabled()
def test_join_group(entries):
    group = create_group(entries[0])

    assert join_group(entries[1], group.code) == group
    assert group.memberships.count() == 2


@pytest.mark.django_db
@scopes_disabled()
def test_join_group_code_is_case_insensitive_and_ignores_spaces_and_dashes(entries):
    group = create_group(entries[0])
    typed = " {}-{} ".format(group.code[:3].lower(), group.code[3:].lower())

    assert join_group(entries[1], typed) == group


@pytest.mark.django_db
@scopes_disabled()
def test_join_group_unknown_code(entries):
    with pytest.raises(ValidationError):
        join_group(entries[0], "ZZZZZZ")
    assert get_group(entries[0]) is None


@pytest.mark.django_db
@scopes_disabled()
def test_join_group_for_different_product(lottery_env, entries):
    other_item = Item.objects.create(event=lottery_env["event"], name="Other", default_price=10)
    other_entry = WaitingListEntry.objects.create(
        event=lottery_env["event"], item=other_item, email="other@example.org"
    )
    group = create_group(entries[0])

    with pytest.raises(ValidationError):
        join_group(other_entry, group.code)
    assert get_group(other_entry) is None


@pytest.mark.django_db
@scopes_disabled()
def test_join_group_when_full(lottery_env, entries):
    lottery_env["event"].settings.set("lottery_group_max_size", 2)
    group = create_group(entries[0])
    join_group(entries[1], group.code)

    with pytest.raises(ValidationError):
        join_group(entries[2], group.code)
    assert group.memberships.count() == 2


@pytest.mark.django_db
@scopes_disabled()
def test_max_group_size_defaults_to_ten(lottery_env):
    assert lottery_env["event"].settings.lottery_group_max_size == 10


@pytest.mark.django_db
@scopes_disabled()
def test_join_own_group_again_is_a_no_op(lottery_env, entries):
    lottery_env["event"].settings.set("lottery_group_max_size", 1)
    group = create_group(entries[0])

    assert join_group(entries[0], group.code) == group
    assert group.memberships.count() == 1


@pytest.mark.django_db
@scopes_disabled()
def test_switching_groups_keeps_old_group_if_others_remain(entries):
    old = create_group(entries[0])
    join_group(entries[1], old.code)
    new = create_group(entries[2])

    join_group(entries[1], new.code)

    assert get_group(entries[1]) == new
    assert list(old.memberships.values_list("entry", flat=True)) == [entries[0].pk]


@pytest.mark.django_db
@scopes_disabled()
def test_switching_groups_deletes_old_group_if_empty(entries):
    old = create_group(entries[0])
    new = create_group(entries[1])

    join_group(entries[0], new.code)

    assert not LotteryGroup.objects.filter(pk=old.pk).exists()


@pytest.mark.django_db
@scopes_disabled()
def test_leave_group_keeps_group_if_others_remain(entries):
    group = create_group(entries[0])
    join_group(entries[1], group.code)

    leave_group(entries[1])

    assert get_group(entries[1]) is None
    assert LotteryGroup.objects.filter(pk=group.pk).exists()


@pytest.mark.django_db
@scopes_disabled()
def test_leave_group_deletes_empty_group(entries):
    group = create_group(entries[0])

    leave_group(entries[0])

    assert not LotteryGroup.objects.filter(pk=group.pk).exists()


@pytest.mark.django_db
@scopes_disabled()
def test_leave_group_when_not_in_one(entries):
    leave_group(entries[0])
    assert get_group(entries[0]) is None


@pytest.mark.django_db
@scopes_disabled()
def test_groups_locked_after_lottery_runs(lottery_env, entries):
    group = create_group(entries[0])
    _mark_lottery_run(lottery_env)

    with pytest.raises(ValidationError):
        create_group(entries[1])
    with pytest.raises(ValidationError):
        join_group(entries[1], group.code)
    with pytest.raises(ValidationError):
        leave_group(entries[0])
    assert get_group(entries[0]) == group
    assert get_group(entries[1]) is None


@pytest.mark.django_db
@scopes_disabled()
def test_lottery_on_other_product_does_not_lock_groups(lottery_env, entries):
    other_item = Item.objects.create(event=lottery_env["event"], name="Other", default_price=10)
    lottery_env["event"].settings.set(f"lottery_date_for_item_{other_item.pk}", now().isoformat())

    group = create_group(entries[0])
    join_group(entries[1], group.code)
    leave_group(entries[1])


@pytest.mark.django_db
@scopes_disabled()
def test_deleting_entry_removes_membership(entries):
    group = create_group(entries[0])
    join_group(entries[1], group.code)

    entries[1].delete()

    assert not LotteryGroupMembership.objects.filter(entry_id=entries[1].pk).exists()
    assert group.memberships.count() == 1


@pytest.mark.django_db
@scopes_disabled()
def test_generate_group_code_skips_banned_and_taken_codes(lottery_env, entries, monkeypatch):
    taken = create_group(entries[0]).code
    candidates = iter(["BANNED", taken, "GOOD23"])
    monkeypatch.setattr(groups, "get_random_string", lambda *args, **kwargs: next(candidates))
    monkeypatch.setattr(groups, "banned", lambda code: code == "BANNED")

    assert generate_group_code(lottery_env["event"]) == "GOOD23"


def test_normalize_group_code():
    assert normalize_group_code(" ab-c 23d ") == "ABC23D"
    assert normalize_group_code(None) == ""
