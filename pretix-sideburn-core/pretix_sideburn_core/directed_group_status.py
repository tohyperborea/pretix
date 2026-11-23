"""
Derived display status for directed-group slots (leader/admin UI).
"""
from __future__ import annotations

from typing import Literal

from pretix.base.models import OrderPosition

from .models import DirectedGroupSlot

SlotDisplayStatus = Literal[
    "empty",
    "no_account",
    "already_ticketed",
    "denied",
    "approval_pending",
    "ticket_purchased",
    "ticket_canceled",
    "voucher_expired",
    "voucher_sent",
]


def get_slot_display_status(slot: DirectedGroupSlot) -> SlotDisplayStatus:
    """
    Derived leader/admin-facing status for a directed-group slot.

    Workflow decisions (no_account / already_ticketed / rejected / pending) win over
    voucher/order state. After a voucher is sent, decision is cleared and status comes
    from the voucher and its order positions.
    """
    if slot.decision == DirectedGroupSlot.DECISION_NO_ACCOUNT:
        return "no_account"
    if slot.decision == DirectedGroupSlot.DECISION_ALREADY_TICKETED:
        return "already_ticketed"
    if slot.decision == DirectedGroupSlot.DECISION_REJECTED:
        return "denied"
    if slot.decision == DirectedGroupSlot.DECISION_PENDING:
        return "approval_pending"

    voucher = slot.voucher
    if voucher is None:
        return "empty"

    if OrderPosition.objects.filter(voucher=voucher).exists():
        return "ticket_purchased"
    if (
        OrderPosition.all.filter(voucher=voucher, canceled=True).exists()
        and not voucher.is_fully_redeemed()
    ):
        return "ticket_canceled"
    if voucher.is_expired() and not voucher.is_fully_redeemed():
        return "voucher_expired"
    return "voucher_sent"
