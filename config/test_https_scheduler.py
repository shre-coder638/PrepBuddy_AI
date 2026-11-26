"""Security tests for the restricted HTTPS scheduler."""

from unittest.mock import patch

import pytest
from django.test import Client


URL = "/internal/scheduler/v1/tick/"
TOKEN = "s" * 64


@pytest.fixture
def scheduler_client(settings):
    settings.STAGING_MODE = True
    settings.HTTPS_SCHEDULER_ENABLED = True
    settings.HTTPS_SCHEDULER_RECONCILE_ENABLED = False
    settings.HTTPS_SCHEDULER_DELIVERY_ENABLED = False
    settings.HTTPS_SCHEDULER_TOKEN = TOKEN
    settings.STAGING_ACCESS_TOKEN = "b" * 64
    settings.ANN_SERVICE_TOKEN = "a" * 64

    settings.ALLOWED_HOSTS = ["testserver"]

    settings.MIDDLEWARE = [
        "config.staging.StagingAccessMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
    ]

    return Client(enforce_csrf_checks=True)


def tick(client, token=TOKEN, body="{}"):
    return client.post(
        URL,
        data=body,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer " + token,
        secure=True,
    )


def test_real_heartbeat(scheduler_client):
    response = tick(scheduler_client)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "heartbeat-only",
    }

    assert response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("token", [
    "",
    "invalid",
    "a" * 64,
    "b" * 64,
])
def test_invalid_credentials(scheduler_client, token):
    assert tick(
        scheduler_client, token=token
    ).status_code == 401


def test_disabled_scheduler(scheduler_client, settings):
    settings.HTTPS_SCHEDULER_ENABLED = False

    assert tick(scheduler_client).status_code == 401


def test_non_staging_scheduler(scheduler_client, settings):
    settings.STAGING_MODE = False

    assert tick(scheduler_client).status_code == 401


def test_shared_token_rejected(scheduler_client, settings):
    settings.ANN_SERVICE_TOKEN = TOKEN

    assert tick(scheduler_client).status_code == 401


def test_get_not_allowed(scheduler_client):
    response = scheduler_client.get(
        URL,
        HTTP_AUTHORIZATION="Bearer " + TOKEN,
        secure=True,
    )

    assert response.status_code == 405


@pytest.mark.parametrize("body", [
    '{"task":"process_due_reminders"}',
    '{"reminder_id":1}',
    '[]',
    '',
    'null',
    'a' * 10000,
])
def test_arbitrary_arguments_rejected(
    scheduler_client,
    body,
):
    response = tick(
        scheduler_client,
        body=body,
    )

    # Django may omit Content-Type for an empty request.
    expected_status = 415 if body == "" else 400

    assert response.status_code == expected_status


def test_scheduler_token_cannot_access_admin(scheduler_client):
    response = scheduler_client.get(
        "/admin/",
        HTTP_AUTHORIZATION="Bearer " + TOKEN,
        secure=True,
    )

    assert response.status_code == 401


def test_heartbeat_does_not_publish_celery_task(
    scheduler_client,
):
    with patch(
        "notifications.tasks.scheduler_heartbeat.delay"
    ) as delay, patch(
        "notifications.tasks.scheduler_heartbeat.apply_async"
    ) as apply_async:

        assert tick(scheduler_client).status_code == 200

        delay.assert_not_called()
        apply_async.assert_not_called()


def test_heartbeat_failure(scheduler_client):
    with patch(
        "notifications.tasks.scheduler_heartbeat.run",
        side_effect=RuntimeError("Synthetic failure"),
    ):
        response = tick(scheduler_client)

    assert response.status_code == 503



def test_reconciliation_disabled_by_default(scheduler_client):
    with patch(
        "config.scheduler_execution.run_reconciliation_tick"
    ) as execute:

        response = tick(scheduler_client)

        assert response.status_code == 200
        assert response.json()["mode"] == "heartbeat-only"

        execute.assert_not_called()


@pytest.mark.parametrize("status", ["ok", "busy"])
def test_reconciliation_mode(
    scheduler_client,
    settings,
    status,
):
    settings.HTTPS_SCHEDULER_RECONCILE_ENABLED = True

    with patch(
        "config.scheduler_execution.run_reconciliation_tick",
        return_value={
            "status": status,
            "mode": "reconciliation",
        },
    ) as execute:

        response = tick(scheduler_client)

        assert response.status_code == 200
        assert response.json()["status"] == status
        assert response.json()["mode"] == "reconciliation"

        execute.assert_called_once_with()


def test_reconciliation_failure(scheduler_client, settings):
    settings.HTTPS_SCHEDULER_RECONCILE_ENABLED = True

    with patch(
        "config.scheduler_execution.run_reconciliation_tick",
        side_effect=RuntimeError("Synthetic failure"),
    ):
        response = tick(scheduler_client)

    assert response.status_code == 503


def test_unauthorized_reconciliation_blocked(
    scheduler_client,
    settings,
):
    settings.HTTPS_SCHEDULER_RECONCILE_ENABLED = True

    with patch(
        "config.scheduler_execution.run_reconciliation_tick"
    ) as execute:

        assert tick(
            scheduler_client,
            token="invalid",
        ).status_code == 401

        execute.assert_not_called()



@pytest.mark.parametrize("status", ["ok", "busy"])
def test_delivery_execution_mode(
    scheduler_client,
    settings,
    status,
):
    settings.HTTPS_SCHEDULER_DELIVERY_ENABLED = True

    with patch(
        "config.scheduler_execution.run_delivery_tick",
        return_value={
            "status": status,
            "mode": "reconciliation-and-delivery",
        },
    ) as execute:

        response = tick(scheduler_client)

        assert response.status_code == 200
        assert response.json()["status"] == status

        assert response.json()["mode"] == (
            "reconciliation-and-delivery"
        )

        execute.assert_called_once_with()


def test_unauthorized_delivery_blocked(
    scheduler_client,
    settings,
):
    settings.HTTPS_SCHEDULER_DELIVERY_ENABLED = True

    with patch(
        "config.scheduler_execution.run_delivery_tick"
    ) as execute:

        assert tick(
            scheduler_client,
            token="invalid",
        ).status_code == 401

        execute.assert_not_called()
