from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("thread/<uuid:thread_id>/", views.thread_detail, name="thread_detail"),
    path("followup/dismiss/<uuid:thread_id>/",views.dismiss_followup,name="dismiss_followup"),

]