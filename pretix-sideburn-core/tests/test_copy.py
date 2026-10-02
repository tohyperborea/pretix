"""
Sideburn copy: the default checkout email help text.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-core/tests/test_copy.py -v
"""
from pathlib import Path

import pytest
from django.utils import translation
from django.utils.timezone import now
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString

import pretix_sideburn_core
from pretix.base.models import Event, Organizer

HELPTEXT_EN = "We will send you an order confirmation including a link that you need to access your order later."
HELPTEXT_FR = (
    "Nous vous enverrons une confirmation de votre commande et un lien si vous "
    "souhaitez modifier votre commande ultérieurement."
)
FR_CATALOG = Path(pretix_sideburn_core.__file__).parent / "locale" / "fr" / "LC_MESSAGES" / "django.mo"


@pytest.fixture
@scopes_disabled()
def event():
    organizer = Organizer.objects.create(name="Sideburn Test", slug="sideburntest")
    return Event.objects.create(organizer=organizer, name="Test Event", slug="testevent", date_from=now())


@pytest.mark.django_db
def test_default_checkout_email_helptext(event):
    with translation.override("en"):
        assert str(event.settings.checkout_email_helptext) == HELPTEXT_EN


@pytest.mark.django_db
def test_event_can_still_override_checkout_email_helptext(event):
    event.settings.checkout_email_helptext = LazyI18nString({"en": "Custom text"})
    with translation.override("en"):
        assert str(event.settings.checkout_email_helptext) == "Custom text"


@pytest.mark.django_db
@pytest.mark.skipif(not FR_CATALOG.exists(), reason="French catalog not compiled (run compilemessages)")
def test_checkout_email_helptext_in_french(event):
    with translation.override("fr"):
        assert str(event.settings.checkout_email_helptext) == HELPTEXT_FR
