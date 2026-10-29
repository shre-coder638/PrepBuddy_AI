
import pytest

from notifications.models import WhatsAppAssistantSession
from patients.models import Patient
from chatbot.conversation import (
    build_followup_question,
    get_recent_conversation,
    save_conversation_message,
)


@pytest.fixture
def assistant_session(db):
    patient = Patient.objects.create(
        first_name="Conversation",
        last_name="Test",
        phone_number="+919999000099",
    )

    return WhatsAppAssistantSession.objects.create(
        patient=patient,
        is_active=True,
    )


@pytest.mark.django_db
def test_saves_patient_and_assistant_messages(assistant_session):
    patient_message = save_conversation_message(
        assistant_session,
        "patient",
        "Can I drink water?",
    )
    assistant_message = save_conversation_message(
        assistant_session,
        "assistant",
        "Please check your assigned preparation instructions.",
    )

    assert patient_message.role == "patient"
    assert assistant_message.role == "assistant"
    assert assistant_session.messages.count() == 2


@pytest.mark.django_db
def test_rejects_invalid_message_content(assistant_session):
    with pytest.raises(ValueError):
        save_conversation_message(assistant_session, "patient", " ")

    with pytest.raises(ValueError):
        save_conversation_message(assistant_session, "unknown", "Hello")


@pytest.mark.django_db
def test_recent_history_is_chronological_and_limited(assistant_session):
    save_conversation_message(assistant_session, "patient", "First")
    save_conversation_message(assistant_session, "assistant", "Second")
    save_conversation_message(assistant_session, "patient", "Third")

    history = get_recent_conversation(assistant_session, limit=2)

    assert [message.content for message in history] == [
        "Second",
        "Third",
    ]


@pytest.mark.django_db
def test_followup_query_includes_context_and_current_question(
    assistant_session,
):
    save_conversation_message(
        assistant_session,
        "patient",
        "What does my protocol say about fasting?",
    )
    save_conversation_message(
        assistant_session,
        "assistant",
        "Check the fasting instruction in your assigned protocol.",
    )

    history = get_recent_conversation(assistant_session)
    query = build_followup_question("What about water?", history)

    assert "fasting" in query
    assert "What about water?" in query
    assert query.index("What about water?") > query.index("fasting")


def test_followup_query_without_history_is_unchanged():
    question = "What about water?"

    assert build_followup_question(question, []) == question

from types import SimpleNamespace

from chatbot.conversation import resolve_followup_question


def test_resolves_clear_followup_using_previous_patient_question():
    history = [
        SimpleNamespace(
            role="patient",
            content="When should I stop eating?",
        ),
        SimpleNamespace(
            role="assistant",
            content="Please check your approved fasting instruction.",
        ),
    ]

    result = resolve_followup_question("And when?", history)

    assert result is not None
    assert "When should I stop eating?" in result
    assert "And when?" in result


def test_does_not_expand_a_new_topic():
    history = [
        SimpleNamespace(
            role="patient",
            content="When should I stop eating?",
        ),
    ]

    assert resolve_followup_question("What about water?", history) is None


def test_does_not_resolve_followup_without_patient_question():
    history = [
        SimpleNamespace(
            role="assistant",
            content="Please check your approved instructions.",
        ),
    ]

    assert resolve_followup_question("And when?", history) is None


def test_does_not_resolve_followup_without_history():
    assert resolve_followup_question("And when?", []) is None

def test_uses_most_recent_patient_question_for_followup():
    from types import SimpleNamespace
    from chatbot.conversation import resolve_followup_question

    history = [
        SimpleNamespace(
            role="patient",
            content="When should I stop eating?",
        ),
        SimpleNamespace(
            role="assistant",
            content="Check your approved fasting instruction.",
        ),
        SimpleNamespace(
            role="patient",
            content="Can I drink water?",
        ),
        SimpleNamespace(
            role="assistant",
            content="Check the water instruction in your protocol.",
        ),
    ]

    result = resolve_followup_question("And when?", history)

    assert result is not None
    assert "Can I drink water?" in result
    assert "When should I stop eating?" not in result


def test_does_not_resolve_unrecognized_followup_phrase():
    from types import SimpleNamespace
    from chatbot.conversation import resolve_followup_question

    history = [
        SimpleNamespace(
            role="patient",
            content="When should I stop eating?",
        ),
    ]

    assert resolve_followup_question("What about tomorrow?", history) is None