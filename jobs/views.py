import json
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.utils import timezone

from accounts.models import GmailToken  # ✅ NEW (STEP 6)
from dashboard.services.realtime_dashboard import push_dashboard_update

from .models import JobThread
from intelligence.processor import calculate_followups


EVENT_TYPE_TO_STATUS = {
    "APPLICATION_DETECTED": "APPLIED",
    "INTERVIEW_INVITE": "INTERVIEW_SCHEDULED",
    "ASSESSMENT_REQUESTED": "ASSESSMENT_PENDING",
    "ACTION_REQUIRED": "ACTION_REQUIRED",
    "REJECTION": "REJECTED",
    "OFFER": "OFFER_RECEIVED",
    "RECRUITER_REPLY": "RECRUITER_REPLIED",
}


def resolve_thread_display_status(thread):
    latest_event = thread.events.first()

    if latest_event:
        return EVENT_TYPE_TO_STATUS.get(
            latest_event.event_type,
            thread.status
        )

    return thread.status


# =====================================================
# DASHBOARD
# =====================================================

@login_required
def dashboard(request):

    threads = (

        JobThread.objects
        .filter(user=request.user)
        .select_related("user")
        .prefetch_related("events")
        .order_by("-last_activity_at")

    )

    for thread in threads:
        thread.display_status = resolve_thread_display_status(thread)

    # -------------------------------------------------
    # ✅ STEP 6 — Gmail Connection Status
    # -------------------------------------------------

    gmail_connected = GmailToken.objects.filter(
        user=request.user,
        is_active=True
    ).exists()

    # ----------------------------
    # BASIC COUNTS
    # ----------------------------

    total = threads.count()

    interviews = threads.filter(
        status="INTERVIEW_SCHEDULED"
    ).count()

    offers = threads.filter(status="OFFER_RECEIVED").count()
    threads_rejected = threads.filter(status="REJECTED").count()

    # ----------------------------
    # PENDING COUNT
    # ----------------------------

    pending_statuses = [

        "APPLIED",
        "RECRUITER_REPLIED",
        "ASSESSMENT_PENDING",
        "ACTION_REQUIRED",

    ]

    pending = (

        threads
        .filter(
            status__in=pending_statuses,
            followup_dismissed=False
        )
        .exclude(
            status__in=[
                "REJECTED",
                "OFFER_RECEIVED"
            ]
        )
        .count()

    )

    # ----------------------------
    # INTERVIEW CONVERSION %
    # ----------------------------

    interview_conversion = (

        round((interviews / total) * 100, 1)
        if total else 0

    )

    # ----------------------------
    # OFFER RATE %
    # ----------------------------

    offer_rate = (

        round((offers / total) * 100, 1)
        if total else 0

    )

    # ----------------------------
    # AVG TIME TO OFFER
    # ----------------------------

    offer_threads = threads.filter(
        status="OFFER_RECEIVED"
    )

    time_deltas = []

    for t in offer_threads:

        if t.first_detected_at and t.last_activity_at:

            delta = (

                t.last_activity_at -
                t.first_detected_at

            ).days

            if delta >= 0:
                time_deltas.append(delta)

    avg_time_to_offer = (

        round(
            sum(time_deltas) /
            len(time_deltas),
            1
        )

        if time_deltas else 0

    )

    # ----------------------------
    # WEEKLY APPLICATIONS
    # ----------------------------

    weekly_queryset = (

        threads
        .exclude(
            first_detected_at__isnull=True
        )
        .annotate(
            week=TruncWeek(
                "first_detected_at"
            )
        )
        .values("week")
        .annotate(
            count=Count("id")
        )
        .order_by("week")

    )

    weekly_data = [

        {

            "week":

            item["week"].isoformat()

            if item["week"]
            else None,

            "count":

            item["count"]

        }

        for item in weekly_queryset

    ]

    # ----------------------------
    # RECENT UPDATES (7 DAYS)
    # ----------------------------

    seven_days_ago = (

        timezone.now() -
        timedelta(days=7)

    )

    recent_updates = threads.filter(

        last_activity_at__gte=
        seven_days_ago

    ).count()

    # ----------------------------
    # FOLLOWUPS
    # ----------------------------

    followups = calculate_followups(
        request.user
    )

    # ----------------------------
    # CONTEXT
    # ----------------------------

    context = {

        "threads": threads,

        "total": total,
        "interviews": interviews,
        "offers": offers,
        "threads_rejected": threads_rejected,

        "pending": pending,

        "interview_conversion":
        interview_conversion,

        "offer_rate":
        offer_rate,

        "avg_time_to_offer":
        avg_time_to_offer,

        # JS SAFE
        "weekly_data":
        json.dumps(weekly_data),

        "recent_updates":
        recent_updates,

        "followups":
        followups,

        "followup_count":
        len(followups),

        # ✅ STEP 6 UX
        "gmail_connected":
        gmail_connected,

    }

    return render(

        request,
        "dashboard.html",
        context

    )


# =====================================================
# THREAD DETAIL
# =====================================================

@login_required
def thread_detail(request, thread_id):

    thread = get_object_or_404(

        JobThread.objects.prefetch_related(
            "events"
        ),

        id=thread_id,
        user=request.user

    )

    context = {

        "thread": thread,
        "events": thread.events.all(),

    }

    return render(

        request,
        "thread_detail.html",
        context

    )


# =====================================================
# DISMISS FOLLOWUP
# =====================================================

@require_POST
@login_required
def dismiss_followup(request, thread_id):

    thread = get_object_or_404(

        JobThread,

        id=thread_id,
        user=request.user

    )

    thread.followup_dismissed = True

    thread.save(

        update_fields=[
            "followup_dismissed"
        ]

    )

    push_dashboard_update(request.user)

    return redirect(
        "dashboard"
    )
