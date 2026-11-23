from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, ListView
from django_scopes.forms import SafeModelChoiceField

from pretix.base.models import Customer
from pretix.control.forms.filter import FilterForm
from pretix.control.forms.widgets import Select2
from pretix.control.permissions import OrganizerPermissionRequiredMixin
from pretix.control.views import PaginationMixin
from pretix.control.views.organizer import OrganizerDetailViewMixin

from .denylist import customer_select_label
from .models import CustomerAllowlistEntry


class AllowlistFilterForm(FilterForm):
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
            )
        return qs.order_by("-created", "pk")


class AllowlistCustomerChoiceField(SafeModelChoiceField):
    def label_from_instance(self, obj):
        return customer_select_label(obj)


class AllowlistAddForm(forms.ModelForm):
    customer = AllowlistCustomerChoiceField(
        queryset=Customer.objects.none(),
        label=_("Customer"),
    )

    class Meta:
        model = CustomerAllowlistEntry
        fields = ["customer"]

    def __init__(self, *args, organizer=None, **kwargs):
        self.organizer = organizer
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = self.organizer.customers.all()
        self.fields["customer"].widget = Select2(
            attrs={
                "data-model-select2": "generic",
                "data-select2-url": reverse(
                    "plugins:pretix_sideburn_core:allowlist.customers.select2",
                    kwargs={"organizer": self.organizer.slug},
                ),
            }
        )
        self.fields["customer"].widget.choices = self.fields["customer"].choices

    def clean_customer(self):
        customer = self.cleaned_data["customer"]
        if customer.organizer_id != self.organizer.pk:
            raise forms.ValidationError(_("Invalid customer."))
        if CustomerAllowlistEntry.objects.filter(
            organizer=self.organizer, customer=customer
        ).exists():
            raise forms.ValidationError(_("This customer is already on the allowlist."))
        return customer


class AllowlistListView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, PaginationMixin, ListView
):
    model = CustomerAllowlistEntry
    template_name = "pretix_sideburn_core/allowlist_list.html"
    permission = "organizer.customers:read"
    context_object_name = "entries"

    def get_queryset(self):
        qs = CustomerAllowlistEntry.objects.filter(
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
        return AllowlistFilterForm(data=self.request.GET, request=self.request)


class AllowlistAddView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, CreateView
):
    model = CustomerAllowlistEntry
    form_class = AllowlistAddForm
    template_name = "pretix_sideburn_core/allowlist_add.html"
    permission = "organizer.customers:write"
    context_object_name = "entry"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organizer"] = self.request.organizer
        return kwargs

    def get_success_url(self):
        return reverse(
            "plugins:pretix_sideburn_core:allowlist",
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
            "entry": form.instance.pk,
        }
        self.request.organizer.log_action(
            "pretix_sideburn_core.allowlist.added",
            user=self.request.user,
            data=data,
        )
        customer.log_action(
            "pretix_sideburn_core.allowlist.added",
            user=self.request.user,
            data=data,
        )
        messages.success(self.request, _("The customer has been added to the allowlist."))
        return response
