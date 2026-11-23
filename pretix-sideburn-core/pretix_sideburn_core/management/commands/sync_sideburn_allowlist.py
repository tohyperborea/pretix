from django.core.management.base import BaseCommand, CommandError
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer

from pretix_sideburn_core.allowlist_sync import sync_allowlists


class Command(BaseCommand):
    help = (
        "Backfill Sideburn allowlist entries from past paid attendance on "
        "events with allowlist-counting products configured."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--organizer",
            metavar="SLUG",
            help="Limit to one organizer slug.",
        )
        parser.add_argument(
            "--event",
            metavar="SLUG",
            help="Limit to one event slug (requires --organizer).",
        )

    def handle(self, *args, **options):
        organizer_slug = options.get("organizer")
        event_slug = options.get("event")

        with scopes_disabled():
            organizer = None
            event = None
            if organizer_slug:
                try:
                    organizer = Organizer.objects.get(slug=organizer_slug)
                except Organizer.DoesNotExist as exc:
                    raise CommandError(f"Unknown organizer: {organizer_slug}") from exc
            if event_slug:
                if not organizer:
                    raise CommandError("--event requires --organizer.")
                try:
                    event = Event.objects.get(organizer=organizer, slug=event_slug)
                except Event.DoesNotExist as exc:
                    raise CommandError(
                        f"Unknown event: {organizer_slug}/{event_slug}"
                    ) from exc

            created = sync_allowlists(organizer=organizer, event=event)

        self.stdout.write(
            self.style.SUCCESS(f"Created {created} allowlist entr{'y' if created == 1 else 'ies'}.")
        )
