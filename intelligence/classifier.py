import re


# ----------------------------------------------------------
# TEXT NORMALIZATION
# ----------------------------------------------------------

def normalize_text(text):
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text


# ----------------------------------------------------------
# JOB CONTEXT SCORING (IMPROVED)
# ----------------------------------------------------------

JOB_INDICATORS = [
    "application",
    "interview",
    "position",
    "job",
    "role",
    "hiring",
    "candidate",
    "offer letter",
    "shortlisted",
    "recruiter",
    "selection process",
    "assessment",
    "assignment",
]

NON_JOB_INDICATORS = [
    "insurance",
    "policy",
    "travel",
    "booking",
    "flight",
    "pnr",
    "bank",
    "transaction",
    "payment",
    "invoice",
    "order",
    "shipment",
]


def job_context_score(text):
    """
    Returns a score indicating how job-related this email is.
    """

    score = 0

    for word in JOB_INDICATORS:
        if word in text:
            score += 1

    for word in NON_JOB_INDICATORS:
        if word in text:
            score -= 1

    return score


# ----------------------------------------------------------
# KEY PHRASE GROUPS (SEMANTIC CLUSTERS)
# ----------------------------------------------------------

INTENT_PATTERNS = {

    "OFFER": [
        r"\bjob offer\b",
        r"\boffer letter\b",
        r"\bpleased to offer\b",
        r"\bdelighted to offer\b",
    ],

    "REJECTION": [
        r"\bwe regret\b",
        r"\bunfortunately\b",
        r"\bnot selected\b",
        r"\bwill not be moving forward\b",
        r"\bposition has been filled\b",
    ],

    "INTERVIEW_INVITE": [
        r"\binterview invitation\b",
        r"\bshortlisted\b",
        r"\binvite you\b.*\binterview\b",
        r"\battend an interview\b",
        r"\bschedule\b.*\binterview\b",
        r"\bselection process\b",
        r"\bnext phase\b",
    ],

    "ASSESSMENT_REQUESTED": [
        r"\bcase study\b",
        r"\btechnical task\b",
        r"\bcoding assignment\b",
        r"\bcomplete the assignment\b",
        r"\bassessment round\b",
        r"\bsubmission link\b",
        r"\bdue date\b",
    ],

    "ACTION_REQUIRED": [
        r"\baction required\b",
        r"\bcomplete your application\b",
        r"\bmissing from your submission\b",
        r"\bverify your email\b",
        r"\bplease complete\b",
    ],

    "APPLICATION_DETECTED": [
        r"\bapplication received\b",
        r"\bthank you for applying\b",
        r"\bwe have received your application\b",
        r"\byour application was sent\b",
        r"\bapplication submitted\b",
    ],
}


# ----------------------------------------------------------
# PRIORITY ORDER
# ----------------------------------------------------------

PRIORITY = [
    "OFFER",
    "REJECTION",
    "INTERVIEW_INVITE",
    "ASSESSMENT_REQUESTED",
    "ACTION_REQUIRED",
    "APPLICATION_DETECTED",
]


# ----------------------------------------------------------
# MAIN CLASSIFIER
# ----------------------------------------------------------

def classify_email(subject, sender, snippet, body_text=None):

    combined_text = f"{subject or ''} {snippet or ''} {body_text or ''}"
    text = normalize_text(combined_text)

    # ------------------------------------------------------
    # STEP 1: JOB CONTEXT SCORING
    # ------------------------------------------------------

    context_score = job_context_score(text)

    # If strongly non-job, ignore completely
    if context_score < -1:
        return None, 0.0

    scores = {}

    # ------------------------------------------------------
    # STEP 2: INTENT SCORING
    # ------------------------------------------------------

    for intent, patterns in INTENT_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, text):
                score += 1

        if score > 0:
            scores[intent] = score

    # ------------------------------------------------------
    # STEP 3: RECRUITER REPLY (always allow)
    # ------------------------------------------------------

    if subject and subject.lower().startswith("re:"):
        scores["RECRUITER_REPLY"] = 1

    if not scores:
        return None, 0.0

    # ------------------------------------------------------
    # STEP 4: RESOLVE USING PRIORITY
    # ------------------------------------------------------

    for intent in PRIORITY:
        if intent in scores:
            base_conf = 0.65 + scores[intent] * 0.1

            # Slight boost if context strongly job-related
            if context_score > 1:
                base_conf += 0.05

            confidence = min(1.0, base_conf)
            return intent, confidence

    # fallback
    best_intent = max(scores, key=scores.get)
    confidence = min(1.0, 0.65 + scores[best_intent] * 0.1)
    return best_intent, confidence
