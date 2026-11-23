"""
Effective customer familiarity status (deny / allow / unfamiliar).

Later purchase enforcement should call this helper rather than reading the
tables directly. Denylist supersedes allowlist; unfamiliar is derived (not stored).
"""
from __future__ import annotations

from typing import Literal

from pretix.base.models import Customer

CustomerFamiliarityStatus = Literal["deny", "allow", "unfamiliar"]


def get_customer_familiarity_status(customer: Customer) -> CustomerFamiliarityStatus:
    """
    Return the effective familiarity status for ``customer``.

    Precedence: denylist wins over allowlist. Being on both lists does not
    remove the allowlist row; effective status is still ``deny``.
    """
    if customer.sideburn_denylist_entries.exists():
        return "deny"
    if customer.sideburn_allowlist_entries.exists():
        return "allow"
    return "unfamiliar"
