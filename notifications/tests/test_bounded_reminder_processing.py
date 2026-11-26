"""Regression tests for bounded reminder processing."""

from unittest.mock import MagicMock, patch

import pytest

from notifications import tasks


@pytest.mark.parametrize("batch_size", [
    0, -1, 11, True, False, "1", 1.5,
])
def test_invalid_batch_size_rejected(
    settings,
    batch_size,
):
    settings.WHATSAPP_SEND_ENABLED = True

    with patch.object(
        tasks.Reminder.objects,
        "filter",
    ) as query:

        with pytest.raises(ValueError):
            tasks.process_due_reminders.run(
                batch_size=batch_size,
            )

        query.assert_not_called()


@pytest.mark.parametrize("batch_size", [1, 3, 10])
def test_due_query_is_bounded(
    settings,
    batch_size,
):
    settings.WHATSAPP_SEND_ENABLED = True

    query = MagicMock()

    query.filter.return_value = query
    query.exclude.return_value = query
    query.order_by.return_value = query
    query.values_list.return_value = query

    selected_ids = list(range(1, batch_size + 1))

    query.__getitem__.return_value = selected_ids

    with patch.object(
        tasks.Reminder.objects,
        "filter",
        return_value=query,
    ) as initial_filter, patch.object(
        tasks,
        "_claim_reminder",
        return_value=None,
    ) as claim:

        tasks.process_due_reminders.run(
            batch_size=batch_size,
        )

        query.__getitem__.assert_called_once_with(
            slice(None, batch_size, None)
        )

        assert claim.call_count == batch_size

        assert (
            initial_filter.call_args.kwargs[
                "delivery_attempts__lt"
            ]
            == tasks.MAX_DELIVERY_ATTEMPTS
        )


def test_disabled_bounded_processing(settings):
    settings.WHATSAPP_SEND_ENABLED = False

    with patch.object(
        tasks.Reminder.objects,
        "filter",
    ) as query:

        tasks.process_due_reminders.run(batch_size=1)

        query.assert_not_called()
