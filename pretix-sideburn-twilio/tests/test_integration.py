"""
Integration tests for pretix-sideburn-twilio hooks and waiting-list SMS flow.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-twilio/tests/test_integration.py -v
"""
import pytest
from django import forms
from django.test import RequestFactory
from django_scopes import scope, scopes_disabled

from pretix.base.models import WaitingListEntry
from pretix.presale.forms.customer import ChangeInfoForm
from pretix.presale.forms.waitinglist import WaitingListForm
from pretix.presale.signals import (
    change_information_form_class, waitinglist_form_class,
)
from pretix_twilio_sms.forms import ChangeInfoSmsMixin, WaitingListSmsMixin
from pretix_twilio_sms.models import CustomerSmsPreference
from pretix_twilio_sms.signals import (
    inject_change_info_form_with_sms, inject_waitinglist_form_with_sms,
)

TEST_PHONE = "+12125552368"
TEST_EMAIL = "waitlist@example.com"


@pytest.mark.django_db
def test_waitinglist_signup_with_sms_opt_in(client, twilio_env, logged_in_customer):
    event = twilio_env["event"]
    item = twilio_env["item"]
    organizer = twilio_env["organizer"]

    response = client.post(
        "/{}/{}/waitinglist/?item={}".format(organizer.slug, event.slug, item.pk),
        {
            "email": TEST_EMAIL,
            "itemvar": str(item.pk),
            "sms_opt_in": "on",
            "sms_phone_0": "+1",
            "sms_phone_1": "2125552368",
        },
    )
    assert response.status_code == 302

    with scopes_disabled():
        entry = WaitingListEntry.objects.get(event=event, email=TEST_EMAIL)
        pref = CustomerSmsPreference.objects.get(customer=logged_in_customer)

    assert entry.phone
    assert pref.sms_opt_in is True
    assert str(logged_in_customer.phone) == TEST_PHONE


@pytest.mark.django_db
def test_waitinglist_signup_opt_out(client, twilio_env, logged_in_customer):
    event = twilio_env["event"]
    item = twilio_env["item"]
    organizer = twilio_env["organizer"]

    response = client.post(
        "/{}/{}/waitinglist/?item={}".format(organizer.slug, event.slug, item.pk),
        {
            "email": TEST_EMAIL,
            "itemvar": str(item.pk),
        },
    )
    assert response.status_code == 302

    with scopes_disabled():
        pref = CustomerSmsPreference.objects.get(customer=logged_in_customer)
    assert pref.sms_opt_in is False


@pytest.mark.django_db
def test_waitinglist_form_prefills_returning_customer(client, twilio_env, logged_in_customer):
    """An opted-in customer sees their choice and phone pre-filled, so resubmitting keeps them opted in."""
    event = twilio_env["event"]
    item = twilio_env["item"]
    organizer = twilio_env["organizer"]
    with scopes_disabled():
        CustomerSmsPreference.objects.create(customer=logged_in_customer, sms_opt_in=True)

    response = client.get("/{}/{}/waitinglist/?item={}".format(organizer.slug, event.slug, item.pk))

    assert response.status_code == 200
    form = response.context["form"]
    assert form.initial["sms_opt_in"] is True
    assert str(form.initial["sms_phone"]) == TEST_PHONE


@pytest.mark.django_db
def test_send_voucher_queues_sms_when_opted_in(twilio_env, ticket_available, sms_calls):
    event = twilio_env["event"]
    item = twilio_env["item"]
    customer = twilio_env["customer"]

    CustomerSmsPreference.objects.create(customer=customer, sms_opt_in=True)

    with scope(organizer=event.organizer):
        entry = WaitingListEntry.objects.create(
            event=event,
            item=item,
            email=TEST_EMAIL,
            phone=TEST_PHONE,
        )
        entry.send_voucher()

    assert len(sms_calls) == 1
    assert sms_calls[0]["sms_opt_in"] is True
    assert sms_calls[0]["phone"] == TEST_PHONE
    assert sms_calls[0]["entry_id"] == entry.pk


@pytest.mark.django_db
def test_send_voucher_skips_sms_when_opted_out(twilio_env, ticket_available, sms_calls):
    event = twilio_env["event"]
    item = twilio_env["item"]
    customer = twilio_env["customer"]

    CustomerSmsPreference.objects.create(customer=customer, sms_opt_in=False)

    with scope(organizer=event.organizer):
        entry = WaitingListEntry.objects.create(
            event=event,
            item=item,
            email=TEST_EMAIL,
            phone=TEST_PHONE,
        )
        entry.send_voucher()

    assert len(sms_calls) == 0


@pytest.mark.django_db
def test_send_voucher_skips_sms_without_phone(twilio_env, ticket_available, sms_calls):
    event = twilio_env["event"]
    item = twilio_env["item"]
    customer = twilio_env["customer"]
    customer.phone = None
    customer.save(update_fields=["phone"])

    CustomerSmsPreference.objects.create(customer=customer, sms_opt_in=True)

    with scope(organizer=event.organizer):
        entry = WaitingListEntry.objects.create(
            event=event,
            item=item,
            email=TEST_EMAIL,
        )
        entry.send_voucher()

    assert len(sms_calls) == 0


