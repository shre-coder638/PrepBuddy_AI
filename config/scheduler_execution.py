"""Concurrency-protected HTTPS scheduler execution."""

from django.conf import settings
from django.db import connection, transaction


SCHEDULER_LOCK_ID = 0x5052455042554444
MISSED_BATCH_SIZE = 10


def run_reconciliation_tick():
    """Run one bounded database-only reconciliation tick."""

    if connection.vendor != "postgresql":
        raise RuntimeError("Scheduler requires PostgreSQL.")

    if connection.in_atomic_block:
        raise RuntimeError("Unexpected outer transaction.")

    from notifications.tasks import check_missed_reminders

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_xact_lock(%s)",
                [SCHEDULER_LOCK_ID],
            )

            acquired = cursor.fetchone()[0]

        if not acquired:
            return {
                "status": "busy",
                "mode": "reconciliation",
            }

        check_missed_reminders.run(
            batch_size=MISSED_BATCH_SIZE,
        )

    return {
        "status": "ok",
        "mode": "reconciliation",
    }



def run_delivery_tick():
    """Serialize reconciliation and bounded external delivery."""

    if connection.vendor != "postgresql":
        raise RuntimeError("Scheduler requires PostgreSQL.")

    if connection.in_atomic_block or not connection.get_autocommit():
        raise RuntimeError("Unexpected outer transaction.")

    if not getattr(
        settings, "HTTPS_SCHEDULER_RECONCILE_ENABLED", False
    ):
        raise RuntimeError("Reconciliation must be enabled.")

    if not getattr(settings, "WHATSAPP_SEND_ENABLED", False):
        raise RuntimeError("WhatsApp delivery is disabled.")

    from notifications.tasks import (
        process_due_reminders,
        _send_pending_missed_reminder_whatsapp_alerts,
    )

    acquired = False

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_lock(%s)",
                [SCHEDULER_LOCK_ID],
            )

            acquired = cursor.fetchone()[0]

    except Exception:
        connection.close()
        raise

    if not acquired:
        return {
            "status": "busy",
            "mode": "reconciliation-and-delivery",
        }

    try:
        reconciliation = run_reconciliation_tick()

        if reconciliation["status"] != "ok":
            return {
                "status": "busy",
                "mode": "reconciliation-and-delivery",
            }

        # External network operations must remain outside
        # the reconciliation transaction.
        if connection.in_atomic_block:
            raise RuntimeError("Unexpected delivery transaction.")

        process_due_reminders.run(batch_size=1)

        _send_pending_missed_reminder_whatsapp_alerts(
            batch_size=1,
        )

        return {
            "status": "ok",
            "mode": "reconciliation-and-delivery",
        }

    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_unlock(%s)",
                    [SCHEDULER_LOCK_ID],
                )

                if cursor.fetchone()[0] is not True:
                    raise RuntimeError("Scheduler lock ownership lost.")

        except Exception:
            connection.close()
            raise
