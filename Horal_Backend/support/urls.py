from django.urls import path
from .views import (
    SupportMessageListCreateView, SingleSupportView,
    SupportEmailWebhookView, SupportTeamUpdateView,
    SupportTeamCreateView, SupportTeamNameAPIView,
    SingleSupportTeamView, SingleSupportTicketView,
    UpdateSupportView, RetrieveAllStaffView,
    UpdateTicketView, AllTicketsListView,
    CreateSupportView,
)


urlpatterns = [
    path('', CreateSupportView.as_view(), name="create_support"),
    path('<uuid:pk>/messages/', SupportMessageListCreateView.as_view(), name="create_list_support_message"),
    path('webhook/', SupportEmailWebhookView.as_view(), name="support webhook"),
    path("team/add/", SupportTeamCreateView.as_view(), name="create-support-team"),
    path("team/<uuid:team_id>/update/", SupportTeamUpdateView.as_view(), name="update-support-team"),
    path("team/", SupportTeamNameAPIView.as_view(), name="support-team"),
    path("team/<uuid:team_id>/", SingleSupportTeamView.as_view(), name="single-support-team"),
    path("ticket/<uuid:ticket_id>/", SingleSupportTicketView.as_view(), name="single-support-ticket"),
    path("<uuid:support_id>/", SingleSupportView.as_view(), name="retrieve-support"),
    path("<uuid:support_id>/update/", UpdateSupportView.as_view(), name="update-support"),
    path("staff/", RetrieveAllStaffView.as_view(), name="retrieve-all-staff"),
    path("tickets/<uuid:ticket_id>/update/", UpdateTicketView.as_view(), name="update-ticket"),
    path("tickets/", AllTicketsListView.as_view(), name="all-tickets"),

]