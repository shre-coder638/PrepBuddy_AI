"""Database concurrency tests for HTTPS scheduling."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from django.db import connection, connections, transaction

from config.scheduler_execution import (
    MISSED_BATCH_SIZE,
    SCHEDULER_LOCK_ID,
    run_reconciliation_tick,
)


def require_postgresql():
    if connection.vendor != "postgresql":
        pytest.skip("Requires a PostgreSQL test database.")


@pytest.mark.django_db(transaction=True)
def test_reconciliation_executes_bounded_task():
    require_postgresql()

    with patch(
        "notifications.tasks.check_missed_reminders.run"
    ) as reconcile, patch(
        "notifications.tasks.process_due_reminders.run"
    ) as deliver:

        result = run_reconciliation_tick()

        assert result == {
            "status": "ok",
            "mode": "reconciliation",
        }

        reconcile.assert_called_once_with(
            batch_size=MISSED_BATCH_SIZE,
        )

        deliver.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_concurrent_scheduler_tick_is_blocked():
    require_postgresql()

    def competing_tick():
        try:
            return run_reconciliation_tick()
        finally:
            connections.close_all()

    with patch(
        "notifications.tasks.check_missed_reminders.run"
    ) as reconcile:

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_try_advisory_xact_lock(%s)",
                    [SCHEDULER_LOCK_ID],
                )

                assert cursor.fetchone()[0] is True

            with ThreadPoolExecutor(
                max_workers=1
            ) as executor:
                result = executor.submit(
                    competing_tick
                ).result(timeout=10)

            assert result == {
                "status": "busy",
                "mode": "reconciliation",
            }

            reconcile.assert_not_called()

        # Lock released after transaction completion.
        result = run_reconciliation_tick()

        assert result["status"] == "ok"

        reconcile.assert_called_once_with(
            batch_size=MISSED_BATCH_SIZE,
        )


@pytest.mark.django_db(transaction=True)
def test_scheduler_lock_released_after_failure():
    require_postgresql()

    with patch(
        "notifications.tasks.check_missed_reminders.run",
        side_effect=RuntimeError("Synthetic failure"),
    ):
        with pytest.raises(
            RuntimeError,
            match="Synthetic failure",
        ):
            run_reconciliation_tick()

    with patch(
        "notifications.tasks.check_missed_reminders.run"
    ) as reconcile:

        result = run_reconciliation_tick()

        assert result["status"] == "ok"

        reconcile.assert_called_once_with(
            batch_size=MISSED_BATCH_SIZE,
        )


@pytest.mark.django_db(transaction=True)
def test_nested_transaction_is_rejected():
    require_postgresql()

    with transaction.atomic():
        with pytest.raises(
            RuntimeError,
            match="Unexpected outer transaction",
        ):
            run_reconciliation_tick()



@pytest.fixture
def delivery_settings(settings):
    settings.HTTPS_SCHEDULER_RECONCILE_ENABLED = True
    settings.WHATSAPP_SEND_ENABLED = True
    return settings


@pytest.mark.django_db(transaction=True)
def test_delivery_tick_execution(delivery_settings):
    require_postgresql()

    from config.scheduler_execution import run_delivery_tick

    def outside_transaction(*args, **kwargs):
        assert not connection.in_atomic_block
        assert connection.get_autocommit()

    with patch(
        "notifications.tasks.check_missed_reminders.run"
    ) as reconcile, patch(
        "notifications.tasks.process_due_reminders.run",
        side_effect=outside_transaction,
    ) as deliver, patch(
        "notifications.tasks._send_pending_missed_reminder_whatsapp_alerts",
        side_effect=outside_transaction,
    ) as alerts:

        result = run_delivery_tick()

        assert result == {
            "status": "ok",
            "mode": "reconciliation-and-delivery",
        }

        reconcile.assert_called_once_with(
            batch_size=MISSED_BATCH_SIZE,
        )

        deliver.assert_called_once_with(batch_size=1)
        alerts.assert_called_once_with(batch_size=1)


@pytest.mark.django_db(transaction=True)
def test_delivery_blocked_by_existing_lock(delivery_settings):
    require_postgresql()

    from config.scheduler_execution import run_delivery_tick

    def competing_tick():
        try:
            return run_delivery_tick()
        finally:
            connections.close_all()

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_xact_lock(%s)",
                [SCHEDULER_LOCK_ID],
            )
            assert cursor.fetchone()[0] is True

        with patch(
            "notifications.tasks.process_due_reminders.run"
        ) as deliver, patch(
            "notifications.tasks._send_pending_missed_reminder_whatsapp_alerts"
        ) as alerts:

            with ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(
                    competing_tick
                ).result(timeout=10)

            assert result["status"] == "busy"
            deliver.assert_not_called()
            alerts.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_delivery_lock_released_after_failure(delivery_settings):
    require_postgresql()

    from config.scheduler_execution import run_delivery_tick

    with patch(
        "notifications.tasks.check_missed_reminders.run"
    ), patch(
        "notifications.tasks.process_due_reminders.run",
        side_effect=RuntimeError("Synthetic failure"),
    ):
        with pytest.raises(RuntimeError, match="Synthetic failure"):
            run_delivery_tick()

    def competing_reconciliation():
        try:
            return run_reconciliation_tick()
        finally:
            connections.close_all()

    with patch(
        "notifications.tasks.check_missed_reminders.run"
    ):
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(
                competing_reconciliation
            ).result(timeout=10)

        assert result["status"] == "ok"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("disabled_setting", [
    "WHATSAPP_SEND_ENABLED",
    "HTTPS_SCHEDULER_RECONCILE_ENABLED",
])
def test_delivery_requires_explicit_configuration(
    delivery_settings,
    disabled_setting,
):
    require_postgresql()

    from config.scheduler_execution import run_delivery_tick

    setattr(delivery_settings, disabled_setting, False)

    with patch(
        "notifications.tasks.process_due_reminders.run"
    ) as deliver:
        with pytest.raises(RuntimeError):
            run_delivery_tick()

        deliver.assert_not_called()
