"""
URL configuration for the Sideburn lottery plugin.
"""
from django.urls import re_path

from .views.control import (
    DeleteSelectedEntriesView, RevertLotteryView, RunLotteryView,
)

urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/sideburn-lottery/run/$",
        RunLotteryView.as_view(),
        name="run",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/sideburn-lottery/revert/$",
        RevertLotteryView.as_view(),
        name="revert",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/sideburn-lottery/delete-selected/$",
        DeleteSelectedEntriesView.as_view(),
        name="delete_selected_entries",
    ),
]
