import csv
import io
import random

from django.http import HttpResponse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from ..models import LotteryGroupMembership
from .groups import groups_allowed


def lottery_results_filename(event_slug, *, revert=False):
    if revert:
        return "{}_lottery_results_REVERTED".format(event_slug)
    return "{}_lottery_results".format(event_slug)


def _lottery_units(entries, groups_by_entry):
    """
    Split entries into lottery units: one per solo entry, one per group.

    A group draws as a single unit so its members end up next to each other in line.
    Members are shuffled within their unit so join order doesn't decide who goes first.
    """
    units = []
    group_units = {}
    for w in entries:
        group = groups_by_entry.get(w.pk)
        if group is None:
            units.append([w])
        elif group.pk in group_units:
            group_units[group.pk].append(w)
        else:
            group_units[group.pk] = [w]
            units.append(group_units[group.pk])
    for unit in units:
        random.shuffle(unit)
    return units


def run_lottery(event, queryset, item_id, *, revert=False):
    """
    Run or revert the waiting-list lottery for a product.

    Shuffles solo entries and whole groups (run) or restores signup order (revert), updates
    lottery_date_for_item_{item_id} on the event, and returns a CSV download.

    Returns None if there are no matching waiting-list entries.
    """
    qs = list(queryset.filter(item_id=item_id))
    if not qs:
        return None

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC, delimiter=",")

    groups_by_entry = {}
    if groups_allowed(event, item_id):
        groups_by_entry = {
            m.entry_id: m.group
            for m in LotteryGroupMembership.objects.filter(
                entry_id__in=[w.pk for w in qs]
            ).select_related("group")
        }

    qs = sorted(qs, key=lambda o: o.created)
    if revert:
        ordered = qs
    else:
        units = _lottery_units(qs, groups_by_entry)
        random.shuffle(units)
        ordered = [w for unit in units for w in unit]

    for w, priority in zip(ordered, range(len(ordered), 0, -1)):
        w.old_priority = w.priority
        w.priority = priority
        w.save(update_fields=["priority"])

    qs = sorted(qs, key=lambda o: o.priority, reverse=True)

    if not revert:
        event.settings.set(f"lottery_date_for_item_{item_id}", now().isoformat())
    else:
        event.settings.delete(f"lottery_date_for_item_{item_id}")

    headers = [
        _("Name"),
        _("E-mail address"),
        _("Phone number"),
        _("Product"),
        _("On list since"),
        _("Status"),
        _("Voucher code"),
        _("Language"),
        _("Priority"),
        "OldPriority",
        "GroupCode",
    ]
    writer.writerow(headers)

    for w in qs:
        if w.item:
            if w.variation:
                prod = "%s – %s" % (str(w.item), str(w.variation))
            else:
                prod = "%s" % str(w.item)
        if w.voucher:
            if w.voucher.redeemed >= w.voucher.max_usages:
                status = _("Voucher redeemed")
            elif not w.voucher.is_active():
                status = _("Voucher expired")
            else:
                status = _("Voucher assigned")
        else:
            status = _("Waiting")

        row = [
            w.name,
            w.email,
            w.phone,
            prod,
            w.created.isoformat(),
            status,
            w.voucher.code if w.voucher else "",
            w.locale,
            str(w.priority),
            str(w.old_priority),
            groups_by_entry[w.pk].code if w.pk in groups_by_entry else "",
        ]
        if event.has_subevents:
            row.append(str(w.subevent))
        writer.writerow(row)

    response = HttpResponse(output.getvalue().encode("utf-8"), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="{}.csv"'.format(
        lottery_results_filename(event.slug, revert=revert)
    )
    return response
