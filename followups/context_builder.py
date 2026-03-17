from django.utils import timezone


def build_context(thread):
    """
    Build minimal deterministic context for follow-up generation using
    stored JobThread fields only.
    """
    last_reply_at = getattr(thread, "last_recruiter_reply_at", None)

    days_since_last_reply = None
    if last_reply_at:
        days_since_last_reply = (timezone.now() - last_reply_at).days

    return {
        "status": getattr(thread, "status", ""),
        "last_recruiter_intent": getattr(thread, "last_recruiter_intent", None),
        "last_recruiter_reply_at": last_reply_at,
        "days_since_last_reply": days_since_last_reply,
    }
