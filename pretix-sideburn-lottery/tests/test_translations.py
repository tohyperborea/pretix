"""
Every French string in this plugin must be translated.

The French catalogs are regenerated with makemessages from a copy of the plugin, so strings that were
added to the code but never extracted fail too. Needs GNU gettext: skipped without it, except in CI.

Run from the monorepo:
    cd src && pytest ../pretix-sideburn-lottery/tests/test_translations.py -v
"""
import os
import shutil
from pathlib import Path

import pytest
from babel.messages.pofile import read_po
from django.core.management import call_command

import pretix_sideburn_lottery

PACKAGE_DIR = Path(pretix_sideburn_lottery.__file__).parent


@pytest.fixture
def regenerated_french_catalogs(tmp_path, monkeypatch, settings):
    if not (shutil.which("xgettext") and shutil.which("msgmerge")):
        if os.environ.get("CI"):
            pytest.fail("GNU gettext is required to check translations in CI")
        pytest.skip("GNU gettext not found; install it to check translations")
    shutil.copytree(
        PACKAGE_DIR, tmp_path / PACKAGE_DIR.name, ignore=shutil.ignore_patterns("__pycache__", "*.mo", "*.pot")
    )
    # makemessages deletes the .pot files in every LOCALE_PATHS entry, which includes core's.
    settings.LOCALE_PATHS = []
    monkeypatch.chdir(tmp_path)
    for domain in ("django", "djangojs"):
        call_command("makemessages", locale=["fr"], domain=domain, verbosity=0)
    return sorted((tmp_path / PACKAGE_DIR.name / "locale" / "fr" / "LC_MESSAGES").glob("*.po"))


def test_all_french_strings_translated(regenerated_french_catalogs):
    problems = []
    for po_path in regenerated_french_catalogs:
        with po_path.open("rb") as f:
            catalog = read_po(f)
        for message in catalog:
            if not message.id:
                continue
            strings = message.string if isinstance(message.string, tuple) else (message.string,)
            if message.fuzzy:
                problems.append(f"{po_path.name}: needs review: {message.id!r}")
            elif not all(strings):
                problems.append(f"{po_path.name}: untranslated: {message.id!r}")
    assert not problems, (
        "Run makemessages for French and translate these in locale/fr/LC_MESSAGES:\n" + "\n".join(problems)
    )
