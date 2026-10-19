"""
Waiting-list rules: vouchers sent from the waiting list bypass the quota, and an email that already
holds a live voucher for a product can't sign up for it again.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_waitinglist_ops.py -v
"""
from datetime import timedelta

import pytest
from django.core import mail as djmail
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    CartPosition, Event, Item, Organizer, Quota, Voucher, WaitingListEntry,
)
from pretix.base.models.waitinglist import WaitingListException

EMAIL = "foo@bar.com"
PASSWORD = "customerpass"


@pytest.fixture
@scopes_disabled()
def env():
    organizer = Organizer.objects.create(name="Dummy", slug="dummy")
    organizer.settings.customer_accounts = True
    organizer.settings.customer_accounts_native = True
    event = Event.objects.create(
        organizer=organizer, name="Dummy", slug="dummy", date_from=now() + timedelta(days=30), live=True,
        plugins="pretix_sideburn_core",
    )
    event.settings.set("waiting_list_enabled", True)
    quota = Quota.objects.create(name="Test", size=0, event=event)
    item = Item.objects.create(event=event, name="Ticket", default_price=23, admission=True)
    quota.items.add(item)
    customer = organizer.customers.create(email=EMAIL, is_verified=True, is_active=True)
    customer.set_password(PASSWORD)
    customer.save()
    return {"organizer": organizer, "event": event, "item": item}


def log_in(client):
    response = client.post("/dummy/account/login", {"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 302


@pytest.mark.django_db
def test_waiting_list_voucher_can_be_used_while_sold_out(client, env):
    item = env["item"]
    with scopes_disabled():
        wle = WaitingListEntry.objects.create(event=env["event"], item=item, email=EMAIL)
        djmail.outbox = []
        wle.send_voucher()
        wle.refresh_from_db()
        code = wle.voucher.code
    assert len(djmail.outbox) == 1
    assert code in djmail.outbox[0].body

    log_in(client)
    client.post("/dummy/dummy/cart/add", {"item_%d" % item.pk: "1", "_voucher_code": code}, follow=True)
    with scopes_disabled():
        assert CartPosition.objects.filter(item=item, voucher__code=code).count() == 1


@pytest.mark.django_db
@scopes_disabled()
def test_send_voucher_respects_quota_without_plugin(env):
    env["event"].disable_plugin("pretix_sideburn_core")
    env["event"].save()
    wle = WaitingListEntry.objects.create(event=env["event"], item=env["item"], email=EMAIL)
    with pytest.raises(WaitingListException):
        wle.send_voucher()


@pytest.mark.django_db
def test_signup_rejected_when_customer_already_has_a_valid_voucher(client, env):
    with scopes_disabled():
        v = Voucher.objects.create(event=env["event"], valid_until=now() + timedelta(days=1), redeemed=0)
        WaitingListEntry.objects.create(event=env["event"], item=env["item"], email=EMAIL, voucher=v)

    log_in(client)
    response = client.post(
        "/dummy/dummy/waitinglist/?item=%d" % env["item"].pk,
        {"email": EMAIL, "itemvar": str(env["item"].pk)},
        follow=True,
    )

    assert "You have already been assigned a ticket!" in response.content.decode()
    with scopes_disabled():
        assert WaitingListEntry.objects.filter(email=EMAIL).count() == 1


def existing_entry_with_voucher(env, **voucher_kwargs):
    v = Voucher.objects.create(event=env["event"], **voucher_kwargs)
    WaitingListEntry.objects.create(event=env["event"], item=env["item"], email=EMAIL, voucher=v)
    return WaitingListEntry(event=env["event"], item=env["item"], email=EMAIL)


@pytest.mark.django_db
@scopes_disabled()
def test_duplicate_allows_expired_unredeemed_voucher(env):
    wle = existing_entry_with_voucher(env, valid_until=now() - timedelta(days=1), redeemed=0)
    wle.full_clean()


@pytest.mark.django_db
@scopes_disabled()
def test_duplicate_blocks_redeemed_voucher(env):
    wle = existing_entry_with_voucher(env, valid_until=now() - timedelta(days=1), redeemed=1)
    with pytest.raises(ValidationError):
        wle.full_clean()


@pytest.mark.django_db
@scopes_disabled()
def test_duplicate_blocks_valid_unredeemed_voucher(env):
    wle = existing_entry_with_voucher(env, valid_until=now() + timedelta(days=1), redeemed=0)
    with pytest.raises(ValidationError):
        wle.full_clean()


@pytest.mark.django_db
@scopes_disabled()
def test_duplicate_check_is_off_without_plugin(env):
    env["event"].disable_plugin("pretix_sideburn_core")
    env["event"].save()
    wle = existing_entry_with_voucher(env, valid_until=now() + timedelta(days=1), redeemed=0)
    wle.full_clean()
