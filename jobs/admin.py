from django.contrib import admin
from .models import JobThread, ThreadEvent, RawEmail


# =========================
# THREAD EVENT INLINE
# =========================

class ThreadEventInline(admin.TabularInline):
    model = ThreadEvent
    extra = 0
    readonly_fields = ("event_type", "event_timestamp", "created_at")
    ordering = ("-event_timestamp",)


# =========================
# JOB THREAD ADMIN
# =========================

@admin.register(JobThread)
class JobThreadAdmin(admin.ModelAdmin):
    list_display = (
        "company_name",
        "job_title",
        "status",
        "confidence_score",
        "last_activity_at",
        "created_at",
    )

    list_filter = ("status",)

    search_fields = ("company_name", "job_title", "gmail_thread_id")

    ordering = ("-last_activity_at",)

    inlines = [ThreadEventInline]


# =========================
# THREAD EVENT ADMIN
# =========================

@admin.register(ThreadEvent)
class ThreadEventAdmin(admin.ModelAdmin):
    list_display = (
        "thread",
        "event_type",
        "event_timestamp",
        "created_at",
    )

    list_filter = ("event_type",)

    search_fields = ("thread__company_name",)

    ordering = ("-event_timestamp",)


# =========================
# RAW EMAIL ADMIN
# =========================

@admin.register(RawEmail)
class RawEmailAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "sender",
        "gmail_thread_id",
        "processed",
        "classification",
        "confidence_score",
        "received_at",
    )

    list_filter = ("processed", "classification")

    search_fields = ("subject", "sender", "gmail_thread_id")

    ordering = ("-received_at",)

    readonly_fields = ("created_at",)
