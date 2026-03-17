import json
import time
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.template.loader import render_to_string
from django.utils import timezone

from jobs.models import JobThread


DASHBOARD_PUSH_DEBOUNCE_SECONDS = 0.5
THREAD_LIMIT = 20

EVENT_TYPE_TO_STATUS = {
    "APPLICATION_DETECTED": "APPLIED",
    "INTERVIEW_INVITE": "INTERVIEW_SCHEDULED",
    "ASSESSMENT_REQUESTED": "ASSESSMENT_PENDING",
    "ACTION_REQUIRED": "ACTION_REQUIRED",
    "REJECTION": "REJECTED",
    "OFFER": "OFFER_RECEIVED",
    "RECRUITER_REPLY": "RECRUITER_REPLIED",
}


def _resolve_thread_display_status(thread):
    latest_event = thread.events.first()
    if latest_event:
        return EVENT_TYPE_TO_STATUS.get(latest_event.event_type, thread.status)
    return thread.status


def _build_metrics(user, threads):
    total = threads.count()
    interviews = threads.filter(status="INTERVIEW_SCHEDULED").count()
    offers = threads.filter(status="OFFER_RECEIVED").count()
    pending = (
        threads
        .filter(
            status__in=[
                "APPLIED",
                "RECRUITER_REPLIED",
                "ASSESSMENT_PENDING",
                "ACTION_REQUIRED",
            ],
            followup_dismissed=False,
        )
        .exclude(status__in=["REJECTED", "OFFER_RECEIVED"])
        .count()
    )
    recent_updates = threads.filter(
        last_activity_at__gte=timezone.now() - timedelta(days=7)
    ).count()

    return {
        "total": total,
        "pending": pending,
        "interview": interviews,
        "rejected": threads.filter(status="REJECTED").count(),
        "offers": offers,
        "recent_updates": recent_updates,
    }


def _build_chart_data(threads):
    weekly_queryset = (
        threads
        .exclude(first_detected_at__isnull=True)
        .annotate(week=TruncWeek("first_detected_at"))
        .values("week")
        .annotate(count=Count("id"))
        .order_by("week")
    )

    labels = []
    values = []
    for item in weekly_queryset:
        if item["week"]:
            labels.append(item["week"].date().isoformat())
            values.append(item["count"])

    return {
        "labels": labels,
        "values": values,
    }


def _build_threads_html(user):
    threads = (
        JobThread.objects
        .filter(user=user)
        .prefetch_related("events")
        .order_by("-last_activity_at")[:THREAD_LIMIT]
    )

    for thread in threads:
        thread.display_status = _resolve_thread_display_status(thread)

    return render_to_string(
        "dashboard/_threads.html",
        {"threads": threads},
    )


def push_dashboard_update(user):
    cache_key = f"dashboard:last-push:{user.id}"
    now = time.monotonic()
    last_sent = cache.get(cache_key)
    if last_sent and now - float(last_sent) < DASHBOARD_PUSH_DEBOUNCE_SECONDS:
        return

    threads = JobThread.objects.filter(user=user)

    payload = {
        "type": "dashboard_update",
        "metrics": _build_metrics(user, threads),
        "chart": _build_chart_data(threads),
        "threads_html": _build_threads_html(user),
    }

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        f"dashboard_{user.id}",
        {
            "type": "dashboard.message",
            "payload": json.loads(json.dumps(payload)),
        },
    )
    cache.set(cache_key, now, timeout=60)
