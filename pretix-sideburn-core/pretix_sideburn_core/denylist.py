from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, ListView, UpdateView
from django_scopes.forms import SafeModelChoiceField

from pretix.base.models import Customer
from pretix.control.forms.filter import FilterForm
from pretix.control.forms.widgets import Select2
from pretix.control.permissions import (
    OrganizerPermissionRequiredMixin, organizer_permission_required,
)
from pretix.control.views import PaginationMixin
from pretix.control.views.organizer import OrganizerDetailViewMixin
from pretix.helpers.compat import CompatDeleteView

from .models import CustomerDenylistEntry


def customer_select_label(customer):
    """Admin-facing label: ``Name (email)``, with sensible fallbacks."""
    name = (customer.name or "").strip()
    email = (customer.email or "").strip()
    if name and email:
        return f"{name} ({email})"
    return name or email or f"#{customer.identifier}"


@organizer_permission_required("organizer.customers:write")
def denylist_customer_select2(request, **kwargs):
    query = request.GET.get("query", "")
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1

    qs = request.organizer.customers.filter(
        Q(email__icontains=query)
        | Q(name_cached__icontains=query)
        | Q(identifier__istartswith=query)
    ).order_by("name_cached")

    total = qs.count()
    pagesize = 20
    offset = (page - 1) * pagesize
    return JsonResponse({
        "results": [
            {"id": c.pk, "text": customer_select_label(c)}
            for c in qs[offset:offset + pagesize]
        ],
        "pagination": {"more": total >= (offset + pagesize)},
    })


class DenylistFilterForm(FilterForm):
    query = forms.CharField(
        label=_("Search query"),
        widget=forms.TextInput(attrs={"placeholder": _("Search query")}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def filter_qs(self, qs):
        query = self.cleaned_data.get("query")
        if query:
            qs = qs.filter(
                Q(customer__email__icontains=query)
                | Q(customer__name_cached__icontains=query)
                | Q(customer__identifier__istartswith=query)
                | Q(notes__icontains=query)
            )
        return qs.order_by("-created", "pk")


class DenylistCustomerChoiceField(SafeModelChoiceField):
    def label_from_instance(self, obj):
        return customer_select_label(obj)


class DenylistAddForm(forms.ModelForm):
    customer = DenylistCustomerChoiceField(
        queryset=Customer.objects.none(),
        label=_("Customer"),
    )

    class Meta:
        model = CustomerDenylistEntry
        fields = ["customer", "notes"]

    def __init__(self, *args, organizer=None, **kwargs):
        self.organizer = organizer
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = self.organizer.customers.all()
        self.fields["customer"].widget = Select2(
            attrs={
                "data-model-select2": "generic",
                "data-select2-url": reverse(
                    "plugins:pretix_sideburn_core:denylist.customers.select2",
                    kwargs={"organizer": self.organizer.slug},
                ),
            }
        )
        self.fields["customer"].widget.choices = self.fields["customer"].choices
        self.fields["notes"].required = False

    def clean_customer(self):
        customer = self.cleaned_data["customer"]
        if customer.organizer_id != self.organizer.pk:
            raise forms.ValidationError(_("Invalid customer."))
        if CustomerDenylistEntry.objects.filter(
            organizer=self.organizer, customer=customer
        ).exists():
            raise forms.ValidationError(_("This customer is already on the denylist."))
        return customer


class DenylistNotesForm(forms.ModelForm):
    class Meta:
        model = CustomerDenylistEntry
        fields = ["notes"]


class DenylistListView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, PaginationMixin, ListView
):
    model = CustomerDenylistEntry
    template_name = "pretix_sideburn_core/denylist_list.html"
    permission = "organizer.customers:read"
    context_object_name = "entries"

    def get_queryset(self):
        qs = CustomerDenylistEntry.objects.filter(
            organizer=self.request.organizer
        ).select_related("customer", "created_by")
        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)
        else:
            qs = qs.order_by("-created", "pk")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = self.filter_form
        return ctx

    @cached_property
    def filter_form(self):
        return DenylistFilterForm(data=self.request.GET, request=self.request)


