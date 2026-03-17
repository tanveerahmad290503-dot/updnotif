from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),
    # path("google/login/", views.google_login, name="google_login"),
    path("gmail/connect/", views.google_login, name="gmail_connect"),
    path("google/callback/", views.google_callback, name="google_callback"),
]