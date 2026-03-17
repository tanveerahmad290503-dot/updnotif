import os

import requests


def improve_followup(draft, thread, user):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    role = getattr(thread, "role", None) or getattr(thread, "job_title", None) or "the role"
    company_name = getattr(thread, "company_name", None) or "the company"
    user_full_name = user.get_full_name() or user.username

    prompt = (
        "Rewrite this follow-up email to be concise, professional, and polite. "
        "Preserve factual details. Return only the improved email text.\n\n"
        f"Company: {company_name}\n"
        f"Role: {role}\n"
        f"Candidate: {user_full_name}\n\n"
        f"Draft:\n{draft}"
    )

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You improve recruiting follow-up emails. Output improved text only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        },
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content.strip() or draft
