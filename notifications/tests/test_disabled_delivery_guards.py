"""Ensure disabled delivery cannot mutate reminder state."""

from unittest.mock import patch

from notifications import tasks


def test_disabled_reminder_delivery_has_no_side_effects(
    settings,
):
    settings.WHATSAPP_SEND_ENABLED = False

    with patch.object(
        tasks.Reminder.objects,
        "filter",
    ) as query, patch.object(
        tasks,
        "_claim_reminder",
    ) as claim, patch.object(
        tasks,
        "send_reminder",
    ) as send, patch.object(
        tasks,
        "_schedule_retry",
    ) as retry:

        tasks.process_due_reminders.run()

        query.assert_not_called()
        claim.assert_not_called()
        send.assert_not_called()
        retry.assert_not_called()


def test_disabled_doctor_alerts_have_no_side_effects(
    settings,
):
    settings.WHATSAPP_SEND_ENABLED = False

    with patch.object(
        tasks.MissedReminderAlert.objects,
        "filter",
    ) as alerts, patch.object(
        tasks.StaffProfile.objects,
        "filter",
    ) as staff, patch.object(
        tasks,
        "send_openwa_message",
    ) as send:

        tasks._send_pending_missed_reminder_whatsapp_alerts()

        alerts.assert_not_called()
        staff.assert_not_called()
        send.assert_not_called()


def test_disabled_email_alerts_have_no_side_effects(
    settings,
):
    settings.EMAIL_SEND_ENABLED = False

    with patch.object(
        tasks.MissedReminderAlert.objects,
        "filter",
    ) as alerts, patch.object(
        tasks,
        "send_mail",
    ) as send:

        tasks._send_pending_missed_reminder_alerts()

        alerts.assert_not_called()
        send.assert_not_called()
