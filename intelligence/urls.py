from django.urls import path
from .views import process_emails_view

urlpatterns = [
    path("process/", process_emails_view, name="process_emails"),
]
