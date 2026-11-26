"""Tests for bounded missed-reminder reconciliation."""

from unittest.mock import MagicMock, patch

import pytest

from notifications import tasks


@pytest.mark.parametrize("batch_size", [
    0, -1, 51, True, False, "10", 1.5,
])
def test_invalid_batch_size(batch_size):
    with pytest.raises(ValueError):
        tasks.check_missed_reminders.run(
            batch_size=batch_size,
        )


def empty_queryset():
    query = MagicMock()

    for method in (
        "filter",
        "exclude",
        "select_related",
        "values_list",
        "distinct",
        "annotate",
        "order_by",
    ):
        getattr(query, method).return_value = query

    query.__getitem__.return_value = []
    query.__iter__.return_value = iter([])

    return query


@pytest.mark.parametrize("batch_size", [1, 10, 50])
def test_bounded_database_operations(batch_size):
    reminders = empty_queryset()
    procedures = empty_queryset()

    with patch.object(
        tasks.Reminder.objects,
        "filter",
        return_value=reminders,
    ), patch.object(
        tasks.Procedure.objects,
        "filter",
        return_value=procedures,
    ), patch.object(
        tasks.Procedure.objects,
        "exclude",
        return_value=procedures,
    ), patch.object(
        tasks,
        "_send_pending_missed_reminder_alerts",
    ) as email, patch.object(
        tasks,
        "_send_pending_missed_reminder_whatsapp_alerts",
    ) as whatsapp, patch(
        "django.db.models.Exists",
        return_value=MagicMock(),
    ):

        tasks.check_missed_reminders.run(
            batch_size=batch_size,
        )

        assert reminders.__getitem__.call_count == 2
        assert procedures.__getitem__.call_count == 2

        for query in (reminders, procedures):
            for call in query.__getitem__.call_args_list:
                assert call.args[0] == slice(
                    None, batch_size, None
                )

        email.assert_not_called()
        whatsapp.assert_not_called()


@pytest.mark.django_db
def test_empty_bounded_database_execution():
    with patch.object(
        tasks,
        "_send_pending_missed_reminder_alerts",
    ) as email, patch.object(
        tasks,
        "_send_pending_missed_reminder_whatsapp_alerts",
    ) as whatsapp:

        tasks.check_missed_reminders.run(batch_size=10)

        email.assert_not_called()
        whatsapp.assert_not_called()
