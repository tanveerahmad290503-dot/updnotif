from sentence_transformers import SentenceTransformer, util
import torch

# Load once (global)
model = SentenceTransformer("all-MiniLM-L6-v2")

# Define intent descriptions
INTENT_DESCRIPTIONS = {
    "INTERVIEW_INVITE": "This email invites the candidate to schedule or attend an interview.",
    "REJECTION": "This email informs the candidate that they were not selected or rejected.",
    "OFFER": "This email contains a job offer for the candidate.",
    "ASSESSMENT_REQUESTED": "This email asks the candidate to complete a test, assignment, or assessment.",
    "ACTION_REQUIRED": "This email requires the candidate to take an action such as submitting documents or completing information.",
    "APPLICATION_DETECTED": "This email confirms that the job application has been received.",
    "RECRUITER_REPLY": "This email is a reply from a recruiter in an ongoing conversation.",
}

# Precompute intent embeddings
intent_embeddings = {
    intent: model.encode(description, convert_to_tensor=True)
    for intent, description in INTENT_DESCRIPTIONS.items()
}


def classify_with_embeddings(email_text):
    if not email_text:
        return None, 0.0

    email_embedding = model.encode(email_text, convert_to_tensor=True)

    best_intent = None
    best_score = 0.0

    for intent, intent_embedding in intent_embeddings.items():
        score = util.cos_sim(email_embedding, intent_embedding).item()

        if score > best_score:
            best_score = score
            best_intent = intent

    # Confidence scaling
    confidence = round(float(best_score), 3)

    # Threshold protection
    if confidence < 0.45:
        return None, 0.0

    return best_intent, confidence
