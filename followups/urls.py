from django.urls import path

from .views import generate_followup_view, improve_followup_view


urlpatterns = [
    path("thread/<thread_id>/generate/", generate_followup_view, name="generate_followup"),
    path("thread/<thread_id>/improve/", improve_followup_view, name="improve_followup"),
]
