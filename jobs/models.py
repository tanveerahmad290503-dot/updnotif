import uuid
from django.db import models
from django.contrib.auth.models import User


# ==========================================================
# JOB THREAD (CORE ENTITY)
# ==========================================================

class JobThread(models.Model):

    STATUS_CHOICES = [
        ("APPLIED", "Applied"),
        ("RECRUITER_REPLIED", "Recruiter Replied"),
        ("INTERVIEW_SCHEDULED", "Interview Scheduled"),
        ("ASSESSMENT_PENDING", "Assessment Pending"),
        ("ACTION_REQUIRED", "Action Required"),
        ("REJECTED", "Rejected"),
        ("OFFER_RECEIVED", "Offer Received"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    gmail_thread_id = models.CharField(max_length=255)

    company_name = models.CharField(max_length=255, null=True, blank=True)
    job_title = models.CharField(max_length=255, null=True, blank=True)

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="APPLIED"
    )

    confidence_score = models.FloatField(default=0.0)

    first_detected_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    followup_dismissed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "gmail_thread_id")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
            models.Index(fields=["gmail_thread_id"]),
            models.Index(fields=["last_activity_at"]),
        ]

    def __str__(self):
        return f"{self.company_name or 'Unknown Company'} - {self.job_title or 'Unknown Role'}"


# ==========================================================
# THREAD EVENTS (STATE MACHINE HISTORY)
# ==========================================================

class ThreadEvent(models.Model):

    EVENT_TYPES = [
        ("APPLICATION_DETECTED", "Application Detected"),
        ("RECRUITER_REPLY", "Recruiter Reply"),
        ("USER_REPLY", "User Reply"),
        ("INTERVIEW_INVITE", "Interview Invite"),
        ("ASSESSMENT_REQUESTED", "Assessment Requested"),
        ("ACTION_REQUIRED", "Action Required"),
        ("REJECTION", "Rejection"),
        ("OFFER", "Offer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    thread = models.ForeignKey(
        JobThread,
        on_delete=models.CASCADE,
        related_name="events"
    )

    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)

    event_timestamp = models.DateTimeField()

    metadata = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_timestamp"]  # Always newest first
        indexes = [
            models.Index(fields=["thread"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["event_timestamp"]),
        ]

    def __str__(self):
        return f"{self.thread.company_name} - {self.event_type}"

# ==========================================================
# RAW EMAIL (INGESTION LAYER)
# ==========================================================

class RawEmail(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    gmail_message_id = models.CharField(max_length=255, unique=True)
    gmail_thread_id = models.CharField(max_length=255)

    subject = models.TextField(null=True, blank=True)
    sender = models.CharField(max_length=255, null=True, blank=True)
    snippet = models.TextField(null=True, blank=True)

    # Full email body for intelligent parsing
    body_text = models.TextField(null=True, blank=True)

    received_at = models.DateTimeField()

    processed = models.BooleanField(default=False)

    classification = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    confidence_score = models.FloatField(default=0.0)

    # ✅ NEW FIELD — Track whether RULE or AI classified it
    classification_source = models.CharField(
        max_length=20,
        default="RULE"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["gmail_thread_id"]),
            models.Index(fields=["processed"]),
            models.Index(fields=["received_at"]),
            models.Index(fields=["classification"]),
            models.Index(fields=["classification_source"]),
        ]

    def __str__(self):
        return f"{self.subject or 'No Subject'}"
