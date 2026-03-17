import re
from django.utils import timezone
from jobs.models import JobThread, ThreadEvent, RawEmail
from .classifier import classify_email
from .semantic_classifier import classify_with_embeddings
from dashboard.services.realtime_dashboard import push_dashboard_update


# ==========================================================
# MAIN EMAIL PROCESSOR
# ==========================================================

def process_unprocessed_emails(user):
    emails = RawEmail.objects.filter(user=user, processed=False)

    for email in emails:

        classification_source = "RULE"

        # --------------------------------------------------
        # 0️⃣ Detect USER_REPLY (very important)
        # --------------------------------------------------
        if email.sender and user.email.lower() in email.sender.lower():
            event_type = "USER_REPLY"
            confidence = 0.95
        else:
            # --------------------------------------------------
            # 1️⃣ RULE-BASED CLASSIFICATION
            # --------------------------------------------------
            event_type, confidence = classify_email(
                email.subject,
                email.sender,
                email.snippet,
                email.body_text,
            )

            # --------------------------------------------------
            # 2️⃣ AI FALLBACK (only if weak or unknown)
            # --------------------------------------------------
            if not event_type or confidence < 0.85:

                combined_text = f"{email.subject or ''} {email.body_text or ''} {email.snippet or ''}"

                ai_event, ai_conf = classify_with_embeddings(combined_text)

                if ai_event and ai_conf > confidence:
                    event_type = ai_event
                    confidence = ai_conf
                    classification_source = "AI"

        # --------------------------------------------------
        # Nothing classified → skip
        # --------------------------------------------------
        if not event_type:
            email.processed = True
            email.save(update_fields=["processed", "classification", "confidence_score", "classification_source"])
            continue

        # --------------------------------------------------
        # DATA EXTRACTION
        # --------------------------------------------------
        company_name = (
            extract_company_from_text(email.body_text)
            or extract_company_from_text(email.snippet)
            or extract_company(email.sender)
        )

        job_title = (
            extract_role_from_subject(email.subject)
            or email.subject
        )

        event_time = email.received_at or timezone.now()

        # --------------------------------------------------
        # CREATE OR GET THREAD
        # --------------------------------------------------
        thread, created = JobThread.objects.get_or_create(
            user=user,
            gmail_thread_id=email.gmail_thread_id,
            defaults={
                "company_name": company_name,
                "job_title": job_title,
                "confidence_score": confidence,
                "first_detected_at": event_time,
                "last_activity_at": event_time,
            }
        )

        # Update confidence if improved
        if confidence > thread.confidence_score:
            thread.confidence_score = confidence
            thread.save(update_fields=["confidence_score"])

        activity_updated = thread.bump_last_activity(event_time)

        # --------------------------------------------------
        # PREVENT DUPLICATE EVENT INSERT
        # --------------------------------------------------
        existing_event = ThreadEvent.objects.filter(
            thread=thread,
            event_type=event_type,
            event_timestamp=event_time
        ).exists()

        inserted_event = False
        if not existing_event:
            ThreadEvent.objects.create(
                thread=thread,
                event_type=event_type,
                event_timestamp=event_time,
                metadata={
                    "subject": email.subject,
                    "sender": email.sender,
                }
            )
            inserted_event = True

        # --------------------------------------------------
        # UPDATE STATUS
        # --------------------------------------------------
        status_changed = update_thread_status(thread, event_type, event_time)

        # --------------------------------------------------
        # MARK EMAIL PROCESSED
        # --------------------------------------------------
        email.processed = True
        email.classification = event_type
        email.confidence_score = confidence
        email.classification_source = classification_source
        email.save(update_fields=["processed", "classification", "confidence_score", "classification_source"])

        if created or inserted_event or status_changed or activity_updated or event_type in [
            "RECRUITER_REPLY",
            "USER_REPLY",
            "ASSESSMENT_REQUESTED",
            "ACTION_REQUIRED",
        ]:
            push_dashboard_update(user, activity_thread=thread)


# ==========================================================
# THREAD STATUS MACHINE (WITH PROTECTION)
# ==========================================================

