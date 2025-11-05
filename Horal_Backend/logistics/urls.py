# logistics/urls.py
from django.urls import path
from .views import (
    fez_webhook, TrackOrderShipmentsView, SingleShipmentView,
    TrackSingleShipmentView, SearchShipmentView, 
)

urlpatterns = [
    path("track/<str:fez_order_id>/", TrackSingleShipmentView.as_view(), name="track-single-fez-shipment"),
    path("track/order/<str:order_id>/", TrackOrderShipmentsView.as_view(), name="track-all-order-shipment"),
    path("shipment/<str:fez_order_id>/details/", SingleShipmentView.as_view(), name="get-details-for-single-shipment"),
    path("search/<str:waybill_number>/", SearchShipmentView.as_view(), name="search-single-shipment-with-waybill-number"),
    path('fez/webhook/', fez_webhook, name='fez-webhook'),
]
