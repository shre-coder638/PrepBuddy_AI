#!/bin/sh

set -eu

if [ "${RENDER_APPLY_MIGRATIONS:-False}" = "True" ]; then
    if [ "${STAGING_MODE:-False}" != "True" ]; then
        echo "Automatic migration requires staging mode."
        exit 1
    fi

    echo "Applying approved staging migrations."
    python manage.py migrate --noinput
else
    echo "Checking database migration status."
    python manage.py migrate --check
fi

echo "Database schema ready."

if [ "${STAGING_ADMIN_RESET_ENABLED:-False}" = "True" ]; then
    python -u -m deploy.reset_staging_admin
fi

unset STAGING_ADMIN_RESET_HASH
unset STAGING_ADMIN_RESET_ENABLED

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 1 \
    --threads 2 \
    --timeout 120
