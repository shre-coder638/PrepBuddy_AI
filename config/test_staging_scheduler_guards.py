"""Prevent unbounded legacy scheduling in hybrid staging."""

import pytest

from notifications import tasks


@pytest.mark.parametrize("function", [
    tasks.process_due_reminders.run,
    tasks.check_missed_reminders.run,
    tasks._send_pending_missed_reminder_whatsapp_alerts,
])
def test_legacy_scheduler_disabled_in_staging(
    settings,
    function,
):
    settings.STAGING_MODE = True
    settings.WHATSAPP_SEND_ENABLED = True
    settings.EMAIL_SEND_ENABLED = True

    # No database permission and no external calls.
    assert function() is None
