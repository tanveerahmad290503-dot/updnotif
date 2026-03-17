import base64
import json

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from accounts.models import GmailToken

from gmail_sync.services import fetch_incremental_emails

from intelligence.processor import process_unprocessed_emails
from dashboard.services.realtime_dashboard import push_dashboard_update


# ==========================================================
# GMAIL PUSH WEBHOOK
# ==========================================================

@csrf_exempt
def gmail_push_webhook(request):

    if request.method != "POST":
        return HttpResponse("OK")

    try:

        body = json.loads(
            request.body.decode("utf-8")
        )

        message = body.get("message", {})

        data = message.get("data")

        if not data:
            return HttpResponse("No Data")

        decoded = base64.b64decode(
            data
        ).decode("utf-8")

        payload = json.loads(decoded)

        print(
            "Gmail Push Payload:",
            payload
        )

        email_address = payload.get(
            "emailAddress"
        )

        # ---------------------------------------
        # FIND USER TOKEN
        # ---------------------------------------

        tokens = GmailToken.objects.filter(

            user__email=email_address,

            is_active=True

        ).select_related("user")

        if not tokens.exists():

            print(
                "No active Gmail token found."
            )

            return HttpResponse("OK")

        # ---------------------------------------
        # FETCH USING STORED HISTORY ID
        # ---------------------------------------

        for token in tokens:

            user = token.user

            try:

                # ⭐ DO NOT PASS PUSH HISTORY ID

                fetch_incremental_emails(

                    user

                )

                process_unprocessed_emails(

                    user

                )

                # Event-driven fallback push (debounced in service)
                push_dashboard_update(user)

            except Exception as user_error:

                print(

                    f"Webhook user error ({user.id}):",

                    str(user_error)

                )

                continue

        return HttpResponse("Processed")

    except Exception as e:

        print(
            "Webhook Error:",
            str(e)
        )

        return HttpResponse("OK")