@pytest.mark.django_db
def test_customer_profile_shows_sms_opt_in_status(client, twilio_env, logged_in_customer):
    CustomerSmsPreference.objects.create(customer=logged_in_customer, sms_opt_in=True)
    organizer = twilio_env["organizer"]

    response = client.get("/{}/account/".format(organizer.slug))
    assert response.status_code == 200
    assert "signed up to receive SMS updates" in response.content.decode()


@pytest.mark.django_db
def test_customer_profile_shows_sms_opt_out_status(client, twilio_env, logged_in_customer):
    CustomerSmsPreference.objects.create(customer=logged_in_customer, sms_opt_in=False)
    organizer = twilio_env["organizer"]

    response = client.get("/{}/account/".format(organizer.slug))
    assert response.status_code == 200
    assert "not signed up to receive SMS updates" in response.content.decode()


@pytest.mark.django_db
def test_change_account_form_saves_sms_preference(client, twilio_env, logged_in_customer):
    organizer = twilio_env["organizer"]
    customer = logged_in_customer

    response = client.post(
        "/{}/account/change".format(organizer.slug),
        {
            "name_parts_0": customer.name or "Test User",
            "email": TEST_EMAIL,
            "phone_0": TEST_PHONE,
            "sms_opt_in": "on",
        },
    )
    assert response.status_code == 302

    pref = CustomerSmsPreference.objects.get(customer=customer)
    assert pref.sms_opt_in is True


@pytest.mark.django_db
def test_admin_path_send_voucher_queues_sms(twilio_env, ticket_available, sms_calls):
    """Direct send_voucher call mirrors control/admin assignment paths."""
    event = twilio_env["event"]
    item = twilio_env["item"]
    customer = twilio_env["customer"]
    CustomerSmsPreference.objects.create(customer=customer, sms_opt_in=True)

    with scope(organizer=event.organizer):
        entry = WaitingListEntry.objects.create(
            event=event,
            item=item,
            email=TEST_EMAIL,
        )
        entry.send_voucher()

    assert len(sms_calls) == 1
    assert sms_calls[0]["entry_id"] == entry.pk


@pytest.mark.django_db
def test_waitinglist_form_hook_resolves_sms_form(twilio_env):
    event = twilio_env["event"]

    form_class = waitinglist_form_class.send_chained(event, "cls", cls=WaitingListForm)

    assert issubclass(form_class, WaitingListForm)
    assert issubclass(form_class, WaitingListSmsMixin)


@pytest.mark.django_db
def test_waitinglist_form_hook_keeps_previous_plugins_form(twilio_env):
    """The SMS form is stacked onto whatever class an earlier plugin returned."""
    event = twilio_env["event"]
    item = twilio_env["item"]

    class EarlierPluginForm(WaitingListForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields["earlier_plugin_field"] = forms.CharField(required=False)

    form_class = inject_waitinglist_form_with_sms(sender=event, cls=EarlierPluginForm)
    with scope(organizer=event.organizer):
        form = form_class(
            request=RequestFactory().get("/"), event=event, itemvars=[(str(item.pk), str(item.name))],
            instance=WaitingListEntry(event=event, item=item),
        )

    assert issubclass(form_class, EarlierPluginForm)
    assert "earlier_plugin_field" in form.fields
    assert "sms_opt_in" in form.fields


@pytest.mark.django_db
def test_change_info_form_hook_resolves_sms_form(twilio_env):
    organizer = twilio_env["organizer"]

    form_class = change_information_form_class.send_chained(
        organizer, "cls", cls=ChangeInfoForm, request=RequestFactory().get("/"),
    )

    assert issubclass(form_class, ChangeInfoForm)
    assert issubclass(form_class, ChangeInfoSmsMixin)


@pytest.mark.django_db
def test_change_info_form_hook_keeps_previous_plugins_form(twilio_env):
    """The SMS checkbox is stacked onto whatever class an earlier plugin returned."""
    organizer = twilio_env["organizer"]
    customer = twilio_env["customer"]

    class EarlierPluginForm(ChangeInfoForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields["earlier_plugin_field"] = forms.CharField(required=False)

    form_class = inject_change_info_form_with_sms(sender=organizer, cls=EarlierPluginForm)
    request = RequestFactory().get("/")
    request.organizer = organizer
    with scope(organizer=organizer):
        form = form_class(request=request, instance=customer)

    assert issubclass(form_class, EarlierPluginForm)
    assert "earlier_plugin_field" in form.fields
    assert "sms_opt_in" in form.fields
    assert list(form.fields).index("sms_opt_in") == list(form.fields).index("phone") + 1
