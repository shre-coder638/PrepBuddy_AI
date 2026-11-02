import pytest
from django.test import Client
from unittest.mock import Mock, patch

from chatbot.conversation import get_recent_conversation
from notifications.models import (
    WhatsAppAssistantSession,
    WhatsAppConversationMessage,
    WhatsAppMessageAnalysis,
)
from .test_missed_reminders import setup_data
from .test_openwa_webhook import post_event


PHONE = "910000000001"


@pytest.fixture
def webhook_client():
    return Client()


def configure_registered_sender(mock_get):
    mock_get.return_value = Mock(
        status_code=200,
        text='{"phone":"910000000001"}',
    )
    mock_get.return_value.json.return_value = {"phone": PHONE}


def activate_assistant(client, message_id="stage2c-activation"):
    return post_event(
        client,
        "message.received",
        {
            "id": message_id,
            "from": f"{PHONE}@c.us",
            "body": "TALK TO ASSISTANT",
        },
    )


def send_patient_message(client, message, message_id):
    return post_event(
        client,
        "message.received",
        {
            "id": message_id,
            "from": f"{PHONE}@c.us",
            "body": message,
        },
    )


@pytest.mark.django_db
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
@patch("chatbot.views.answer_with_rag")
def test_clinical_concern_is_persisted_and_never_reaches_rag(
    mock_rag, mock_get, mock_send, webhook_client, setup_data
):
    configure_registered_sender(mock_get)
    assert activate_assistant(webhook_client).status_code == 200

    response = send_patient_message(
        webhook_client, "I have chest pain", "stage2c-chest-pain"
    )

    assert response.status_code == 200
    assert response.json()["answered"] is True
    assert response.json()["needs_clinical_team"] is True
    mock_rag.assert_not_called()

    session = WhatsAppAssistantSession.objects.get(
        patient=setup_data["procedure"].patient
    )
    patient_message = WhatsAppConversationMessage.objects.get(
        session=session, role="patient", content="I have chest pain"
    )
    analysis = WhatsAppMessageAnalysis.objects.get(message=patient_message)

    assert analysis.sentiment == "negative"
    assert analysis.intent == "clinical_concern"
    assert analysis.requires_human is True
    assert "clinical team" in mock_send.call_args.args[1].lower()


@pytest.mark.django_db
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
@patch("chatbot.views.answer_with_rag")
def test_distressed_message_is_escalated_even_without_clinical_keyword(
    mock_rag, mock_get, mock_send, webhook_client, setup_data
):
    configure_registered_sender(mock_get)
    assert activate_assistant(webhook_client, "stage2c-distress-activation").status_code == 200

    response = send_patient_message(
        webhook_client, "I feel overwhelmed and hopeless", "stage2c-distress"
    )

    assert response.status_code == 200
    assert response.json()["needs_clinical_team"] is True
    mock_rag.assert_not_called()

    session = WhatsAppAssistantSession.objects.get(
        patient=setup_data["procedure"].patient
    )
    patient_message = WhatsAppConversationMessage.objects.get(
        session=session, role="patient", content="I feel overwhelmed and hopeless"
    )
    analysis = WhatsAppMessageAnalysis.objects.get(message=patient_message)

    assert analysis.emotion == "distressed"
    assert analysis.requires_human is True
    assert "clinical team" in mock_send.call_args.args[1].lower()


@pytest.mark.django_db
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
@patch("chatbot.views.answer_with_rag")
def test_ordinary_preparation_question_continues_to_rag(
    mock_rag, mock_get, mock_send, webhook_client, setup_data
):
    configure_registered_sender(mock_get)
    mock_rag.return_value = {
        "answer": "Follow your stored preparation instructions.",
        "sources": [],
        "needs_clinical_team": False,
    }
    assert activate_assistant(webhook_client, "stage2c-normal-activation").status_code == 200

    response = send_patient_message(
        webhook_client, "When should I arrive?", "stage2c-normal-question"
    )

    assert response.status_code == 200
    assert response.json()["needs_clinical_team"] is False
    mock_rag.assert_called_once()
    assert mock_rag.call_args.kwargs["communication_style"] == "neutral"
    assert mock_rag.call_args.kwargs["requires_human"] is False
    assert "Follow your stored preparation instructions." in mock_send.call_args.args[1]


@pytest.mark.django_db
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
@patch("chatbot.views.answer_with_rag")
def test_positive_patient_message_uses_positive_style(
    mock_rag, mock_get, mock_send, webhook_client, setup_data
):
    configure_registered_sender(mock_get)
    mock_rag.return_value = {
        "answer": "You're welcome. Follow your stored instructions.",
        "sources": [],
        "needs_clinical_team": False,
    }
    assert activate_assistant(webhook_client, "stage2c-positive-activation").status_code == 200

    response = send_patient_message(
        webhook_client, "Thank you, that was helpful", "stage2c-positive"
    )

    assert response.status_code == 200
    assert response.json()["needs_clinical_team"] is False
    mock_rag.assert_called_once()
    assert mock_rag.call_args.kwargs["communication_style"] == "positive"


@pytest.mark.django_db
@patch("notifications.views.analyze_patient_message", side_effect=RuntimeError("classifier unavailable"))
@patch("notifications.views.send_openwa_message")
@patch("notifications.views.requests.get")
@patch("chatbot.views.answer_with_rag")
def test_classifier_failure_does_not_disable_text_safety_rules(
    mock_rag, mock_get, mock_send, mock_analyze, webhook_client, setup_data
):
    configure_registered_sender(mock_get)
    assert activate_assistant(webhook_client, "stage2c-failure-activation").status_code == 200

    response = send_patient_message(
        webhook_client, "I have chest pain", "stage2c-classifier-failure"
    )

    assert response.status_code == 200
    assert response.json()["needs_clinical_team"] is True
    mock_analyze.assert_called_once()
    mock_rag.assert_not_called()
    assert "clinical team" in mock_send.call_args.args[1].lower()
    # Analysis persistence is best-effort; a failed classifier creates no row.
    assert WhatsAppMessageAnalysis.objects.count() == 0
