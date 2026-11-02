"""
The per-product "Allow registrants to line up together" setting.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_item_groups_setting.py -v
"""
import pytest
from django.test import RequestFactory
from django_scopes import scopes_disabled

from pretix.base.models import Item, Team, User
from pretix.base.signals import item_copy_data
from pretix_sideburn_lottery.forms import ItemLotteryGroupsForm
from pretix_sideburn_lottery.services.groups import (
    groups_allowed, set_groups_allowed,
)
from pretix_sideburn_lottery.signals import item_lottery_groups_form


@pytest.fixture
def admin_client(client, lottery_env):
    with scopes_disabled():
        user = User.objects.create_user("admin@example.org", "admin")
        team = Team.objects.create(
            organizer=lottery_env["organizer"],
            limit_event_permissions={"event.items:read": True, "event.items:write": True},
        )
        team.members.add(user)
        team.limit_events.add(lottery_env["event"])
    client.login(email="admin@example.org", password="admin")
    return client


def item_url(env):
    return "/control/event/{}/{}/items/{}/".format(env["organizer"].slug, env["event"].slug, env["item"].pk)


@pytest.mark.django_db
def test_product_page_shows_setting_off_by_default(admin_client, lottery_env):
    response = admin_client.get(item_url(lottery_env))

    assert response.status_code == 200
    field = response.context["plugin_forms"][0]["allow_groups"]
    assert "Allow registrants to line up together" in response.content.decode()
    assert field.value() is False


@pytest.mark.django_db
def test_product_page_shows_setting_when_on(admin_client, lottery_env):
    set_groups_allowed(lottery_env["event"], lottery_env["item"].pk, True)

    response = admin_client.get(item_url(lottery_env))

    assert response.context["plugin_forms"][0]["allow_groups"].value() is True


@pytest.mark.django_db
@pytest.mark.parametrize("posted, expected", [({"sideburn_lottery-allow_groups": "on"}, True), ({}, False)])
def test_saving_product_form_stores_setting(lottery_env, posted, expected):
    set_groups_allowed(lottery_env["event"], lottery_env["item"].pk, not expected)
    request = RequestFactory().post("/", posted)

    form = item_lottery_groups_form(sender=lottery_env["event"], request=request, item=lottery_env["item"])
    assert form.is_valid()
    form.save()

    assert groups_allowed(lottery_env["event"], lottery_env["item"].pk) is expected


@pytest.mark.django_db
def test_form_is_unbound_on_get(lottery_env):
    form = item_lottery_groups_form(
        sender=lottery_env["event"], request=RequestFactory().get("/"), item=lottery_env["item"]
    )

    assert isinstance(form, ItemLotteryGroupsForm)
    assert not form.is_bound


@pytest.mark.django_db
def test_copying_product_copies_setting(lottery_env):
    event = lottery_env["event"]
    set_groups_allowed(event, lottery_env["item"].pk, True)
    with scopes_disabled():
        copy = Item.objects.create(event=event, name="Copy", default_price=100)

    item_copy_data.send(sender=event, source=lottery_env["item"], target=copy)

    assert groups_allowed(event, copy.pk)
