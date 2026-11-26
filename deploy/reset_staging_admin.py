import os

import django


def main():
    if os.environ.get("STAGING_ADMIN_RESET_ENABLED") != "True":
        raise RuntimeError("Administrator reset not authorized.")

    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "config.settings"
    )

    django.setup()

    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.auth.hashers import identify_hasher
    from django.db import connection, transaction

    if not settings.STAGING_MODE:
        raise RuntimeError("Staging mode required.")

    if any([
        settings.WHATSAPP_SEND_ENABLED,
        settings.EMAIL_SEND_ENABLED,
        settings.HTTPS_SCHEDULER_RECONCILE_ENABLED,
        settings.HTTPS_SCHEDULER_DELIVERY_ENABLED,
        settings.STAGING_OPENWA_WEBHOOK_ENABLED,
    ]):
        raise RuntimeError("Disable delivery and reconciliation first.")

    if os.environ.get("RENDER_APPLY_MIGRATIONS") != "False":
        raise RuntimeError("Automatic migrations must be disabled.")

    encoded = os.environ.get("STAGING_ADMIN_RESET_HASH", "")

    hasher = identify_hasher(encoded)

    if hasher.algorithm != "pbkdf2_sha256":
        raise RuntimeError("Unexpected password hash algorithm.")

    hasher.decode(encoded)

    print("Administrator reset safety checks passed.", flush=True)

    if connection.vendor != "postgresql":
        raise RuntimeError("PostgreSQL required.")

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")

        if cursor.fetchone()[0] != "prepbuddy_ann_staging":
            raise RuntimeError("Unexpected database.")

    User = get_user_model()

    with transaction.atomic():
        user = User.objects.select_for_update().get(
            username="shreyash",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )

        if user.password != encoded:
            user.password = encoded
            user.save(update_fields=["password"])

    connection.close()

    print(
        "CLOUD ADMIN PASSWORD RESET SUCCESSFUL",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            "Administrator reset failed:",
            type(exc).__name__,
            flush=True,
        )
        raise SystemExit(1)