class DenylistAddView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView
):
    model = CustomerDenylistEntry
    form_class = DenylistAddForm
    template_name = "pretix_sideburn_core/denylist_add.html"
    permission = "organizer.customers:write"
    context_object_name = "entry"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organizer"] = self.request.organizer
        return kwargs

    def get_success_url(self):
        return reverse(
            "plugins:pretix_sideburn_core:denylist",
            kwargs={"organizer": self.request.organizer.slug},
        )

    @transaction.atomic
    def form_valid(self, form):
        form.instance.organizer = self.request.organizer
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        customer = form.instance.customer
        data = {
            "customer": customer.pk,
            "customer_identifier": customer.identifier,
            "customer_email": customer.email,
            "notes": form.instance.notes,
            "entry": form.instance.pk,
        }
        self.request.organizer.log_action(
            "pretix_sideburn_core.denylist.added",
            user=self.request.user,
            data=data,
        )
        customer.log_action(
            "pretix_sideburn_core.denylist.added",
            user=self.request.user,
            data=data,
        )
        messages.success(self.request, _("The customer has been added to the denylist."))
        return response


class DenylistUpdateView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView
):
    model = CustomerDenylistEntry
    form_class = DenylistNotesForm
    template_name = "pretix_sideburn_core/denylist_edit.html"
    permission = "organizer.customers:write"
    context_object_name = "entry"

    def get_object(self, queryset=None):
        return get_object_or_404(
            CustomerDenylistEntry.objects.filter(
                organizer=self.request.organizer
            ).select_related("customer"),
            pk=self.kwargs.get("pk"),
        )

    def get_success_url(self):
        return reverse(
            "plugins:pretix_sideburn_core:denylist",
            kwargs={"organizer": self.request.organizer.slug},
        )

    @transaction.atomic
    def form_valid(self, form):
        if form.has_changed():
            data = {
                "customer": self.object.customer_id,
                "customer_identifier": self.object.customer.identifier,
                "customer_email": self.object.customer.email,
                "notes": form.cleaned_data.get("notes", ""),
                "entry": self.object.pk,
            }
            self.request.organizer.log_action(
                "pretix_sideburn_core.denylist.changed",
                user=self.request.user,
                data=data,
            )
            self.object.customer.log_action(
                "pretix_sideburn_core.denylist.changed",
                user=self.request.user,
                data=data,
            )
        messages.success(self.request, _("Your changes have been saved."))
        return super().form_valid(form)


class DenylistDeleteView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CompatDeleteView
):
    model = CustomerDenylistEntry
    template_name = "pretix_sideburn_core/denylist_delete.html"
    permission = "organizer.customers:write"
    context_object_name = "entry"

    def get_object(self, queryset=None):
        return get_object_or_404(
            CustomerDenylistEntry.objects.filter(
                organizer=self.request.organizer
            ).select_related("customer"),
            pk=self.kwargs.get("pk"),
        )

    def get_success_url(self):
        return reverse(
            "plugins:pretix_sideburn_core:denylist",
            kwargs={"organizer": self.request.organizer.slug},
        )

    @transaction.atomic
    def form_valid(self, form):
        customer = self.object.customer
        data = {
            "customer": customer.pk,
            "customer_identifier": customer.identifier,
            "customer_email": customer.email,
            "notes": self.object.notes,
            "entry": self.object.pk,
        }
        self.request.organizer.log_action(
            "pretix_sideburn_core.denylist.removed",
            user=self.request.user,
            data=data,
        )
        customer.log_action(
            "pretix_sideburn_core.denylist.removed",
            user=self.request.user,
            data=data,
        )
        messages.success(self.request, _("The customer has been removed from the denylist."))
        return super().form_valid(form)
