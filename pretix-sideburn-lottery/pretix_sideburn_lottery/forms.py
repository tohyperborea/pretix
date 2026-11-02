from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.translation import gettext, gettext_lazy as _

from .services.groups import (
    create_group,
    ensure_group_has_room,
    ensure_groups_unlocked,
    find_group,
    join_group,
    lottery_has_run,
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
        if all(lottery_has_run(self.event, item_id) for item_id in item_ids):
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
            widget=forms.RadioSelect,
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
            widget=forms.TextInput(
                attrs={
                    "autocomplete": "off",
                    "data-display-dependency": "#id_lottery_group_action_2",
                }
            ),
        )

    def clean(self):
        data = super().clean()
        action = data.get("lottery_group_action") or GROUP_NONE
        if action == GROUP_NONE or not self.instance.item_id:
            return data

        try:
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
