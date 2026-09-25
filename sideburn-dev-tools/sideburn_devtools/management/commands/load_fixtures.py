from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_scopes import scopes_disabled


class Command(BaseCommand):
    help = """Load this project's curated fixture set (with django-scopes disabled).

            Examples:
            python manage.py load_fixtures
            python manage.py load_fixtures --only all --ignorenonexistent
            """

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            choices=("all", "base", "plugin"),
            default="all",
            help="Load only a subset of fixtures (default: all).",
        )
        parser.add_argument(
            "--ignorenonexistent",
            action="store_true",
            help="Pass --ignorenonexistent through to Django's loaddata.",
        )

    def handle(self, *args, **options):
        # Fixture names resolve via sideburn_devtools/fixtures/ (app must be in INSTALLED_APPS).
        # Deterministic order matters due to foreign keys.
        base_fixtures = [
            "organizer",
            "customer",
            "event",
            "tickets",
            "tax_and_global_settings",
        ]
        # Core pretix plugin fixture (still ships with pretix).
        plugin_fixtures = [
            "pretix/plugins/ticketoutputpdf/fixtures/ticketlayout.json",
        ]

        only = options["only"]
        fixtures: list[str]
        if only == "base":
            fixtures = base_fixtures
        elif only == "plugin":
            fixtures = plugin_fixtures
        else:
            fixtures = base_fixtures + plugin_fixtures

        loaddata_opts = {}
        if options.get("ignorenonexistent"):
            loaddata_opts["ignorenonexistent"] = True

        with scopes_disabled():
            call_command("loaddata", *fixtures, **loaddata_opts)
