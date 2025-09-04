# logistics/urls.py
from django.urls import path
from .views import (
    TrackShipmentView, gigl_webhook
)

urlpatterns = [
    path("track/<str:waybill>/", TrackShipmentView.as_view(), name="gig-track-shipment"),
    path('gigl/webhook/', gigl_webhook, name='gigl-webhook'),
]
