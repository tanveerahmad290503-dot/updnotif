from django.urls import path
from .views import fetch_emails_view
from gmail_sync.webhooks import gmail_push_webhook

urlpatterns = [
    path("fetch/", fetch_emails_view, name="fetch_emails"),
    path("webhook/", gmail_push_webhook, name="gmail_webhook"),
]
