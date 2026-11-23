from django.urls import re_path

from .allowlist import AllowlistAddView, AllowlistListView
from .denylist import (
    DenylistAddView, DenylistDeleteView, DenylistListView, DenylistUpdateView,
    denylist_customer_select2,
)
from .views import DeleteSelectedEntriesView

urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/sideburn-core/waitinglist/delete-selected/$",
        DeleteSelectedEntriesView.as_view(),
        name="delete_selected_entries",
    ),
    re_path(
        r"^control/organizer/(?P<organizer>[^/]+)/sideburn-core/allowlist/$",
        AllowlistListView.as_view(),
        name="allowlist",
    ),
    re_path(
        r"^control/organizer/(?P<organizer>[^/]+)/sideburn-core/allowlist/add/$",
        AllowlistAddView.as_view(),
        name="allowlist.add",
    ),
    re_path(
        r"^control/organizer/(?P<organizer>[^/]+)/sideburn-core/allowlist/customers/select2/$",
        denylist_customer_select2,
        name="allowlist.customers.select2",
    ),
    re_path(
        r"^control/organizer/(?P<organizer>[^/]+)/sideburn-core/denylist/$",
        DenylistListView.as_view(),
        name="denylist",
    ),
    re_path(
        r"^control/organizer/(?P<organizer>[^/]+)/sideburn-core/denylist/add/$",
        DenylistAddView.as_view(),
        name="denylist.add",
    ),
    re_path(
        r"^control/organizer/(?P<organizer>[^/]+)/sideburn-core/denylist/customers/select2/$",
        denylist_customer_select2,
        name="denylist.customers.select2",
    ),
    re_path(
        r"^control/organizer/(?P<organizer>[^/]+)/sideburn-core/denylist/(?P<pk>\d+)/edit/$",
        DenylistUpdateView.as_view(),
        name="denylist.edit",
    ),
    re_path(
        r"^control/organizer/(?P<organizer>[^/]+)/sideburn-core/denylist/(?P<pk>\d+)/delete/$",
        DenylistDeleteView.as_view(),
        name="denylist.delete",
    ),
]
