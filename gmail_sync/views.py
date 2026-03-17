from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

from .services import fetch_recent_emails
from accounts.models import GmailToken


@login_required
def fetch_emails_view(request):

    # -----------------------------------------
    # Check Gmail Connected
    # -----------------------------------------
    try:
        token = GmailToken.objects.get(user=request.user)

    except GmailToken.DoesNotExist:
        return HttpResponse(
            "Gmail not connected. Please reconnect Gmail."
        )

    # -----------------------------------------
    # If token already inactive → reconnect
    # -----------------------------------------
    if not getattr(token, "is_active", True):

        return HttpResponse(
            "Gmail access expired or revoked. "
            "Please reconnect Gmail."
        )

    # -----------------------------------------
    # SAFE FETCH
    # -----------------------------------------
    fetch_recent_emails(
        request.user,
        max_results=40
    )

    # -----------------------------------------
    # Check again after fetch
    # (service may disable token)
    # -----------------------------------------
    token.refresh_from_db()

    if not getattr(token, "is_active", True):

        return HttpResponse(
            "Gmail connection expired during sync. "
            "Reconnect Gmail."
        )

    return HttpResponse(
        "Emails fetched successfully!"
    )

import base64
import json

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User

from gmail_sync.services import fetch_recent_emails
from intelligence.processor import process_unprocessed_emails


# ============================================
# GMAIL PUBSUB WEBHOOK
# ============================================

@csrf_exempt
def gmail_webhook(request):

    if request.method != "POST":
        return HttpResponse("OK")

    try:

        body = json.loads(request.body.decode("utf-8"))

        message = body.get("message")

        if not message:
            return HttpResponse("No Message")

        data = message.get("data")

        if data:

            decoded = base64.b64decode(data).decode("utf-8")

            notification = json.loads(decoded)

            email_address = notification.get("emailAddress")

            # Find connected user
            user = User.objects.filter(
                email=email_address
            ).first()

            if user:

                # Fetch latest mails
                fetch_recent_emails(user, max_results=40)

                # Process intelligence
                process_unprocessed_emails(user)

    except Exception as e:

        print("Webhook Error:", e)

    return HttpResponse("OK")