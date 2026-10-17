"""
French translations ship with the plugin (not core's fr catalog).

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_locale.py -v
"""
from pathlib import Path

import pytest
from django.utils import translation

import pretix_sideburn_lottery

FR_CATALOG = Path(pretix_sideburn_lottery.__file__).parent / "locale" / "fr" / "LC_MESSAGES" / "django.mo"


@pytest.mark.skipif(not FR_CATALOG.exists(), reason="French catalog not compiled (run make)")
@pytest.mark.parametrize("english, french", [
    ("How do tickets work for SideBurn?", "Comment fonctionnent les billets pour SideBurn ?"),
    ("Register here", "Inscrivez-vous ici"),
    ("SideBurn Code of Conduct", "Code de conduite SideBurn"),
])
def test_french_translation(english, french):
    with translation.override("fr"):
        assert translation.gettext(english) == french
