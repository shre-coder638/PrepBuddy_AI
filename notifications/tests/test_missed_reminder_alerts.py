
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from frontend.models import StaffProfile
from notifications.models import MissedReminderAlert
from notifications.tasks import (
    _queue_missed_reminder_alert,
    _send_pending_missed_reminder_alerts,
    _send_pending_missed_reminder_whatsapp_alerts,
    check_missed_reminders,
)

from patients.models import Patient
from procedures.models import Procedure
from protocols.models import PrepProtocol, PrepStep
from reminders.models import Reminder


@pytest.fixture
def alert_data(db):
    patient = Patient.objects.create(
        first_name="Alert",
        last_name="Test",
        phone_number="+910000000002",
        email="alert-test@example.com",
    )

    protocol = PrepProtocol.objects.create(
        name="Alert Test Protocol",
        description="Protocol for alert tests",
    )

    step = PrepStep.objects.create(
        protocol=protocol,
        title="Critical preparation",
        instruction="Complete the preparation step.",
        minutes_before_procedure=120,
        is_critical=True,
    )

    procedure = Procedure.objects.create(
        patient=patient,
        protocol=protocol,
        procedure_name="Alert Test Procedure",
        scheduled_at=timezone.now() + timedelta(days=1),
        status="prep_in_progress",
    )

    reminder = Reminder.objects.create(
        procedure=procedure,
        prep_step=step,
        scheduled_at=timezone.now() - timedelta(hours=3),
        sent_at=timezone.now() - timedelta(hours=3),
        status="sent",
    )

    User = get_user_model()
    user = User.objects.create_user(
        username="alert_test_staff",
        password="test-password-not-for-production",
        email="staff-alert-test@example.com",
    )
    StaffProfile.objects.create(
        user=user,
        role="clinic_staff",
    )

    return {
        "procedure": procedure,
        "reminder": reminder,
        "user": user,
    }


@pytest.mark.django_db
def test_alert_helper_creates_only_one_alert(alert_data):
    reminder = alert_data["reminder"]

    first = _queue_missed_reminder_alert(reminder)
    second = _queue_missed_reminder_alert(reminder)

    assert first.pk == second.pk
    assert MissedReminderAlert.objects.filter(
        reminder=reminder
    ).count() == 1


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_SEND_ENABLED=True,
    DEFAULT_FROM_EMAIL="prepbuddy-test@example.com",
)
def test_missed_reminder_creates_alert_and_emails_staff(alert_data):
    reminder = alert_data["reminder"]

    check_missed_reminders()

    reminder.refresh_from_db()
    assert reminder.status == "missed"

    alert = MissedReminderAlert.objects.get(reminder=reminder)
    assert alert.email_sent_at is not None
    assert alert.last_error == ""

    assert len(mail.outbox) == 1
    assert "Missed reminder" in mail.outbox[0].subject
    assert alert_data["user"].email in mail.outbox[0].to


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_SEND_ENABLED=True,
    DEFAULT_FROM_EMAIL="prepbuddy-test@example.com",
)
def test_successful_alert_email_is_not_sent_again(alert_data):
    reminder = alert_data["reminder"]
    alert = _queue_missed_reminder_alert(reminder)

    _send_pending_missed_reminder_alerts()
    alert.refresh_from_db()

    assert alert.email_sent_at is not None
    assert len(mail.outbox) == 1

    _send_pending_missed_reminder_alerts()

    assert len(mail.outbox) == 1


@pytest.mark.django_db
@override_settings(EMAIL_SEND_ENABLED=True)
def test_failed_alert_email_remains_retryable(alert_data):
    reminder = alert_data["reminder"]
    alert = _queue_missed_reminder_alert(reminder)

    with patch(
        "notifications.tasks.send_mail",
        side_effect=RuntimeError("Simulated email failure"),
    ):
        _send_pending_missed_reminder_alerts()

    alert.refresh_from_db()
    assert alert.email_sent_at is None
    assert "Simulated email failure" in alert.last_error
    assert alert.email_claimed_at is None

    with patch(
        "notifications.tasks.send_mail",
        return_value=1,
    ) as mock_send:
        _send_pending_missed_reminder_alerts()

    alert.refresh_from_db()
    assert alert.email_sent_at is not None
    assert alert.last_error == ""
    mock_send.assert_called_once()


