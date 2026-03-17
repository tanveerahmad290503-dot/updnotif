import os
from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from google_auth_oauthlib.flow import Flow

from .models import GmailToken


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


# ==========================================
# USER SIGNUP
# ==========================================

def signup(request):

    if request.method == "POST":

        name = request.POST.get("name")
        username = request.POST.get("username")
        password = request.POST.get("password")

        if User.objects.filter(
            username=username
        ).exists():

            messages.error(
                request,
                "Username already exists."
            )

            return redirect("signup")

        user = User.objects.create_user(
            username=username,
            password=password,
        )

        user.first_name = name
        user.save()

        login(request, user)

        return redirect("/")

    return render(request, "signup.html")


# ==========================================
# USER LOGIN
# ==========================================

def user_login(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user:

            login(request, user)

            return redirect("/")

        messages.error(
            request,
            "Invalid credentials."
        )

    return render(request, "login.html")


# ==========================================
# USER LOGOUT
# ==========================================

def user_logout(request):

    logout(request)

    return redirect("/auth/login/")


# ==========================================
# GOOGLE OAUTH LOGIN
# ==========================================

@login_required
def google_login(request):

    flow = Flow.from_client_config(

        {
            "web": {

                "client_id":
                settings.GOOGLE_CLIENT_ID,

                "client_secret":
                settings.GOOGLE_CLIENT_SECRET,

                "auth_uri":
                "https://accounts.google.com/o/oauth2/auth",

                "token_uri":
                "https://oauth2.googleapis.com/token",

            }
        },

        scopes=SCOPES,

        redirect_uri=
        settings.GOOGLE_REDIRECT_URI,

    )

    authorization_url, state = flow.authorization_url(

        access_type="offline",

        prompt="consent",

    )

    request.session["oauth_state"] = state

    return redirect(authorization_url)


# ==========================================
# GOOGLE CALLBACK
# ==========================================

@login_required
def google_callback(request):

    state = request.session.get(
        "oauth_state"
    )

    flow = Flow.from_client_config(

        {
            "web": {

                "client_id":
                settings.GOOGLE_CLIENT_ID,

                "client_secret":
                settings.GOOGLE_CLIENT_SECRET,

                "auth_uri":
                "https://accounts.google.com/o/oauth2/auth",

                "token_uri":
                "https://oauth2.googleapis.com/token",

            }
        },

        scopes=SCOPES,

        state=state,

        redirect_uri=
        settings.GOOGLE_REDIRECT_URI,

    )

    flow.fetch_token(

        authorization_response=
        request.build_absolute_uri()

    )

    credentials = flow.credentials

    # -------------------------------------
    # SAVE OR UPDATE TOKEN
    # -------------------------------------

    GmailToken.objects.update_or_create(

        user=request.user,

        defaults={

            "access_token":
            credentials.token,

            "refresh_token":
            credentials.refresh_token,

            "client_id":
            settings.GOOGLE_CLIENT_ID,

            "client_secret":
            settings.GOOGLE_CLIENT_SECRET,

            "scopes":
            credentials.scopes,

            "expires_at":
            credentials.expiry,

            # 🔥 auto reconnect support
            "is_active": True,
            "last_error": "",

        },

    )

    # =====================================
    # 🔥 START REALTIME GMAIL WATCH
    # =====================================

    try:

        # GOD LEVEL:
        # initializes watch + saves historyId

        from gmail_sync.services import (
            initialize_gmail_watch
        )

        initialize_gmail_watch(
            request.user
        )

        print(
            "✅ Gmail realtime watch started."
        )

    except Exception as e:

        # Never break login

        print(
            "⚠ Gmail watch failed:",
            e
        )

    # =====================================
    # 🔥 AUTO FETCH + PROCESS AFTER CONNECT
    # =====================================

    try:

        from gmail_sync.services import (
            fetch_recent_emails
        )

        from intelligence.processor import (
            process_unprocessed_emails
        )

        fetch_recent_emails(
            request.user,
            max_results=50
        )

        process_unprocessed_emails(
            request.user
        )

    except Exception as e:

        print(
            "⚠ Initial fetch failed:",
            e
        )

    # Redirect dashboard

    return redirect("/")