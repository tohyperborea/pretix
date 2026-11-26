"""
Per-product Directed Group Management (DGM) settings helpers.
"""
from __future__ import annotations

from datetime import datetime

from django.utils.timezone import now


def _enabled_key(item_id):
    return "sideburn_dgm_enabled_item_{}".format(item_id)


def _deadline_key(item_id):
    return "sideburn_dgm_leader_lock_item_{}".format(item_id)


def dgm_enabled(event, item_id) -> bool:
    return event.settings.get(_enabled_key(item_id), as_type=bool, default=False)


def set_dgm_enabled(event, item_id, enabled: bool) -> None:
    if enabled:
        event.settings.set(_enabled_key(item_id), True)
    else:
        event.settings.delete(_enabled_key(item_id))


def dgm_leader_deadline(event, item_id) -> datetime | None:
    return event.settings.get(_deadline_key(item_id), as_type=datetime, default=None)


def set_dgm_leader_deadline(event, item_id, deadline: datetime | None) -> None:
    if deadline is not None:
        event.settings.set(_deadline_key(item_id), deadline.isoformat())
    else:
        event.settings.delete(_deadline_key(item_id))


def dgm_leader_editing_closed(event, item_id) -> bool:
    """
    True when leaders must not mutate slots for this product (DGM disabled or
    past the per-product leader deadline). Admins are unaffected.
    """
    if not dgm_enabled(event, item_id):
        return True
    deadline = dgm_leader_deadline(event, item_id)
    if deadline is None:
        return False
    return now() >= deadline