STATUS_PRIORITY = {
    "APPLIED": 1,
    "RECRUITER_REPLIED": 2,
    "ASSESSMENT_PENDING": 3,
    "ACTION_REQUIRED": 4,
    "INTERVIEW_SCHEDULED": 5,
    "REJECTED": 6,
    "OFFER_RECEIVED": 7,
}


def update_thread_status(thread, event_type, event_time):

    changed = False

    event_to_status = {
        "APPLICATION_DETECTED": "APPLIED",
        "INTERVIEW_INVITE": "INTERVIEW_SCHEDULED",
        "ASSESSMENT_REQUESTED": "ASSESSMENT_PENDING",
        "ACTION_REQUIRED": "ACTION_REQUIRED",
        "REJECTION": "REJECTED",
        "OFFER": "OFFER_RECEIVED",
        "RECRUITER_REPLY": "RECRUITER_REPLIED",
    }

    new_status = event_to_status.get(event_type)

    # Reset followup dismissed when new activity happens
    if event_type in ["RECRUITER_REPLY", "USER_REPLY"] and thread.followup_dismissed:
        thread.followup_dismissed = False
        changed = True

    if new_status:
        current_priority = STATUS_PRIORITY.get(thread.status, 0)
        new_priority = STATUS_PRIORITY.get(new_status, 0)

        # Prevent downgrade
        if new_priority >= current_priority and thread.status != new_status:
            thread.status = new_status
            changed = True

    # Update last activity only if newer
    if not thread.last_activity_at or event_time > thread.last_activity_at:
        thread.last_activity_at = event_time
        changed = True

    if changed:
        update_fields = []
        if new_status and thread.status == new_status:
            update_fields.append("status")
        if event_type in ["RECRUITER_REPLY", "USER_REPLY"]:
            update_fields.append("followup_dismissed")
        if not thread.last_activity_at or event_time >= thread.last_activity_at:
            update_fields.append("last_activity_at")

        thread.save(update_fields=list(dict.fromkeys(update_fields)))

    return changed


# ==========================================================
# FOLLOW-UP INTELLIGENCE
# ==========================================================

def calculate_followups(user):

    followups = []

    threads = JobThread.objects.filter(
        user=user,
        followup_dismissed=False
    )

    for thread in threads:

        if not thread.last_activity_at:
            continue

        events = thread.events.all()
        if not events.exists():
            continue

        latest_event = events.first()

        # ------------------------------------------
        # Case 1: Applied but no recruiter reply
        # ------------------------------------------
        if thread.status == "APPLIED":

            days_since = (timezone.now() - thread.last_activity_at).days

            recruiter_reply_exists = thread.events.filter(
                event_type="RECRUITER_REPLY"
            ).exists()

            if not recruiter_reply_exists and days_since >= 7:
                followups.append({
                    "thread": thread,
                    "reason": "No reply in 7 days",
                    "type": "NO_RESPONSE"
                })

        # ------------------------------------------
        # Case 2: Recruiter replied, waiting on user
        # ------------------------------------------
        if thread.status == "RECRUITER_REPLIED":

            user_reply_exists = thread.events.filter(
                event_type="USER_REPLY",
                event_timestamp__gt=latest_event.event_timestamp
            ).exists()

            if not user_reply_exists:
                followups.append({
                    "thread": thread,
                    "reason": "Recruiter replied — response pending",
                    "type": "REPLY_PENDING"
                })

    return followups


# ==========================================================
# COMPANY EXTRACTION LOGIC
# ==========================================================

def extract_company(sender):
    if not sender:
        return "Unknown"

    if "<" in sender:
        email_part = sender.split("<")[-1].replace(">", "")
    else:
        email_part = sender

    if "@" not in email_part:
        return sender.split()[0]

    domain = email_part.split("@")[-1]
    company = domain.split(".")[0]

    return company.capitalize()


def extract_company_from_text(text):
    if not text:
        return None

    patterns = [
        r"sent to ([a-zA-Z0-9 &\-]+)",
        r"position at ([a-zA-Z0-9 &\-]+)",
        r"application for .* at ([a-zA-Z0-9 &\-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1).title()

    return None


def extract_role_from_subject(subject):
    if not subject:
        return None

    if "–" in subject:
        return subject.split("–")[-1].strip()

    if "-" in subject:
        return subject.split("-")[-1].strip()

    return None