@pytest.mark.django_db
@override_settings(EMAIL_SEND_ENABLED=False)
def test_disabled_email_delivery_leaves_alert_pending(alert_data):
    alert = _queue_missed_reminder_alert(alert_data["reminder"])

    with patch("notifications.tasks.send_mail") as mock_send:
        _send_pending_missed_reminder_alerts()

    alert.refresh_from_db()

    mock_send.assert_not_called()
    assert alert.email_sent_at is None
    assert alert.email_claimed_at is None
    assert alert.last_error == ""


@pytest.mark.django_db
def test_successful_doctor_whatsapp_alert_is_recorded(alert_data):
    reminder = alert_data["reminder"]
    alert = _queue_missed_reminder_alert(reminder)

    doctor_user = get_user_model().objects.create_user(
        username="alert_test_doctor",
        password="test-password-not-for-production",
    )
    StaffProfile.objects.create(
        user=doctor_user,
        role="doctor",
        phone_number="+91 98765 43210",
    )

    with patch(
        "notifications.tasks.send_openwa_message",
        return_value={"success": True, "messageId": "mock-message-1"},
    ) as mock_send:
        _send_pending_missed_reminder_whatsapp_alerts()

    alert.refresh_from_db()

    assert alert.whatsapp_sent_at is not None
    assert alert.whatsapp_last_error == ""
    mock_send.assert_called_once()

    kwargs = mock_send.call_args.kwargs
    assert kwargs["chat_id"] == "919876543210@c.us"
    assert f"Reminder ID: {reminder.id}" in kwargs["text"]
    assert "does not authorize proceeding" in kwargs["text"]


@pytest.mark.django_db
def test_successful_doctor_whatsapp_alert_is_not_sent_again(alert_data):
    alert = _queue_missed_reminder_alert(alert_data["reminder"])

    doctor_user = get_user_model().objects.create_user(
        username="alert_test_doctor_once",
        password="test-password-not-for-production",
    )
    StaffProfile.objects.create(
        user=doctor_user,
        role="doctor",
        phone_number="919876543210",
    )

    with patch(
        "notifications.tasks.send_openwa_message",
        return_value={"success": True},
    ) as mock_send:
        _send_pending_missed_reminder_whatsapp_alerts()
        _send_pending_missed_reminder_whatsapp_alerts()

    alert.refresh_from_db()

    assert alert.whatsapp_sent_at is not None
    assert mock_send.call_count == 1


@pytest.mark.django_db
def test_failed_doctor_whatsapp_alert_remains_retryable(alert_data):
    alert = _queue_missed_reminder_alert(alert_data["reminder"])

    doctor_user = get_user_model().objects.create_user(
        username="alert_test_doctor_retry",
        password="test-password-not-for-production",
    )
    StaffProfile.objects.create(
        user=doctor_user,
        role="doctor",
        phone_number="919876543210",
    )

    with patch(
        "notifications.tasks.send_openwa_message",
        side_effect=RuntimeError("Simulated WhatsApp failure"),
    ):
        _send_pending_missed_reminder_whatsapp_alerts()

    alert.refresh_from_db()
    assert alert.whatsapp_sent_at is None
    assert "send failed" in alert.whatsapp_last_error

    with patch(
        "notifications.tasks.send_openwa_message",
        return_value={"success": True},
    ) as mock_send:
        _send_pending_missed_reminder_whatsapp_alerts()

    alert.refresh_from_db()
    assert alert.whatsapp_sent_at is not None
    assert alert.whatsapp_last_error == ""
    mock_send.assert_called_once()


@pytest.mark.django_db
def test_no_doctor_phone_keeps_whatsapp_alert_pending(alert_data):
    alert = _queue_missed_reminder_alert(alert_data["reminder"])

    with patch(
        "notifications.tasks.send_openwa_message",
    ) as mock_send:
        _send_pending_missed_reminder_whatsapp_alerts()

    alert.refresh_from_db()

    assert alert.whatsapp_sent_at is None
    assert "No active doctors" in alert.whatsapp_last_error
    mock_send.assert_not_called()
