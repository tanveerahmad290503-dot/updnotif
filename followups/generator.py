from .context_builder import build_context
from .templates_engine import (
    GENERAL_TEMPLATE,
    INTERVIEW_TEMPLATE,
    POST_ACCEPTANCE_TEMPLATE,
)


def select_template(context):
    days_since = context.get("days_since_last_reply")

    if (
        context.get("last_recruiter_intent") == "ACCEPTED"
        and days_since is not None
        and days_since >= 7
    ):
        return POST_ACCEPTANCE_TEMPLATE

    if context.get("status") == "INTERVIEW":
        return INTERVIEW_TEMPLATE

    return GENERAL_TEMPLATE


def generate_followup(thread, user):
    context = build_context(thread)
    template = select_template(context)

    recruiter_name = getattr(thread, "recruiter_name", None) or "Recruiter"
    company_name = getattr(thread, "company_name", None) or "your company"
    role = getattr(thread, "role", None) or getattr(thread, "job_title", None) or "the role"
    user_full_name = user.get_full_name() or user.username

    return template.format(
        recruiter_name=recruiter_name,
        company_name=company_name,
        role=role,
        user_full_name=user_full_name,
    )
