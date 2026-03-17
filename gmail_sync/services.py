import base64
import re
from datetime import datetime

from django.utils import timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError

from accounts.models import GmailToken
from jobs.models import RawEmail


# ==========================================================
# BUILD GMAIL SERVICE
# ==========================================================

def get_gmail_service(user):

    try:
        token_obj = GmailToken.objects.get(
            user=user,
            is_active=True
        )

    except GmailToken.DoesNotExist:
        return None

    creds = Credentials(

        token=token_obj.access_token,
        refresh_token=token_obj.refresh_token,
        token_uri=token_obj.token_uri,
        client_id=token_obj.client_id,
        client_secret=token_obj.client_secret,
        scopes=token_obj.scopes,

    )

    try:

        return build(
            "gmail",
            "v1",
            credentials=creds
        )

    except RefreshError as e:

        token_obj.is_active = False
        token_obj.last_error = str(e)

        token_obj.save(
            update_fields=[
                "is_active",
                "last_error"
            ]
        )

        return None


# ==========================================================
# EMAIL BODY EXTRACTION
# ==========================================================

def extract_email_body(payload):

    body = ""

    if not payload:
        return body

    if payload.get("mimeType") == "text/plain":

        data = payload.get(
            "body",
            {}
        ).get("data")

        if data:

            body += base64.urlsafe_b64decode(
                data
            ).decode(
                "utf-8",
                errors="ignore"
            )

    for part in payload.get("parts", []):

        body += extract_email_body(part)

    return body


def strip_quoted_content(text):

    if not text:
        return ""

    cleaned_lines = []

    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)

    # Common "On ... wrote:" marker in replies
    cleaned = re.split(r"\nOn .+ wrote:\s*", cleaned, maxsplit=1)[0]

    return cleaned.strip()


# ==========================================================
# SAVE MESSAGE
# ==========================================================

def save_message(service, user, msg_id):

    if RawEmail.objects.filter(
        gmail_message_id=msg_id
    ).exists():
        return

    try:

        message = service.users().messages().get(

            userId="me",
            id=msg_id,
            format="full"

        ).execute()

    except Exception:
        return

    headers = message.get(
        "payload",
        {}
    ).get(
        "headers",
        []
    )

    subject = None
    sender = None

    for header in headers:

        if header["name"] == "Subject":
            subject = header["value"]

        if header["name"] == "From":
            sender = header["value"]

    timestamp_ms = int(message["internalDate"])

    received_at = timezone.make_aware(

        datetime.utcfromtimestamp(
            timestamp_ms / 1000
        )

    )

    body_text = extract_email_body(
        message.get("payload", {})
    )

    body_text = strip_quoted_content(body_text)

    RawEmail.objects.get_or_create(

        gmail_message_id=msg_id,

        defaults={

            "user": user,

            "gmail_thread_id":
            message["threadId"],

            "subject": subject,

            "sender": sender,

            "snippet":
            message.get("snippet"),

            "body_text":
            body_text,

            "received_at":
            received_at,

            "processed": False,

        }

    )

    print("Saved Email:", msg_id)


# ==========================================================
# FETCH RECENT EMAILS (FIRST CONNECT)
# ==========================================================

def fetch_recent_emails(user, max_results=40):

    service = get_gmail_service(user)

    if not service:
        return

    try:

        results = service.users().messages().list(

            userId="me",
            maxResults=max_results

        ).execute()

    except Exception:
        return

    for msg in results.get("messages", []):

        save_message(
            service,
            user,
            msg["id"]
        )


# ==========================================================
# 🔥 INCREMENTAL FETCH (REALTIME PUSH)
# ==========================================================

def fetch_incremental_emails(

    user,
    push_history_id=None

):

    token = GmailToken.objects.filter(
        user=user,
        is_active=True
    ).first()

    if not token:
        print("Incremental Fetch → No active token")
        return

    service = get_gmail_service(user)

    if not service:
        print("Incremental Fetch → Service unavailable")
        return

    # ⭐ IMPORTANT FIX
    history_id = push_history_id or token.gmail_history_id

    print("Fetching history from:", history_id)

    # FIRST TIME CONNECT
    if not history_id:

        print("First sync → full fetch")

        fetch_recent_emails(
            user,
            max_results=40
        )

        try:

            profile = service.users().getProfile(
                userId="me"
            ).execute()

            token.gmail_history_id = profile.get(
                "historyId"
            )

            token.save(
                update_fields=[
                    "gmail_history_id"
                ]
            )

        except Exception as e:

            print("History init failed:", e)

        return

    # HISTORY FETCH
    try:

        response = service.users().history().list(

            userId="me",

            startHistoryId=str(
                history_id
            ),

            historyTypes=[
                "messageAdded"
            ]

        ).execute()

    except Exception as e:

        print("History expired fallback:", e)

        fetch_recent_emails(
            user,
            max_results=40
        )

        return

    histories = response.get(
        "history",
        []
    )

    print("History Response:", histories)

    # SAVE EMAILS
    for record in histories:

        added = record.get(
            "messagesAdded",
            []
        )

        for msg in added:

            message = msg.get(
                "message",
                {}
            )

            msg_id = message.get("id")

            if msg_id:

                save_message(
                    service,
                    user,
                    msg_id
                )

        # Gmail fallback case
        fallback = record.get(
            "messages",
            []
        )

        for message in fallback:

            msg_id = message.get("id")

            if msg_id:

                save_message(
                    service,
                    user,
                    msg_id
                )

    # SAVE NEW HISTORY ID
    new_history = response.get(
        "historyId"
    )

    if new_history:

        token.gmail_history_id = new_history

        token.save(
            update_fields=[
                "gmail_history_id"
            ]
        )

        print("History updated:", new_history)


from .pubsub import start_gmail_watch


def initialize_gmail_watch(user):
    return start_gmail_watch(user)