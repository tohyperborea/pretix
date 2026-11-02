from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.translation import gettext, gettext_lazy as _

from .services.groups import (
    create_group,
    ensure_group_has_room,
    ensure_groups_allowed,
    ensure_groups_unlocked,
    find_group,
    groups_allowed,
    join_group,
    lottery_has_run,
    set_groups_allowed,
)

GROUP_NONE = "none"
GROUP_CREATE = "create"
GROUP_JOIN = "join"


class WaitingListGroupMixin:
    """
    Adds optional "create a group" / "join a group" fields to the waiting list form, and puts the
    new entry in that group on save.

    Mixed into whatever form class the ``waitinglist_form_class`` chain provides; see
    ``waitinglist_form_with_group``.
    """

    def __init__(self, *args, **kwargs):
        self._group_request = kwargs.get("request")
        itemvars = kwargs.get("itemvars") or []
        super().__init__(*args, **kwargs)

        item_ids = {value.split("-")[0] for _category, choices in itemvars for value, _label in choices}
        group_item_ids = sorted(
            item_id
            for item_id in item_ids
            if groups_allowed(self.event, item_id) and not lottery_has_run(self.event, item_id)
        )
        if not group_item_ids:
            return

        self.fields["lottery_group_action"] = forms.ChoiceField(
            label=_("Lottery group"),
            choices=[
                (GROUP_NONE, _("Register on my own")),
                (GROUP_CREATE, _("Create a new group")),
                (GROUP_JOIN, _("Join an existing group")),
            ],
            initial=GROUP_NONE,
            required=False,
            widget=forms.RadioSelect(attrs={"data-lottery-group-items": ",".join(group_item_ids)}),
            help_text=gettext(
                "Optional. Joining a group doesn't change your odds in the lottery: your group is one entry, "
                "same as someone registering on their own. When tickets are offered, your group needs one "
                "ticket per person and moves together. Groups can have up to %(max)s people."
            ) % {"max": self.event.settings.lottery_group_max_size},
        )
        self.fields["lottery_group_code"] = forms.CharField(
            label=_("Group code"),
            required=False,
            max_length=32,
            help_text=_("Ask the person who created the group for its code."),
            widget=forms.TextInput(attrs={"autocomplete": "off"}),
        )

    def clean(self):
        data = super().clean()
        action = data.get("lottery_group_action") or GROUP_NONE
        if action == GROUP_NONE or not self.instance.item_id:
            return data

        try:
            ensure_groups_allowed(self.event, self.instance.item_id)
            ensure_groups_unlocked(self.event, self.instance.item_id)
        except ValidationError as e:
            self.add_error("lottery_group_action", e)
            return data

        if action == GROUP_JOIN:
            if not data.get("lottery_group_code"):
                self.add_error("lottery_group_code", _("Enter the code of the group you want to join."))
                return data
            try:
                ensure_group_has_room(find_group(self.event, self.instance.item_id, data["lottery_group_code"]))
            except ValidationError as e:
                self.add_error("lottery_group_code", e)
        return data

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if not commit:
            return instance

        action = self.cleaned_data.get("lottery_group_action") or GROUP_NONE
        try:
            if action == GROUP_CREATE:
                group = create_group(instance)
                self._group_message(
                    messages.SUCCESS,
                    gettext(
                        "Your group code is %(code)s. Share it with your friends so they can join your group."
                    ) % {"code": group.code},
                )
            elif action == GROUP_JOIN:
                group = join_group(instance, self.cleaned_data["lottery_group_code"])
                self._group_message(
                    messages.SUCCESS, gettext("You've joined group %(code)s.") % {"code": group.code}
                )
        except ValidationError as e:
            self._group_message(
                messages.WARNING,
                gettext("You're on the waiting list, but we couldn't add you to the group: %(reason)s")
                % {"reason": " ".join(e.messages)},
            )
        return instance

    def _group_message(self, level, text):
        if self._group_request is not None:
            messages.add_message(self._group_request, level, text)


def waitinglist_form_with_group(cls):
    return type("WaitingListFormWithGroup", (WaitingListGroupMixin, cls), {})


class ItemLotteryGroupsForm(forms.Form):
    """Per-product switch for lottery groups, shown on the product edit page."""

    title = _("Lottery")

    allow_groups = forms.BooleanField(
        label=_("Allow registrants to line up together"),
        required=False,
        help_text=_(
            "Registrants for this product can create or join a group when they sign up for the waiting "
            "list. A group enters the lottery as one entry, so its members are offered tickets together. "
            "Being in a group does not improve chances of getting a ticket."
        ),
    )

    def __init__(self, *args, event, item, **kwargs):
        self.event = event
        self.item = item
        super().__init__(*args, **kwargs)
        self.fields["allow_groups"].initial = groups_allowed(event, item.pk)

    def save(self):
        set_groups_allowed(self.event, self.item.pk, self.cleaned_data["allow_groups"])
