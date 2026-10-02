import pytest
from django.utils.timezone import now

from pretix.base.models import Event, Organizer
from pretix.base.plugins import get_all_plugins

from pretix_sideburn_core import __version__
from pretix_sideburn_core.apps import PluginApp


def test_version():
    assert __version__ == "1.0.0"


def test_plugin_metadata():
    meta = PluginApp.PretixPluginMeta
    assert meta.category == "CUSTOMIZATION"
    assert meta.visible


@pytest.mark.django_db
def test_plugin_is_registered_and_can_be_enabled():
    assert "pretix_sideburn_core" in [p.module for p in get_all_plugins()]

    organizer = Organizer.objects.create(name="Dummy", slug="dummy")
    event = Event.objects.create(
        organizer=organizer, name="Dummy", slug="dummy", date_from=now(),
        plugins="pretix_sideburn_core",
    )
    assert "pretix_sideburn_core" in event.get_plugins()
