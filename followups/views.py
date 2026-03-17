import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from dashboard.services.realtime_dashboard import push_dashboard_update
from jobs.models import JobThread

from .ai_service import improve_followup
from .generator import generate_followup


@login_required
@require_GET
def generate_followup_view(request, thread_id):
    thread = get_object_or_404(JobThread, id=thread_id, user=request.user)
    generated_text = generate_followup(thread, request.user)
    thread.bump_last_activity(timezone.now())
    push_dashboard_update(request.user, activity_thread=thread)
    return JsonResponse({"message": generated_text})


@login_required
@require_POST
def improve_followup_view(request, thread_id):
    thread = get_object_or_404(JobThread, id=thread_id, user=request.user)

    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        payload = {}

    draft = (payload.get("draft") or "").strip()
    if not draft:
        return JsonResponse({"detail": "Draft is required."}, status=400)

    with transaction.atomic():
        user = (
            type(request.user)
            .objects
            .select_for_update()
            .select_related("profile")
            .get(pk=request.user.pk)
        )

        profile = getattr(user, "profile", None)
        has_active_plan = bool(getattr(profile, "has_active_plan", False))
        ai_credits = int(getattr(profile, "ai_credits", 0) or 0)

        if not has_active_plan and ai_credits <= 0:
            return JsonResponse({"detail": "AI improvement unavailable."}, status=403)

        try:
            improved_text = improve_followup(draft, thread, user)
        except Exception:
            return JsonResponse({"detail": "AI service unavailable."}, status=502)

        if not has_active_plan and profile and ai_credits > 0:
            profile.ai_credits = ai_credits - 1
            profile.save(update_fields=["ai_credits"])

    return JsonResponse({"message": improved_text})
