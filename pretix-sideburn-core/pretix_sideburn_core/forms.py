from django import forms
from django.utils.translation import gettext_lazy as _

from pretix.control.forms import SplitDateTimeField, SplitDateTimePickerWidget

from .dgm import (
    dgm_enabled, dgm_leader_deadline, set_dgm_enabled, set_dgm_leader_deadline,
)


class ItemDirectedGroupsForm(forms.Form):
    """Per-product DGM enable + leader deadline, shown on the product edit page."""

    title = _("Directed groups")

    enabled = forms.BooleanField(
        label=_("Enable DGM for this ticket"),
        required=False,
        help_text=_(
            "When enabled, admins can create directed groups for this product and "
            "leaders can assign slots to customers."
        ),
    )
    leader_deadline = SplitDateTimeField(
        label=_("DGM leader deadline"),
        required=False,
        help_text=_(
            "After this date and time, group leaders can no longer change slot "
            "assignments for this product. Admins keep full control. Leave empty "
            "for no deadline."
        ),
        widget=SplitDateTimePickerWidget(),
    )

    def __init__(self, *args, event, item, **kwargs):
        self.event = event
        self.item = item
        super().__init__(*args, **kwargs)
        self.fields["enabled"].initial = dgm_enabled(event, item.pk)
        self.fields["leader_deadline"].initial = dgm_leader_deadline(event, item.pk)

    def save(self):
        set_dgm_enabled(self.event, self.item.pk, self.cleaned_data["enabled"])
        set_dgm_leader_deadline(
            self.event, self.item.pk, self.cleaned_data.get("leader_deadline")
        )


class ReadOnlyEmailMixin:
    """
    Locks the waiting-list email to the logged-in customer's address. The view pre-fills it from
    the customer, and Django ignores submitted values for disabled fields.

    Mixed into whatever form class the ``waitinglist_form_class`` chain provides; see
    ``waitinglist_form_with_readonly_email``.
    """

    def __init__(self, *args, **kwargs):
        customer = getattr(kwargs.get("request"), "customer", None)
        super().__init__(*args, **kwargs)
        if customer:
            self.fields["email"].disabled = True


def waitinglist_form_with_readonly_email(cls):
    return type("WaitingListFormWithReadOnlyEmail", (ReadOnlyEmailMixin, cls), {})
