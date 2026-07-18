from django.urls import re_path
from .consumers import VendorNotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/vendor/notifications/$', VendorNotificationConsumer.as_asgi()),
]

