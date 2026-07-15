"""
assistant/urls.py
URL patterns for the FAQ assistant app.
"""

from django.urls import path
from . import views

app_name = "assistant"

urlpatterns = [
    # Twilio WhatsApp webhook
    path("webhook/whatsapp/", views.whatsapp_webhook, name="whatsapp_webhook"),

    # Health-check / status endpoint
    path("health/", views.health_check, name="health_check"),

    # Direct API endpoint for text queries (optional — useful for testing)
    path("api/query/", views.api_query, name="api_query"),
]
