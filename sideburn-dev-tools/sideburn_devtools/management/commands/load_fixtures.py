from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_scopes import scopes_disabled


class Command(BaseCommand):
    help = """Load this project's curated fixture set (with django-scopes disabled).

            Examples:
            python manage.py load_fixtures
            python manage.py load_fixtures --ignorenonexistent
            """

    def add_arguments(self, parser):
        parser.add_argument(
            "--ignorenonexistent",
            action="store_true",
            help="Pass --ignorenonexistent through to Django's loaddata.",
        )

    def handle(self, *args, **options):
        # Fixture names resolve via sideburn_devtools/fixtures/ (app must be in INSTALLED_APPS).
        # All fixtures load in one loaddata call, so cross-references resolve regardless of order.
        fixtures = [
            "organizer",
            "customer",
            "event",
            "tickets",
            "tax_and_global_settings",
            "ticketlayout",
        ]

        loaddata_opts = {}
        if options.get("ignorenonexistent"):
            loaddata_opts["ignorenonexistent"] = True

        with scopes_disabled():
            call_command("loaddata", *fixtures, **loaddata_opts)
