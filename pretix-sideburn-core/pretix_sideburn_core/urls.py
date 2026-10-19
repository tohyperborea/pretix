from django.urls import re_path

from .views import DeleteSelectedEntriesView

urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/sideburn-core/waitinglist/delete-selected/$",
        DeleteSelectedEntriesView.as_view(),
        name="delete_selected_entries",
    ),
]
