
from notifications.models import WhatsAppConversationMessage


MAX_HISTORY_MESSAGES = 6
MAX_MESSAGE_LENGTH = 1000


def save_conversation_message(session, role, content):
    """Save one message belonging to an activated patient session."""
    if role not in {"patient", "assistant"}:
        raise ValueError("Unsupported conversation role.")

    if not isinstance(content, str):
        raise ValueError("Message content must be text.")

    content = content.strip()

    if not content:
        raise ValueError("Message content cannot be empty.")

    if len(content) > MAX_MESSAGE_LENGTH:
        raise ValueError("Message content exceeds the allowed length.")

    return WhatsAppConversationMessage.objects.create(
        session=session,
        role=role,
        content=content,
    )


def get_recent_conversation(session, limit=MAX_HISTORY_MESSAGES):
    """Return recent conversation messages in chronological order."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer.")

    messages = (
        WhatsAppConversationMessage.objects
        .filter(session=session)
        .order_by("-created_at", "-id")[:limit]
    )

    return list(reversed(list(messages)))


def build_followup_question(question, history):
    """
    Build a context-aware query from recent conversation messages.

    This preserves the patient's original wording and does not generate
    or invent medical instructions.
    """
    if not isinstance(question, str):
        raise ValueError("Question must be text.")

    question = question.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    if not history:
        return question

    context_lines = []

    for message in history:
        role = getattr(message, "role", None)
        content = getattr(message, "content", "")

        if role in {"patient", "assistant"} and isinstance(content, str):
            content = content.strip()

            if content:
                context_lines.append(f"{role}: {content}")

    if not context_lines:
        return question

    # Keep the original question last so retrieval can prioritize it.
    return (
        "Recent conversation for interpreting the patient's follow-up "
        "question. Treat this conversation as context only, not as a "
        "source of medical facts:\n"
        + "\n".join(context_lines)
        + f"\npatient's current question: {question}"
    )

import re


# Follow-ups that clearly depend on an earlier question and do not
# introduce a new preparation topic.
FOLLOWUP_PATTERNS = (
    r"^and when(?: exactly)?\??$",
    r"^when should i stop\??$",
    r"^when do i stop\??$",
    r"^what time(?: should i stop)?\??$",
    r"^how long(?: before)?\??$",
    r"^and after that\??$",
    r"^what about it\??$",
    r"^can you explain that\??$",
    r"^what does that mean\??$",
)


def resolve_followup_question(question, history):
    """
    Resolve only explicitly recognized follow-ups using the latest
    patient question as context.

    Assistant messages are not treated as clinical evidence.
    New topics and ambiguous questions remain unchanged.
    """
    if not isinstance(question, str):
        raise ValueError("Question must be text.")

    question = question.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    if not history:
        return None

    normalized = re.sub(r"\s+", " ", question.lower()).strip()

    is_followup = any(
        re.fullmatch(pattern, normalized)
        for pattern in FOLLOWUP_PATTERNS
    )

    if not is_followup:
        return None

    # Use only the most recent patient question, never an assistant reply.
    previous_patient_question = None

    for message in reversed(history):
        if getattr(message, "role", None) != "patient":
            continue

        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            previous_patient_question = content.strip()
            break

    if not previous_patient_question:
        return None

    # Preserve the patient's wording. This adds context but no medical facts.
    return (
        f"Earlier patient question: {previous_patient_question}\n"
        f"Current patient follow-up: {question}"
    )

def is_context_dependent_followup(question):
    """Identify follow-ups that need context before retrieval."""
    if not isinstance(question, str):
        return False



    normalized = re.sub(r"\s+", " ", question.lower()).strip()

    ambiguous_prefixes = (
        "what about ",
        "and ",
        "what if ",
        "how about ",
        "what then",
        "what about it",
        "and then",
    )

    return normalized.startswith(ambiguous_prefixes)