"""
Per-product flag: holding this ticket counts as attendance for auto-allowlist.

Stored on the event as ``sideburn_allowlist_item_<item_id>`` (same pattern as
lottery's per-item flags). Product edit UI can call these helpers later.
"""


def item_counts_for_allowlist(event, item_id) -> bool:
    return bool(
        event.settings.get(
            f"sideburn_allowlist_item_{item_id}", as_type=bool, default=False
        )
    )


def set_item_counts_for_allowlist(event, item_id, counts: bool) -> None:
    key = f"sideburn_allowlist_item_{item_id}"
    if counts:
        event.settings.set(key, True)
    else:
        event.settings.delete(key)


def get_allowlist_item_ids(event) -> set[int]:
    """Item PKs on this event that are configured to count toward allowlist."""
    return {
        item.pk
        for item in event.items.all()
        if item_counts_for_allowlist(event, item.pk)
    }