@pytest.mark.django_db
def test_partial_doctor_whatsapp_success_retries_without_duplicate_sends(
    alert_data,
):
    alert = _queue_missed_reminder_alert(alert_data["reminder"])

    User = get_user_model()

    doctor_a = User.objects.create_user(
        username="partial_alert_doctor_a",
    )
    StaffProfile.objects.create(
        user=doctor_a,
        role="doctor",
        phone_number="919876543211",
    )

    doctor_b = User.objects.create_user(
        username="partial_alert_doctor_b",
    )
    StaffProfile.objects.create(
        user=doctor_b,
        role="doctor",
        phone_number="919876543212",
    )

    attempts = {}
    accepted_keys = set()
    actual_sends = []

    def idempotent_send(**kwargs):
        key = kwargs["dedupe_key"]
        chat_id = kwargs["chat_id"]

        attempts[key] = attempts.get(key, 0) + 1

        if key in accepted_keys:
            return {"success": True, "cached": True}

        if chat_id == "919876543212@c.us" and attempts[key] == 1:
            raise RuntimeError("Simulated temporary failure")

        accepted_keys.add(key)
        actual_sends.append(key)
        return {"success": True}

    with patch(
        "notifications.tasks.send_openwa_message",
        side_effect=idempotent_send,
    ):
        _send_pending_missed_reminder_whatsapp_alerts()

        alert.refresh_from_db()
        assert alert.whatsapp_sent_at is None
        assert "send failed" in alert.whatsapp_last_error
        assert len(actual_sends) == 1

        _send_pending_missed_reminder_whatsapp_alerts()

    alert.refresh_from_db()

    assert alert.whatsapp_sent_at is not None
    assert alert.whatsapp_last_error == ""
    assert len(actual_sends) == 2
    assert len(set(actual_sends)) == 2
    assert len(attempts) == 2
    assert all(count == 2 for count in attempts.values())


@pytest.mark.django_db
@override_settings(EMAIL_SEND_ENABLED=True)
def test_active_email_claim_prevents_duplicate_send(alert_data):
    alert = _queue_missed_reminder_alert(alert_data["reminder"])
    active_claim = timezone.now()

    MissedReminderAlert.objects.filter(pk=alert.pk).update(
        email_claimed_at=active_claim,
    )

    with patch("notifications.tasks.send_mail") as mock_send:
        _send_pending_missed_reminder_alerts()

    alert.refresh_from_db()

    mock_send.assert_not_called()
    assert alert.email_sent_at is None
    assert alert.email_claimed_at == active_claim


@pytest.mark.django_db
@override_settings(EMAIL_SEND_ENABLED=True)
def test_expired_email_claim_is_recovered(alert_data):
    alert = _queue_missed_reminder_alert(alert_data["reminder"])

    MissedReminderAlert.objects.filter(pk=alert.pk).update(
        email_claimed_at=timezone.now() - timedelta(minutes=6),
    )

    with patch(
        "notifications.tasks.send_mail",
        return_value=1,
    ) as mock_send:
        _send_pending_missed_reminder_alerts()

    alert.refresh_from_db()

    mock_send.assert_called_once()
    assert alert.email_sent_at is not None
    assert alert.email_claimed_at is None
    assert alert.last_error == ""


@pytest.mark.django_db
@override_settings(EMAIL_SEND_ENABLED=True)
def test_stale_email_claim_cannot_mark_alert_as_sent(alert_data):
    alert = _queue_missed_reminder_alert(alert_data["reminder"])
    replacement_claim = timezone.now() + timedelta(seconds=1)

    def replace_claim_before_send_returns(*args, **kwargs):
        MissedReminderAlert.objects.filter(pk=alert.pk).update(
            email_claimed_at=replacement_claim,
        )
        return 1

    with patch(
        "notifications.tasks.send_mail",
        side_effect=replace_claim_before_send_returns,
    ) as mock_send:
        _send_pending_missed_reminder_alerts()

    alert.refresh_from_db()

    mock_send.assert_called_once()
    assert alert.email_sent_at is None
    assert alert.email_claimed_at == replacement_claim
