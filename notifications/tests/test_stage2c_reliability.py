import pytest
from django.test import Client
from unittest.mock import Mock, patch

from chatbot.conversation import save_conversation_message as real_save_conversation_message
from notifications.models import (
    ProcessedWhatsAppMessage,
    WhatsAppAssistantSession,
    WhatsAppConversationMessage,
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


def activate_assistant(client, message_id):
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
def test_processed_duplicate_inbound_message_does_not_send_second_reply(
    webhook_client, setup_data
):
    with (
        patch("notifications.views.requests.get") as mock_get,
        patch("notifications.views.send_openwa_message") as mock_send,
        patch("notifications.views.answer_question") as mock_answer,
    ):
        configure_registered_sender(mock_get)
        mock_answer.return_value = {
            "answer": "Follow the stored preparation instructions.",
            "sources": [],
            "needs_clinical_team": False,
        }

        assert activate_assistant(
            webhook_client, "stage2c-duplicate-activation"
        ).status_code == 200
        mock_send.reset_mock()

        first = send_patient_message(
            webhook_client,
            "When should I arrive?",
            "stage2c-duplicate-question",
        )
        second = send_patient_message(
            webhook_client,
            "When should I arrive?",
            "stage2c-duplicate-question",
        )

        assert first.status_code == 200
        assert first.json()["answered"] is True
        assert second.status_code == 200
        assert second.json()["duplicate"] is True
        mock_answer.assert_called_once()
        mock_send.assert_called_once()

        record = ProcessedWhatsAppMessage.objects.get(
            message_id="stage2c-duplicate-question"
        )
        assert record.is_processed is True
        assert record.processing_started_at is None


@pytest.mark.django_db
def test_failed_primary_and_fallback_send_releases_claim_for_retry(
    webhook_client, setup_data
):
    with (
        patch("notifications.views.requests.get") as mock_get,
        patch("notifications.views.send_openwa_message") as mock_send,
        patch("notifications.views.answer_question") as mock_answer,
    ):
        configure_registered_sender(mock_get)
        mock_answer.return_value = {
            "answer": "Follow the stored preparation instructions.",
            "sources": [],
            "needs_clinical_team": False,
        }

        assert activate_assistant(
            webhook_client, "stage2c-retry-activation"
        ).status_code == 200
        mock_send.reset_mock()

        # First attempt: primary response and fallback both fail.
        # Retry: primary response send succeeds.
        mock_send.side_effect = [
            RuntimeError("primary send failed"),
            RuntimeError("fallback send failed"),
            None,
        ]

        first = send_patient_message(
            webhook_client,
            "When should I arrive?",
            "stage2c-send-retry",
        )

        record = ProcessedWhatsAppMessage.objects.get(
            message_id="stage2c-send-retry"
        )
        assert first.status_code == 500
        assert first.json()["answered"] is False
        assert record.is_processed is False
        assert record.processing_started_at is None

        second = send_patient_message(
            webhook_client,
            "When should I arrive?",
            "stage2c-send-retry",
        )

        record.refresh_from_db()
        assert second.status_code == 200
        assert second.json()["answered"] is True
        assert record.is_processed is True
        assert record.processing_started_at is None
        assert mock_answer.call_count == 2
        assert mock_send.call_count == 3


@pytest.mark.django_db
def test_assistant_history_write_failure_does_not_send_duplicate_reply(
    webhook_client, setup_data
):
    with (
        patch("notifications.views.requests.get") as mock_get,
        patch("notifications.views.send_openwa_message") as mock_send,
        patch("notifications.views.answer_question") as mock_answer,
        patch("notifications.views.save_conversation_message") as mock_save,
    ):
        configure_registered_sender(mock_get)
        mock_answer.return_value = {
            "answer": "Follow the stored preparation instructions.",
            "sources": [],
            "needs_clinical_team": False,
        }

        def save_patient_but_fail_assistant(*, session, role, content):
            if role == "assistant":
                raise RuntimeError("conversation history database unavailable")
            return real_save_conversation_message(
                session=session, role=role, content=content
            )

        mock_save.side_effect = save_patient_but_fail_assistant

        assert activate_assistant(
            webhook_client, "stage2c-history-activation"
        ).status_code == 200
        mock_send.reset_mock()

        response = send_patient_message(
            webhook_client,
            "When should I arrive?",
            "stage2c-history-write-failure",
        )

        assert response.status_code == 200
        assert response.json()["answered"] is True
        mock_send.assert_called_once()
        mock_answer.assert_called_once()

        session = WhatsAppAssistantSession.objects.get(
            patient=setup_data["procedure"].patient
        )
        assert WhatsAppConversationMessage.objects.filter(
            session=session,
            role="patient",
            content="When should I arrive?",
        ).exists()
        assert not WhatsAppConversationMessage.objects.filter(
            session=session,
            role="assistant",
            content="Follow the stored preparation instructions.",
        ).exists()

        record = ProcessedWhatsAppMessage.objects.get(
            message_id="stage2c-history-write-failure"
        )
        assert record.is_processed is True


@pytest.mark.django_db
def test_analysis_persistence_failure_keeps_text_based_clinical_safety(
    webhook_client, setup_data
):
    with (
        patch("notifications.views.requests.get") as mock_get,
        patch("notifications.views.send_openwa_message") as mock_send,
        patch(
            "notifications.views.WhatsAppMessageAnalysis.objects.update_or_create",
            side_effect=RuntimeError("analysis database write failed"),
        ),
        patch("chatbot.views.answer_with_rag") as mock_rag,
    ):
        configure_registered_sender(mock_get)

        assert activate_assistant(
            webhook_client, "stage2c-analysis-db-activation"
        ).status_code == 200
        mock_send.reset_mock()

        response = send_patient_message(
            webhook_client,
            "I have chest pain",
            "stage2c-analysis-db-failure",
        )

        assert response.status_code == 200
        assert response.json()["answered"] is True
        assert response.json()["needs_clinical_team"] is True
        mock_rag.assert_not_called()
        mock_send.assert_called_once()
        assert "clinical team" in mock_send.call_args.args[1].lower()
