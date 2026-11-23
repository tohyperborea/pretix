"""
Upsert organizer allowlist rows from past attendance (paid admission tickets).

Idempotent creates only — never removes rows (not on cancel, not on denylist).
Uses pretix's built-in ``Item.admission`` flag (vs merch/add-ons).
"""
from __future__ import annotations

import logging

from django.db.models import Q
from django.utils.timezone import now

from pretix.base.models import Event, Order, OrderPosition

from .models import CustomerAllowlistEntry

logger = logging.getLogger(__name__)

PLUGIN_MODULE = "pretix_sideburn_core"


def event_has_ended(event: Event, *, at=None) -> bool:
    """True when the event end (or start if no end) is in the past."""
    at = at or now()
    end = event.date_to or event.date_from
    if end is None:
        return False
    return at >= end


def event_uses_plugin(event: Event) -> bool:
    return PLUGIN_MODULE in (event.get_plugins() or [])


def sync_event_allowlist(event: Event) -> int:
    """
    Create allowlist entries for customers with paid admission positions.

    Returns the number of newly created rows. Skips events that have not ended.
    """
    if not event_has_ended(event):
        return 0

    customer_ids = (
        OrderPosition.objects.filter(
            order__event=event,
            order__status=Order.STATUS_PAID,
            order__customer_id__isnull=False,
            item__admission=True,
        )
        .values_list("order__customer_id", flat=True)
        .distinct()
    )

    created = 0
    for customer_id in customer_ids:
        _, was_created = CustomerAllowlistEntry.objects.get_or_create(
            organizer_id=event.organizer_id,
            customer_id=customer_id,
        )
        if was_created:
            created += 1
    return created


def iter_sync_events(*, organizer=None, event: Event | None = None):
    """Yield ended plugin events that should be scanned for attendance."""
    if event is not None:
        qs = Event.objects.filter(pk=event.pk)
    elif organizer is not None:
        qs = Event.objects.filter(organizer=organizer)
    else:
        qs = Event.objects.filter(
            Q(plugins=PLUGIN_MODULE)
            | Q(plugins__startswith=PLUGIN_MODULE + ",")
            | Q(plugins__endswith="," + PLUGIN_MODULE)
            | Q(plugins__contains="," + PLUGIN_MODULE + ",")
        )

    qs = qs.select_related("organizer")
    for ev in qs.iterator():
        if not event_uses_plugin(ev):
            continue
        if not event_has_ended(ev):
            continue
        yield ev


def sync_allowlists(*, organizer=None, event: Event | None = None) -> int:
    """
    Sync allowlist rows for matching ended events.

    Returns total newly created allowlist entries across all events processed.
    """
    total = 0
    for ev in iter_sync_events(organizer=organizer, event=event):
        created = sync_event_allowlist(ev)
        if created:
            logger.info(
                "Allowlist sync: created %s entries for event %s/%s",
                created,
                ev.organizer.slug,
                ev.slug,
            )
        total += created
    return total
